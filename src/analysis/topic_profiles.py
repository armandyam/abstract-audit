#!/usr/bin/env python3
"""What the topics are, and whether the field moved into less readable ones.

Two outputs, both at the primary resolution k = 15 (topic_clusters.py):

1. A profile of each topic over every year: size, mean Flesch Reading Ease,
   mean abstract length in words and mean words per sentence (the readability
   file's `avg_sentence_length`), sorted from least to most readable.

2. A fixed-mix counterfactual. From BASE_YEAR to LAST_YEAR each year is
   reweighted to the BASE_YEAR topic mix and its mean Flesch recomputed. The
   gap between the raw and the reweighted decline is the topic-composition
   component under this weighting; the reweighted decline is the aggregate
   within-topic change at the BASE_YEAR topic mix. The window starts at the base year: reweighting thin early
   years (2002 has 207 papers over 14 topics) is unstable enough to reverse
   the sign of the composition share. It stops at 2025, because ICLR 2026 is
   the only venue in 2026 and would let a venue-mix change enter a series
   meant to hold topic mix fixed. Years with fewer than MIN_YEAR_N scored
   papers are skipped.

The TMLR paper's profile table also carries median citations per topic. This
release computes the citation-free columns. `topic_profiles` takes an
optional per-paper citations frame (`paper_id`, `n_citations`); when given,
the profile gains `median_citations` and `n_with_citations` in the paper's
column order and the across-topic correlation with Flesch is printed.

Reads:  data/aggregate/topic_assignments.csv, data/aggregate/topic_terms.csv
        data/per_paper/readability/{venue}.csv
Writes: data/aggregate/topic_profiles.csv
        data/aggregate/fixed_mix_readability.csv

Run:
  python src/analysis/topic_profiles.py
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

_D = os.environ.get("AA_DATA", "data")
PER_PAPER = os.path.join(_D, "per_paper")
OUT = os.path.join(_D, "aggregate")
VENUES = ["neurips", "iclr", "icml"]
K = 15            # primary resolution
BASE_YEAR = 2015  # topic mix held fixed at this year in the counterfactual
LAST_YEAR = 2025  # last year in which all three venues contribute papers
MIN_YEAR_N = 200  # skip years too thin for a stable mix


def read_readability(per_paper: str = PER_PAPER, venues: list[str] = VENUES) -> pd.DataFrame:
    return pd.concat([
        pd.read_csv(os.path.join(per_paper, "readability", f"{v}.csv"),
                    usecols=["paper_id", "flesch_ease", "word_count",
                             "avg_sentence_length"])
        for v in venues])


def topic_profiles(top: pd.DataFrame, terms: pd.DataFrame, read: pd.DataFrame,
                   citations: pd.DataFrame | None = None, k: int = K
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(per-topic profile sorted by Flesch, the joined per-paper frame).

    Every paper with a topic counts in `n`; papers without a readability row
    (an abstract below the scoring minimum) count in `n` but not in the means.
    """
    col = f"topic_k{k}"
    label = {r.cluster: r.top_terms for _, r in terms[terms.k == k].iterrows()}
    d = top.merge(read, on="paper_id", how="left")
    if citations is not None:
        d = d.merge(citations[["paper_id", "n_citations"]], on="paper_id", how="left")

    g = d.groupby(col)
    cols = {
        "n": g.size(),
        "flesch": g.flesch_ease.mean(),
        "abstract_words": g.word_count.mean(),
        "sentence_length": g.avg_sentence_length.mean(),
    }
    if citations is not None:
        cols["median_citations"] = g.n_citations.median()
        cols["n_with_citations"] = g.n_citations.count()
    prof = pd.DataFrame(cols).reset_index()
    prof["top_terms"] = prof[col].map(label)
    return prof.sort_values("flesch"), d


def fixed_mix(d: pd.DataFrame, k: int = K, base_year: int = BASE_YEAR,
              last_year: int = LAST_YEAR, min_year_n: int = MIN_YEAR_N) -> pd.DataFrame:
    """Raw and base-year-mix mean Flesch per year, base_year to last_year.

    A topic absent in the base year gets weight zero; a year in which no
    present topic has base-year weight is skipped.
    """
    col = f"topic_k{k}"
    dd = d.dropna(subset=["flesch_ease"])
    base = dd[dd.year == base_year][col].value_counts(normalize=True)
    rows = []
    for yr in sorted(dd.year.unique()):
        if yr < base_year or yr > last_year:
            continue
        s = dd[dd.year == yr]
        if len(s) < min_year_n:
            continue
        per = s.groupby(col).flesch_ease.mean()
        w = base.reindex(per.index).fillna(0)
        if w.sum() == 0:
            continue
        w = w / w.sum()
        rows.append({"year": int(yr), "n": len(s),
                     "raw": float(s.flesch_ease.mean()),
                     "fixed_mix": float((per * w).sum())})
    return pd.DataFrame(rows, columns=["year", "n", "raw", "fixed_mix"])


def report(prof: pd.DataFrame, d: pd.DataFrame, fm: pd.DataFrame, k: int = K) -> None:
    col = f"topic_k{k}"
    cit = "median_citations" in prof.columns
    print(f"{'topic':<44}{'n':>7}{'Flesch':>8}{'words':>7}{'sent':>6}"
          + (f"{'med cit':>9}" if cit else ""))
    for _, r in prof.iterrows():
        short = ", ".join(str(r.top_terms).split(", ")[:4])[:38]
        print(f"  c{int(r[col]):<2d} {short:<39}{int(r.n):>7}{r.flesch:>8.1f}"
              f"{r.abstract_words:>7.0f}{r.sentence_length:>6.1f}"
              + (f"{r.median_citations:>9.0f}" if cit else ""))
    spread = prof.flesch.max() - prof.flesch.min()
    print(f"\n  corpus mean Flesch {d.flesch_ease.mean():.1f}, "
          f"between-topic spread {spread:.1f} points")
    if cit:
        pear = np.corrcoef(prof.flesch, prof.median_citations)[0, 1]
        spear = prof.flesch.corr(prof.median_citations, method="spearman")
        print(f"\n  across topics: corr(Flesch, median citations) = "
              f"{pear:.3f} Pearson, {spear:.3f} Spearman")
    if fm.empty:
        print("\n  fixed-mix counterfactual: no year qualifies")
        return
    a, b = fm.iloc[0], fm.iloc[-1]
    d_raw = b.raw - a.raw
    d_fix = b.fixed_mix - a.fixed_mix
    print(f"\n  fixed-mix counterfactual, {int(a.year)} to {int(b.year)}, "
          f"mix held at {BASE_YEAR}")
    print(f"    raw       {a.raw:6.2f} -> {b.raw:6.2f}  ({d_raw:+.2f})")
    print(f"    fixed mix {a.fixed_mix:6.2f} -> {b.fixed_mix:6.2f}  ({d_fix:+.2f})")
    if d_raw:
        print(f"    composition accounts for {100 * (d_raw - d_fix) / d_raw:.1f}% "
              f"of the decline; {100 * d_fix / d_raw:.1f}% is within-topic")


def main() -> None:
    if not os.path.exists(os.path.join(OUT, "topic_assignments.csv")):
        # No abstracts, so topic_clusters.py wrote no topics.
        print(f"  no topic_assignments.csv under {OUT}; skipping")
        return
    top = pd.read_csv(os.path.join(OUT, "topic_assignments.csv"))
    terms = pd.read_csv(os.path.join(OUT, "topic_terms.csv"))
    prof, d = topic_profiles(top, terms, read_readability())
    fm = fixed_mix(d)
    report(prof, d, fm)

    os.makedirs(OUT, exist_ok=True)
    prof.to_csv(os.path.join(OUT, "topic_profiles.csv"), index=False)
    fm.to_csv(os.path.join(OUT, "fixed_mix_readability.csv"), index=False)
    print(f"\nwrote topic_profiles.csv and fixed_mix_readability.csv to {OUT}")


if __name__ == "__main__":
    main()
