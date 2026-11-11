#!/usr/bin/env python3
"""Write shared/baselines/arxiv_snapshot.json: where the arXiv snapshot ends.

How much of calendar year 2025 the arXiv snapshot covers is a property of
the snapshot's cutoff date, not of how many papers 2025 has, so it is
computed from the cutoff and not from a ratio of yearly counts (which growth
and seasonality distort).

The processed arXiv records carry no submission date, only the identifier.
A new-style identifier YYMM.NNNNN gives the month of first submission and,
through its sequence number, how far into that month the submission came:
arXiv numbers each month's submissions consecutively from 00001. So the last
identifier of the snapshot places its cutoff:

  month     the YYMM of the largest identifier dated in the last year
  position  its sequence number divided by the mean of the largest sequence
            numbers of that year's earlier, complete months: the fraction of
            a typical month the snapshot reached
  fraction  (month - 1 + position) / 12, the share of the calendar year
            covered. It always lies between (month - 1) / 12 and month / 12,
            which the month alone guarantees; those bounds are written too.

Reads:   {processed_dir}/arxiv/arxiv_{year}.json   (processed records; only
         the "paper_id" fields are read, with a regular expression, so the
         300 MB files are not parsed)
Writes:  shared/baselines/arxiv_snapshot.json

The processed arXiv corpus is not distributed (see shared/baselines/README.md), so
the JSON is committed. It was written by this script from the corpus the
paper used (processed in April 2026 from the Kaggle Cornell-University/arxiv
snapshot), and only identifiers and counts are recorded in it.

    python src/baselines/arxiv_snapshot.py --processed-dir /path/to/processed
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, "shared", "baselines", "arxiv_snapshot.json")
NEW_ID = re.compile(r'"paper_id"\s*:\s*"(\d{2})(\d{2})\.(\d{4,5})(?:v\d+)?"')


def month_maxima(text: str, year: int) -> dict[int, int]:
    """Largest sequence number per month among the new-style identifiers of
    one calendar year in `text`."""
    yy = year % 100
    out: dict[int, int] = {}
    for a, m, n in NEW_ID.findall(text):
        if int(a) != yy:
            continue
        out[int(m)] = max(out.get(int(m), 0), int(n))
    return out


def cutoff(maxima: dict[int, int], year: int) -> dict:
    """The snapshot's cutoff from one year's per-month maximum identifiers."""
    if not maxima:
        raise ValueError(f"no new-style identifiers for {year}")
    month = max(maxima)
    full = [maxima[m] for m in sorted(maxima) if m < month]
    if not full:
        raise ValueError(f"no complete month before {year}-{month:02d}")
    typical = sum(full) / len(full)
    position = min(1.0, maxima[month] / typical)
    return {
        "year": year,
        "last_id": f"{year % 100:02d}{month:02d}.{maxima[month]:05d}",
        "last_month": f"{year}-{month:02d}",
        "last_month_sequence": maxima[month],
        "mean_complete_month_sequence": round(typical, 1),
        "complete_months": len(full),
        "cutoff_month_position": round(position, 4),
        "cutoff_year_fraction": round((month - 1 + position) / 12, 4),
        "cutoff_year_fraction_min": round((month - 1) / 12, 4),
        "cutoff_year_fraction_max": round(month / 12, 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--processed-dir",
                    default=os.path.join(os.environ.get("AA_DATA", "data"), "processed"))
    ap.add_argument("--year", type=int, default=2025, help="the partial year")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    path = os.path.join(a.processed_dir, "arxiv", f"arxiv_{a.year}.json")
    if not os.path.exists(path):
        sys.exit(f"{path} is absent; the committed {os.path.relpath(a.out, REPO)} "
                 "was written from the paper's corpus (see the docstring)")
    with open(path, encoding="utf-8") as fh:
        rec = cutoff(month_maxima(fh.read(), a.year), a.year)
    rec["source"] = (f"processed/arxiv/arxiv_{a.year}.json of the paper's arXiv corpus "
                     "(Kaggle Cornell-University/arxiv snapshot, processed 2026-04); "
                     "written by src/baselines/arxiv_snapshot.py")
    with open(a.out, "w") as fh:
        json.dump(rec, fh, indent=2)
        fh.write("\n")
    print(json.dumps(rec, indent=2))


if __name__ == "__main__":
    main()
