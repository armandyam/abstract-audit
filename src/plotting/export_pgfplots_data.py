#!/usr/bin/env python3
"""Export plot-ready CSV files for the pgfplots figures.

Two output sets:

  data/pgfplots/              the series more than one paper plots, one copy
                              each: one CSV per metric, papers per year, and
                              the judge series for all three venues. The TMLR
                              and AI-Native Academia papers read the metric
                              series, all three papers the NeurIPS judge series.
  data/uncertainlp/pgfplots/  the UncertaiNLP paper's own readability series:
                              NeurIPS only, `year,neurips`, unchanged in content
                              from the tag uncertainlp-2026.

By default the per-metric series hold the conferences alone:
`year,neurips,iclr,icml`, restricted to the years at least one of them covers.

With --baselines they are the papers' figure data in full. The arXiv and
PubMed aggregates shipped in shared/baselines/ are merged in, and each
per-metric file has the seven columns

  year, neurips, iclr, icml, arxiv_ml, arxiv_nonml, pubmed

over every year any of its corpora covers (up to 2027 for the series with
PubMed records; the rows past 2025 come from ICLR 2026 and PubMed's
ahead-of-print records, and PubMed values after 2025 are blank). arxiv_ml and
arxiv_nonml are count-weighted means over the primary categories of each
group (src/arxiv_categories.py), and PubMed is cut at PUBMED_MAX = 2025.
Papers per year takes the arXiv counts from the acronym aggregate's
categories and PubMed's from the readability-scored count (see
shared/baselines/README.md for the two PubMed denominators). This is the
upstream computation, and the files equal shared/reference/pgfplots/.

Each source supplies only its own columns. The conference series always come
from data/aggregate/; arXiv and PubMed come only from the --baselines
directory. A local aggregate built with AA_BASELINES also holds arxiv_* and
pubmed_* columns, and those are ignored here (the run says so). To plot
locally computed baselines, write them to a directory of their own with
src/baselines/make_baselines.py --out-dir DIR and pass --baselines DIR.

The judge series and the UncertaiNLP set are the same either way.

Run:
  python src/plotting/export_pgfplots_data.py
  python src/plotting/export_pgfplots_data.py --baselines            # shared/baselines/
  python src/plotting/export_pgfplots_data.py --baselines path/to/dir
"""

from __future__ import annotations
import argparse
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from aggregate._utils import CATEGORY_COL, VENUES
from arxiv_categories import is_ml

_D = os.environ.get("AA_DATA", "data")
AGG  = os.path.join(_D, "aggregate")
OUT    = os.path.join(_D, "uncertainlp", "pgfplots")
SHARED = os.path.join(_D, "pgfplots")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASELINES = os.path.join(REPO, "shared", "baselines")

# PubMed's last full year. The baseline holds ahead-of-print records dated
# 2026 and 2027, which belong to no publication year.
PUBMED_MAX = 2025

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
    out = out or SHARED
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
    out = out or SHARED
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
    save(result, "papers_per_year.csv", out or SHARED)


# ── arXiv and PubMed baselines ───────────────────────────────────────────────

def weighted_mean_by_year(df_cat: pd.DataFrame, col: str, mask: pd.Series) -> pd.DataFrame:
    """Count-weighted mean of {col}_mean over the categories in `mask`, per
    year: sum(mean_i * count_i) / sum(count_i). Columns: year, wmean.

    A category-year without a mean or count is left out. A year whose counts
    sum to zero has no mean (NaN). Upstream also computed a pooled interval
    here; no figure reads it, so it is not ported.
    """
    mean_col, count_col = f"{col}_mean", f"{col}_count"
    if mean_col not in df_cat.columns or count_col not in df_cat.columns:
        return pd.DataFrame({"year": pd.Series(dtype="int64"),
                             "wmean": pd.Series(dtype="float64")})
    sub = df_cat[mask].copy()
    sub = sub.dropna(subset=[mean_col, count_col])
    sub["_sum"] = sub[mean_col] * sub[count_col]
    agg = sub.groupby("year").agg(
        _sum=("_sum", "sum"),
        _cnt=(count_col, "sum"),
    ).reset_index()
    agg["wmean"] = agg["_sum"] / agg["_cnt"].replace(0, np.nan)
    return agg[["year", "wmean"]]


def arxiv_split(df_cat: pd.DataFrame, col: str) -> pd.DataFrame:
    """year, arxiv_ml, arxiv_nonml: the count-weighted means of each group."""
    ml = is_ml(df_cat[CATEGORY_COL])
    a = weighted_mean_by_year(df_cat, col, ml).rename(columns={"wmean": "arxiv_ml"})
    b = weighted_mean_by_year(df_cat, col, ~ml).rename(columns={"wmean": "arxiv_nonml"})
    return a.merge(b, on="year", how="outer")


BASELINE_PREFIXES = ("pubmed_", "arxiv_")


def _columns_from(df: pd.DataFrame, prefixes: tuple[str, ...]) -> pd.DataFrame:
    """year and the columns that start with one of `prefixes`."""
    return df[["year"] + [c for c in df.columns if c.startswith(prefixes)]]


def export_metric_full(metric_name: str, col: str, out_name: str,
                       baselines: str, out: str) -> None:
    """The paper's six-column series: conferences from the aggregate,
    arXiv and PubMed from `baselines`, on the union of their years.

    Each source contributes only its own columns, so the two never overlap
    in a merge."""
    main_csv = f"{AGG}/{metric_name}.csv"
    if not os.path.exists(main_csv):
        print(f"  SKIP {main_csv} (not found)")
        return
    local = pd.read_csv(main_csv)
    df = _columns_from(local, tuple(f"{v}_" for v in VENUES))
    # Years only a local arXiv/PubMed aggregate covers carry no conference
    # value; the baseline years come from `baselines` alone.
    conf_cols = [c for c in df.columns if c != "year"]
    if conf_cols:
        df = df.dropna(how="all", subset=conf_cols)
    ignored = [c for c in local.columns if c.startswith(BASELINE_PREFIXES)]
    if ignored:
        print(f"  note: {main_csv} has {len(ignored)} arXiv/PubMed columns; "
              f"those series are taken from {baselines} instead")
    base_csv = os.path.join(baselines, "aggregate", f"{metric_name}.csv")
    if os.path.exists(base_csv):
        base = _columns_from(pd.read_csv(base_csv), BASELINE_PREFIXES)
        df = (df.merge(base, on="year", how="outer", validate="one_to_one")
                .sort_values("year").reset_index(drop=True))

    result = df[["year"]].copy()
    for venue in VENUES:
        mean_col = f"{venue}_{col}_mean"
        if mean_col in df.columns:
            result[venue] = df[mean_col]
    cat_csv = os.path.join(baselines, "aggregate", f"{metric_name}_arxiv_by_category.csv")
    if os.path.exists(cat_csv):
        result = result.merge(arxiv_split(pd.read_csv(cat_csv), col), on="year", how="left")
    pubmed_col = f"pubmed_{col}_mean"
    if pubmed_col in df.columns:
        pub = df[["year", pubmed_col]].rename(columns={pubmed_col: "pubmed"})
        result = result.merge(pub, on="year", how="left")
        result.loc[result["year"] > PUBMED_MAX, "pubmed"] = np.nan
    else:
        result["pubmed"] = np.nan  # the column is always present
    save(result, f"{out_name}.csv", out)


def export_papers_per_year_full(baselines: str, out: str) -> None:
    """Papers per year with the arXiv groups and PubMed (readability-scored
    count, cut at PUBMED_MAX). The year index is the conferences' plus the
    years arXiv covers, as the upstream count over processed records was."""
    src = f"{AGG}/papers_per_year.csv"
    if not os.path.exists(src):
        print(f"  SKIP {src} (not found)")
        return
    df = pd.read_csv(src)
    base_csv = os.path.join(baselines, "papers_per_year.csv")
    base = pd.read_csv(base_csv) if os.path.exists(base_csv) else None
    # Conference years only: a local count with the arXiv opt-in also lists
    # arXiv years, which the baselines below supply instead.
    conf = [v for v in VENUES if v in df.columns]
    years = set(df.loc[(df[conf].fillna(0) > 0).any(axis=1), "year"]) if conf else set()
    if base is not None:
        arxiv_years = base.loc[base[["arxiv_ml", "arxiv_nonml"]].notna().any(axis=1), "year"]
        years |= set(arxiv_years)
    result = pd.DataFrame({"year": sorted(years)})
    conf = df.set_index("year")
    for venue in VENUES:
        if venue in df.columns:
            result[venue] = result["year"].map(conf[venue]).replace(0, np.nan)
    if base is not None:
        for col in ("arxiv_ml", "arxiv_nonml"):
            result = result.merge(base[["year", col]].dropna(), on="year", how="left")
        pub = base[["year", "pubmed_scored"]].dropna().rename(columns={"pubmed_scored": "pubmed"})
        result = result.merge(pub, on="year", how="left")
        result.loc[result["year"] > PUBMED_MAX, "pubmed"] = np.nan
    save(result, "papers_per_year.csv", out)


# The sentence length series is in the full set only, and only once the
# conference aggregate for it (data/aggregate/sentence_length.csv) exists.
FULL_EXTRA = [("sentence_length", "words_per_sentence", "sentence_length")]


def export_shared(baselines: str | None = None) -> None:
    """The shared set under the papers' file names: the three conferences, or
    with `baselines` the full six-column series."""
    series = ([("readability", m, f"readability_{m}") for m in READABILITY]
              + [("acronyms", "title_acronym_density", "acronyms_title"),
                 ("acronyms", "abstract_acronym_density", "acronyms_abstract")]
              + [("sensational_language", col, f"sensational_{short}")
                 for col, short in SENSATIONAL]
              + list(STYLE))
    if baselines:
        names = {s[2] for s in series}
        series += [s for s in FULL_EXTRA if s[2] not in names]
        for metric_file, col, out_name in series:
            export_metric_full(metric_file, col, out_name, baselines, SHARED)
        export_papers_per_year_full(baselines, SHARED)
    else:
        for metric_file, col, out_name in series:
            export_metric(metric_file, col, out_name, out=SHARED)
        export_papers_per_year(SHARED)
    export_llm_scores(VENUES, SHARED)
    export_standardized_llm(VENUES, SHARED)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baselines", nargs="?", const=BASELINES, default=None,
                    metavar="DIR",
                    help="merge the arXiv and PubMed baselines into the shared set "
                         "(default DIR: shared/baselines/)")
    a = ap.parse_args()
    if a.baselines and not os.path.isdir(a.baselines):
        sys.exit(f"--baselines: {a.baselines} is not a directory")

    print("Exporting pgfplots CSVs")
    print("UncertaiNLP set")
    export_readability()
    print("shared set" + (f" with baselines from {a.baselines}" if a.baselines else ""))
    export_shared(a.baselines)
    print("Done.")


if __name__ == "__main__":
    main()
