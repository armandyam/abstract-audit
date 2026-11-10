#!/usr/bin/env python3
"""Build baselines/, the shipped arXiv and PubMed aggregates.

The TMLR paper sets the three conferences against two baselines: arXiv,
split into machine learning and the rest by primary category, and PubMed.
Their per-paper metric files run to 13 GB, and their sources cannot be
fetched again in the form the paper used (see src/scraping/download_arxiv.py
and src/processing/fetch_pubmed.py). This script reduces the per-paper files
to the per-year aggregates the paper's figures and tables read, and those are
what the repository ships.

Reads:
  {per_paper_dir}/{family}/arxiv.csv and pubmed.csv   per-paper metrics
  {processed_dir}/arxiv/*.json                        only for families whose
                                                      arXiv file has no
                                                      arxiv_primary_category

Writes, under --out-dir (default: baselines/):

  aggregate/{family}.csv
      year, then pubmed_{col}_{mean,std,count} and arxiv_{col}_{mean,std,count},
      exactly the baseline columns of the upstream data/aggregate/{family}.csv
      (src/aggregate/_utils.py with both baselines enabled). PubMed has no file
      for the spaCy families (parse depth, NP density, passive rate, TTR,
      clauses, noun chunks, nouns, verbs, numbers), so those carry arXiv only.
      PubMed years run to 2027: ahead-of-print records. The export caps PubMed
      at 2025.
  aggregate/{family}_arxiv_by_category.csv
      year, arxiv_primary_category, {col}_{mean,std,count}. The ML and non-ML
      series are count-weighted means over these rows.
  papers_per_year.csv
      year, arxiv_ml, arxiv_nonml, pubmed_scored, pubmed_records.
      arxiv_ml and arxiv_nonml sum title_acronym_density_count over the
      categories of each group (every arXiv record has a title density, so
      this is the record count). PubMed has two denominators:
        pubmed_scored   abstracts with a Flesch score, i.e. at least ten words
                        (readability.py's guard): 24,301,259 for 1990-2025.
                        papers_per_year in the paper plots this one.
        pubmed_records  every cleaned record (the sentence-length count):
                        24,306,644 for 1990-2025, and 156,564 more dated
                        2026-2027.
  acronym_histograms.csv
      group, occurrences, acronym_types: for arxiv_ml, arxiv_nonml and pubmed,
      how many distinct abstract acronyms occur exactly `occurrences` times
      across the group's abstracts. The acronym reuse table's unique counts
      and bucket shares follow from it (reuse_row below). PubMed is limited to
      records dated up to --max-year (2025), as in the paper's table.

Every number is computed by the same code as the pipeline's own aggregation,
so the shipped files equal the upstream aggregates value for value.

Run (about 12 minutes, with a peak memory footprint near 14 GB, on the TMLR
corpus; the PubMed files are read one column at a time):
  AA_DATA=/path/with/per_paper python src/baselines/make_baselines.py
  python src/baselines/make_baselines.py --families acronyms readability
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from aggregate._utils import BASELINES, CATEGORY_COL, aggregate  # noqa: E402
from arxiv_categories import is_ml  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.environ.get("AA_DATA", "data")
OUT_DIR = os.path.join(REPO, "baselines")
MAX_YEAR = 2025

# Metric family and the columns aggregated, as in src/aggregate/aggregate_*.py.
FAMILIES: dict[str, list[str]] = {
    "readability": [
        "word_count", "avg_sentence_length", "avg_syllables_per_word",
        "flesch_ease", "flesch_kincaid", "gunning_fog", "smog", "dale_chall",
        "spache", "coleman_liau", "ari", "linsear_write", "lix", "rix",
        "forcast", "powers_sumner_kearl",
    ],
    "acronyms": ["title_acronym_density", "abstract_acronym_density"],
    "active_narration": ["has_narrator"],
    "clauses_per_sentence": ["clauses_per_sent"],
    "hedging": ["hedging_per_100"],
    "noun_chunks": ["noun_chunks_per_100"],
    "nouns": ["noun_per_100"],
    "np_density": ["np_density"],
    "numbers": ["num_per_100"],
    "parse_depth": ["parse_depth"],
    "passive_rate": ["passive_rate"],
    "sensational_language": [
        "hype_importance_per_100", "hype_novelty_per_100", "hype_rigor_per_100",
        "hype_scale_per_100", "hype_utility_per_100", "hype_quality_per_100",
        "hype_attitude_per_100", "hype_problem_per_100",
        "hype_additional_per_100", "hype_total_per_100",
    ],
    "sentence_length": ["n_words", "words_per_sentence"],
    "signposting": ["signposting_per_100"],
    "ttr": ["ttr"],
    "verbs": ["verb_per_100"],
}

# Acronym reuse buckets, as in the paper's table: share of distinct acronyms
# used once, 2-9, 10-99, 100-999 and 1000 or more times.
BUCKETS = [("1", 1, 1), ("2--9", 2, 9), ("10--99", 10, 99),
           ("100--999", 100, 999), ("1000+", 1000, None)]
HIST_GROUPS = ["arxiv_ml", "arxiv_nonml", "pubmed"]
ACRONYM_COL = "abstract_acronyms"
CHUNK = 1_000_000


# ── aggregates ───────────────────────────────────────────────────────────────

def build_aggregates(families: list[str], per_paper_dir: str, processed_dir: str,
                     out_dir: str) -> None:
    for family in families:
        print(f"[{family}]")
        aggregate(family, FAMILIES[family], venues=[], baselines=BASELINES,
                  per_paper_dir=per_paper_dir, out_dir=out_dir,
                  processed_dir=processed_dir)


def papers_per_year(agg_dir: str) -> pd.DataFrame:
    """Record counts per year for the two arXiv groups and both PubMed
    denominators, from the aggregates this script wrote."""
    cat = pd.read_csv(os.path.join(agg_dir, "acronyms_arxiv_by_category.csv"))
    ml = is_ml(cat[CATEGORY_COL])
    count = "title_acronym_density_count"
    parts = [
        cat[ml].groupby("year")[count].sum().rename("arxiv_ml"),
        cat[~ml].groupby("year")[count].sum().rename("arxiv_nonml"),
    ]
    for family, col, name in [("readability", "pubmed_flesch_ease_count", "pubmed_scored"),
                              ("sentence_length", "pubmed_words_per_sentence_count",
                               "pubmed_records")]:
        df = pd.read_csv(os.path.join(agg_dir, f"{family}.csv"))
        parts.append(df.set_index("year")[col].dropna().rename(name))
    out = pd.concat(parts, axis=1).sort_index()
    out.index.name = "year"
    return out.astype("Int64").reset_index()


# ── acronym histograms ───────────────────────────────────────────────────────

def count_acronyms(cells, counter: Counter | None = None) -> Counter:
    """Occurrences of each acronym over pipe-separated cells, missing cells
    skipped. The same rule as the upstream reuse table."""
    counter = Counter() if counter is None else counter
    for cell in cells:
        if pd.isna(cell):
            continue
        for acr in str(cell).split("|"):
            acr = acr.strip()
            if acr:
                counter[acr] += 1
    return counter


def histogram(counter: Counter) -> dict[int, int]:
    """Number of distinct acronyms for each occurrence count."""
    return dict(sorted(Counter(counter.values()).items()))


def reuse_row(hist: dict[int, int]) -> dict:
    """Unique acronyms and the percentage in each reuse bucket.

    Equal to what the upstream table computed from the full counter, since
    the buckets depend only on each acronym's occurrence count.
    """
    total = sum(hist.values())
    row: dict = {"n_unique": total}
    for label, lo, hi in BUCKETS:
        n = sum(v for k, v in hist.items() if k >= lo and (hi is None or k <= hi))
        row[label] = 100.0 * n / total if total else 0.0
    return row


def acronym_histograms(per_paper_dir: str, max_year: int = MAX_YEAR) -> pd.DataFrame:
    counters = {g: Counter() for g in HIST_GROUPS}

    ax = os.path.join(per_paper_dir, "acronyms", "arxiv.csv")
    for chunk in pd.read_csv(ax, usecols=[ACRONYM_COL, CATEGORY_COL], chunksize=CHUNK,
                             dtype={ACRONYM_COL: str, CATEGORY_COL: str}):
        ml = is_ml(chunk[CATEGORY_COL])
        count_acronyms(chunk.loc[ml, ACRONYM_COL], counters["arxiv_ml"])
        count_acronyms(chunk.loc[~ml, ACRONYM_COL], counters["arxiv_nonml"])

    pm = os.path.join(per_paper_dir, "acronyms", "pubmed.csv")
    dropped = 0
    for chunk in pd.read_csv(pm, usecols=["year", ACRONYM_COL], chunksize=CHUNK,
                             dtype={ACRONYM_COL: str}):
        keep = chunk["year"] <= max_year
        dropped += int((~keep).sum())
        count_acronyms(chunk.loc[keep, ACRONYM_COL], counters["pubmed"])
    print(f"  PubMed: {dropped:,} records dated after {max_year} left out")

    rows = []
    for group in HIST_GROUPS:
        hist = histogram(counters[group])
        print(f"  {group}: {sum(hist.values()):,} distinct acronyms")
        rows += [{"group": group, "occurrences": k, "acronym_types": v}
                 for k, v in hist.items()]
    return pd.DataFrame(rows, columns=["group", "occurrences", "acronym_types"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-paper-dir", default=os.path.join(DATA_DIR, "per_paper"))
    ap.add_argument("--processed-dir", default=os.path.join(DATA_DIR, "processed"),
                    help="For the arXiv category map (processed/arxiv/*.json)")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--families", nargs="+", choices=sorted(FAMILIES),
                    default=list(FAMILIES))
    ap.add_argument("--max-year", type=int, default=MAX_YEAR,
                    help="Last PubMed year in the acronym histogram")
    ap.add_argument("--skip-aggregates", action="store_true")
    ap.add_argument("--skip-histograms", action="store_true")
    a = ap.parse_args()

    agg_dir = os.path.join(a.out_dir, "aggregate")
    if not a.skip_aggregates:
        build_aggregates(a.families, a.per_paper_dir, a.processed_dir, agg_dir)

    needed = ["acronyms_arxiv_by_category.csv", "readability.csv", "sentence_length.csv"]
    if all(os.path.exists(os.path.join(agg_dir, f)) for f in needed):
        path = os.path.join(a.out_dir, "papers_per_year.csv")
        papers_per_year(agg_dir).to_csv(path, index=False)
        print(f"  papers per year -> {path}")
    else:
        print("  papers_per_year.csv needs the acronyms, readability and "
              "sentence_length aggregates; skipped")

    if not a.skip_histograms:
        print("[acronym histograms]")
        path = os.path.join(a.out_dir, "acronym_histograms.csv")
        acronym_histograms(a.per_paper_dir, a.max_year).to_csv(path, index=False)
        print(f"  -> {path}")


if __name__ == "__main__":
    main()
