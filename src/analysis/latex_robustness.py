#!/usr/bin/env python3
"""Does the readability decline survive LaTeX and URL normalisation?

The metric pipeline applies no normalisation for math markup or URLs:
abstracts reach textstat with both intact. Each tokenises as a long
many-syllable word, and the prevalence of each rises sharply over the
observation window, so either could manufacture part of the readability trend.

This script recomputes Flesch Reading Ease on the three conference corpora
under four normalisations (processing/text_cleaning.py) and writes a per-year
comparison. It only reads data/processed; nothing in the pipeline changes.

  keep      no normalisation, the pipeline's behaviour
  mathonly  LaTeX handled, URLs left in
  token     LaTeX and URLs handled, math replaced by a one-syllable token
  drop      as token, but math deleted

Writes:
  data/aggregate/latex_robustness.csv          one row per venue-year
  data/aggregate/latex_robustness_summary.csv  the numbers the TMLR paper
                                               quotes (Table tab:normalisation
                                               and Section 4), as name,value

    python src/analysis/latex_robustness.py
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

import pandas as pd
import textstat

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from processing.text_cleaning import clean_abstract  # noqa: E402

_D = os.environ.get("AA_DATA", "data")
PROCESSED = os.path.join(_D, "processed")
OUT = os.path.join(_D, "aggregate")

VENUES = ["neurips", "iclr", "icml"]
VARIANTS = ["keep", "mathonly", "token", "drop"]
MIN_WORDS = 10                          # matches readability.compute()


def flesch(text: str) -> float | None:
    if not text or len(text.split()) < MIN_WORDS:
        return None
    try:
        return textstat.flesch_reading_ease(text)
    except Exception:
        return None


def normalise(raw: str, variant: str) -> str:
    if variant == "keep":
        return raw
    if variant == "mathonly":
        return clean_abstract(raw, math="token", urls=False)
    return clean_abstract(raw, math=variant)


def year_row(venue: str, papers: list[dict]) -> dict:
    """Markup prevalence and mean Flesch under each normalisation, one year."""
    rec = {"venue": venue, "year": int(papers[0]["year"]), "n": len(papers)}
    rec["pct_with_math"] = 100.0 * sum(
        1 for p in papers if re.search(r"(?<!\\)\$", p.get("abstract") or "")
    ) / len(papers)
    rec["pct_with_url"] = 100.0 * sum(
        1 for p in papers if re.search(r"https?://|www\.", p.get("abstract") or "")
    ) / len(papers)
    for variant in VARIANTS:
        vals = [v for p in papers
                if (v := flesch(normalise(p.get("abstract") or "", variant))) is not None]
        rec[f"flesch_{variant}"] = sum(vals) / len(vals) if vals else None
        rec[f"n_scored_{variant}"] = len(vals)
    return rec


def summary(d: pd.DataFrame) -> pd.DataFrame:
    """The derived numbers the TMLR paper quotes.

    Per venue, first to last year: the decline in Flesch with no normalisation
    (raw) and with full normalisation (norm), and the share of the raw decline
    that markup, LaTeX alone, and URLs alone account for. Across venues: the
    smallest and largest markup share. NeurIPS markup prevalence: the mean of
    the annual math percentages before 2005, the 2025 math percentage, and the
    2014 and 2024 URL percentages. Over all venue-years: the mean level shift
    (token minus keep), the number of venue-years, and how many shifts are
    positive; and the NeurIPS shift in its first and last year.
    """
    rows: list[tuple[str, float]] = []
    shares = []
    for venue in VENUES:
        g = d[d.venue == venue].dropna(subset=["flesch_keep"]).sort_values("year")
        if g.empty:
            continue
        a, b = g.iloc[0], g.iloc[-1]
        dk = b.flesch_keep - a.flesch_keep
        dt = b.flesch_token - a.flesch_token
        dm = b.flesch_mathonly - a.flesch_mathonly
        rows += [(f"{venue}_first_year", a.year), (f"{venue}_last_year", b.year),
                 (f"{venue}_raw_decline", dk), (f"{venue}_norm_decline", dt),
                 (f"{venue}_latex_only_decline", dm),
                 (f"{venue}_markup_share_pct", 100 * (dk - dt) / dk),
                 (f"{venue}_latex_share_pct", 100 * (dk - dm) / dk),
                 (f"{venue}_url_share_pct", 100 * (dm - dt) / dk)]
        shares.append(100 * (dk - dt) / dk)
    rows += [("markup_share_min_pct", min(shares)), ("markup_share_max_pct", max(shares))]

    n = d[d.venue == "neurips"]
    rows += [("neurips_math_pct_mean_before_2005", n[n.year < 2005].pct_with_math.mean()),
             ("neurips_math_pct_2025", n[n.year == 2025].pct_with_math.iloc[0]),
             ("neurips_url_pct_2014", n[n.year == 2014].pct_with_url.iloc[0]),
             ("neurips_url_pct_2024", n[n.year == 2024].pct_with_url.iloc[0])]
    shift = d.flesch_token - d.flesch_keep
    rows += [("level_shift_mean", shift.mean()), ("venue_years", len(d)),
             ("level_shift_positive", int((shift > 0).sum()))]
    ng = n.dropna(subset=["flesch_keep"]).sort_values("year")
    rows += [("neurips_shift_first_year", ng.iloc[0].flesch_token - ng.iloc[0].flesch_keep),
             ("neurips_shift_last_year", ng.iloc[-1].flesch_token - ng.iloc[-1].flesch_keep)]
    return pd.DataFrame(rows, columns=["name", "value"])


def main() -> None:
    rows = []
    for venue in VENUES:
        files = sorted(glob.glob(os.path.join(PROCESSED, venue, "*.json")))
        if not files:
            print(f"  {venue}: no processed files, skipping")
            continue
        for path in files:
            with open(path, encoding="utf-8") as fh:
                papers = json.load(fh)
            if not papers:
                continue
            rec = year_row(venue, papers)
            rows.append(rec)
            print(f"  {venue} {rec['year']}: n={rec['n']:5d} math={rec['pct_with_math']:5.1f}% "
                  f"url={rec['pct_with_url']:5.1f}%  keep={rec['flesch_keep']:6.2f} "
                  f"mathonly={rec['flesch_mathonly']:6.2f} token={rec['flesch_token']:6.2f}")

    if not rows:
        # The pipeline run from the shipped per-paper metrics has no abstracts.
        print(f"  no processed abstracts under {PROCESSED}; skipping")
        return
    df = pd.DataFrame(rows).sort_values(["venue", "year"])
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, "latex_robustness.csv")
    df.to_csv(dest, index=False)
    print(f"\nwrote {dest}  ({len(df)} venue-years)")

    s = summary(df)
    dest = os.path.join(OUT, "latex_robustness_summary.csv")
    s.to_csv(dest, index=False)
    print(f"wrote {dest}")
    print(s.to_string(index=False))


if __name__ == "__main__":
    main()
