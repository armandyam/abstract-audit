#!/usr/bin/env python3
"""Does the readability and citation association survive a topic control?

The citation regression (regression.py) absorbs venue-year fixed effects and
controls for abstract length and author count, but not for subfield. If the
topic mix shifted over the window, and some topics are both more cited and
harder to read, the Flesch coefficient could reflect that shift.

Venue-year fixed effects are absorbed by within-transformation exactly as in
regression.py, and topic enters as dummies (first level dropped) in the
demeaned design matrix: the two-way fixed effects estimator, with the same
cluster-robust (CR1) standard errors. The normal equations are solved with a
pseudo-inverse, as upstream.

For the model without topics and for k = 10, 15, 20 and 30: the Flesch
coefficient, its standard error and 95 percent interval, the within
R-squared, and a cluster-robust Wald statistic that the topic dummies are
jointly zero. These are the numbers of the TMLR paper's Table
tab:topic-controls and of the macros BetaNoTopic, BetaTopicMin/Max,
RtwoNoTopic and RtwoTopicMin/Max.

Topic assignments (paper_id, venue, year, topic_k10, topic_k15, ...) come
from the topic clustering, which is a separate stage; pass its CSV.

Reads:
  --assignments  topic_assignments.csv
  the inputs of regression.py
Writes:
  $AA_DATA/aggregate/citations/citation_regression_topics.csv

    python src/citations/regression_topics.py --assignments path/to/topic_assignments.csv
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from citations._common import OUT_DIR, VENUES, require  # noqa: E402
from citations.regression import load  # noqa: E402

K_VALUES = [10, 15, 20, 30]


def fit(d: pd.DataFrame, topic_col: str | None) -> dict:
    """Two-way FE OLS with CR1 errors. topic_col=None is the published model."""
    d = d.copy()
    g = d["venue"] + "_" + d["year"].astype(int).astype(str)

    def z(s):
        return (s - s.mean()) / s.std(ddof=1)

    y = z(np.log1p(d["n_citations"]))
    X = pd.DataFrame({
        "flesch_ease": z(d["flesch_ease"]),
        "log_abstract_words": z(np.log(d["word_count"])),
        "log_authors": z(np.log(d["n_authors"])),
    }, index=d.index)
    n_topic_cols = 0
    if topic_col is not None:
        dum = pd.get_dummies(d[topic_col].astype("category"), prefix="t",
                             drop_first=True).astype(float)
        dum.index = d.index
        n_topic_cols = dum.shape[1]
        X = pd.concat([X, dum], axis=1)

    y_w = (y - y.groupby(g).transform("mean")).to_numpy()
    X_w = (X - X.groupby(g).transform("mean")).to_numpy()
    n, k = X_w.shape
    n_clusters = g.nunique()
    XtX_inv = np.linalg.pinv(X_w.T @ X_w)
    beta = XtX_inv @ (X_w.T @ y_w)
    resid = y_w - X_w @ beta
    meat = np.zeros((k, k))
    codes = g.to_numpy()
    for c in np.unique(codes):
        m = codes == c
        u = (X_w[m] * resid[m][:, None]).sum(axis=0)
        meat += np.outer(u, u)
    df_resid = n - k - n_clusters
    corr = (n_clusters / (n_clusters - 1)) * ((n - 1) / df_resid)
    V = XtX_inv @ meat @ XtX_inv * corr
    se = np.sqrt(np.diag(V))
    r2 = 1 - (resid @ resid) / (y_w @ y_w)
    out = {
        "n": int(n), "n_clusters": int(n_clusters),
        "beta_flesch": float(beta[0]), "se_flesch": float(se[0]),
        "ci_lo": float(beta[0] - 1.96 * se[0]),
        "ci_hi": float(beta[0] + 1.96 * se[0]),
        "r2_within": float(r2), "n_topic_dummies": n_topic_cols,
    }
    if n_topic_cols:
        idx = list(range(3, 3 + n_topic_cols))
        b = beta[idx]
        Vt = V[np.ix_(idx, idx)]
        out["wald_topics"] = float(b @ np.linalg.pinv(Vt) @ b)
        out["wald_df"] = n_topic_cols
    return out


def run(pooled: pd.DataFrame, topics: pd.DataFrame,
        k_values: list[int] = K_VALUES) -> pd.DataFrame:
    pooled = pooled.merge(topics.drop(columns=["venue", "year"], errors="ignore"),
                          on="paper_id", how="left")
    base = fit(pooled, None)
    base["model"] = "no topic control (published)"
    rows = [base]
    for k in k_values:
        col = f"topic_k{k}"
        if col not in pooled.columns:
            print(f"  (no {col} in the assignments, skipped)")
            continue
        r = fit(pooled.dropna(subset=[col]), col)
        r["model"] = f"+ topic FE (k={k})"
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assignments", required=True, help="topic_assignments.csv")
    ap.add_argument("--venues", nargs="+", default=VENUES)
    ap.add_argument("--out-dir", default=OUT_DIR)
    a = ap.parse_args()
    pooled = pd.concat([load(v) for v in a.venues], ignore_index=True)
    out = run(pooled, pd.read_csv(require(a.assignments)))
    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, "citation_regression_topics.csv")
    out.to_csv(path, index=False)
    print(out[["model", "n", "beta_flesch", "se_flesch", "r2_within"]].to_string(index=False))
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
