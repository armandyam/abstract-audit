#!/usr/bin/env python3
"""Within-topic and between-topic parts of the readability decline.

Splits the change in mean Flesch Reading Ease across the three conferences
from BASE_YEAR to LAST_YEAR exactly into two parts, over the k = 15 topics
(topic_clusters.py):

    within  = sum_k  (w0_k + w1_k) / 2 * (f1_k - f0_k)
    between = sum_k  (f0_k + f1_k) / 2 * (w1_k - w0_k)

where w is a topic's share of papers and f its mean score in each year. The
symmetric weights make the two parts sum to the observed change with no
interaction term. The two one-sided versions, weighting by the first-year mix
(which reproduces the fixed-mix counterfactual of topic_profiles.py) or the
last-year mix, bracket the symmetric split.

All three value a topic at its own mean in BASE_YEAR, which rests on a handful
of papers for the topics that later grew. The fourth, year-adjusted version
avoids those cells. It values each topic by its readability gap to papers of
the same year, estimated by one least-squares fit of Flesch on topic and year
indicators over every year of the window, and sets

    between = sum_k  gap_k * (w1_k - w0_k),   within = total - between.

The year-adjusted between term is also reported for the N_HARD least readable
topics (lowest mean Flesch in topic_profiles.csv). A group's share of the
between term depends on where the gaps are centred, because the shares sum
to one in both years. The gaps are centred on their mean over the two years'
average mix, so a topic adds to the decline only if it is less readable than
that average and grows.

A topic absent in one of the two years has no mean there. It then contributes
only through its share, valued at its mean in the year in which it exists.

Reads:  data/aggregate/topic_assignments.csv
        data/aggregate/topic_profiles.csv     (which topics are least readable)
        data/per_paper/readability/{venue}.csv
Writes: data/aggregate/topic_decomposition.csv          one row per topic
        data/aggregate/topic_decomposition_summary.csv  one row per method

Run:
  python src/analysis/topic_decomposition.py
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

_D = os.environ.get("AA_DATA", "data")
PER_PAPER = os.path.join(_D, "per_paper")
OUT = os.path.join(_D, "aggregate")
VENUES = ["neurips", "iclr", "icml"]
K = 15            # primary resolution, matches topic_profiles.py
BASE_YEAR = 2015  # same window as the fixed-mix counterfactual
LAST_YEAR = 2025  # last year in which all three venues contribute papers
N_HARD = 4        # least readable topics


def topic_gaps(d: pd.DataFrame, col: str) -> pd.Series:
    """Each topic's mean Flesch gap to same-year papers, by least squares.

    Gaps are relative to the lowest-numbered topic, whose gap is zero.
    """
    X = pd.concat([pd.get_dummies(d[col], prefix="t", drop_first=True),
                   pd.get_dummies(d.year, prefix="y")], axis=1).astype(float)
    beta, *_ = np.linalg.lstsq(X.to_numpy(), d.flesch_ease.to_numpy(), rcond=None)
    gaps = pd.Series(beta, index=X.columns)
    first = sorted(d[col].unique())[0]
    return pd.Series({k: (0.0 if k == first else gaps[f"t_{k}"])
                      for k in sorted(d[col].unique())})


def decompose(top: pd.DataFrame, read: pd.DataFrame, hard: set, k: int = K,
              base_year: int = BASE_YEAR, last_year: int = LAST_YEAR,
              n_hard: int = N_HARD) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(per-topic table, per-method summary)."""
    col = f"topic_k{k}"
    d = top.merge(read, on="paper_id", how="left").dropna(subset=["flesch_ease"])
    a = d[d.year == base_year]
    b = d[d.year == last_year]
    if a.empty or b.empty:
        raise ValueError(f"no scored papers in {base_year if a.empty else last_year}")

    t = pd.DataFrame({
        "w0": a[col].value_counts(normalize=True),
        "w1": b[col].value_counts(normalize=True),
        "f0": a.groupby(col).flesch_ease.mean(),
        "f1": b.groupby(col).flesch_ease.mean(),
        "n0": a[col].value_counts(),
        "n1": b[col].value_counts(),
    }).fillna({"w0": 0.0, "w1": 0.0, "n0": 0, "n1": 0})
    t["f0"] = t.f0.fillna(t.f1)
    t["f1"] = t.f1.fillna(t.f0)
    t.index.name = col
    t["hard"] = t.index.isin(hard)
    t["within"] = (t.w0 + t.w1) / 2 * (t.f1 - t.f0)
    t["between"] = (t.f0 + t.f1) / 2 * (t.w1 - t.w0)

    total = b.flesch_ease.mean() - a.flesch_ease.mean()
    sym_w = t.within.sum()
    las_w = (t.w0 * (t.f1 - t.f0)).sum()
    paa_w = (t.w1 * (t.f1 - t.f0)).sum()
    assert abs(sym_w + t.between.sum() - total) < 1e-9
    win = d[(d.year >= base_year) & (d.year <= last_year)]
    t["gap"] = topic_gaps(win, col)
    adj_b = (t.gap * (t.w1 - t.w0)).sum()
    gc = t.gap - (t.gap * (t.w0 + t.w1) / 2).sum()
    hard_b = (gc * (t.w1 - t.w0))[t.hard].sum()

    summ = pd.DataFrame([
        {"method": "symmetric", "within": sym_w, "between": total - sym_w},
        {"method": "base_year_mix", "within": las_w, "between": total - las_w},
        {"method": "last_year_mix", "within": paa_w, "between": total - paa_w},
        {"method": "year_adjusted", "within": total - adj_b, "between": adj_b},
    ])
    summ["total"] = total
    summ["within_share"] = 100 * summ.within / total
    summ["between_share"] = 100 * summ.between / total
    summ["first_year"], summ["last_year"] = base_year, last_year
    summ["first_mean"], summ["last_mean"] = a.flesch_ease.mean(), b.flesch_ease.mean()
    summ["hard_between"] = hard_b
    summ["hard_share0"] = 100 * t[t.hard].w0.sum()
    summ["hard_share1"] = 100 * t[t.hard].w1.sum()
    # How many of the pooled least readable topics stay in the bottom n_hard
    # once each is compared with papers of the same year.
    summ["hard_in_adjusted_bottom"] = len(hard & set(t.gap.nsmallest(n_hard).index))
    summ["topics_declining"] = int((t.f1 < t.f0).sum())
    summ["topics"] = len(t)
    return t, summ


def main() -> None:
    col = f"topic_k{K}"
    if not os.path.exists(os.path.join(OUT, "topic_assignments.csv")):
        # No abstracts, so topic_clusters.py wrote no topics.
        print(f"  no topic_assignments.csv under {OUT}; skipping")
        return
    top = pd.read_csv(os.path.join(OUT, "topic_assignments.csv"))
    read = pd.concat([
        pd.read_csv(os.path.join(PER_PAPER, "readability", f"{v}.csv"),
                    usecols=["paper_id", "flesch_ease"])
        for v in VENUES])
    prof = pd.read_csv(os.path.join(OUT, "topic_profiles.csv"))
    hard = set(prof.nsmallest(N_HARD, "flesch")[col])

    t, summ = decompose(top, read, hard)
    r0 = summ.iloc[0]
    print(f"Flesch Reading Ease, three conferences, {BASE_YEAR} to {LAST_YEAR}")
    print(f"  mean {r0['first_mean']:.2f} -> {r0['last_mean']:.2f} ({r0['total']:+.2f})")
    # Bracket access: Series.between is a method and shadows the column.
    for _, r in summ.iterrows():
        print(f"  {r['method']:<14} within {r['within']:+6.2f} ({r['within_share']:5.1f}%)   "
              f"between {r['between']:+6.2f} ({r['between_share']:5.1f}%)")
    print(f"  year-adjusted between term from the {N_HARD} least readable topics: "
          f"{r0['hard_between']:+.2f}; their share "
          f"{r0['hard_share0']:.1f}% -> {r0['hard_share1']:.1f}%")
    print(f"  of those, still among the {N_HARD} least readable once compared with "
          f"same-year papers: {r0['hard_in_adjusted_bottom']}")
    print(f"  topics declining: {r0['topics_declining']} of {r0['topics']}")

    os.makedirs(OUT, exist_ok=True)
    t.reset_index().to_csv(os.path.join(OUT, "topic_decomposition.csv"), index=False)
    summ.to_csv(os.path.join(OUT, "topic_decomposition_summary.csv"), index=False)
    print(f"\nwrote topic_decomposition.csv and topic_decomposition_summary.csv to {OUT}")


if __name__ == "__main__":
    main()
