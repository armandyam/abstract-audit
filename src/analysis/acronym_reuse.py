#!/usr/bin/env python3
"""
How often each distinct abstract acronym is reused, per corpus.

For every corpus, each distinct acronym (type) is counted by the number of its
occurrences across all abstracts, and the types are binned by that count:
used once, 2 to 9 times, 10 to 99, 100 to 999, and 1000 or more. Each cell is
the percentage of the corpus's distinct acronyms that fall in the bin. The
TMLR paper reports this as Table tab:acronym-reuse, against the published
figures of Barnett and Doubleday (2020) for PubMed titles and abstracts,
1950-2019: 30 percent used once, 49 percent 2 to 9 times, with the higher
bins not reported.

Rows, in the table's order:

  NeurIPS, ICLR, ICML     from data/per_paper/acronyms/{venue}.csv, all years
  further corpora         from frequency histograms given with --histogram
                          (the paper's arXiv ML, arXiv non-ML and PubMed rows)
  B\\&D (2020)            the literature constant

A histogram file is a CSV with columns `count,n_types`: n_types distinct
acronyms occur exactly `count` times. That is all the table needs, so a corpus
too large to ship per-paper files for can still contribute a row. Write one
from a Counter of acronym occurrences with `write_histogram`.

Writes: data/aggregate/acronym_reuse_freq.csv
  venue, n_unique, 1, 2--9, 10--99, 100--999, 1000+   (percentages, 1 decimal)

Run:
  python src/analysis/acronym_reuse.py
  python src/analysis/acronym_reuse.py \\
      --histogram "arXiv ML" hist_arxiv_ml.csv --histogram PubMed hist_pubmed.csv
"""

from __future__ import annotations

import argparse
import os
from collections import Counter
from collections.abc import Mapping

import pandas as pd

_D = os.environ.get("AA_DATA", "data")
ACR_DIR = os.path.join(_D, "per_paper", "acronyms")
OUT_CSV = os.path.join(_D, "aggregate", "acronym_reuse_freq.csv")

CONFERENCES = [("NeurIPS", "neurips"), ("ICLR", "iclr"), ("ICML", "icml")]

# Bin labels as the table prints them. A type used `count` times falls in the
# first bin whose lower edge it reaches.
LABELS = ["1", "2--9", "10--99", "100--999", "1000+"]
_EDGES = [1, 2, 10, 100, 1000]

# Barnett and Doubleday (2020), text p.2: "30% occurring only once, 49% between
# 2 and 10 times"; 1,112,345 distinct acronyms. The higher bins are not
# reported and stay empty.
BD_LABEL = "B\\&D (2020)"
BD_N_UNIQUE = 1_112_345
BD_BASELINE = {"1": 30.0, "2--9": 49.0, "10--99": None, "100--999": None, "1000+": None}


def extract_acronym_counts(df: pd.DataFrame, col: str = "abstract_acronyms") -> Counter:
    """Occurrences of each acronym across all papers in df.

    A cell holds the paper's acronyms joined by "|", one entry per occurrence.
    Empty cells and empty entries are skipped; entries are whitespace-stripped.
    """
    c: Counter = Counter()
    for cell in df[col].dropna():
        for acr in str(cell).split("|"):
            acr = acr.strip()
            if acr:
                c[acr] += 1
    return c


def histogram(counter: Mapping[str, int]) -> dict[int, int]:
    """{count: number of distinct acronyms occurring exactly `count` times}."""
    return dict(Counter(counter.values()))


def _bin(count: int) -> str:
    for lbl, lo in zip(reversed(LABELS), reversed(_EDGES)):
        if count >= lo:
            return lbl
    raise ValueError(f"an acronym type cannot occur {count} times")


def freq_distribution(hist: Mapping[int, int]) -> dict[str, float]:
    """Percentage of distinct acronyms in each bin, from a {count: n_types}
    histogram. An empty corpus gives zero in every bin."""
    total = sum(hist.values())
    buckets = {lbl: 0 for lbl in LABELS}
    for count, n_types in hist.items():
        if n_types:
            buckets[_bin(int(count))] += n_types
    if total == 0:
        return {lbl: 0.0 for lbl in LABELS}
    return {lbl: 100.0 * n / total for lbl, n in buckets.items()}


def reuse_row(label: str, hist: Mapping[int, int]) -> dict:
    """One table row from a {count: n_types} histogram."""
    return {"venue": label, "n_unique": int(sum(hist.values())), **freq_distribution(hist)}


def bd_row() -> dict:
    return {"venue": BD_LABEL, "n_unique": BD_N_UNIQUE,
            **{lbl: (float("nan") if v is None else v) for lbl, v in BD_BASELINE.items()}}


def read_histogram(path: str) -> dict[int, int]:
    """A `count,n_types` CSV as a histogram. Repeated counts are summed."""
    df = pd.read_csv(path)
    missing = {"count", "n_types"} - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    if (df["count"] < 1).any():
        raise ValueError(f"{path}: counts must be at least 1")
    return {int(k): int(v) for k, v in df.groupby("count")["n_types"].sum().items()}


def write_histogram(counter: Mapping[str, int], path: str) -> None:
    """Write a Counter of acronym occurrences as a `count,n_types` CSV."""
    h = histogram(counter)
    pd.DataFrame(sorted(h.items()), columns=["count", "n_types"]).to_csv(path, index=False)


def conference_rows(acr_dir: str = ACR_DIR) -> list[dict]:
    rows = []
    for label, key in CONFERENCES:
        path = os.path.join(acr_dir, f"{key}.csv")
        if not os.path.exists(path):
            print(f"  WARNING: {path} not found, skipping {label}")
            continue
        c = extract_acronym_counts(pd.read_csv(path, low_memory=False))
        rows.append(reuse_row(label, histogram(c)))
        print(f"  {label}: {len(c):,} unique acronyms")
    return rows


def build_table(rows: list[dict]) -> pd.DataFrame:
    """The table: the given corpus rows, then the Barnett and Doubleday row."""
    return pd.DataFrame([*rows, bd_row()], columns=["venue", "n_unique", *LABELS])


# Group names in baselines/acronym_histograms.csv and their table labels, in
# the paper's row order.
BASELINE_GROUPS = [("arxiv_ml", "arXiv ML"), ("arxiv_nonml", "arXiv non-ML"),
                   ("pubmed", "PubMed")]


def read_baseline_histograms(path: str) -> list[tuple[str, dict[int, int]]]:
    """(label, histogram) per baseline corpus from the shipped
    `group,occurrences,acronym_types` file, in BASELINE_GROUPS order."""
    df = pd.read_csv(path)
    missing = {"group", "occurrences", "acronym_types"} - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    out = []
    for group, label in BASELINE_GROUPS:
        g = df[df["group"] == group]
        if g.empty:
            continue
        out.append((label, {int(c): int(n) for c, n in zip(g["occurrences"], g["acronym_types"])}))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--acr-dir", default=ACR_DIR)
    ap.add_argument("--histogram", nargs=2, action="append", default=[],
                    metavar=("LABEL", "CSV"),
                    help="add a row from a count,n_types histogram; repeatable, "
                         "rows follow the conferences in the order given")
    ap.add_argument("--baselines", default=None,
                    help="baselines/acronym_histograms.csv: add the arXiv ML, arXiv "
                         "non-ML and PubMed rows from the shipped histograms")
    ap.add_argument("--out", default=OUT_CSV)
    args = ap.parse_args()

    rows = conference_rows(args.acr_dir)
    if args.baselines:
        for label, h in read_baseline_histograms(args.baselines):
            rows.append(reuse_row(label, h))
            print(f"  {label}: {sum(h.values()):,} unique acronyms (baselines)")
    for label, path in args.histogram:
        h = read_histogram(path)
        rows.append(reuse_row(label, h))
        print(f"  {label}: {sum(h.values()):,} unique acronyms (histogram)")

    out = build_table(rows)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    out.to_csv(args.out, index=False, float_format="%.1f")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
