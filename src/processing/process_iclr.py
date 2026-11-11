#!/usr/bin/env python3
"""
Convert raw ICLR JSON files to canonical processed per-year JSON files.

Each year has exactly one raw source, set in SOURCES:

  2013        iclr_2013_openreview.json   scrape_iclr_openreview_early.py
  2014-2016   iclr_{year}_arxiv.json      scrape_iclr_arxiv.py
  2017-2026   iclr_{year}_data.json       scrape_iclr.py

2013-2016 (early sources): the scrapers already keep only accepted papers with
a title and an abstract, and their records carry the canonical fields. They
pass through unchanged apart from dropping the one source-specific key
(`decision`, `arxiv_id`). No further sanitising is applied, because the
published values were computed on exactly this text.

2017-2026 (OpenReview export), filtering applied (raw -> processed):
  - Keep only accepted papers (decision starts with "Accept", or for the
    OpenReview v2 export, a Poster/Oral/Spotlight venue label)
  - Drop records with empty title or paper_id, or an abstract under 5 words
  - sanitize_text() applied to title and abstract

Output fields: paper_id, venue, year, title, abstract, authors
Output:        data/processed/iclr/iclr_{year}.json

Usage:
  python src/processing/process_iclr.py
  python src/processing/process_iclr.py --years 2023 2024 2025
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from schema import make_paper, save_processed, sanitize_text

SOURCES = {2013: "openreview", 2014: "arxiv", 2015: "arxiv", 2016: "arxiv",
           **{y: "data" for y in range(2017, 2027)}}

# Source-specific raw keys that are not part of the processed schema.
_EXTRA_KEY = {"openreview": "decision", "arxiv": "arxiv_id"}


def parse_authors(raw) -> list[str]:
    if isinstance(raw, list):
        return [a.strip() for a in raw if isinstance(a, str) and a.strip()]
    if isinstance(raw, str):
        return [a.strip() for a in raw.split(",") if a.strip()]
    return []


def is_accepted(record: dict) -> bool:
    decision = (record.get("decision") or "").strip()
    if decision.lower().startswith("accept"):
        return True
    # OpenReview API v2 (used for 2026+) does not expose `decision` directly;
    # `labels` carries the venue track (e.g. "ICLR 2026 Poster" / "Oral"), and
    # only accepted papers are publicly listed under the venue id.
    label = (record.get("labels") or "").strip().lower()
    return any(track in label for track in ("poster", "oral", "spotlight"))


def from_early(raw: list[dict], source: str) -> list[dict]:
    """Early-year raw records minus their source-specific key, order kept."""
    extra = _EXTRA_KEY[source]
    return [{k: v for k, v in r.items() if k != extra} for r in raw]


def from_openreview_export(raw: list[dict], year: int) -> tuple[list[dict], int]:
    """2017+ OpenReview export -> (processed records, n_skipped)."""
    papers, skipped = [], 0
    for r in raw:
        if not is_accepted(r):
            skipped += 1
            continue

        paper_id = str(r.get("id") or "").strip()
        title    = sanitize_text(r.get("title") or "")
        abstract = sanitize_text(r.get("abstract") or "")
        authors  = parse_authors(r.get("authors", ""))

        if not paper_id or not title:
            skipped += 1
            continue

        if len(abstract.split()) < 5:
            skipped += 1
            continue

        papers.append(make_paper(
            paper_id=paper_id,
            venue="iclr",
            year=int(r.get("year", year)),
            title=title,
            abstract=abstract,
            authors=authors,
        ))
    return papers, skipped


def process_year(year: int, raw_dir: str, out_dir: str) -> tuple[int, int]:
    """Returns (n_accepted, n_skipped)."""
    source = SOURCES.get(year)
    if source is None:
        print(f"  [ICLR {year}] no raw source configured, skipping")
        return 0, 0
    path = os.path.join(raw_dir, f"iclr_{year}_{source}.json")
    if not os.path.exists(path):
        print(f"  [ICLR {year}] not found: {path}")
        return 0, 0

    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    if source == "data":
        papers, skipped = from_openreview_export(raw, year)
    else:
        papers, skipped = from_early(raw, source), 0

    save_processed(papers, os.path.join(out_dir, f"iclr_{year}.json"))
    print(f"  [ICLR {year}] {len(papers)} accepted  |  {skipped} rejected/withdrawn/empty")
    return len(papers), skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir",       default="data/raw/iclr")
    parser.add_argument("--processed-dir", default="data/processed/iclr")
    parser.add_argument("--years", nargs="+", type=int, default=sorted(SOURCES))
    args = parser.parse_args()

    total_accepted = total_skipped = 0
    for year in args.years:
        a, s = process_year(year, args.raw_dir, args.processed_dir)
        total_accepted += a
        total_skipped  += s

    print(f"\nICLR total: {total_accepted} accepted papers  |  {total_skipped} skipped")


if __name__ == "__main__":
    main()
