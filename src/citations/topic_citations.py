#!/usr/bin/env python3
"""The citation columns of the topic profiles, and the across-topic correlation.

The topic stage profiles each topic without citations (size, mean Flesch
Reading Ease, abstract length, sentence length, leading terms). This script
adds, per topic at --k (15 in the paper):

  median_citations  median citation count of the topic's papers in the
                    regression sample (regression.py: matched, through 2024,
                    with a readability score and at least one author)
  n_with_citations  how many of the topic's papers that is

and the correlation across topics between mean Flesch and median citations,
Pearson (the paper's TopicCitCorr, -0.59) and Spearman. The correlation is
negative: the least readable topics are the most cited, the opposite sign to
the within-topic regression coefficient.

With --profiles, the citation-free profile CSV of the topic stage is read and
written back out with the two columns inserted before top_terms, which is the
layout of the paper's topic_profiles.csv. Without it, the topic size and mean
Flesch are computed here from the assignments and readability, the same way.

Reads:
  --assignments  topic_assignments.csv (paper_id, venue, year, topic_k{k}, ...)
  --profiles     optional, the citation-free topic profile CSV
  $AA_DATA/per_paper/readability/{venue}.csv and the inputs of regression.py
Writes:
  $AA_DATA/aggregate/citations/topic_citations.csv
  $AA_DATA/aggregate/citations/topic_citation_corr.csv   pearson, spearman, n_topics

    python src/citations/topic_citations.py --assignments topic_assignments.csv
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from citations._common import OUT_DIR, READ_DIR, VENUES, require  # noqa: E402
from citations.regression import load  # noqa: E402

K = 15


def citation_columns(assign: pd.DataFrame, cit: pd.DataFrame, k: int = K) -> pd.DataFrame:
    """Per topic: median_citations and n_with_citations. A topic none of whose
    papers is in the citation sample gets NaN and 0."""
    col = f"topic_k{k}"
    d = assign[["paper_id", col]].merge(cit[["paper_id", "n_citations"]],
                                        on="paper_id", how="left")
    g = d.groupby(col)
    return pd.DataFrame({
        "median_citations": g.n_citations.median(),
        "n_with_citations": g.n_citations.count(),
    }).reset_index()


def base_profile(assign: pd.DataFrame, read: pd.DataFrame, k: int = K) -> pd.DataFrame:
    """Topic size and mean Flesch, as the topic stage computes them."""
    col = f"topic_k{k}"
    d = assign.merge(read[["paper_id", "flesch_ease"]], on="paper_id", how="left")
    g = d.groupby(col)
    return pd.DataFrame({"n": g.size(), "flesch": g.flesch_ease.mean()}).reset_index()


def add_to_profile(profile: pd.DataFrame, cols: pd.DataFrame, k: int = K) -> pd.DataFrame:
    """Merge the citation columns into a profile, before top_terms if present.
    Row order of the profile is kept."""
    col = f"topic_k{k}"
    keep = [c for c in profile.columns if c not in ("median_citations", "n_with_citations")]
    out = profile[keep].merge(cols, on=col, how="left", sort=False)
    out.index = profile.index
    order = [c for c in keep if c != "top_terms"] + ["median_citations", "n_with_citations"]
    if "top_terms" in keep:
        order.append("top_terms")
    return out[order]


def topic_citation_corr(profile: pd.DataFrame) -> dict:
    """Across topics, mean Flesch against median citations."""
    p = profile.dropna(subset=["flesch", "median_citations"])
    if len(p) < 3:
        return {"pearson": float("nan"), "spearman": float("nan"), "n_topics": len(p)}
    return {"pearson": float(np.corrcoef(p.flesch, p.median_citations)[0, 1]),
            "spearman": float(p.flesch.corr(p.median_citations, method="spearman")),
            "n_topics": len(p)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assignments", required=True)
    ap.add_argument("--profiles", default=None,
                    help="citation-free topic profile CSV from the topic stage")
    ap.add_argument("--k", type=int, default=K)
    ap.add_argument("--venues", nargs="+", default=VENUES)
    ap.add_argument("--out-dir", default=OUT_DIR)
    a = ap.parse_args()

    assign = pd.read_csv(require(a.assignments))
    cit = pd.concat([load(v) for v in a.venues])[["paper_id", "n_citations"]]
    cols = citation_columns(assign, cit, a.k)
    if a.profiles:
        # round_trip: the default parser can move the last digit of a float
        prof = add_to_profile(pd.read_csv(require(a.profiles), float_precision="round_trip"),
                              cols, a.k)
    else:
        read = pd.concat([pd.read_csv(require(os.path.join(READ_DIR, f"{v}.csv")),
                                      usecols=["paper_id", "flesch_ease"])
                          for v in a.venues])
        prof = add_to_profile(base_profile(assign, read, a.k), cols, a.k).sort_values("flesch")
    corr = topic_citation_corr(prof)

    os.makedirs(a.out_dir, exist_ok=True)
    p1 = os.path.join(a.out_dir, "topic_citations.csv")
    p2 = os.path.join(a.out_dir, "topic_citation_corr.csv")
    prof.to_csv(p1, index=False)
    pd.DataFrame([corr]).to_csv(p2, index=False)
    print(f"  across {corr['n_topics']} topics: Pearson {corr['pearson']:.3f}, "
          f"Spearman {corr['spearman']:.3f}")
    print(f"wrote {p1}\nwrote {p2}")


if __name__ == "__main__":
    main()
