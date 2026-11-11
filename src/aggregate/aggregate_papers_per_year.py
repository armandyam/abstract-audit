#!/usr/bin/env python3
"""
Aggregate number of papers published per year, per venue (raw counts, no std).

Reads:  data/processed/{venue}/
Writes: data/aggregate/papers_per_year.csv
Columns: year, neurips, iclr, icml   (0 where a venue has no data that year)
         plus arxiv when AA_BASELINES names it, as upstream wrote it. PubMed
         is never counted here: its corpus runs to tens of millions of
         records, and its counts come from the aggregates (see shared/baselines/).

Run:
  python src/aggregate/aggregate_papers_per_year.py
"""

from __future__ import annotations
import csv
import json
import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import DATA_DIR, OUT_DIR, VENUES, baselines_from_env

PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
OUT_PATH = os.path.join(OUT_DIR, "papers_per_year.csv")


def count_papers_by_year(venue: str, processed_dir: str = PROCESSED_DIR) -> dict[int, int]:
    venue_dir = os.path.join(processed_dir, venue)
    counts: dict[int, int] = {}
    if not os.path.isdir(venue_dir):
        print(f"  WARNING: {venue_dir} not found", file=sys.stderr)
        return counts
    for fname in sorted(os.listdir(venue_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(venue_dir, fname), encoding="utf-8") as fh:
            for p in json.load(fh):
                year = int(p["year"])
                counts[year] = counts.get(year, 0) + 1
    return counts


def main():
    venues = VENUES + (["arxiv"] if "arxiv" in baselines_from_env() else [])
    venue_counts = {v: count_papers_by_year(v) for v in venues}
    if not any(venue_counts.values()):
        # The pipeline run from the shipped per-paper metrics has no abstracts.
        print(f"  no processed abstracts under {PROCESSED_DIR}; skipping")
        return
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    all_years = sorted({y for counts in venue_counts.values() for y in counts})

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["year"] + venues)
        for year in all_years:
            writer.writerow([year] + [venue_counts[v].get(year, 0) for v in venues])

    print(f"  {len(all_years)} rows -> {OUT_PATH}")
    for v in venues:
        total = sum(venue_counts[v].values())
        print(f"    {v}: {total} papers")


if __name__ == "__main__":
    main()
