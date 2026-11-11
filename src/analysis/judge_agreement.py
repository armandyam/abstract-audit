#!/usr/bin/env python3
"""Inter-judge agreement and run-to-run stability of the six LLM judges.

Each judge scored every abstract three times per prompt, sampling at
temperature 0.7. This script measures how stable a judge is under that
resampling and how far the six judges agree with each other:

  run stability   per model and prompt, over the parsed scores of each paper:
                  the mean standard deviation (papers with at least two
                  scores), the mean range, and the percentage of papers whose
                  scores are all identical (a paper with one parsed score
                  counts as identical)
  raw levels      per model and prompt, the paper-level score (median of the
                  available parsed scores) averaged over all papers and over the first and
                  last year, on the raw 1 to 5 scale
  scored papers   per model and prompt, how many papers carry a paper-level
                  score in the first and in the last year
  agreement       per prompt, the Spearman correlation between every pair of
                  judges over the papers all six scored, and Cronbach's alpha
                  with the six judges as items

The AI-Native Academia workshop paper reports these for NeurIPS in its
tables tab:raw-stability and tab:agreement. Ported from the upstream
uncertainlp/analysis/judge_agreement.py (commit 1922ca3), which also wrote a
scale-resolution and a baseline-sensitivity table that no paper here prints.

Reads:  shared/judge_scores/{venue}/{model}.csv   ($AA_JUDGE overrides the root)
Writes: data/aggregate/judge_run_stability_{venue}.csv
        data/aggregate/judge_raw_levels_{venue}.csv
        data/aggregate/judge_scored_papers_{venue}.csv
        data/aggregate/judge_pairwise_agreement_{venue}.csv
        data/aggregate/judge_cronbach_alpha_{venue}.csv

    python src/analysis/judge_agreement.py
    python src/analysis/judge_agreement.py --venue neurips --first-year 1987 --last-year 2024
"""
from __future__ import annotations

import argparse
import itertools
import os

import pandas as pd
from scipy.stats import spearmanr

_D = os.environ.get("AA_DATA", "data")
OUT = os.path.join(_D, "aggregate")
JUDGE_DIR = os.environ.get("AA_JUDGE", "shared/judge_scores")

MODELS = [
    "Gemma-3-27B-Instruct",
    "Gemma-4-31B-Instruct",
    "Llama-3.1-8B-Instruct",
    "Mistral-7B-Instruct",
    "Mixtral-8x7B-Instruct",
    "Qwen2.5-32B-Instruct",
]
PROMPTS = ["simple", "ascb", "own_reasoning"]
FIRST_YEAR, LAST_YEAR = 1987, 2024      # the NeurIPS years every judge scored


def load(venue_dir: str, models: list[str] = MODELS) -> pd.DataFrame:
    """Every parsed generation of the given models, long format."""
    frames = []
    for m in models:
        df = pd.read_csv(os.path.join(venue_dir, f"{m}.csv"),
                         usecols=["paper_id", "year", "prompt_name", "run", "score"])
        df = df[df["score"].notna()]
        df["model"] = m
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    return df[df["score"].notna()]


def run_stability(df: pd.DataFrame) -> pd.DataFrame:
    """Spread across the sampled generations of each (paper, model, prompt)."""
    g = df.groupby(["model", "prompt_name", "paper_id"])["score"]
    return (pd.DataFrame({"run_sd": g.std(ddof=1), "run_range": g.max() - g.min()})
            .reset_index()
            .groupby(["model", "prompt_name"])
            .agg(mean_run_sd=("run_sd", "mean"),
                 mean_run_range=("run_range", "mean"),
                 pct_all_three_identical=("run_range",
                                          lambda s: 100.0 * (s == 0).mean()))
            .reset_index())


def per_paper_median(df: pd.DataFrame) -> pd.DataFrame:
    """The paper-level score: the median over the runs."""
    return (df.groupby(["prompt_name", "model", "paper_id", "year"])["score"]
              .median().reset_index())


def agreement(med: pd.DataFrame, models: list[str] = MODELS,
              prompts: list[str] = PROMPTS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pairwise per-paper Spearman between judges, and Cronbach's alpha, over
    the papers every judge scored."""
    pair_rows, alpha_rows = [], []
    for prompt in prompts:
        wide = (med[med["prompt_name"] == prompt]
                .pivot(index="paper_id", columns="model", values="score").dropna())
        for a, b in itertools.combinations(models, 2):
            pair_rows.append({"prompt": prompt, "model_a": a, "model_b": b,
                              "spearman": spearmanr(wide[a], wide[b]).statistic,
                              "n_papers": len(wide)})
        k = wide.shape[1]
        item_var = wide.var(axis=0, ddof=1).sum()
        total_var = wide.sum(axis=1).var(ddof=1)
        alpha_rows.append({"prompt": prompt,
                           "cronbach_alpha": (k / (k - 1)) * (1 - item_var / total_var),
                           "k_models": k, "n_papers": len(wide)})
    return pd.DataFrame(pair_rows), pd.DataFrame(alpha_rows)


def raw_levels(med: pd.DataFrame, first: int = FIRST_YEAR,
               last: int = LAST_YEAR) -> pd.DataFrame:
    """Raw 1 to 5 means per model and prompt, overall and at both ends."""
    overall = (med.groupby(["prompt_name", "model"])["score"]
                  .agg(raw_mean="mean", raw_sd="std").reset_index())
    ends = []
    for (prompt, model), g in med.groupby(["prompt_name", "model"]):
        y = g.groupby("year")["score"].mean()
        if first in y.index and last in y.index:
            ends.append({"prompt_name": prompt, "model": model,
                         f"raw_{first}": y.loc[first], f"raw_{last}": y.loc[last],
                         "raw_delta": y.loc[last] - y.loc[first]})
    return overall.merge(pd.DataFrame(ends), on=["prompt_name", "model"])


def scored_papers(med: pd.DataFrame, first: int = FIRST_YEAR,
                  last: int = LAST_YEAR) -> pd.DataFrame:
    """Papers with a paper-level score, per model and prompt, at both ends."""
    n = (med[med.year.isin([first, last])]
         .groupby(["prompt_name", "model", "year"]).size()
         .unstack("year").reindex(columns=[first, last]).fillna(0).astype(int))
    n.columns = [f"n_{first}", f"n_{last}"]
    return n.reset_index()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venue", default="neurips")
    ap.add_argument("--judge-dir", default=JUDGE_DIR)
    ap.add_argument("--out-dir", default=OUT)
    ap.add_argument("--first-year", type=int, default=FIRST_YEAR)
    ap.add_argument("--last-year", type=int, default=LAST_YEAR)
    a = ap.parse_args()

    df = load(os.path.join(a.judge_dir, a.venue))
    print(f"{a.venue}: {len(df):,} parsed generations")
    med = per_paper_median(df)
    pairs, alpha = agreement(med)
    outputs = {
        "judge_run_stability": run_stability(df),
        "judge_raw_levels": raw_levels(med, a.first_year, a.last_year),
        "judge_scored_papers": scored_papers(med, a.first_year, a.last_year),
        "judge_pairwise_agreement": pairs,
        "judge_cronbach_alpha": alpha,
    }
    os.makedirs(a.out_dir, exist_ok=True)
    for name, frame in outputs.items():
        path = os.path.join(a.out_dir, f"{name}_{a.venue}.csv")
        frame.to_csv(path, index=False)
        print(f"wrote {path}")
    print(pairs.groupby("prompt")["spearman"].agg(["mean", "min", "max"])
          .to_string(float_format=lambda x: f"{x:.3f}"))
    print(alpha.to_string(index=False))


if __name__ == "__main__":
    main()
