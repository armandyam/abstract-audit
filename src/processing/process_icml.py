#!/usr/bin/env python3
"""
Convert raw ICML JSON files to canonical processed per-year JSON files.

Each year has exactly one raw source, set in SOURCES:

  2008-2012   icml_{year}_legacy.json   scrape_icml_legacy.py (icml.cc archive)
  2013-2016   icml_{year}_pmlr.json     scrape_icml_pmlr.py   (PMLR)
  2017-2025   icml_{year}_data.json     download_icml.py      (icml.cc export)

2008-2016 (archive and PMLR sources): the record is rebuilt as
{paper_id, venue, year, title, abstract, authors} from the raw fields, in raw
order, with no further filtering or sanitising. The scrapers have already
cleaned the text, and the published values were computed on exactly this
text. Every record must carry an abstract; validate.py rejects one that does
not, so an incomplete scrape fails loudly rather than shrinking the corpus.

2017-2025 (virtual-site export), filtering applied (raw -> processed):
  - Keep only accepted papers (type == "Poster"; the virtual site exports
    every accepted paper as Poster). Workshops, Tutorials, and Invited Talks
    are excluded: they are not peer-reviewed papers and their blurbs would
    pollute the writing metrics.
  - Drop records missing title, abstract (< 5 words), or authors
  - HTML tags stripped and entities unescaped (the virtual-site export leaks
    <img>/<br>/<sup> markup and &#x27;-style entities into some fields)
  - sanitize_text() applied to title and abstract

Output fields: paper_id, venue, year, title, abstract, authors
Output:        data/processed/icml/icml_{year}.json

Usage:
  python src/processing/process_icml.py
  python src/processing/process_icml.py --years 2023 2024 2025
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from schema import make_paper, save_processed, sanitize_text

SOURCES = {**{y: "legacy" for y in range(2008, 2013)},
           **{y: "pmlr" for y in range(2013, 2017)},
           **{y: "data" for y in range(2017, 2026)}}

_TAG_RE = re.compile(r"<[^>]+>")

# Accepted-paper entry types on the ICML virtual site: every accepted paper is
# exported as "Poster" (orals and spotlights are Posters with session markers).
_PAPER_TYPES = {"Poster"}


def strip_html(text: str) -> str:
    """Remove markup and entities the virtual-site export leaks into fields."""
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", text))).strip()


def make_paper_id(record: dict, year: int) -> str:
    """Derive a stable ID from the virtual-site URL or title hash."""
    url = record.get("virtualsite_url", "")
    if url:
        return url.rstrip("/").rsplit("/", 1)[-1]
    title = record.get("name", "")
    return hashlib.md5(f"{year}:{title}".encode()).hexdigest()[:12]


def parse_authors(raw) -> list[str]:
    if isinstance(raw, list):
        return [a.strip() for a in raw if isinstance(a, str) and a.strip()]
    if isinstance(raw, str):
        return [a.strip() for a in raw.split(",") if a.strip()]
    return []


def from_archive(raw: list[dict]) -> list[dict]:
    """Legacy and PMLR raw records -> processed records, order kept."""
    return [{"paper_id": r["paper_id"], "venue": "icml", "year": r["year"],
             "title": r["title"], "abstract": r["abstract"], "authors": r["authors"]}
            for r in raw]


def from_export(raw: list[dict], year: int) -> tuple[list[dict], int]:
    """2017+ virtual-site export -> (processed records, n_skipped)."""
    papers, skipped = [], 0
    for r in raw:
        # Keep accepted papers only (missing type = legacy export, treat as paper).
        rtype = (r.get("type") or "Poster").strip()
        if rtype not in _PAPER_TYPES:
            skipped += 1
            continue

        title    = sanitize_text(strip_html(r.get("name") or ""))
        abstract = sanitize_text(strip_html(r.get("abstract") or ""))
        authors  = [html.unescape(a) for a in parse_authors(r.get("speakers/authors", ""))]
        paper_id = make_paper_id(r, year)

        if not title:
            skipped += 1
            continue

        if len(abstract.split()) < 5:
            skipped += 1
            continue

        if not authors:
            skipped += 1
            continue

        papers.append(make_paper(
            paper_id=paper_id,
            venue="icml",
            year=year,
            title=title,
            abstract=abstract,
            authors=authors,
        ))
    return papers, skipped


def process_year(year: int, raw_dir: str, out_dir: str) -> tuple[int, int]:
    source = SOURCES.get(year)
    if source is None:
        print(f"  [ICML {year}] no raw source configured, skipping")
        return 0, 0
    path = os.path.join(raw_dir, f"icml_{year}_{source}.json")
    if not os.path.exists(path):
        print(f"  [ICML {year}] not found: {path}")
        return 0, 0

    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    if source == "data":
        papers, skipped = from_export(raw, year)
    else:
        papers, skipped = from_archive(raw), 0

    save_processed(papers, os.path.join(out_dir, f"icml_{year}.json"))
    print(f"  [ICML {year}] {len(papers)} papers  |  {skipped} skipped (non-paper or missing title/abstract/authors)")
    return len(papers), skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir",       default="data/raw/icml")
    parser.add_argument("--processed-dir", default="data/processed/icml")
    parser.add_argument("--years", nargs="+", type=int, default=sorted(SOURCES))
    args = parser.parse_args()

    total_papers = total_skipped = 0
    for year in args.years:
        p, s = process_year(year, args.raw_dir, args.processed_dir)
        total_papers  += p
        total_skipped += s

    print(f"\nICML total: {total_papers} papers  |  {total_skipped} skipped")


if __name__ == "__main__":
    main()
