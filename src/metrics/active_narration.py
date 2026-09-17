#!/usr/bin/env python3
"""
Per-paper active narration metric — binary presence of first-person language.

Based on Hohmann, Barnett, King & Connell (2025), Scientometrics 130:3349-3366.
DOI: https://doi.org/10.1007/s11192-025-05353-8
Source R code: https://github.com/agbarnett/narrator

Active narration = personal language using "We/we/Us/us", which helps audiences
relate to the text (Hillier et al., 2016; Pinker, 2014; Sword, 2012). This is a
binary YES/NO outcome per paper (i.e. does the abstract use first-person plural?).

Detection: case-sensitive whole-word match on "We", "we", "Us", "us".
"US" (uppercase) is intentionally excluded to avoid false positives from
the country abbreviation.

Output: data/per_paper/active_narration/{venue}.csv
Columns: paper_id, venue, year, n_words, has_narrator (0/1)

Usage:
  python src/metrics/active_narration.py
  python src/metrics/active_narration.py --venues neurips iclr
"""

from __future__ import annotations
import argparse
import os
import re
import sys

import pandas as pd

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)
from metrics._narrator_utils import (
    preprocess, word_count, has_narrator, iter_venue_papers,
)
from schema import load_processed, resume_year_counts, resume_year_ids

VENUES = ["neurips", "iclr", "icml", "arxiv"]


def process_venue(venue: str, processed_dir: str, out_dir: str) -> int:
    import csv as _csv, re as _re
    venue_dir = os.path.join(processed_dir, venue)
    if not os.path.isdir(venue_dir):
        print(f"  [{venue}] not found"); return 0

    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"{venue}.csv")

    done_counts = resume_year_counts(csv_path)
    if done_counts:
        print(f"  [{venue}] resuming — {len(done_counts)} years present in output")

    header_written = os.path.exists(csv_path)
    total = 0
    for fname in sorted(os.listdir(venue_dir)):
        if not fname.endswith('.json'): continue
        m = _re.search(r'(\d{4})', fname)
        year = int(m.group(1)) if m else -1
        papers = load_processed(os.path.join(venue_dir, fname))
        if done_counts.get(year, 0) >= len(papers):
            print(f"  [{venue}] {fname}: skip (complete)"); continue
        if done_counts.get(year, 0) > 0:
            done = resume_year_ids(csv_path, year)
            papers = [p for p in papers if p["paper_id"] not in done]
            print(f"  [{venue}] {fname}: partial year — {len(papers)} papers to top up")
        rows = []
        for paper in papers:
            abstract = preprocess(paper.get("abstract", ""))
            nw = word_count(abstract)
            rows.append({
                "paper_id":     paper["paper_id"],
                "venue":        paper["venue"],
                "year":         paper["year"],
                "n_words":      nw,
                "has_narrator": int(has_narrator(abstract)),
            })
        if rows:
            pd.DataFrame(rows).to_csv(csv_path, mode='a', header=not header_written, index=False)
            header_written = True
            total += len(rows)
        print(f"  [{venue}] {fname}: {len(papers)} papers → {len(rows)} rows (total {total})")

    print(f"  [{venue}] done — {total} new rows → {csv_path}")
    return total


def main():
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-dir", default=os.path.join(repo, "data", "processed"))
    parser.add_argument("--out-dir",       default=os.path.join(repo, "data", "per_paper", "active_narration"))
    parser.add_argument("--venues", nargs="+", default=VENUES)
    args = parser.parse_args()

    total = 0
    for venue in args.venues:
        total += process_venue(venue, args.processed_dir, args.out_dir)
    print(f"\nTotal: {total} papers")


if __name__ == "__main__":
    main()
