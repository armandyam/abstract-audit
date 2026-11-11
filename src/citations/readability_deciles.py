#!/usr/bin/env python3
"""Readability of the top and bottom citation deciles.

Pools NeurIPS, ICLR and ICML papers with a within-venue-year citation
percentile (enrich.py) and a readability score, through --max-year (2024 for
the paper: the most recent year has had little time to collect citations, and
its many low-count ties distort the within-year percentiles).
The top decile is citation_percentile >= 90 and the bottom <= 10.

For each of 13 readability formulas and two surface measures, writes the
group means, the half-width of a 95 percent normal-approximation confidence
interval (1.96 std / sqrt(n)), and the difference top minus bottom. These are
every number in the TMLR paper's Table tab:citation-readability-combined; the
table's n_top and n_bottom are top_n and bottom_n (no metric has a missing
value in the deciles).

Reads:
  $AA_DATA/per_paper/readability/{venue}.csv
  $AA_DATA/per_paper/citations/{venue}_s2.csv
Writes:
  $AA_DATA/aggregate/citations/citation_readability_top_bottom{suffix}.csv
  where suffix is _combined for several venues, empty for NeurIPS alone and
  _{venue} for another single venue.

    python src/citations/readability_deciles.py --venues neurips iclr icml --max-year 2024
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from citations._common import CIT_DIR, OUT_DIR, READ_DIR, VENUES, read_citations, require  # noqa: E402

READABILITY_METRICS = [
    "flesch_ease", "flesch_kincaid", "gunning_fog", "smog", "dale_chall",
    "spache", "coleman_liau", "ari", "linsear_write", "lix", "rix", "forcast",
    "powers_sumner_kearl", "avg_sentence_length", "avg_syllables_per_word",
]
Z95 = 1.96


def ci_half(std: float, n: int) -> float:
    return Z95 * std / np.sqrt(n)


def suffix(venues: list[str]) -> str:
    if len(venues) == 1:
        return "" if venues[0] == "neurips" else f"_{venues[0]}"
    return "_combined"


def load(venues: list[str], max_year: int | None, read_dir: str | None = None,
         cit_dir: str | None = None) -> pd.DataFrame:
    frames = []
    for v in venues:
        rd = pd.read_csv(require(os.path.join(read_dir or READ_DIR, f"{v}.csv")))
        ct = read_citations(os.path.join(cit_dir or CIT_DIR, f"{v}_s2.csv"))[
            ["paper_id", "year", "citation_percentile"]]
        m = rd.merge(ct, on=["paper_id", "year"], how="inner").dropna(
            subset=["citation_percentile"])
        if max_year is not None:
            m = m[m["year"] <= max_year]
        m["venue"] = v
        frames.append(m)
    return pd.concat(frames, ignore_index=True)


def top_bottom(df: pd.DataFrame) -> pd.DataFrame:
    top = df[df["citation_percentile"] >= 90]
    bottom = df[df["citation_percentile"] <= 10]
    rows = []
    for metric in READABILITY_METRICS:
        if metric not in df.columns:
            continue
        t, b = top[metric].dropna(), bottom[metric].dropna()
        rows.append({
            "metric": metric,
            "top_n": len(t), "top_mean": t.mean(),
            "top_ci": ci_half(t.std(ddof=1), len(t)),
            "bottom_n": len(b), "bottom_mean": b.mean(),
            "bottom_ci": ci_half(b.std(ddof=1), len(b)),
            "delta": t.mean() - b.mean(),
        })
    return pd.DataFrame(rows, columns=["metric", "top_n", "top_mean", "top_ci", "bottom_n",
                                       "bottom_mean", "bottom_ci", "delta"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venues", nargs="+", default=VENUES)
    ap.add_argument("--max-year", type=int, default=2024)
    ap.add_argument("--out-dir", default=OUT_DIR)
    a = ap.parse_args()
    df = load(a.venues, a.max_year)
    out = top_bottom(df)
    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, f"citation_readability_top_bottom{suffix(a.venues)}.csv")
    out.to_csv(path, index=False, float_format="%.4f")
    print(f"  {len(df):,} papers with a citation percentile; wrote {path}")


if __name__ == "__main__":
    main()
