#!/usr/bin/env python3
"""
Collinearity of the 15 classical readability metrics, per venue.

Reports the mean absolute pairwise correlation among the 15 metrics and the
variance explained by the first one, two and three principal components of the
standardised metrics. The TMLR paper quotes the NeurIPS row.

Reads:  data/per_paper/readability/{venue}.csv
Writes: data/aggregate/readability_collinearity.csv

Run:
  python src/analysis/readability_collinearity.py
"""

from __future__ import annotations
import argparse
import os

import numpy as np
import pandas as pd

_D = os.environ.get("AA_DATA", "data")
READ_CSV = os.path.join(_D, "per_paper", "readability", "{venue}.csv")
OUT_CSV = os.path.join(_D, "aggregate", "readability_collinearity.csv")

METRICS = [
    "flesch_ease",
    "flesch_kincaid",
    "gunning_fog",
    "smog",
    "dale_chall",
    "spache",
    "coleman_liau",
    "ari",
    "linsear_write",
    "lix",
    "rix",
    "forcast",
    "powers_sumner_kearl",
    "avg_sentence_length",
    "avg_syllables_per_word",
]


def analyse_frame(df: pd.DataFrame, venue: str) -> dict:
    n_total = len(df)
    df = df[METRICS].replace([np.inf, -np.inf], np.nan).dropna()
    n = len(df)

    corr = df.corr().to_numpy()
    iu = np.triu_indices_from(corr, k=1)
    mean_abs_r = float(np.abs(corr[iu]).mean())

    # PCA on the standardised metrics == eigendecomposition of the
    # correlation matrix. Eigenvalues sum to the number of metrics.
    eigvals = np.linalg.eigvalsh(corr)[::-1]
    ratio = eigvals / eigvals.sum()

    return {
        "venue": venue,
        "n_papers_total": n_total,
        "n_papers_complete": n,
        "n_metrics": len(METRICS),
        "n_pairs": len(iu[0]),
        "mean_abs_pairwise_corr": round(mean_abs_r, 4),
        "pc1_var_explained": round(float(ratio[0]), 4),
        "pc1_pc2_var_explained": round(float(ratio[:2].sum()), 4),
        "pc1_pc3_var_explained": round(float(ratio[:3].sum()), 4),
    }


def analyse(venue: str) -> dict:
    df = pd.read_csv(READ_CSV.format(venue=venue), usecols=METRICS + ["year"])
    return analyse_frame(df, venue)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venues", nargs="+", default=["neurips", "iclr", "icml"])
    args = ap.parse_args()

    out = pd.DataFrame([analyse(v) for v in args.venues])
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    pd.set_option("display.width", 200)
    print(out.to_string(index=False))
    print(f"\nwrote {OUT_CSV}")


if __name__ == "__main__":
    main()
