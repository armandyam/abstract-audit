#!/usr/bin/env python3
"""How many papers have a citation count, and how they were matched.

Per venue, from {venue}_s2.csv (one row per paper of the processed corpus):

  n_papers_to_max_year        rows with year <= --max-year (2024 in the paper)
  n_with_citations_to_max_year  of those, rows with a citation count
  coverage_pct                the share, in percent.
  n_papers                    rows over all years
  n_{title,s2_fuzzy,openalex,unmatched,error}
                              rows per match_type over all years
  supplemented_pct            (s2_fuzzy + openalex) / n_papers, in percent:
                              the share recovered by the fallback pass.

Reads:  $AA_DATA/per_paper/citations/{venue}_s2.csv
Writes: $AA_DATA/aggregate/citations/citation_coverage.csv

    python src/citations/coverage.py
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from citations._common import CIT_DIR, OUT_DIR, VENUES, read_citations  # noqa: E402

MAX_YEAR = 2024
MATCH_TYPES = ["title", "s2_fuzzy", "openalex", "unmatched", "error"]
COLUMNS = (["venue", "max_year", "n_papers_to_max_year", "n_with_citations_to_max_year",
            "coverage_pct", "n_papers"] + [f"n_{m}" for m in MATCH_TYPES]
           + ["supplemented_pct"])


def _pct(num: int, den: int) -> float:
    return 100.0 * num / den if den else float("nan")


def venue_row(df: pd.DataFrame, venue: str, max_year: int = MAX_YEAR) -> dict:
    cites = pd.to_numeric(df["n_citations"], errors="coerce")
    upto = df["year"] <= max_year
    n_upto = int(upto.sum())
    n_cit = int(cites[upto].notna().sum())
    mt = df["match_type"].fillna("").value_counts()
    row = {"venue": venue, "max_year": max_year,
           "n_papers_to_max_year": n_upto, "n_with_citations_to_max_year": n_cit,
           "coverage_pct": _pct(n_cit, n_upto), "n_papers": len(df)}
    for m in MATCH_TYPES:
        row[f"n_{m}"] = int(mt.get(m, 0))
    row["supplemented_pct"] = _pct(row["n_s2_fuzzy"] + row["n_openalex"], len(df))
    return row


def coverage(venues: list[str], cit_dir: str | None = None,
             max_year: int = MAX_YEAR) -> pd.DataFrame:
    rows = []
    for v in venues:
        df = read_citations(os.path.join(cit_dir or CIT_DIR, f"{v}_s2.csv"),
                            usecols=["year", "n_citations", "match_type"], low_memory=False)
        rows.append(venue_row(df, v, max_year))
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venues", nargs="+", default=VENUES)
    ap.add_argument("--max-year", type=int, default=MAX_YEAR)
    ap.add_argument("--out-dir", default=OUT_DIR)
    a = ap.parse_args()
    out = coverage(a.venues, max_year=a.max_year)
    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, "citation_coverage.csv")
    out.to_csv(path, index=False)
    print(out.to_string(index=False))
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
