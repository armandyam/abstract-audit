#!/usr/bin/env python3
"""Per-topic trends: is the readability decline carried by a few topics?

For every k = 15 topic (topic_clusters.py), the change in Flesch Reading
Ease, sensational language and title and abstract acronym density within the
window 2015 to 2025. If a trend is carried by two or three topics it is a
compositional story about which subfields grew. If every topic moves the same
way it is a field-wide change in how people write.

Each topic is measured over its own span of well-populated years (at least
MIN_CELL papers in a topic-year, at least MIN_YEARS such years). Half the
topics barely exist in 2015, and a common window would drop them from the
count. Per metric and topic the output carries the first and last populated
year, their annual means, the change, the slope of a least-squares line
through the annual means, and the slope fitted on individual papers with a
95 percent interval clustered by venue-year (`_beta`, `_ci_lo`, `_ci_hi`;
`_sig` if the interval excludes zero, `_sig_same` if it does so in the
direction of the aggregate trend: down for Flesch, up for the rest).

The window stops at 2025, the last year in which all three venues contribute
papers. ICLR 2026 is the only venue in 2026, so including it would confound a
topic-mix change with a venue-mix change.

Reads:  data/aggregate/topic_assignments.csv, data/aggregate/topic_terms.csv
        data/per_paper/{readability,sensational_language,acronyms}/{venue}.csv
Writes: data/aggregate/topic_trends.csv   one row per topic

Run:
  python src/analysis/topic_trends.py
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

_D = os.environ.get("AA_DATA", "data")
PER_PAPER = os.path.join(_D, "per_paper")
OUT = os.path.join(_D, "aggregate")
VENUES = ["neurips", "iclr", "icml"]

K = 15              # primary topic resolution
FIRST_YEAR = 2015   # base year of the fixed-mix counterfactual
LAST_YEAR = 2025    # last year with all three venues present
MIN_CELL = 30       # papers required in a topic-year before it is used
MIN_YEARS = 5       # populated years required before a topic is given a slope

METRICS = {
    "flesch": "flesch_ease",
    "hype": "hype_total_per_100",
    "acr_abstract": "abstract_acronym_density",
    "acr_title": "title_acronym_density",
}


def read_per_paper(metric: str, cols: list[str], venues: list[str] = VENUES,
                   per_paper: str = PER_PAPER) -> pd.DataFrame:
    return pd.concat([
        pd.read_csv(os.path.join(per_paper, metric, f"{v}.csv"), usecols=cols)
        for v in venues
    ], ignore_index=True)


def load(agg: str = OUT, per_paper: str = PER_PAPER) -> pd.DataFrame:
    """Topic labels joined to the per-paper metrics, within the window."""
    top = pd.read_csv(os.path.join(agg, "topic_assignments.csv"),
                      usecols=["paper_id", "venue", "year", f"topic_k{K}"])
    read = read_per_paper("readability", ["paper_id", "flesch_ease", "word_count",
                                          "sentence_count", "syllable_count"],
                          per_paper=per_paper)
    hype = read_per_paper("sensational_language", ["paper_id", "hype_total_per_100"],
                          per_paper=per_paper)
    acr = read_per_paper("acronyms", ["paper_id", "title_acronym_density",
                                      "abstract_acronym_density", "abstract_acronyms"],
                         per_paper=per_paper)
    d = top.merge(read, on="paper_id").merge(hype, on="paper_id").merge(acr, on="paper_id")
    return d[(d.year >= FIRST_YEAR) & (d.year <= LAST_YEAR)].copy()


def ols_clustered(y: np.ndarray, x: np.ndarray, cluster: np.ndarray):
    """Slope of y on x with a cluster-robust 95 percent interval.

    Fitted on individual papers rather than on annual means, so the interval
    reflects the spread within each year as well as the movement between
    years. Uses the CR1 small-sample correction G/(G-1) * (n-1)/(n-k), so it
    needs at least two clusters. Returns (slope, lower, upper).
    """
    X = np.column_stack([np.ones(len(x)), x])
    n, k = X.shape
    XtXi = np.linalg.inv(X.T @ X)
    beta = XtXi @ X.T @ y
    resid = y - X @ beta
    meat = np.zeros((k, k))
    for c in np.unique(cluster):
        m = cluster == c
        s = X[m].T @ resid[m]
        meat += np.outer(s, s)
    g = len(np.unique(cluster))
    v = XtXi @ meat @ XtXi * (g / (g - 1)) * ((n - 1) / (n - k))
    se = float(np.sqrt(np.diag(v))[1])
    return float(beta[1]), float(beta[1]) - 1.96 * se, float(beta[1]) + 1.96 * se


def topic_trends(d: pd.DataFrame, terms: pd.DataFrame, k: int = K,
                 min_cell: int = MIN_CELL, min_years: int = MIN_YEARS) -> pd.DataFrame:
    """One row per topic, sorted by Flesch slope (most negative first).

    A topic with fewer than `min_years` populated years gets NaN endpoints and
    slope for that metric and no interval columns.
    """
    col = f"topic_k{k}"
    label = {r.cluster: r.top_terms for _, r in terms[terms.k == k].iterrows()}

    rows = []
    for topic, g in d.groupby(col):
        row = {"topic": int(topic), "n": len(g), "top_terms": label.get(topic, "")}
        for tag, metric in METRICS.items():
            per_year = g.groupby("year")[metric].agg(["mean", "size"])
            per_year = per_year[per_year["size"] >= min_cell]
            if len(per_year) < min_years:
                for suffix in ["first_year", "last_year", "first", "last",
                               "change", "slope"]:
                    row[f"{tag}_{suffix}"] = np.nan
                continue
            years = per_year.index.to_numpy(float)
            means = per_year["mean"].to_numpy(float)
            row[f"{tag}_first_year"] = int(years[0])
            row[f"{tag}_last_year"] = int(years[-1])
            row[f"{tag}_first"] = means[0]
            row[f"{tag}_last"] = means[-1]
            row[f"{tag}_change"] = means[-1] - means[0]
            row[f"{tag}_slope"] = np.polyfit(years, means, 1)[0]

            gm = g.dropna(subset=[metric])
            b, lo, hi = ols_clustered(
                gm[metric].to_numpy(float), gm.year.to_numpy(float),
                (gm.venue + "_" + gm.year.astype(str)).to_numpy())
            row[f"{tag}_beta"] = b
            row[f"{tag}_ci_lo"] = lo
            row[f"{tag}_ci_hi"] = hi
            row[f"{tag}_sig"] = bool(hi < 0 or lo > 0)
            row[f"{tag}_sig_same"] = bool(hi < 0 if tag == "flesch" else lo > 0)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("flesch_slope")


def report(out: pd.DataFrame, d: pd.DataFrame) -> None:
    print(f"per-topic trend within {FIRST_YEAR} to {LAST_YEAR}, k={K}, "
          f"each topic over its own populated years\n")
    print(f"{'topic':<40}{'n':>7}{'span':>11}{'Flesch/yr':>11}"
          f"{'hype/yr':>9}{'acr/yr':>8}")
    for _, r in out.iterrows():
        short = ", ".join(str(r.top_terms).split(", ")[:4])[:34]
        span = f"{int(r.flesch_first_year)}-{int(r.flesch_last_year)}"
        print(f"  c{r.topic:<2d} {short:<35}{int(r.n):>7}{span:>11}"
              f"{r.flesch_slope:>11.2f}{r.hype_slope:>9.3f}"
              f"{r.acr_abstract_slope:>8.3f}")

    for tag, name, want in [("flesch", "Flesch Reading Ease", "down"),
                            ("hype", "sensational language", "up"),
                            ("acr_abstract", "abstract acronym density", "up"),
                            ("acr_title", "title acronym density", "up")]:
        s = out[f"{tag}_slope"].dropna()
        n_same = int((s < 0).sum()) if want == "down" else int((s > 0).sum())
        n_sig = int(out[f"{tag}_sig_same"].sum())
        print(f"\n  {name}: {n_same} of {len(s)} topics trend {want}, "
              f"slope range {s.min():+.3f} to {s.max():+.3f} per year")
        print(f"    of those, {n_sig} have a cluster-robust interval "
              f"excluding zero in that direction")

    # Printed only: how the sign counts move with the minimum topic-year size.
    print("\n  sensitivity of the sign counts to the two cutoffs:")
    col = f"topic_k{K}"
    for mc in [10, 30, 50, 100]:
        cells = []
        for tag, metric in METRICS.items():
            n_same = n_tot = 0
            for _, g in d.groupby(col):
                py = g.groupby("year")[metric].agg(["mean", "size"])
                py = py[py["size"] >= mc]
                if len(py) < MIN_YEARS:
                    continue
                sl = np.polyfit(py.index.to_numpy(float),
                                py["mean"].to_numpy(float), 1)[0]
                n_tot += 1
                n_same += int(sl < 0) if tag == "flesch" else int(sl > 0)
            cells.append(f"{tag}={n_same}/{n_tot}")
        print(f"    min papers per topic-year {mc:>3}: " + "  ".join(cells))


def main() -> None:
    if not os.path.exists(os.path.join(OUT, "topic_assignments.csv")):
        # No abstracts, so topic_clusters.py wrote no topics.
        print(f"  no topic_assignments.csv under {OUT}; skipping")
        return
    terms = pd.read_csv(os.path.join(OUT, "topic_terms.csv"))
    d = load()
    print(f"conference papers in window: {len(d):,}\n")
    out = topic_trends(d, terms)
    report(out, d)
    os.makedirs(OUT, exist_ok=True)
    out.to_csv(os.path.join(OUT, "topic_trends.csv"), index=False)
    print(f"\nwrote topic_trends.csv to {OUT}")


if __name__ == "__main__":
    main()
