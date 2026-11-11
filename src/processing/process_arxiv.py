#!/usr/bin/env python3
"""
Convert the arXiv metadata snapshot into canonical per-year processed JSON files.

Raw input:  data/raw/arxiv/arxiv-metadata-oai-snapshot.json  (JSON lines)
Output:     data/processed/arxiv/arxiv_{year}.json

Filters (raw to processed):
  - drop a record with an empty id or title, or no determinable year;
  - drop a record whose abstract has fewer than five words;
  - optionally keep only papers carrying one of --categories (not used for
    the TMLR paper, which keeps every category and splits ML from non-ML
    later by primary category; see src/arxiv_categories.py).

Year: taken from the arXiv identifier, which encodes the submission month
(YYMM.NNNNN since April 2007, archive/YYMMNNN before). The `update_date`
field is only a fallback, because arXiv re-indexed large batches in 2009 and
2015 and dating by it puts spikes in those years.

Text: sanitize_text() on title and abstract (NFC, control characters
removed, whitespace collapsed).

Output fields: paper_id, venue, year, title, abstract, authors,
               arxiv_categories, arxiv_primary_category
The primary category is the first entry of the record's `categories` field.

On the snapshot the TMLR paper used, this wrote 2,823,623 records for
1991-2025. See src/scraping/download_arxiv.py for why a new download
recomputes rather than regenerates those numbers.

Usage:
  python src/processing/process_arxiv.py
  python src/processing/process_arxiv.py --years 2015 2016 2017
  python src/processing/process_arxiv.py --categories cs.LG stat.ML
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from schema import make_paper, save_processed, sanitize_text

DATA_DIR = os.environ.get("AA_DATA", "data")
SNAPSHOT = os.path.join(DATA_DIR, "raw", "arxiv", "arxiv-metadata-oai-snapshot.json")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed", "arxiv")


def parse_authors(record: dict) -> list[str]:
    """`authors_parsed` ([last, first, suffix] triples) as "first last";
    the comma-separated `authors` string when that field is absent."""
    parsed = record.get("authors_parsed") or []
    if parsed:
        names = []
        for parts in parsed:
            last  = parts[0].strip() if len(parts) > 0 else ""
            first = parts[1].strip() if len(parts) > 1 else ""
            name  = f"{first} {last}".strip() if first else last
            if name:
                names.append(name)
        return names
    raw = record.get("authors", "")
    return [a.strip() for a in raw.split(",") if a.strip()]


def parse_categories(record: dict) -> tuple[list[str], str | None]:
    """All categories, and the primary one (the first), or None."""
    raw  = (record.get("categories") or "").strip()
    cats = raw.split() if raw else []
    return cats, (cats[0] if cats else None)


def _year_from_arxiv_id(arxiv_id: str) -> int | None:
    """Submission year from an arXiv identifier.

    New format (from April 2007): YYMM.NNNNN, e.g. 0704.0001 is 2007.
    Old format (before):          archive/YYMMNNN, e.g. cs/9812021 is 1998.
    A two-digit year up to 30 is read as 20YY, above as 19YY.
    """
    aid = re.sub(r'v\d+$', '', arxiv_id.strip())
    m = re.match(r'^(\d{2})\d{2}\.\d+$', aid)
    if not m:
        m = re.match(r'^[a-zA-Z.\-]+/(\d{2})\d+$', aid)
    if m:
        yy = int(m.group(1))
        return 2000 + yy if yy <= 30 else 1900 + yy
    return None


def get_year(record: dict) -> int | None:
    """The identifier's year; the first four characters of update_date if the
    identifier has no recognisable form."""
    year = _year_from_arxiv_id(str(record.get("id") or ""))
    if year is not None:
        return year
    date = record.get("update_date") or ""
    if date and len(date) >= 4:
        try:
            return int(date[:4])
        except ValueError:
            pass
    return None


def to_paper(r: dict) -> dict | None:
    """One snapshot record as a canonical paper, or None if it is filtered out."""
    paper_id = str(r.get("id") or "").strip()
    title    = sanitize_text(r.get("title") or "")
    abstract = sanitize_text(r.get("abstract") or "")
    year     = get_year(r)

    if not paper_id or not title or year is None:
        return None

    if len(abstract.split()) < 5:
        return None

    authors       = parse_authors(r)
    cats, primary = parse_categories(r)

    return make_paper(
        paper_id=paper_id,
        venue="arxiv",
        year=year,
        title=title,
        abstract=abstract,
        authors=authors,
        arxiv_categories=cats if cats else None,
        arxiv_primary_category=primary,
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot", default=SNAPSHOT)
    parser.add_argument("--processed-dir", default=PROCESSED_DIR)
    parser.add_argument("--years", nargs="+", type=int, default=None,
                        help="Only emit these years (default: all)")
    parser.add_argument("--categories", nargs="+", default=None,
                        help="Keep only papers with at least one of these categories")
    args = parser.parse_args()

    if not os.path.exists(args.snapshot):
        sys.exit(f"Snapshot not found: {args.snapshot}\n"
                 "Run: python src/scraping/download_arxiv.py")

    os.makedirs(args.processed_dir, exist_ok=True)
    year_set = set(args.years) if args.years else None
    cat_set  = set(args.categories) if args.categories else None

    buckets: dict[int, list[dict]] = defaultdict(list)
    kept = skipped = 0

    print(f"Streaming {args.snapshot}")
    with open(args.snapshot, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            year = get_year(r)
            if year is None or (year_set and year not in year_set):
                skipped += 1
                continue

            if cat_set:
                cats, _ = parse_categories(r)
                if not set(cats).intersection(cat_set):
                    skipped += 1
                    continue

            paper = to_paper(r)
            if paper is None:
                skipped += 1
                continue

            buckets[paper["year"]].append(paper)
            kept += 1

            if (i + 1) % 500_000 == 0:
                print(f"  {i+1:,} lines  |  {kept:,} kept  |  {skipped:,} skipped")

    print(f"\nStream complete: {kept:,} papers across {len(buckets)} years")

    for year, papers in sorted(buckets.items()):
        out_path = os.path.join(args.processed_dir, f"arxiv_{year}.json")
        save_processed(papers, out_path)
        print(f"  [arXiv {year}] {len(papers):,} papers -> {out_path}")

    print("Done.")


if __name__ == "__main__":
    main()
