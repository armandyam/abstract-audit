#!/usr/bin/env python3
"""Readability and citations: OLS with venue-year fixed effects.

Regresses log(1 + citations) on Flesch Reading Ease, controlling for abstract
length (log words) and author count (log authors), absorbing venue-year fixed
effects by within-transformation, with cluster-robust (CR1) standard errors
by venue-year. All continuous variables are z-scored over the sample before
the within-transformation, so the coefficients are standardised.

The sample is every paper with a readability score, a citation count, at
least one author, and a year no later than 2024: the most recent year is
excluded because its citation counts are only months old.

Also computes the top-decile versus bottom-decile Cohen's d on Flesch Reading
Ease and words per sentence over the pooled sample, with deciles by citation
rank within venue-year (pandas rank(pct=True), ties averaged). Upstream
printed these and did not save them.

Reads:
  $AA_DATA/per_paper/readability/{venue}.csv
  $AA_DATA/per_paper/citations/{venue}_s2.csv
  $AA_DATA/processed/{venue}/*.json             (author counts)
Writes:
  $AA_DATA/aggregate/citations/citation_regression.csv   pooled and per venue
  $AA_DATA/aggregate/citations/citation_cohens_d.csv     pooled d, two metrics

    python src/citations/regression.py
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from citations._common import (  # noqa: E402
    CIT_DIR, OUT_DIR, PROCESSED_DIR, READ_DIR, VENUES, read_citations, require,
)

MAX_YEAR = 2024
COLUMNS = ["model", "n", "n_clusters", "beta_flesch", "se_flesch", "ci_lo", "ci_hi",
           "beta_abstract_words", "beta_authors"]
D_METRICS = ["flesch_ease", "avg_sentence_length"]


def author_counts(venue: str, processed_dir: str | None = None) -> pd.DataFrame:
    rows = []
    pattern = os.path.join(processed_dir or PROCESSED_DIR, venue, "*.json")
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as fh:
            for p in json.load(fh):
                rows.append((p["paper_id"], len(p.get("authors") or [])))
    return pd.DataFrame(rows, columns=["paper_id", "n_authors"])


def load(venue: str, read_dir: str | None = None, cit_dir: str | None = None,
         processed_dir: str | None = None, max_year: int = MAX_YEAR) -> pd.DataFrame:
    """The regression sample of one venue."""
    read = pd.read_csv(
        require(os.path.join(read_dir or READ_DIR, f"{venue}.csv")),
        usecols=["paper_id", "year", "flesch_ease", "avg_sentence_length", "word_count"])
    cit = read_citations(os.path.join(cit_dir or CIT_DIR, f"{venue}_s2.csv"),
                         usecols=["paper_id", "year", "n_citations"])
    df = read.merge(cit.drop(columns=["year"]), on="paper_id", how="inner")
    df = df.merge(author_counts(venue, processed_dir), on="paper_id", how="left")
    df["venue"] = venue
    df = df[df["year"] <= max_year]
    df = df.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["flesch_ease", "word_count", "n_authors", "n_citations"])
    return df[df["n_authors"] > 0]


def zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std(ddof=1)


def ols_fe_cluster(df: pd.DataFrame) -> dict:
    """z(log1p citations) on z(Flesch), z(log words), z(log authors); venue-year
    fixed effects absorbed by demeaning; CR1 standard errors by venue-year."""
    d = df.copy()
    d["cluster"] = d["venue"] + "_" + d["year"].astype(int).astype(str)
    y = zscore(np.log1p(d["n_citations"]))
    X = pd.DataFrame({
        "flesch_ease": zscore(d["flesch_ease"]),
        "log_abstract_words": zscore(np.log(d["word_count"])),
        "log_authors": zscore(np.log(d["n_authors"])),
    }, index=d.index)
    g = d["cluster"]
    y_w = y - y.groupby(g).transform("mean")
    X_w = X - X.groupby(g).transform("mean")
    Xm, ym = X_w.to_numpy(), y_w.to_numpy()
    n, k = Xm.shape
    n_clusters = g.nunique()
    XtX_inv = np.linalg.inv(Xm.T @ Xm)
    beta = XtX_inv @ (Xm.T @ ym)
    resid = ym - Xm @ beta
    meat = np.zeros((k, k))
    codes = g.to_numpy()
    for c in np.unique(codes):
        m = codes == c
        u = (Xm[m] * resid[m][:, None]).sum(axis=0)
        meat += np.outer(u, u)
    # small-sample correction; the residual df loses k slopes and the absorbed FE
    df_resid = n - k - n_clusters
    corr = (n_clusters / (n_clusters - 1)) * ((n - 1) / df_resid)
    V = XtX_inv @ meat @ XtX_inv * corr
    se = np.sqrt(np.diag(V))
    return {
        "n": int(n), "n_clusters": int(n_clusters),
        "beta_flesch": float(beta[0]), "se_flesch": float(se[0]),
        "ci_lo": float(beta[0] - 1.96 * se[0]), "ci_hi": float(beta[0] + 1.96 * se[0]),
        "beta_abstract_words": float(beta[1]), "beta_authors": float(beta[2]),
    }


def decile_groups(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Top and bottom citation decile, ranks within venue-year."""
    d = df.copy()
    d["pct"] = d.groupby(["venue", "year"])["n_citations"].rank(pct=True)
    return d[d["pct"] >= 0.90], d[d["pct"] <= 0.10]


def cohens_d(df: pd.DataFrame, col: str) -> float:
    """Top minus bottom decile mean over the pooled standard deviation."""
    top_df, bot_df = decile_groups(df)
    top, bot = top_df[col], bot_df[col]
    n1, n2 = len(top), len(bot)
    s = np.sqrt(((n1 - 1) * top.var(ddof=1) + (n2 - 1) * bot.var(ddof=1)) / (n1 + n2 - 2))
    return float((top.mean() - bot.mean()) / s)


def run(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    pooled = pd.concat(frames.values(), ignore_index=True)
    rows = [{**ols_fe_cluster(pooled), "model": "pooled"}]
    rows += [{**ols_fe_cluster(f), "model": v} for v, f in frames.items()]
    reg = pd.DataFrame(rows)[COLUMNS].round(4)
    top, bot = decile_groups(pooled)
    d = pd.DataFrame([{"sample": "pooled", "metric": m, "n_top": len(top),
                       "n_bottom": len(bot), "cohens_d": cohens_d(pooled, m)}
                      for m in D_METRICS])
    return reg, d


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venues", nargs="+", default=VENUES)
    ap.add_argument("--out-dir", default=OUT_DIR)
    a = ap.parse_args()
    reg, d = run({v: load(v) for v in a.venues})
    os.makedirs(a.out_dir, exist_ok=True)
    reg.to_csv(os.path.join(a.out_dir, "citation_regression.csv"), index=False)
    d.to_csv(os.path.join(a.out_dir, "citation_cohens_d.csv"), index=False)
    pd.set_option("display.width", 250)
    print(reg.to_string(index=False))
    print()
    print(d.to_string(index=False))
    print(f"\nwrote citation_regression.csv and citation_cohens_d.csv to {a.out_dir}")


if __name__ == "__main__":
    main()
