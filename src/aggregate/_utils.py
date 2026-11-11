"""Shared helper for per-metric aggregation.

By default this covers the three conferences NeurIPS, ICLR and ICML. Each
venue is aggregated on its own and the venues are joined on year, so adding
or removing a venue never changes another venue's values.

The arXiv and PubMed baselines are opt-in. Name them in AA_BASELINES
(comma- or space-separated, e.g. AA_BASELINES=pubmed,arxiv) or pass
`baselines=` to aggregate(). With them enabled the output is what the
upstream research repository wrote:

  - {metric}.csv gains pubmed_* and arxiv_* columns, in that order after the
    conferences, so the year index is the union over every venue (PubMed's
    ahead-of-print records extend it to 2027);
  - {metric}_arxiv_by_category.csv groups arXiv by (year, primary category),
    with columns {col}_{mean,std,count}. The category comes from the
    per-paper file when it has an arxiv_primary_category column, otherwise
    from the processed arXiv records (paper_id to primary category).

Without AA_BASELINES the output is byte-identical to the conference-only
release. The baselines' per-paper files run to several gigabytes, so only
the columns being aggregated are read from them, and PubMed one column at a
time. Each column is grouped on its own either way, so this changes no value.

Paths resolve from AA_DATA (default "data") so a caller can redirect the
whole tree without editing this module.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

import pandas as pd

DATA_DIR      = os.environ.get("AA_DATA", "data")
PER_PAPER_DIR = os.path.join(DATA_DIR, "per_paper")
OUT_DIR       = os.path.join(DATA_DIR, "aggregate")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
# The three conferences. validate.py's VALID_VENUES also admits "arxiv";
# adding a venue there without adding it here will pass validation but
# silently skip aggregation.
VENUES        = ["neurips", "iclr", "icml"]
# The opt-in baselines, in upstream column order.
BASELINES     = ["pubmed", "arxiv"]
CATEGORY_COL  = "arxiv_primary_category"

_CATEGORY_MAPS: dict[str, dict[str, str]] = {}


def baselines_from_env(value: str | None = None) -> list[str]:
    """The baselines named in AA_BASELINES (or `value`), in upstream order.

    Empty or unset means none. An unknown name is an error rather than a
    silent no-op, since a typo would otherwise drop a whole baseline.
    """
    raw = os.environ.get("AA_BASELINES", "") if value is None else value
    names = [n for n in re.split(r"[,\s]+", raw.strip().lower()) if n]
    unknown = sorted(set(names) - set(BASELINES))
    if unknown:
        raise ValueError(f"AA_BASELINES: unknown baseline(s) {unknown}; "
                         f"choose from {BASELINES}")
    return [b for b in BASELINES if b in names]


def arxiv_category_map(processed_dir: str | None = None) -> dict[str, str]:
    """paper_id to arxiv_primary_category over processed/arxiv/*.json (cached)."""
    processed_dir = processed_dir or PROCESSED_DIR
    key = os.path.abspath(processed_dir)
    if key in _CATEGORY_MAPS:
        return _CATEGORY_MAPS[key]
    mapping: dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(processed_dir, "arxiv", "*.json"))):
        with open(path, encoding="utf-8") as fh:
            for p in json.load(fh):
                cat = p.get(CATEGORY_COL)
                if cat:
                    mapping[p["paper_id"]] = cat
    print(f"  [category map] {len(mapping):,} arXiv papers", file=sys.stderr)
    _CATEGORY_MAPS[key] = mapping
    return mapping


def _by_year(df: pd.DataFrame, present: list[str]) -> pd.DataFrame:
    return df.groupby("year")[present].agg(["mean", "std", "count"])


def _read_arxiv(path: str, cols: list[str]) -> pd.DataFrame:
    """year, the metric columns present, and the category (or the paper_id
    to look it up). arXiv is small enough to hold whole."""
    header = pd.read_csv(path, nrows=0).columns
    keep = ["year"] + [c for c in cols if c in header]
    keep.append(CATEGORY_COL if CATEGORY_COL in header else "paper_id")
    return pd.read_csv(path, usecols=keep, low_memory=False)


def _aggregate_columnwise(path: str, cols: list[str]) -> tuple[pd.DataFrame | None, list[str]]:
    """Per-year mean, std and count, reading year and one column at a time.

    PubMed's readability file alone is 3.8 GB. Grouping column by column
    gives the same numbers as grouping the whole frame, because pandas
    aggregates every column independently.
    """
    header = pd.read_csv(path, nrows=0).columns
    present = [c for c in cols if c in header]
    if not present:
        return None, present
    parts = [_by_year(pd.read_csv(path, usecols=["year", c], low_memory=False), [c])
             for c in present]
    return pd.concat(parts, axis=1), present


def aggregate_by_category(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Mean, std and count of each col per (year, primary category).

    Rows without a category are left out, as pandas groupby does with a
    missing key.
    """
    present = [c for c in cols if c in df.columns]
    cat_agg = (
        df.groupby(["year", CATEGORY_COL])[present]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    cat_agg.columns = (
        ["year", CATEGORY_COL] + [f"{c}_{s}" for c, s in cat_agg.columns[2:]]
    )
    return cat_agg.sort_values(["year", CATEGORY_COL]).reset_index(drop=True)


def aggregate(
    metric: str,
    cols: list[str],
    out_name: str | None = None,
    venues: list[str] | None = None,
    per_paper_dir: str | None = None,
    out_dir: str | None = None,
    baselines: list[str] | None = None,
    processed_dir: str | None = None,
) -> str:
    """Load {per_paper_dir}/{metric}/{venue}.csv for each venue, group by year,
    compute mean, std and count for each col, merge venues into one wide CSV.

    `baselines` (default: AA_BASELINES) adds PubMed and arXiv after the
    conferences and, for arXiv, writes {out_name or metric}_arxiv_by_category.csv
    beside the wide file.

    Returns the output path.
    """
    venues        = venues if venues is not None else VENUES
    baselines     = baselines if baselines is not None else baselines_from_env()
    per_paper_dir = per_paper_dir or PER_PAPER_DIR
    out_dir       = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    frames = []
    arxiv_df = None
    for venue in list(venues) + [b for b in BASELINES if b in baselines]:
        path = os.path.join(per_paper_dir, metric, f"{venue}.csv")
        if not os.path.exists(path):
            print(f"  WARNING: {path} not found, skipping {venue}", file=sys.stderr)
            continue
        if venue == "pubmed":
            agg, present = _aggregate_columnwise(path, cols)
            if agg is None:
                print(f"  WARNING: {metric}/{venue} has none of {cols}, skipping",
                      file=sys.stderr)
                continue
        else:
            df = _read_arxiv(path, cols) if venue == "arxiv" else pd.read_csv(path, low_memory=False)
            present = [c for c in cols if c in df.columns]
            agg = _by_year(df, present)
        missing = set(cols) - set(present)
        if missing:
            print(f"  WARNING: {metric}/{venue} missing {missing}", file=sys.stderr)

        agg = agg.reset_index()
        agg.columns = ["year"] + [f"{venue}_{c}_{s}" for c, s in agg.columns[1:]]
        frames.append(agg)

        if venue == "arxiv":
            if CATEGORY_COL not in df.columns:
                df[CATEGORY_COL] = df["paper_id"].map(arxiv_category_map(processed_dir))
            arxiv_df = df

    if not frames:
        raise RuntimeError(f"No data found for metric '{metric}'")

    result = frames[0]
    for other in frames[1:]:
        result = result.merge(other, on="year", how="outer")
    result = result.sort_values("year").reset_index(drop=True)

    out_path = os.path.join(out_dir, f"{out_name or metric}.csv")
    result.to_csv(out_path, index=False)
    print(f"  {len(result)} rows -> {out_path}")

    if arxiv_df is not None:
        cat_agg = aggregate_by_category(arxiv_df, cols)
        cat_out = os.path.join(out_dir, f"{out_name or metric}_arxiv_by_category.csv")
        cat_agg.to_csv(cat_out, index=False)
        n_cats = arxiv_df[CATEGORY_COL].nunique()
        print(f"  {len(cat_agg)} rows ({n_cats} categories) -> {cat_out}")

    return out_path
