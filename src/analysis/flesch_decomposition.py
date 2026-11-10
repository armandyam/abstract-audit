#!/usr/bin/env python3
"""Did abstracts get harder to read because sentences grew or because words did?

Flesch Reading Ease is linear in two measured quantities,

    FRE = 206.835 - 1.015 * (words / sentence) - 84.6 * (syllables / word)

so a change in the mean score between two years decomposes exactly into a
sentence length term and a word length term. No model is fitted and the
residual is zero up to floating point.

Both components are recomputed per paper from the integer word, sentence and
syllable counts rather than read from the rounded stored averages, so the
identity closes exactly. Papers with no words or no sentences (abstracts below
the readability minimum) are excluded.

Two rows:
  conferences  NeurIPS, ICLR and ICML pooled, 2015 to 2025
  neurips      NeurIPS alone, 1987 to 2025

Reads:  data/per_paper/readability/{venue}.csv
Writes: data/aggregate/flesch_decomposition.csv

Run:
  python src/analysis/flesch_decomposition.py
"""

from __future__ import annotations

import os

import pandas as pd

_D = os.environ.get("AA_DATA", "data")
PER_PAPER = os.path.join(_D, "per_paper")
OUT = os.path.join(_D, "aggregate")
VENUES = ["neurips", "iclr", "icml"]

# Flesch Reading Ease coefficients, in the form textstat implements.
FRE_CONST, FRE_ASL, FRE_ASW = 206.835, -1.015, -84.6

SPECS = [("conferences", VENUES, 2015, 2025),
         ("neurips", ["neurips"], 1987, 2025)]


def read_counts(venues: list[str], per_paper: str = PER_PAPER) -> pd.DataFrame:
    return pd.concat([
        pd.read_csv(os.path.join(per_paper, "readability", f"{v}.csv"),
                    usecols=["venue", "year", "word_count", "sentence_count",
                             "syllable_count"])
        for v in venues
    ], ignore_index=True)


def decompose(d: pd.DataFrame, name: str, y0: int, y1: int) -> dict:
    """Mean FRE change from y0 to y1, split into sentence and word terms.

    Shares are percentages of the change and are undefined (inf or NaN) when
    the change is zero.
    """
    d = d[(d.year >= y0) & (d.year <= y1)]
    d = d[(d.sentence_count > 0) & (d.word_count > 0)].copy()
    d["asl"] = d.word_count / d.sentence_count
    d["asw"] = d.syllable_count / d.word_count
    d["fre"] = FRE_CONST + FRE_ASL * d.asl + FRE_ASW * d.asw

    a = d[d.year == y0][["asl", "asw", "fre"]].mean()
    b = d[d.year == y1][["asl", "asw", "fre"]].mean()
    d_fre = b.fre - a.fre
    sent = FRE_ASL * (b.asl - a.asl)
    word = FRE_ASW * (b.asw - a.asw)
    return {
        "corpus": name, "first_year": y0, "last_year": y1,
        "asl_first": a.asl, "asl_last": b.asl,
        "asw_first": a.asw, "asw_last": b.asw,
        "fre_first": a.fre, "fre_last": b.fre,
        "fre_change": d_fre,
        "sentence_term": sent, "word_term": word,
        "sentence_share": 100 * sent / d_fre,
        "word_share": 100 * word / d_fre,
        "residual": d_fre - sent - word,
    }


def flesch_decomposition(per_paper: str = PER_PAPER) -> pd.DataFrame:
    return pd.DataFrame([decompose(read_counts(venues, per_paper), name, y0, y1)
                         for name, venues, y0, y1 in SPECS])


def main() -> None:
    out = flesch_decomposition()
    print("Flesch decomposition")
    for _, r in out.iterrows():
        print(f"\n  {r.corpus} {int(r.first_year)} to {int(r.last_year)}: "
              f"{r.fre_first:.2f} -> {r.fre_last:.2f} ({r.fre_change:+.2f})")
        print(f"    words per sentence   {r.asl_first:6.2f} -> {r.asl_last:6.2f}"
              f"   contributes {r.sentence_term:+6.2f}  ({r.sentence_share:.0f}%)")
        print(f"    syllables per word   {r.asw_first:6.3f} -> {r.asw_last:6.3f}"
              f"   contributes {r.word_term:+6.2f}  ({r.word_share:.0f}%)")
        print(f"    residual {r.residual:+.6f}")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "flesch_decomposition.csv")
    out.to_csv(path, index=False)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
