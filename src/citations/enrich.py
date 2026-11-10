#!/usr/bin/env python3
"""Add within-year citation percentiles to a {venue}_s2.csv file.

Two columns are computed within each publication year, over the papers of
that year that have a citation count:

  citation_percentile  scipy.stats.percentileofscore(kind="rank"): the
                       percentile rank, 0 to 100, 100 the most cited. Tied
                       counts share the mean of the ranks they span, so every
                       paper with zero citations in a year gets the same
                       percentile.
  mncs                 mean-normalised citation score: citations divided by
                       the year mean. NaN when the year mean is 0.

Rows without a citation count (unmatched) get NaN for both. The file is
rewritten in place through pandas, which also writes the count columns as
floats ("6.0"); the published snapshot files are in that form.

    python src/citations/enrich.py --venue neurips
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import percentileofscore

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from citations._common import CIT_DIR  # noqa: E402


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["n_citations"] = pd.to_numeric(df["n_citations"], errors="coerce")
    df["citation_percentile"] = np.nan
    df["mncs"] = np.nan
    for _, grp in df.groupby("year"):
        valid = grp["n_citations"].dropna()
        if valid.empty:
            continue
        year_mean = valid.mean()
        pct = valid.apply(lambda c: percentileofscore(valid, c, kind="rank"))
        df.loc[pct.index, "citation_percentile"] = pct.values
        if year_mean > 0:
            df.loc[valid.index, "mncs"] = valid.values / year_mean
        else:
            df.loc[valid.index, "mncs"] = np.nan
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venue", default="neurips")
    ap.add_argument("--csv", default=None,
                    help="default: $AA_DATA/per_paper/citations/{venue}_s2.csv")
    a = ap.parse_args()
    path = a.csv or os.path.join(CIT_DIR, f"{a.venue}_s2.csv")
    if not os.path.exists(path):
        sys.exit(f"missing input: {path}")
    df = enrich(pd.read_csv(path, low_memory=False))
    print(f"  {df['citation_percentile'].notna().sum():,} of {len(df):,} rows enriched")
    df.to_csv(path, index=False)
    print(f"  rewrote {path}")


if __name__ == "__main__":
    main()
