#!/usr/bin/env python3
"""LLM judge scores of the top and bottom citation deciles, by venue.

For each venue, each judge's three runs are averaged per paper and prompt,
joined to the within-venue-year citation percentile (enrich.py) and limited
to years no later than --max-year. The top decile is citation_percentile
>= 90 and the bottom <= 10. Each of the six judges contributes its mean
score in each group; a cell is the mean of the six judge means, with the
half-width of a 95 percent normal-approximation interval over those six
(1.96 std / sqrt(6)).

These are every number in the TMLR paper's Table tab:citation-llm.
Upstream wrote that table directly to LaTeX; this script writes the numbers.

Reads:
  judge_scores/{venue}/{model}.csv            ($AA_JUDGE overrides)
  $AA_DATA/per_paper/citations/{venue}_s2.csv
Writes:
  $AA_DATA/aggregate/citations/citation_llm_top_bottom_combined.csv
    prompt, venue, top_mean, top_ci, bottom_mean, bottom_ci, delta, n_models

    python src/citations/judge_deciles.py --venues neurips iclr icml --max-year 2024
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from citations._common import CIT_DIR, JUDGE_DIR, OUT_DIR, VENUES, read_citations, require  # noqa: E402

MODELS = [
    "Gemma-3-27B-Instruct", "Gemma-4-31B-Instruct", "Llama-3.1-8B-Instruct",
    "Mistral-7B-Instruct", "Mixtral-8x7B-Instruct", "Qwen2.5-32B-Instruct",
]
PROMPTS = ["simple", "ascb", "own_reasoning"]
Z95 = 1.96
COLUMNS = ["prompt", "venue", "top_mean", "top_ci", "bottom_mean", "bottom_ci",
           "delta", "n_models"]


def load_scores(venue_dir: str, models: list[str] = MODELS) -> pd.DataFrame:
    """Mean over runs per paper, year, model and prompt."""
    frames = []
    for model in models:
        df = pd.read_csv(require(os.path.join(venue_dir, f"{model}.csv")),
                         usecols=["paper_id", "year", "prompt_name", "run", "score"],
                         low_memory=False)
        df["model"] = model
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    return (df.groupby(["paper_id", "year", "model", "prompt_name"], as_index=False)
              ["score"].mean())


def venue_cells(scores: pd.DataFrame, cit: pd.DataFrame, max_year: int | None,
                models: list[str] = MODELS) -> dict[str, tuple]:
    """prompt -> (top, top_ci, bottom, bottom_ci, delta, n_models) for one venue."""
    df = scores.merge(cit[["paper_id", "year", "citation_percentile"]],
                      on=["paper_id", "year"], how="inner").dropna(
        subset=["citation_percentile", "score"])
    if max_year is not None:
        df = df[df["year"] <= max_year]
    top = df[df["citation_percentile"] >= 90]
    bot = df[df["citation_percentile"] <= 10]
    cells = {}
    for prompt in PROMPTS:
        tm = np.array([top.loc[(top.prompt_name == prompt) & (top.model == m), "score"].mean()
                       for m in models], float)
        bm = np.array([bot.loc[(bot.prompt_name == prompt) & (bot.model == m), "score"].mean()
                       for m in models], float)
        t, b = tm.mean(), bm.mean()
        cells[prompt] = (t, Z95 * tm.std(ddof=1) / np.sqrt(len(tm)),
                         b, Z95 * bm.std(ddof=1) / np.sqrt(len(bm)), t - b, len(tm))
    return cells


def build(venues: list[str], max_year: int | None, judge_dir: str | None = None,
          cit_dir: str | None = None, models: list[str] = MODELS) -> pd.DataFrame:
    cells = {}
    for v in venues:
        scores = load_scores(os.path.join(judge_dir or JUDGE_DIR, v), models)
        cit = read_citations(os.path.join(cit_dir or CIT_DIR, f"{v}_s2.csv"))
        for prompt, c in venue_cells(scores, cit, max_year, models).items():
            cells[(prompt, v)] = c
    rows = [{"prompt": p, "venue": v, **dict(zip(COLUMNS[2:], cells[(p, v)]))}
            for p in PROMPTS for v in venues]
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venues", nargs="+", default=VENUES)
    ap.add_argument("--max-year", type=int, default=2024)
    ap.add_argument("--out-dir", default=OUT_DIR)
    a = ap.parse_args()
    out = build(a.venues, a.max_year)
    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, "citation_llm_top_bottom_combined.csv")
    out.to_csv(path, index=False)
    print(out.to_string(index=False))
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
