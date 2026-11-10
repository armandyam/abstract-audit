#!/usr/bin/env python3
"""How much of the acronym load do the most common acronyms carry?

The token side of the reuse table (acronym_reuse.py reports the type side):
the share of all abstract acronym occurrences held by the 10, 20, 50, 100 and
500 most frequent acronyms, against the long tail of acronyms that occur once.
This is what a reader meets on the page.

Corpus: NeurIPS, ICLR and ICML abstracts from 2015 to 2025, the window of the
topic analyses. ICLR 2026 is the only venue in 2026 and is excluded.

Each "|"-separated entry of `abstract_acronyms` is one occurrence. Ties in
frequency keep the order in which the acronyms first appear (venue, then
file order), so the top-n sets are reproducible.

Reads:  data/per_paper/acronyms/{venue}.csv
Writes: data/aggregate/acronym_concentration.csv  one row per top_n
        data/aggregate/acronym_top_terms.csv      the 25 most frequent acronyms

Run:
  python src/analysis/acronym_concentration.py
"""

from __future__ import annotations

import os
from collections import Counter

import pandas as pd

_D = os.environ.get("AA_DATA", "data")
PER_PAPER = os.path.join(_D, "per_paper")
OUT = os.path.join(_D, "aggregate")
VENUES = ["neurips", "iclr", "icml"]

FIRST_YEAR = 2015
LAST_YEAR = 2025
TOP_N = [10, 20, 50, 100, 500]
N_TOP_TERMS = 25


def load(per_paper: str = PER_PAPER, venues: list[str] = VENUES) -> pd.DataFrame:
    d = pd.concat([
        pd.read_csv(os.path.join(per_paper, "acronyms", f"{v}.csv"),
                    usecols=["paper_id", "year", "abstract_acronyms"])
        for v in venues
    ], ignore_index=True)
    return d[(d.year >= FIRST_YEAR) & (d.year <= LAST_YEAR)].copy()


def acronym_concentration(d: pd.DataFrame, top_n: list[int] = TOP_N,
                          n_top_terms: int = N_TOP_TERMS
                          ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(concentration table, most frequent acronyms) for the papers in d.

    A top_n larger than the number of distinct acronyms reports a type share
    above 100 percent and the full token share, as the formula gives.
    """
    counts: Counter[str] = Counter()
    for s in d.abstract_acronyms.dropna():
        counts.update(str(s).split("|"))
    if not counts:
        raise ValueError("no abstract acronyms in the selected papers")
    freq = pd.Series(counts).sort_values(ascending=False)
    tokens = int(freq.sum())
    types = int(len(freq))

    conc = pd.DataFrame([{"top_n": n,
                          "type_share": 100 * n / types,
                          "token_share": 100 * float(freq.iloc[:n].sum()) / tokens}
                         for n in top_n])
    conc["n_types"] = types
    conc["n_tokens"] = tokens
    conc["singleton_type_share"] = 100 * float((freq == 1).sum()) / types
    conc["singleton_token_share"] = 100 * float((freq == 1).sum()) / tokens

    top = freq.head(n_top_terms).rename_axis("acronym").reset_index(name="tokens")
    top["token_share"] = 100 * top.tokens / tokens
    return conc, top


def main() -> None:
    d = load()
    print(f"conference papers {FIRST_YEAR} to {LAST_YEAR}: {len(d):,}")
    conc, top = acronym_concentration(d)
    print(f"  {conc.n_types.iloc[0]:,} distinct acronyms over "
          f"{conc.n_tokens.iloc[0]:,} occurrences")
    for _, r in conc.iterrows():
        print(f"    top {int(r.top_n):>3} types ({r.type_share:5.2f}% of types) "
              f"carry {r.token_share:5.1f}% of occurrences")
    print(f"    {conc.singleton_type_share.iloc[0]:.1f}% of types occur once, "
          f"carrying {conc.singleton_token_share.iloc[0]:.1f}% of occurrences")
    print("  most frequent: " + ", ".join(
        f"{r.acronym} ({r.token_share:.1f}%)" for _, r in top.head(10).iterrows()))

    os.makedirs(OUT, exist_ok=True)
    conc.to_csv(os.path.join(OUT, "acronym_concentration.csv"), index=False)
    top.to_csv(os.path.join(OUT, "acronym_top_terms.csv"), index=False)
    print(f"\nwrote acronym_concentration.csv and acronym_top_terms.csv to {OUT}")


if __name__ == "__main__":
    main()
