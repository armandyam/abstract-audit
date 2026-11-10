#!/usr/bin/env python3
"""Mean bibliography length per venue and year.

Aggregates the n_references column of {venue}_s2.csv (the length of each
matched paper's Semantic Scholar reference list) to a mean per venue-year.

A missing or zero n_references is excluded. Semantic Scholar has not ingested
the reference lists of a large share of recent papers, and those rows carry a
literal 0 rather than a null. Averaging them in would manufacture a recent decline. A paper with a
genuinely empty bibliography does not occur in these proceedings, so a zero
is always a missing measurement. A venue-year with fewer than --min-papers
usable papers is suppressed.

Reads:
  $AA_DATA/per_paper/citations/{venue}_s2.csv
Writes:
  $AA_DATA/aggregate/citations/references.csv
      venue, year, references_mean, n_papers, n_total, coverage
  $AA_DATA/aggregate/citations/references_per_year.csv
      year, neurips, iclr, icml   (the TMLR bibliography figure; "nan" for gaps)
  $AA_DATA/pgfplots/tmlr/references_per_year.csv
      the same file, where the figure sources read it
      (paper/tmlr/figs/fig_app_references.tex)

    python src/citations/references.py
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from citations._common import CIT_DIR, D, OUT_DIR, VENUES, require, require_unique  # noqa: E402

MIN_PAPERS = 20


def load(path: str) -> tuple[dict[int, list[float]], dict[int, int]]:
    """({year: [usable reference counts]}, {year: rows in the file})."""
    kept: dict[int, list[float]] = defaultdict(list)
    seen: dict[int, int] = defaultdict(int)
    with open(require(path), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    require_unique([r["paper_id"] for r in rows], path)
    for row in rows:
        year = int(row["year"])
        seen[year] += 1
        raw = (row.get("n_references") or "").strip()
        if not raw:
            continue
        value = float(raw)
        if value <= 0:
            continue
        kept[year].append(value)
    return kept, seen


def write(per_venue: dict, totals: dict, venues: list[str], out_dir: str,
          min_papers: int = MIN_PAPERS) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    long_path = os.path.join(out_dir, "references.csv")
    with open(long_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["venue", "year", "references_mean", "n_papers", "n_total", "coverage"])
        for v in venues:
            for year in sorted(per_venue[v]):
                values = per_venue[v][year]
                if len(values) < min_papers:
                    continue
                total = totals[v][year]
                w.writerow([v, year, round(sum(values) / len(values), 2),
                            len(values), total, round(len(values) / total, 4)])
    years = sorted({y for v in venues for y in per_venue[v]})
    wide_path = os.path.join(out_dir, "references_per_year.csv")
    with open(wide_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["year", *venues])
        for year in years:
            row: list[object] = [year]
            for v in venues:
                values = per_venue[v].get(year, [])
                row.append("nan" if len(values) < min_papers
                           else round(sum(values) / len(values), 2))
            w.writerow(row)
    return long_path, wide_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venues", nargs="+", default=VENUES)
    ap.add_argument("--citations-dir", default=CIT_DIR)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--min-papers", type=int, default=MIN_PAPERS)
    ap.add_argument("--pgfplots-dir", default=os.path.join(D, "pgfplots", "tmlr"),
                    help="where the figure sources read references_per_year.csv")
    a = ap.parse_args()
    per_venue, totals = {}, {}
    for v in a.venues:
        per_venue[v], totals[v] = load(os.path.join(a.citations_dir, f"{v}_s2.csv"))
    long_path, wide_path = write(per_venue, totals, a.venues, a.out_dir, a.min_papers)
    os.makedirs(a.pgfplots_dir, exist_ok=True)
    fig_path = shutil.copyfile(wide_path, os.path.join(a.pgfplots_dir, "references_per_year.csv"))
    for p in (long_path, wide_path, fig_path):
        print(f"wrote {p}")


if __name__ == "__main__":
    main()
