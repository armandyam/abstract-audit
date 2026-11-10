#!/usr/bin/env python3
"""Export plot-ready CSV files for the pgfplots figures.

Two output sets, one per paper:

  data/pgfplots/       the UncertaiNLP paper's figures: NeurIPS series only,
                       `year,neurips` for each readability metric and the
                       NeurIPS judge series. Unchanged from the tag
                       uncertainlp-2026, so verify.py checks it as before.
  data/pgfplots/tmlr/  the TMLR paper's conference series under the paper's
                       own file names: `year,neurips,iclr,icml` for each
                       metric, papers per year, and the judge series for all
                       three venues. The paper's arXiv and PubMed series are
                       not part of this release.

Each metric becomes a CSV of `year` plus one column per venue, restricted to
the years at least one of those venues covers.

Run:
  python src/plotting/export_pgfplots_data.py
"""

from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from aggregate._utils import VENUES

_D = os.environ.get("AA_DATA", "data")
AGG  = os.path.join(_D, "aggregate")
OUT  = os.path.join(_D, "pgfplots")
TMLR = os.path.join(OUT, "tmlr")

COMPLETE_MODELS = [
    "Gemma-3-27B-Instruct",
    "Gemma-4-31B-Instruct",
    "Llama-3.1-8B-Instruct",
    "Mistral-7B-Instruct",
    "Mixtral-8x7B-Instruct",
    "Qwen2.5-32B-Instruct",
]




def save(df: pd.DataFrame, name: str, out: str | None = None) -> None:
    out = out or OUT
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, name)
    df.to_csv(path, index=False, na_rep="nan")
    print(f"  {path}  ({len(df)} rows x {len(df.columns)} cols)")




def export_metric(metric_name: str, col: str, out_name: str | None = None,
                  venues: list[str] | None = None, out: str | None = None) -> None:
    """Write year plus one column per venue present in the aggregate."""
    main_csv = f"{AGG}/{metric_name}.csv"
    if not os.path.exists(main_csv):
        print(f"  SKIP {main_csv} (not found)")
        return

    df = pd.read_csv(main_csv)
    result = df[["year"]].copy()
    for venue in venues or VENUES:
        mean_col = f"{venue}_{col}_mean"
        if mean_col in df.columns:
            result[venue] = df[mean_col]

    series = [c for c in result.columns if c != "year"]
    if not series:
        print(f"  SKIP {metric_name}/{col} (no venue columns)")
        return
    result = result.dropna(how="all", subset=series).reset_index(drop=True)

    stem = out_name or f"{metric_name}_{col}"
    save(result, f"{stem}.csv", out)




READABILITY = [
    "flesch_ease", "flesch_kincaid", "gunning_fog", "smog",
    "dale_chall", "spache", "coleman_liau", "ari",
    "linsear_write", "lix", "rix", "forcast",
    "powers_sumner_kearl", "avg_sentence_length", "avg_syllables_per_word",
]

SENSATIONAL = [
    ("hype_importance_per_100", "importance"),
    ("hype_novelty_per_100",    "novelty"),
    ("hype_rigor_per_100",      "rigor"),
    ("hype_scale_per_100",      "scale"),
    ("hype_utility_per_100",    "utility"),
    ("hype_quality_per_100",    "quality"),
    ("hype_attitude_per_100",   "attitude"),
    ("hype_problem_per_100",    "problem"),
    ("hype_additional_per_100", "additional"),
    ("hype_total_per_100",      "total"),
]

# (aggregate file, column, TMLR file name).
STYLE = [
    ("sentence_length",      "words_per_sentence",   "sentence_length"),
    ("parse_depth",          "parse_depth",          "parse_depth"),
    ("clauses_per_sentence", "clauses_per_sent",     "clauses_per_sent"),
    ("np_density",           "np_density",           "np_density"),
    ("noun_chunks",          "noun_chunks_per_100",  "noun_chunks"),
    ("nouns",                "noun_per_100",         "nouns"),
    ("verbs",                "verb_per_100",         "verbs"),
    ("numbers",              "num_per_100",          "numbers"),
    ("signposting",          "signposting_per_100",  "signposting"),
    ("hedging",              "hedging_per_100",      "hedging"),
    ("active_narration",     "has_narrator",         "active_narration"),
    ("passive_rate",         "passive_rate",         "passive_rate"),
    ("ttr",                  "ttr",                  "ttr"),
]


def export_readability() -> None:
    """UncertaiNLP set: NeurIPS only."""
    for m in READABILITY:
        export_metric("readability", m, f"readability_{m}", venues=["neurips"])


def export_llm_scores(venues=("neurips",), out: str | None = None) -> None:
    # neurips keeps the un-suffixed filenames (back-compat with the current
    # figure); iclr/icml emit venue-suffixed files when their aggregates exist.
    for venue in venues:
        suffix = "" if venue == "neurips" else f"_{venue}"
        for prompt in ("simple", "ascb", "own_reasoning"):
            csv = f"{AGG}/llm_scores_{venue}_{prompt}.csv"
            if not os.path.exists(csv):
                continue
            df = pd.read_csv(csv)
            cols = ["year"]
            for m in COMPLETE_MODELS:
                col = f"{m}_mean"
                if col in df.columns:
                    cols.append(col)
            save(df[cols], f"llm_scores{suffix}_{prompt}.csv", out)









def export_standardized_llm(venues=("neurips",), out: str | None = None) -> None:
    """Standardize per-model LLM scores to z-scores (pre-2022 baseline) for all 3 prompts.

    neurips keeps the un-suffixed filenames; iclr/icml emit venue-suffixed
    files when their per-venue score exports exist.
    """
    out = out or OUT
    for venue in venues:
        suffix = "" if venue == "neurips" else f"_{venue}"
        for prompt in ("simple", "ascb", "own_reasoning"):
            src = f"{out}/llm_scores{suffix}_{prompt}.csv"
            if not os.path.exists(src):
                if venue == "neurips":
                    print(f"  SKIP {src} (not found)")
                continue
            df = pd.read_csv(src)
            model_cols = [f"{m}_mean" for m in COMPLETE_MODELS if f"{m}_mean" in df.columns]
            result = df[["year"]].copy()
            for col in model_cols:
                b = df.loc[df["year"] <= 2022, col].dropna()
                if len(b) < 3:
                    continue
                result[col.replace("_mean", "_z")] = (df[col] - b.mean()) / b.std(ddof=1)
            save(result, f"llm_scores_standardized{suffix}_{prompt}.csv", out)






def export_papers_per_year(out: str | None = None) -> None:
    """Accepted papers per year. A 0 marks a year outside a venue's coverage
    (no real conference year has no papers), so it becomes NaN and the figure
    shows a gap rather than a drop to zero."""
    src = f"{AGG}/papers_per_year.csv"
    if not os.path.exists(src):
        print(f"  SKIP {src} (not found)")
        return
    df = pd.read_csv(src)
    result = df[["year"]].copy()
    for venue in VENUES:
        if venue in df.columns:
            result[venue] = df[venue].replace(0, np.nan)
    save(result, "papers_per_year.csv", out or TMLR)


def export_tmlr() -> None:
    """TMLR set: the three conferences, under the paper's file names."""
    TMLR = os.path.join(OUT, "tmlr")
    for m in READABILITY:
        export_metric("readability", m, f"readability_{m}", out=TMLR)
    export_metric("acronyms", "title_acronym_density", "acronyms_title", out=TMLR)
    export_metric("acronyms", "abstract_acronym_density", "acronyms_abstract", out=TMLR)
    for col, short in SENSATIONAL:
        export_metric("sensational_language", col, f"sensational_{short}", out=TMLR)
    for metric_file, col, out_name in STYLE:
        export_metric(metric_file, col, out_name, out=TMLR)
    export_papers_per_year(TMLR)
    export_llm_scores(VENUES, TMLR)
    export_standardized_llm(VENUES, TMLR)


def main() -> None:
    print("Exporting pgfplots CSVs")
    export_readability()
    export_llm_scores()
    export_standardized_llm()
    print("TMLR set")
    export_tmlr()
    print("Done.")


if __name__ == "__main__":
    main()
