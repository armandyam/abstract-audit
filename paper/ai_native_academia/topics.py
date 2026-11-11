#!/usr/bin/env python3
"""The AI-Native Academia paper's NeurIPS topic profile and fixed-mix series.

The workshop paper fits its topics on NeurIPS alone
(src/analysis/topic_clusters.py --venues neurips, k = 15) and profiles them
the way the TMLR paper profiles its pooled topics
(src/analysis/topic_profiles.topic_profiles), with two differences ported
from the upstream script src/aggregate/topic_controls_neurips.py (commit
1922ca3):

  labels      each cluster carries an editorial name (TOPIC_LABELS). The
              clustering is unsupervised, so the names are the authors'
              reading of each cluster, not an output of the method. Each rule
              fires on a distinctive term among the cluster's ten leading
              terms, so the mapping survives a refit that renumbers clusters.
  fixed mix   every NeurIPS year from BASE_YEAR on with at least MIN_YEAR_N
              scored papers, with no upper limit (NeurIPS ends in 2025), and
              the smallest topic cell of each year recorded.

No citation enters here. The paper's profile table also prints the median
citations per topic; that column comes from src/citations/topic_citations.py
and is joined by make_macros.py only when the reader's own counts exist.

Reads:  $AA_DATA/aggregate/topic_assignments_neurips.csv
        $AA_DATA/aggregate/topic_terms_neurips.csv
        $AA_DATA/per_paper/readability/neurips.csv
Writes: $AA_DATA/aggregate/topic_profiles_neurips.csv   citation-free
        $AA_DATA/aggregate/fixed_mix_neurips.csv

    python paper/ai_native_academia/topics.py
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))
from analysis.topic_profiles import read_readability, topic_profiles  # noqa: E402

VENUE = "neurips"
K = 15            # primary resolution
BASE_YEAR = 2015  # topic mix held fixed at this year in the counterfactual
ALT_BASE_YEAR = 2010  # the sensitivity check's earlier base year
MIN_YEAR_N = 200  # skip years too thin for a stable mix
N_HARD = 4        # size of the "least readable topics" bucket

ASSIGNMENTS = f"topic_assignments_{VENUE}.csv"
TERMS = f"topic_terms_{VENUE}.csv"
STABILITY = f"topic_stability_{VENUE}.csv"
PROFILES = f"topic_profiles_{VENUE}.csv"
FIXED_MIX = f"fixed_mix_{VENUE}.csv"

# Editorial names for the clusters, as upstream: the first rule whose term is
# among a cluster's leading terms names it.
TOPIC_LABELS = [
    ("diffusion",              "Diffusion and generative models"),
    ("llms",                   "Large language models"),
    ("reinforcement",          "Reinforcement learning"),
    ("adversarial",            "Adversarial robustness"),
    ("3d",                     "3D vision and reconstruction"),
    ("graph",                  "Graph neural networks"),
    ("regret",                 "Online learning and bandits"),
    ("bayesian",               "Bayesian inference"),
    ("convergence",            "Optimization theory"),
    ("neurons",                "Computational neuroscience"),
    ("detection",              "Object detection"),
    ("text",                   "Vision and language"),
    ("neural networks",        "Neural network architectures"),
    ("linear",                 "Learning theory and algorithms"),
    ("datasets",               "Applied methods and benchmarks"),
]


def topic_label(top_terms: str) -> str:
    terms = [t.strip() for t in str(top_terms).split(",")]
    for key, label in TOPIC_LABELS:
        if key in terms:
            return label
    raise ValueError(f"no TOPIC_LABELS rule matched a cluster with terms: {top_terms}")


def profile(top: pd.DataFrame, terms: pd.DataFrame, read: pd.DataFrame,
            k: int = K) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(labelled profile, least to most readable; the joined per-paper frame)."""
    prof, d = topic_profiles(top, terms, read, k=k)
    prof = prof.reset_index(drop=True)
    prof["label"] = prof.top_terms.map(topic_label)
    dupes = prof.label[prof.label.duplicated()].tolist()
    if dupes:
        raise ValueError(f"topic labels collide, refine TOPIC_LABELS: {dupes}")
    return prof, d


def fixed_mix(d: pd.DataFrame, k: int = K, base_year: int = BASE_YEAR,
              min_year_n: int = MIN_YEAR_N) -> pd.DataFrame:
    """Raw and base-year-mix mean Flesch for each year from base_year on."""
    col = f"topic_k{k}"
    dd = d.dropna(subset=["flesch_ease"])
    basemix = dd[dd.year == base_year][col].value_counts(normalize=True)
    rows = []
    for yr in sorted(dd.year.unique()):
        if yr < base_year:
            continue
        s = dd[dd.year == yr]
        if len(s) < min_year_n:
            continue
        per = s.groupby(col).flesch_ease.mean()
        w = basemix.reindex(per.index).fillna(0)
        if w.sum() == 0:
            continue
        w = w / w.sum()
        rows.append({"year": int(yr), "n": len(s),
                     "min_topic_cell": int(s.groupby(col).size().min()),
                     "raw": float(s.flesch_ease.mean()),
                     "fixed_mix": float((per * w).sum())})
    return pd.DataFrame(rows, columns=["year", "n", "min_topic_cell", "raw", "fixed_mix"])


def composition_share(d: pd.DataFrame, base_year: int, last_year: int,
                      k: int = K) -> float:
    """Percent of the raw Flesch change from base_year to last_year that the
    change in topic mix accounts for, with the mix held at base_year. The
    sensitivity check of the paper's appendix (base year ALT_BASE_YEAR)."""
    col = f"topic_k{k}"
    dd = d.dropna(subset=["flesch_ease"])
    mix = dd[dd.year == base_year][col].value_counts(normalize=True)

    def at(yr: int) -> tuple[float, float]:
        s = dd[dd.year == yr]
        per = s.groupby(col).flesch_ease.mean()
        w = mix.reindex(per.index).fillna(0)
        w = w / w.sum()
        return float(s.flesch_ease.mean()), float((per * w).sum())

    ra, fa = at(base_year)
    rb, fb = at(last_year)
    return 100 * ((rb - ra) - (fb - fa)) / (rb - ra)


def hard_topics(prof: pd.DataFrame, k: int = K, n: int = N_HARD) -> set[int]:
    """The n least readable topics."""
    return set(prof[f"topic_k{k}"].iloc[:n])


def hard_share(d: pd.DataFrame, hard: set[int], year: int, k: int = K) -> float:
    """Percent of the year's scored papers that fall in the hard topics."""
    dd = d.dropna(subset=["flesch_ease"])
    s = dd[dd.year == year]
    return 100 * s[f"topic_k{k}"].isin(hard).mean()


def load(data: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    agg = os.path.join(data, "aggregate")
    top = pd.read_csv(os.path.join(agg, ASSIGNMENTS))
    terms = pd.read_csv(os.path.join(agg, TERMS))
    read = read_readability(os.path.join(data, "per_paper"), [VENUE])
    return profile(top.drop(columns=["venue"], errors="ignore"), terms, read)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=os.environ.get("AA_DATA", "data"))
    a = ap.parse_args()
    agg = os.path.join(a.data_dir, "aggregate")
    if not os.path.exists(os.path.join(agg, ASSIGNMENTS)):
        print(f"  no {ASSIGNMENTS} under {agg}; skipping "
              "(run src/analysis/topic_clusters.py --venues neurips)")
        return
    prof, d = load(a.data_dir)
    fm = fixed_mix(d)
    prof.to_csv(os.path.join(agg, PROFILES), index=False)
    fm.to_csv(os.path.join(agg, FIXED_MIX), index=False)
    for _, r in prof.iterrows():
        print(f"  {r.label:<34}{int(r.n):>7}{r.flesch:>8.1f}")
    print(f"wrote {PROFILES} and {FIXED_MIX} to {agg}")


if __name__ == "__main__":
    main()
