"""Check functions for the numbers printed in the TMLR paper.

paper/tmlr/claims.csv names one of these functions for every number the
manuscript prints (see check_claims.py for the format). None of them reads
the manuscript, except the self-audit's acronym count, which needs the
paper's own abstract ($AA_PAPER, see manuscript.py). Each function computes
its value from this repository's outputs only:

  $AA_DATA/pgfplots/tmlr/      per-venue yearly series, six columns with the
                               arXiv ML, arXiv non-ML and PubMed baselines
  $AA_DATA/aggregate/          aggregates, analyses, self_audit.csv
  $AA_DATA/aggregate/citations/  citation analyses (see below)
  $AA_DATA/per_paper/          per-paper metrics, where a claim needs them
  $AA_DATA/processed/          canonical records (authors per paper)
  $AA_DATA/raw/neurips/        only for the pre-2008 abstract fallback count
  $AA_DATA/tmlr/tables/        the generated tables (make_macros.py)
  shared/baselines/                   the arXiv and PubMed counts and histograms
  src/                         design constants the paper states

A function returns a number, a tuple of numbers (for a printed range or a
fraction such as "3 of the 4"), a string, or a bool. claims.csv says how
the returned value is compared with the printed one (its `rule`).

Citation claims. The Semantic Scholar counts are not distributed, and neither
is any statistic computed from them. The citation functions read
$AA_DATA/aggregate/citations/, which the citations stage computes from the
reader's own counts. check_claims.py compares them with the printed values in
strict citation mode (local counts equal the published snapshot), reports
them without counting them after a fresh fetch, and skips them when the
counts are absent.

Where the paper describes a rule in words rather than a number, the
function's docstring states the rule exactly, so that a
disagreement can be traced to either the data or the wording.
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
from collections import Counter
from functools import lru_cache

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

FIRST, LAST = 2015, 2025          # the paper's 2015 to 2025 window
CONFS = ["neurips", "iclr", "icml"]
ML = CONFS + ["arxiv_ml"]

# The 15 classical readability series and the direction in which each one
# means harder reading. Flesch Reading Ease is the only one where higher is
# easier. Mean sentence length and syllables per word are grade inputs: more
# is harder.
READABILITY = [
    "flesch_ease", "flesch_kincaid", "gunning_fog", "smog", "dale_chall",
    "spache", "coleman_liau", "ari", "linsear_write", "lix", "rix", "forcast",
    "powers_sumner_kearl", "avg_sentence_length", "avg_syllables_per_word",
]
HARDER_SIGN = {m: (-1 if m == "flesch_ease" else 1) for m in READABILITY}
# The twelve grade and difficulty formulas named in Section 3.1.
GRADE = [m for m in READABILITY
         if m not in ("flesch_ease", "avg_sentence_length", "avg_syllables_per_word")]

# The twelve style metrics of Section 3.3: eight Hohmann metrics (sensational
# language is reported apart) and four complexity measures, as pgfplots/tmlr
# file names.
STYLE = ["sentence_length", "signposting", "hedging", "noun_chunks",
         "active_narration", "verbs", "nouns", "numbers",
         "parse_depth", "np_density", "passive_rate", "ttr"]

REGISTRY: dict[str, "Check"] = {}


class Check:
    def __init__(self, fn, citation: bool, exempt: str | None = None,
                 paper: bool = False):
        self.fn, self.citation, self.name = fn, citation, fn.__name__
        self.exempt = exempt
        self.paper = paper

    def __call__(self, ctx, **kw):
        return self.fn(ctx, **kw)


def check(fn=None, *, citation: bool = False, exempt: str | None = None,
          paper: bool = False):
    """Register a check function. citation=True marks one that reads
    citation outputs (ctx.cit). exempt, when given, is the documented reason
    why an absent input may be skipped rather than failed (see
    check_claims.py, Missing inputs). paper=True marks one whose input
    derives from the manuscript (the self-audit): an absent input is skipped
    when no manuscript is given, and fails when one is. Every other check
    fails on an absent input."""
    def wrap(f):
        REGISTRY[f.__name__] = Check(f, citation, exempt, paper)
        return f
    return wrap(fn) if fn is not None else wrap


# ================================================================ context ===

class Ctx:
    """Where the outputs are, and the citation mode. Every file is read once."""

    def __init__(self, data: str, citation_mode: str = "absent",
                 repo: str = REPO, paper: str | None = None):
        self.data = data
        self.repo = repo
        self.citation_mode = citation_mode
        self.paper = paper          # the manuscript directory, or None

    # -- readers ---------------------------------------------------------
    @lru_cache(maxsize=None)
    def pg(self, name: str) -> pd.DataFrame:
        """pgfplots/tmlr/{name}.csv indexed by year."""
        df = pd.read_csv(os.path.join(self.data, "pgfplots", f"{name}.csv"))
        return df.set_index("year").sort_index()

    @lru_cache(maxsize=None)
    def agg(self, name: str) -> pd.DataFrame:
        return pd.read_csv(os.path.join(self.data, "aggregate", name))

    @property
    def cit_dir(self) -> str:
        return os.path.join(self.data, "aggregate", "citations")

    @lru_cache(maxsize=None)
    def cit(self, name: str) -> pd.DataFrame:
        return pd.read_csv(os.path.join(self.cit_dir, name))

    @lru_cache(maxsize=None)
    def base(self, name: str) -> pd.DataFrame:
        return pd.read_csv(os.path.join(self.repo, "shared", "baselines", name))

    @lru_cache(maxsize=None)
    def per_paper(self, family: str, venue: str) -> pd.DataFrame:
        return pd.read_csv(os.path.join(self.data, "per_paper", family, f"{venue}.csv"))

    def summary(self, key: str) -> float:
        s = self.agg("latex_robustness_summary.csv").set_index("name")["value"]
        return float(s[key])

    def value(self, metric: str, col: str, year: int) -> float:
        v = self.pg(metric).loc[int(year), col]
        if pd.isna(v):
            raise ValueError(f"{metric}.{col} has no value for {year}")
        return float(v)


def _list(x) -> list[str]:
    return x if isinstance(x, list) else [s for s in str(x).split("+") if s]


# ======================================================= yearly series ===

@check
def series(ctx, metric, col, year):
    """The value of one venue's yearly series (pgfplots/tmlr/{metric}.csv)."""
    return ctx.value(metric, col, year)


@check
def series_pair(ctx, metric, col, y0, y1):
    """(value in y0, value in y1) of one series."""
    return ctx.value(metric, col, y0), ctx.value(metric, col, y1)


@check
def series_cols_pair(ctx, metric, cols, year):
    """(minimum, maximum) over several venues in one year."""
    v = [ctx.value(metric, c, year) for c in _list(cols)]
    return min(v), max(v)


@check
def series_cols_min(ctx, metric, cols, year):
    """The minimum over several venues in one year."""
    return min(ctx.value(metric, c, year) for c in _list(cols))


@check
def series_cols_max(ctx, metric, cols, year):
    """The maximum over several venues in one year."""
    return max(ctx.value(metric, c, year) for c in _list(cols))


@check
def series_window(ctx, metric, col, y0, y1, stat):
    """min or max of one series over the years y0 to y1 inclusive."""
    s = ctx.pg(metric)[col].loc[int(y0):int(y1)].dropna()
    return float(s.min() if stat == "min" else s.max())


@check
def series_extreme(ctx, metric, cols, stat, what="value", last=None):
    """The maximum (stat=max) or minimum of every value of the venues in
    `cols`, through year `last` if given; what=year gives the year in which it
    occurs instead of the value."""
    df = ctx.pg(metric)
    if last is not None:
        df = df.loc[:int(last)]
    s = df[_list(cols)].stack()
    idx = s.idxmax() if stat == "max" else s.idxmin()
    return int(idx[0]) if what == "year" else float(s.loc[idx])


@check
def series_ratio(ctx, metric, col, y0, y1, den_col=None):
    """value(col, y1) / value(den_col or col, y0). With den_col and y0 == y1
    it compares two venues in one year."""
    return ctx.value(metric, col, y1) / ctx.value(metric, den_col or col, y0)


@check
def pct_above(ctx, metric, col, year, ref):
    """How far one value lies above a reference value, in percent:
    100 * (value / ref - 1)."""
    return 100.0 * (ctx.value(metric, col, year) / float(ref) - 1)


@check
def series_pct_change(ctx, metric, col, y0, y1):
    """Percentage change of one series from y0 to y1: 100 * (v1 / v0 - 1)."""
    return 100.0 * (ctx.value(metric, col, y1) / ctx.value(metric, col, y0) - 1)


@check
def series_fall(ctx, metric, col, y0=FIRST, y1=LAST):
    """value(y0) - value(y1): the points a series loses over the window."""
    return ctx.value(metric, col, y0) - ctx.value(metric, col, y1)


@check
def series_fall_range(ctx, metric, cols, y0=FIRST, y1=LAST):
    """(smallest, largest) fall over the window among the venues in `cols`."""
    f = [series_fall(ctx, metric, c, y0, y1) for c in _list(cols)]
    return min(f), max(f)


@check
def fall_ratio_range(ctx, metric="readability_flesch_ease", num="pubmed",
                     dens="neurips+iclr+icml", y0=FIRST, y1=LAST):
    """(min, max) over the venues in `dens` of fall(num) / fall(venue) over
    the window."""
    a = series_fall(ctx, metric, num, y0, y1)
    r = [a / series_fall(ctx, metric, d, y0, y1) for d in _list(dens)]
    return min(r), max(r)


@check
def gap_range(ctx, metric="readability_flesch_ease", controls="arxiv_nonml+pubmed",
              venues="neurips+iclr+icml", year=LAST):
    """(min, max) over venues of the distance below the nearer control in
    one year: each conference sits between min and max points below both."""
    g = []
    for v in _list(venues):
        x = ctx.value(metric, v, year)
        g.append(min(ctx.value(metric, c, year) for c in _list(controls)) - x)
    return min(g), max(g)


@check
def below_controls(ctx, metric="readability_flesch_ease", venues="neurips+iclr+icml+arxiv_ml",
                   controls="arxiv_nonml+pubmed", year=LAST):
    """True when every venue in `venues` sits below every control in
    `controls` in one year."""
    return all(ctx.value(metric, v, year) < ctx.value(metric, c, year)
               for v in _list(venues) for c in _list(controls))


@check
def all_below(ctx, metric, cols, bound):
    """The largest value any venue in `cols` takes in any year; compared with
    a bound the paper says every venue stays inside."""
    return float(ctx.pg(metric)[_list(cols)].max().max())


def _window(df: pd.DataFrame, col: str, last: int = LAST) -> pd.DataFrame:
    return df.loc[:last][[col]].dropna()


@check
def slope(ctx, metric, col, window_of=None, last=LAST):
    """OLS slope (points per year) of one series over the years through
    `last` in which venue `window_of` (default: col itself) has a value. The
    control's slope over a venue's own window uses window_of=venue; the
    years the control lacks in that window are left out."""
    df = ctx.pg(metric)
    years = df.loc[:int(last)][window_of or col].dropna().index
    s = df.loc[years, col].dropna()
    return float(np.polyfit(s.index.values.astype(float), s.values, 1)[0])


@check
def slope_ratio(ctx, metric, col, control, last=LAST):
    """slope(col) / slope(control over col's window)."""
    return slope(ctx, metric, col, last=last) / slope(ctx, metric, control, col, last)


@check
def steepest_fall_year(ctx, metric="readability_flesch_ease", cols="neurips+iclr+icml"):
    """The earliest, over venues, of the year in which each venue's largest
    single year-over-year fall happens. The paper's claim that every
    venue's steepest fall comes after 2022 holds when this exceeds 2022."""
    years = []
    for c in _list(cols):
        d = ctx.pg(metric)[c].dropna().diff()
        years.append(int(d.idxmin()))
    return min(years)


def _slope(s: pd.Series, y0, y1) -> float:
    """OLS slope per year of a yearly series over y0..y1 inclusive (years
    without a value left out)."""
    s = s.loc[int(y0):int(y1)].dropna()
    if len(s) < 2:
        raise ValueError(f"fewer than two years in {y0}..{y1}")
    return float(np.polyfit(s.index.values.astype(float), s.values, 1)[0])


@check
def rises_over(ctx, metric, col, y0, y1):
    """True when the OLS slope of one series over y0..y1 is positive."""
    return _slope(ctx.pg(metric)[col], y0, y1) > 0


@check
def inflection(ctx, metrics, venues, split, before, after=LAST):
    """True when, for every metric and venue, the OLS slope over split..after
    exceeds the slope over before..split: an inflection at `split` (the
    trend steepens there). For example inflection(acronym density in titles
    and abstracts, sensational total; the four ML venues; split 2022, before
    2015). The magnitude is not part of the rule; where the
    paper quantifies it, that number has its own row."""
    for m in _list(metrics):
        df = ctx.pg(m)
        for v in _list(venues):
            if not _slope(df[v], split, after) > _slope(df[v], before, split):
                return False
    return True


@check
def divergence_accelerates(ctx, metric, split=2022, before=FIRST, after=LAST,
                           ml="neurips+iclr+icml+arxiv_ml", control="arxiv_nonml"):
    """True when the ML minus non-ML gap widens faster after `split` than
    before it: gap(y) = mean of the ML venues in y minus the control in y,
    and the OLS slope of gap over split..after exceeds that over
    before..split."""
    df = ctx.pg(metric)
    gap = df[_list(ml)].mean(axis=1) - df[control]
    return _slope(gap, split, after) > _slope(gap, before, split)


@check
def comoves(ctx, falling="readability_flesch_ease",
            rising="acronyms_abstract+acronyms_title", venue="neurips"):
    """True when, over a venue's years, papers per year has a negative
    Spearman correlation with every series in `falling` and a positive one
    with every series in `rising`: paper volume, readability and acronym density
    trends move together."""
    n = ctx.pg("papers_per_year")[venue]
    for m, sign in [(m, -1) for m in _list(falling)] + [(m, 1) for m in _list(rising)]:
        j = pd.concat([n, ctx.pg(m)[venue]], axis=1).dropna()
        if not sign * j.corr(method="spearman").iloc[0, 1] > 0:
            return False
    return True


# ======================================================= readability ===

def _change(ctx, m, v, y0=FIRST, y1=LAST):
    return ctx.value(f"readability_{m}", v, y1) - ctx.value(f"readability_{m}", v, y0)


@check
def readability_harder(ctx, venues="neurips+iclr+icml", y0=FIRST, y1=LAST, what="count"):
    """Count of the 15 readability formulas whose change points to harder reading from
    y0 to y1 at every venue in `venues`, as (count, 15).

    The harder direction is the sign of value(y1) - value(y0) times HARDER_SIGN: Flesch
    Reading Ease falling, every other series rising. what=other gives the
    number of metrics that do not (15 - count); what=total gives 15."""
    vs = _list(venues)
    n = sum(1 for m in READABILITY
            if all(HARDER_SIGN[m] * _change(ctx, m, v, y0, y1) > 0 for v in vs))
    if what == "other":
        return len(READABILITY) - n
    if what == "total":
        return len(READABILITY)
    if what == "n":
        return n
    return n, len(READABILITY)


@check
def grade_harder_all(ctx, venues="neurips+arxiv_ml", y0=FIRST, y1=LAST):
    """True when every grade and difficulty formula (GRADE) moves toward
    harder reading from y0 to y1 at every venue in `venues`."""
    return all(HARDER_SIGN[m] * _change(ctx, m, v, y0, y1) > 0
               for m in GRADE for v in _list(venues))


@check
def acceleration_exceptions(ctx, venues="neurips+iclr+icml+arxiv_ml", split=2020):
    """The number of (metric, venue) pairs, over the twelve grade and
    difficulty formulas (GRADE) and the four ML venues, that do not
    accelerate after `split`.

    A pair accelerates when its change from `split` to 2025 exceeds its
    change from 2015 to `split`, both measured in the harder direction (the
    endpoint values of the yearly series). With the paper's data only SMOG on
    ICLR fails (+0.72 then +0.67); Linsear Write on ICML accelerates (-0.07
    then +0.26). The paper names two exceptions."""
    n = 0
    for m in GRADE:
        for v in _list(venues):
            a = HARDER_SIGN[m] * _change(ctx, m, v, FIRST, split)
            b = HARDER_SIGN[m] * _change(ctx, m, v, split, LAST)
            if not b > a:
                n += 1
    return n


@check
def collinearity(ctx, venue, col, scale=1.0):
    """A column of aggregate/readability_collinearity.csv, times `scale`."""
    df = ctx.agg("readability_collinearity.csv").set_index("venue")
    return float(df.loc[venue, col]) * float(scale)


@check
def latex_summary(ctx, key):
    """A value of aggregate/latex_robustness_summary.csv."""
    return ctx.summary(key)


@check
def latex_summary_pair(ctx, keys):
    """Two values of aggregate/latex_robustness_summary.csv, as a printed
    range, for example (markup_share_min_pct,
    markup_share_max_pct), each compared at the printed precision (whole
    percent). latex_robustness.py computes the shares; the caption phrase
    make_macros.py writes is not used."""
    a, b = _list(keys)
    return ctx.summary(a), ctx.summary(b)


@check
def collinearity_one_signal(ctx, threshold=0.5):
    """True when the first principal component of the 15 standardised
    readability metrics carries more than `threshold` of their variance at
    every venue (aggregate/readability_collinearity.csv).

    The rule is a majority of the variance on one component. By the Kaiser
    criterion (eigenvalue above 1) a second component also qualifies: it
    carries about 17 percent of 15 units of variance, an eigenvalue near 2.5,
    consistent with two underlying surface quantities."""
    df = ctx.agg("readability_collinearity.csv")
    return bool((df.pc1_var_explained > float(threshold)).all())


# ======================================================== style suite ===

def _style_gaps(ctx) -> dict[str, float]:
    """Change from 2015 to 2025 in the difference between ML venues and the control, per style metric,
    in units of the metric's own standard deviation.

    ML is the mean of NeurIPS, ICLR, ICML and arXiv ML in a year, non-ML is
    arXiv non-ML. gap(y) = ML(y) - nonML(y). The change is
    |gap(2025)| - |gap(2015)|, positive when the gap widens. The metric's
    standard deviation is that of every value in its six-column yearly file
    (pgfplots/tmlr/{metric}.csv, all venues and years, sample SD)."""
    out = {}
    for m in STYLE:
        df = ctx.pg(m)
        sd = float(df[["neurips", "iclr", "icml", "arxiv_ml", "arxiv_nonml", "pubmed"]]
                   .stack().std())

        def gap(y):
            return float(df.loc[y, ML].mean() - df.loc[y, "arxiv_nonml"])

        out[m] = (abs(gap(LAST)) - abs(gap(FIRST))) / sd
    return out


@check
def style_gap_count(ctx, kind, threshold=0.5):
    """How many of the twelve style metrics widen the gap clearly (change >
    threshold SD), marginally (0 < change <= threshold) or narrow
    (change < 0); kind=total gives twelve. See _style_gaps for the gap."""
    g = _style_gaps(ctx)
    if kind == "total":
        return len(g)
    if kind == "clear":
        return sum(1 for v in g.values() if v > threshold)
    if kind == "marginal":
        return sum(1 for v in g.values() if 0 < v <= threshold)
    return sum(1 for v in g.values() if v < 0)


@check
def style_gap_set(ctx, kind, threshold=0.5):
    """The metrics (sorted, joined with +) that widen the gap clearly, or
    that narrow it; see style_gap_count."""
    g = _style_gaps(ctx)
    if kind == "clear":
        sel = [m for m, v in g.items() if v > threshold]
    else:
        sel = [m for m, v in g.items() if v < 0]
    return "+".join(sorted(sel))


@check
def style_suite_size(ctx):
    """The number of style series the release exports (STYLE, all present)."""
    return sum(1 for m in STYLE if os.path.exists(
        os.path.join(ctx.data, "pgfplots", f"{m}.csv")))


@check
def pubmed_style_metrics(ctx):
    """How many of the twelve style series carry any PubMed value."""
    return sum(1 for m in STYLE if ctx.pg(m)["pubmed"].notna().any())


# ============================================================ corpus ===

@check
def corpus_size(ctx, group, last=LAST, unit=1):
    """Papers in a corpus, divided by `unit` (1e6 for a count printed in millions). Conferences: the sum of papers per year
    (pgfplots/tmlr/papers_per_year.csv). arxiv: arXiv ML and non-ML records
    (shared/baselines/papers_per_year.csv). pubmed: PubMed records dated through
    `last` (the cleaned-record count, shared/baselines/papers_per_year.csv)."""
    if group in CONFS:
        n = int(ctx.pg("papers_per_year")[group].sum())
    else:
        b = ctx.base("papers_per_year.csv").set_index("year")
        if group == "arxiv":
            n = int(b[["arxiv_ml", "arxiv_nonml"]].sum().sum())
        elif group == "arxiv_ml":
            n = int(b["arxiv_ml"].sum())
        elif group == "pubmed":
            n = int(b.loc[:int(last), "pubmed_records"].sum())
        else:
            raise ValueError(group)
    return n / float(unit) if float(unit) != 1 else n


@check
def corpus_years(ctx, group, last=None):
    """(first, last) year with at least one paper. arxiv and pubmed from
    shared/baselines/papers_per_year.csv (PubMed cut at 2025 as in every analysis)."""
    if group in CONFS:
        s = ctx.pg("papers_per_year")[group]
    else:
        b = ctx.base("papers_per_year.csv").set_index("year")
        s = (b["arxiv_ml"].fillna(0) + b["arxiv_nonml"].fillna(0)) if group == "arxiv" \
            else b[group if group != "pubmed" else "pubmed_records"]
        if group == "pubmed":
            s = s.loc[:LAST]
    yrs = s[s.fillna(0) > 0].index
    if last is not None:
        yrs = yrs[yrs <= int(last)]
    return int(yrs.min()), int(yrs.max())


@check
def conf_span(ctx, what="pair"):
    """(first, last) year covered by any of the three conferences: the
    x range of the conference figures."""
    df = ctx.pg("papers_per_year")[CONFS]
    yrs = df[(df.fillna(0) > 0).any(axis=1)].index
    first, last = int(yrs.min()), int(yrs.max())
    return {"first": first, "last": last}.get(what, (first, last))


@check
def corpus_first_year(ctx, group):
    return corpus_years(ctx, group)[0]


@check
def corpus_last_year(ctx, group):
    return corpus_years(ctx, group)[1]


@check
def papers(ctx, group, year):
    """Papers in one year. arxiv_all: arXiv ML plus non-ML."""
    if group in CONFS:
        return float(ctx.pg("papers_per_year").loc[int(year), group])
    b = ctx.base("papers_per_year.csv").set_index("year")
    if group == "arxiv_all":
        return float(np.nansum([b.loc[int(year), "arxiv_ml"], b.loc[int(year), "arxiv_nonml"]]))
    if group == "pubmed":
        return float(b.loc[int(year), "pubmed_records"])
    return float(b.loc[int(year), group])


@check
def papers_ratio(ctx, group, y0, y1, log10=False):
    """papers(y1) / papers(y0); with log10 the orders of magnitude."""
    r = papers(ctx, group, y1) / papers(ctx, group, y0)
    return math.log10(r) if str(log10).lower() in ("1", "true") else r


@check
def papers_min(ctx, groups, year):
    """The smallest annual count among `groups` in one year."""
    return min(papers(ctx, g, year) for g in _list(groups))


@check
def arxiv_year_fraction(ctx, key="cutoff_year_fraction"):
    """The share of calendar year 2025 the arXiv snapshot covers, from its
    cutoff (shared/baselines/arxiv_snapshot.json, written by
    src/baselines/arxiv_snapshot.py from the last arXiv identifier).
    key=cutoff_year_fraction_min or _max gives the bounds the month
    of the last identifier alone allows."""
    with open(os.path.join(ctx.repo, "shared", "baselines", "arxiv_snapshot.json")) as fh:
        return float(json.load(fh)[key])


@check
def pubmed_ahead_of_print(ctx):
    """PubMed records dated after 2025 (ahead-of-print)."""
    b = ctx.base("papers_per_year.csv").set_index("year")
    return int(b.loc[LAST + 1:, "pubmed_records"].sum())


@check
def pubmed_ahead_years(ctx, stat):
    """First (stat=min) or last year of the ahead-of-print PubMed records."""
    b = ctx.base("papers_per_year.csv").set_index("year")
    s = b.loc[LAST + 1:, "pubmed_records"]
    yrs = s[s > 0].index
    return int(yrs.min() if stat == "min" else yrs.max())


@check
def mean_authors(ctx, venue, year):
    """Mean number of authors per paper in processed/{venue}/{venue}_{year}.json."""
    with open(os.path.join(ctx.data, "processed", venue, f"{venue}_{int(year)}.json")) as fh:
        recs = json.load(fh)
    return float(np.mean([len(r.get("authors") or []) for r in recs]))


@check
def mean_authors_ratio(ctx, venue, y0, y1):
    return mean_authors(ctx, venue, y1) / mean_authors(ctx, venue, y0)


RAW_EXEMPT = ("raw scrape absent: the count re-reads data/raw/neurips, which "
              "the --from aggregate route does not have; no series or table "
              "depends on it")


@check(exempt=RAW_EXEMPT)
def neurips_fallback_count(ctx, max_year=None):
    """NeurIPS records whose abstract comes from the full-text fallback of
    process_neurips.best_abstract: the abstract field, after an unavailable-abstract
    marker is cleared, has fewer than 20 words and the full
    text has at least 20. Counted over every year (max_year limits it).
    Needs the raw scrape in $AA_DATA/raw/neurips/."""
    from processing.process_neurips import sanitize_text
    paths = sorted(glob.glob(os.path.join(ctx.data, "raw", "neurips", "neurips_*_data.json")))
    if not paths:
        raise FileNotFoundError("raw/neurips (the NeurIPS scrape)")
    n = 0
    for p in paths:
        year = int(re.search(r"neurips_(\d{4})_data", p).group(1))
        if max_year is not None and year > int(max_year):
            continue
        with open(p, encoding="utf-8") as fh:
            for r in json.load(fh):
                if not sanitize_text(r.get("title") or ""):
                    continue
                a = sanitize_text(r.get("abstract") or "")
                if a.lower().startswith("abstract unavailable"):
                    a = ""
                if len(a.split()) < 20 and len(sanitize_text(r.get("full_text") or "").split()) >= 20:
                    n += 1
    return n


@check
def title_words(ctx, venues="neurips+iclr+icml", y0=FIRST, y1=LAST):
    """Mean title word count over the papers of the venues, y0 to y1."""
    w = []
    for v in _list(venues):
        df = ctx.per_paper("acronyms", v)
        w.append(df[(df.year >= int(y0)) & (df.year <= int(y1))]["title_word_count"])
    return float(pd.concat(w).mean())


# =========================================================== acronyms ===

def _reuse_shares(ctx) -> dict[str, float]:
    """Share (percent) of distinct abstract acronyms used fewer than ten
    times, unrounded. Conferences from the per-paper acronym lists (all
    years, as acronym_reuse.py counts them); arXiv ML, arXiv non-ML and PubMed
    from shared/baselines/acronym_histograms.csv; B&D from acronym_reuse.BD_BASELINE."""
    from analysis.acronym_reuse import BD_BASELINE
    out = {}
    for v in CONFS:
        c = Counter(a for s in ctx.per_paper("acronyms", v)["abstract_acronyms"].fillna("")
                    for a in str(s).split("|") if a)
        out[v] = 100.0 * sum(1 for n in c.values() if n < 10) / len(c)
    h = ctx.base("acronym_histograms.csv")
    for g, d in h.groupby("group"):
        out[g] = 100.0 * d.loc[d.occurrences < 10, "acronym_types"].sum() / d.acronym_types.sum()
    out["bd"] = BD_BASELINE["1"] + BD_BASELINE["2--9"]
    return out


@check
def reuse_share(ctx, group):
    """Percent of distinct abstract acronyms used fewer than ten times, for
    one group (neurips, iclr, icml, arxiv_ml, arxiv_nonml, pubmed, bd)."""
    return _reuse_shares(ctx)[group]


@check
def reuse_share_range(ctx, groups="neurips+iclr+icml+arxiv_ml"):
    """(min, max) of reuse_share over groups."""
    s = _reuse_shares(ctx)
    v = [s[g] for g in _list(groups)]
    return min(v), max(v)


@check
def reuse_gap(ctx, groups="neurips", base="bd"):
    """Mean reuse_share over `groups` minus that of `base`, in percentage
    points."""
    s = _reuse_shares(ctx)
    return float(np.mean([s[g] for g in _list(groups)])) - s[base]


REUSE_ROWS = {"neurips": "NeurIPS", "iclr": "ICLR", "icml": "ICML",
              "arxiv_ml": "arXiv ML", "arxiv_nonml": "arXiv non-ML",
              "pubmed": "PubMed", "bd": "B\\&D (2020)"}


@check
def reuse_table(ctx, group, col):
    """One cell of aggregate/acronym_reuse_freq.csv (the table the analysis
    stage writes): row `group`, column n_unique, 1, 2--9, 10--99, 100--999
    or 1000+."""
    df = ctx.agg("acronym_reuse_freq.csv").set_index("venue")
    return float(df.loc[REUSE_ROWS[group], col])


@check
def reuse_bucket_range(ctx, groups, col):
    """(min, max) of one bucket of the reuse table over groups."""
    v = [reuse_table(ctx, g, col) for g in _list(groups)]
    return min(v), max(v)


@check
def acronym_robustness(ctx, col):
    """A column of aggregate/acronym_robustness.csv (NeurIPS 2025)."""
    return float(ctx.agg("acronym_robustness.csv").iloc[0][col])


@check
def acronym_robustness_pair(ctx, cols):
    """Two columns of aggregate/acronym_robustness.csv: with and without the
    common terms."""
    a, b = _list(cols)
    return acronym_robustness(ctx, a), acronym_robustness(ctx, b)


@check
def robust_above_control(ctx, year=LAST):
    """True when NeurIPS title and abstract acronym density without the
    common terms (acronym_robustness.csv) still exceed the arXiv non-ML
    density of the same year."""
    return (acronym_robustness(ctx, "title_density_excl")
            > ctx.value("acronyms_title", "arxiv_nonml", year)
            and acronym_robustness(ctx, "abstract_density_excl")
            > ctx.value("acronyms_abstract", "arxiv_nonml", year))


@check
def common_terms(ctx):
    """The number of established community acronyms excluded in the
    robustness check (acronym_robustness.COMMON)."""
    from analysis.acronym_robustness import COMMON
    return len(COMMON)


# ========================================================== LLM judge ===

def _judge(ctx, venue, prompt) -> pd.Series:
    name = (f"llm_scores_model_avg_{prompt}" if venue == "neurips"
            else f"llm_scores_model_avg_{venue}_{prompt}")
    return ctx.pg(name)["avg_z"]


PROMPTS = ["simple", "ascb", "own_reasoning"]


@check
def judge_last(ctx, venues="neurips", stat="pair"):
    """The six-model average z-score in each venue's last scored year, over
    the three prompts: (min, max), or one of them with stat=min/max."""
    v = []
    for venue in _list(venues):
        for p in PROMPTS:
            s = _judge(ctx, venue, p).dropna()
            v.append(float(s.iloc[-1]))
    if stat == "min":
        return min(v)
    if stat == "max":
        return max(v)
    return min(v), max(v)


@check
def judge_years(ctx, venue, what="last"):
    """First or last year of a venue's judge series (all prompts agree)."""
    yrs = {(int(_judge(ctx, venue, p).dropna().index.min()),
            int(_judge(ctx, venue, p).dropna().index.max())) for p in PROMPTS}
    if len(yrs) != 1:
        raise ValueError(f"prompts disagree on the {venue} years: {yrs}")
    first, last = yrs.pop()
    return first if what == "first" else last


@check
def judge_baseline(ctx, venue):
    """(first year, last baseline year) of a venue's judge standardisation:
    its first scored year and the baseline end in aggregate_llm_model_avg."""
    return judge_years(ctx, venue, "first"), baseline_end(ctx)


@check
def judge_has_year(ctx, venue, year):
    """year if the venue's judge series has it, else the last scored year
    (so a statement that a year is absent compares it with the last year)."""
    return judge_years(ctx, venue, "last")


@check
def judge_span_decades(ctx, venue="neurips"):
    """(last - first scored year) / 10, in decades."""
    return (judge_years(ctx, venue, "last") - judge_years(ctx, venue, "first")) / 10


@check
def judge_n_models(ctx):
    """Models averaged in every judge series (the n_models column)."""
    n = set()
    for venue in CONFS:
        for p in PROMPTS:
            name = (f"llm_scores_model_avg_{p}" if venue == "neurips"
                    else f"llm_scores_model_avg_{venue}_{p}")
            n |= set(ctx.pg(name)["n_models"].dropna().astype(int))
    if len(n) != 1:
        raise ValueError(f"n_models differs across series: {n}")
    return n.pop()


@check
def judge_rises_after(ctx, venues="neurips+icml", split=2022, ratio=10):
    """True when the six-model average rises steeply after `split` at every
    venue in `venues`, for each of the three prompts: the final scored year
    exceeds every year up to `split`, and the OLS slope over split..last is
    positive and at least `ratio` times the absolute slope over first..split.
    With the paper's data the post-2022 slope is 11 to 120 times the
    baseline slope."""
    for venue in _list(venues):
        for p in PROMPTS:
            s = _judge(ctx, venue, p).dropna()
            last = int(s.index.max())
            pre, post = _slope(s, s.index.min(), split), _slope(s, split, last)
            if not (s.iloc[-1] > s.loc[:int(split)].max() and post > 0
                    and post >= float(ratio) * abs(pre)):
                return False
    return True


def _judge_post_change(ctx, venue, split) -> list[float]:
    out = []
    for p in PROMPTS:
        s = _judge(ctx, venue, p).dropna()
        out.append(float(s.iloc[-1] - s.loc[int(split)]))
    return out


@check
def judge_post_small(ctx, venue="iclr", compare="neurips+icml", split=2022):
    """True when a venue's post-`split` movement is small: the largest
    absolute change from `split` to its last scored year, over the three
    prompts, is below the smallest such change at the venues in `compare`."""
    own = max(abs(x) for x in _judge_post_change(ctx, venue, split))
    other = min(x for v in _list(compare) for x in _judge_post_change(ctx, v, split))
    return own < other


@check
def judge_post_unsettled(ctx, venue="iclr", split=2022):
    """True when a venue's post-`split` judge series has no consistent
    direction across the prompts: for every prompt the yearly
    series from `split` on both rises and falls (it is not monotone), and the
    change from `split` to the last year does not have one sign across the
    prompts."""
    for p in PROMPTS:
        d = _judge(ctx, venue, p).dropna().loc[int(split):].diff().dropna()
        if (d > 0).all() or (d < 0).all():
            return False
    signs = {np.sign(x) for x in _judge_post_change(ctx, venue, split)}
    return len(signs) > 1


@check
def judge_prompts(ctx):
    """The number of prompt templates in src/metrics/llm_scores.py."""
    from metrics.llm_scores import PROMPTS as P
    return len(P)


def _source(ctx, rel) -> str:
    with open(os.path.join(ctx.repo, rel), encoding="utf-8") as fh:
        return fh.read()


@check
def code_constant(ctx, path, pattern):
    """A number stated in the code: the first group of `pattern` in the file
    at `path` (repository-relative)."""
    m = re.search(pattern, _source(ctx, path))
    if not m:
        raise ValueError(f"{pattern!r} not found in {path}")
    return float(m.group(1))


@check
def iclr_dataset_years(ctx):
    """(first, last) year of ICLR read from the ICLR dataset
    (src/scraping/fetch_iclr_dataset.YEARS)."""
    m = re.search(r"YEARS = list\(range\((\d{4}), (\d{4})\)\)",
                  _source(ctx, "src/scraping/fetch_iclr_dataset.py"))
    if not m:
        raise ValueError("YEARS not found in fetch_iclr_dataset.py")
    return int(m.group(1)), int(m.group(2)) - 1


@check
def baseline_end(ctx):
    """The last year of the judge standardisation baseline, from
    aggregate_llm_model_avg.py."""
    return int(code_constant(ctx, "src/aggregate/aggregate_llm_model_avg.py",
                             r'result\["year"\] <= (\d{4})'))


@check
def arxiv_ml_categories(ctx):
    """The number of arXiv primary categories counted as ML."""
    from arxiv_categories import ARXIV_ML_CATEGORIES
    return len(ARXIV_ML_CATEGORIES)


@check
def schema_fields(ctx):
    """Fields of the canonical Pydantic schema (src/validate.py)."""
    from validate import ProcessedPaper
    return len(ProcessedPaper.model_fields)


@check
def hype_categories(ctx):
    """Sensational language categories in _narrator_utils.HYPE_CATEGORIES."""
    from metrics._narrator_utils import HYPE_CATEGORIES
    return len(HYPE_CATEGORIES)


@check
def hype_shared_words(ctx, what="words"):
    """Words listed in more than one sensational category: their number, or
    (what=categories) the most categories any of them is in."""
    from metrics._narrator_utils import HYPE_CATEGORIES
    c = Counter(w for words in HYPE_CATEGORIES.values() for w in set(words))
    shared = {w: n for w, n in c.items() if n > 1}
    return len(shared) if what == "words" else max(shared.values())


# ========================================================= self-audit ===

PAPER_EXEMPT = ("the self-audit measures the paper's own abstract, which is not "
                "distributed; set AA_PAPER and rerun the self_audit stage")


@check(paper=True)
def self_audit(ctx, metric, col="abstract"):
    """One cell of aggregate/self_audit.csv (metric row, column abstract,
    title or percentile)."""
    df = ctx.agg("self_audit.csv").set_index("metric")
    return float(df.loc[metric, col])


@check(paper=True)
def self_audit_family_size(ctx, family):
    """Rows of one family in aggregate/self_audit.csv."""
    return int((ctx.agg("self_audit.csv")["family"] == family).sum())


@check(paper=True)
def self_audit_acronyms(ctx, field="abstract"):
    """Distinct acronyms acronyms.py finds in the audited title or abstract,
    read from the manuscript ($AA_PAPER/main.tex) as the self_audit stage
    reads them (audit_self.read_from_tex)."""
    import metrics.acronyms as acronyms
    from metrics.audit_self import read_from_tex
    if ctx.paper is None:
        raise FileNotFoundError("the manuscript ($AA_PAPER/main.tex)")
    title, abstract = read_from_tex(os.path.join(ctx.paper, "main.tex"))
    row = acronyms.compute_row({"paper_id": "audit", "venue": "neurips", "year": 0,
                                "title": title, "abstract": abstract})
    return len({a for a in (row.get(f"{field}_acronyms") or "").split("|") if a})


@check
def per_paper_count(ctx, family="readability", venue="neurips"):
    """Rows of one per-paper metric file: the reference distribution size."""
    return len(ctx.per_paper(family, venue))


# ============================================================ topics ===

@check
def topic_families_all_same(ctx, what="same"):
    """Of the four topic-trend families (Flesch, sensational, abstract and
    title acronym density), how many move the same way in every topic
    (what=same) or not (what=other), from aggregate/topic_trends.csv: a
    topic moves the same way when its change has the field-wide sign."""
    df = ctx.agg("topic_trends.csv")
    fam = {"flesch": -1, "hype": 1, "acr_abstract": 1, "acr_title": 1}
    same = 0
    for f, sign in fam.items():
        col = f"{f}_change"
        if col not in df.columns:
            raise ValueError(f"topic_trends.csv has no {col}")
        if (np.sign(df[col]) == sign).all():
            same += 1
    return same if what == "same" else len(fam) - same


@check
def topics_all_move(ctx, families="flesch+hype+acr_abstract"):
    """True when every topic in aggregate/topic_trends.csv moves the
    field-wide way in each family: Flesch falls, sensational language and
    acronym density rise, in every topic."""
    df = ctx.agg("topic_trends.csv")
    sign = {"flesch": -1, "hype": 1, "acr_abstract": 1, "acr_title": 1}
    return all(bool((np.sign(df[f"{f}_change"]) == sign[f]).all()) for f in _list(families))


@check
def n_topics(ctx):
    """Topics in aggregate/topic_trends.csv."""
    return len(ctx.agg("topic_trends.csv"))


# ========================================================= citations ===

@check(citation=True)
def cit_value(ctx, file, col, key=None, keycol=None, scale=1.0, absval=False):
    """One cell of a citation output: the row whose `keycol` equals `key`
    (or the first row), column `col`, times `scale`; absval takes |value|."""
    df = ctx.cit(file)
    row = df.iloc[0] if key is None else df[df[keycol].astype(str) == str(key)].iloc[0]
    v = float(row[col]) * float(scale)
    return abs(v) if str(absval).lower() in ("1", "true") else v


@check(citation=True)
def cit_pair(ctx, file, cols, key=None, keycol=None):
    """Two cells of one citation row: a confidence interval."""
    a, b = _list(cols)
    return (cit_value(ctx, file, a, key, keycol), cit_value(ctx, file, b, key, keycol))


@check(citation=True)
def cit_coverage_range(ctx):
    """(min, max) citation coverage (percent) over the venues, through the
    last citation year."""
    c = ctx.cit("citation_coverage.csv")["coverage_pct"]
    return float(c.min()), float(c.max())


@check(citation=True)
def cit_max_year(ctx):
    """The last year of the citation analyses (citation_coverage.csv)."""
    y = set(ctx.cit("citation_coverage.csv")["max_year"].astype(int))
    if len(y) != 1:
        raise ValueError(f"venues differ in max_year: {y}")
    return y.pop()


@check(citation=True)
def cit_easier_count(ctx, what="count"):
    """Of the 15 metrics in the top/bottom decile table, how many are better
    for the top-cited decile (delta > 0 for Flesch Reading Ease, delta < 0
    for the rest), as (count, 15); what=other gives 15 - count."""
    df = ctx.cit("citation_readability_top_bottom_combined.csv")
    better = [(d > 0) if m == "flesch_ease" else (d < 0)
              for m, d in zip(df.metric, df.delta)]
    n = int(sum(better))
    if what == "other":
        return len(df) - n
    return n, len(df)


@check(citation=True)
def cit_table(ctx, file, key, col, keycol="metric", key2=None, keycol2=None, absval=False):
    """One cell of a citation table CSV, matched on one or two key columns."""
    df = ctx.cit(file)
    sel = df[keycol].astype(str) == str(key)
    if key2 is not None:
        sel &= df[keycol2].astype(str) == str(key2)
    v = float(df[sel].iloc[0][col])
    return abs(v) if str(absval).lower() in ("1", "true") else v


@check(citation=True)
def cit_llm_delta_range(ctx):
    """(min, max) top minus bottom LLM judge gap over venues and prompts."""
    d = ctx.cit("citation_llm_top_bottom_combined.csv")["delta"]
    return float(d.min()), float(d.max())


@check(citation=True)
def cit_topic_ks(ctx, what="positive"):
    """Topic counts k of the topic-controlled regressions; what=positive
    gives only those whose interval lies above zero, joined with +."""
    df = ctx.cit("citation_regression_topics.csv")
    df = df[df.n_topic_dummies > 0]
    ks = [int(re.search(r"k=(\d+)", m).group(1)) for m in df.model]
    if what == "positive":
        ks = [k for k, lo in zip(ks, df.ci_lo) if lo > 0]
    return "+".join(str(k) for k in sorted(ks))


@check(citation=True)
def cit_topic_k_member(ctx, k):
    """k if a topic-controlled regression at k topics has a positive
    interval, else 0."""
    return int(k) if str(k) in cit_topic_ks(ctx).split("+") else 0


@check(citation=True)
def cit_r2_ratio(ctx):
    """Smallest ratio of the within R^2 with topic controls to that
    without."""
    df = ctx.cit("citation_regression_topics.csv")
    r0 = float(df[df.n_topic_dummies == 0].r2_within.iloc[0])
    return float(df[df.n_topic_dummies > 0].r2_within.min()) / r0


@check(citation=True)
def cit_composition_share(ctx):
    """Mean over the topic counts of (b0 - bk) / b0, the share of the
    no-topic coefficient that topic controls remove."""
    df = ctx.cit("citation_regression_topics.csv")
    b0 = float(df[df.n_topic_dummies == 0].beta_flesch.iloc[0])
    return float(np.mean([(b0 - b) / b0 for b in df[df.n_topic_dummies > 0].beta_flesch]))


@check(citation=True)
def cit_min_ci_lo(ctx):
    """Smallest lower interval bound over the pooled and per-venue
    regressions: every interval excludes zero when it is positive."""
    return float(ctx.cit("citation_regression.csv")["ci_lo"].min())


@check(citation=True)
def refs(ctx, venue, year, col="references_mean", scale=1.0):
    """A value of references.csv for one venue and year."""
    df = ctx.cit("references.csv")
    return float(df[(df.venue == venue) & (df.year == int(year))].iloc[0][col]) * float(scale)


@check(citation=True)
def refs_extreme(ctx, venue, what="value", last=LAST):
    """The peak of a venue's mean bibliography length through `last`, or
    (what=year) its year."""
    df = ctx.cit("references.csv")
    df = df[(df.venue == venue) & (df.year <= int(last))].set_index("year")["references_mean"]
    return int(df.idxmax()) if what == "year" else float(df.max())


@check(citation=True)
def refs_window(ctx, venue, y0, y1, stat):
    """min or max of a venue's mean bibliography length over y0..y1."""
    df = ctx.cit("references.csv")
    s = df[(df.venue == venue) & (df.year >= int(y0)) & (df.year <= int(y1))]["references_mean"]
    return float(s.min() if stat == "min" else s.max())


@check(citation=True)
def refs_ratio(ctx, venue="neurips"):
    """Peak over first-year mean bibliography length."""
    df = ctx.cit("references.csv")
    s = df[(df.venue == venue) & (df.year <= LAST)].set_index("year")["references_mean"]
    return float(s.max() / s.iloc[0])


@check(citation=True)
def refs_years_to_peak(ctx, venue="neurips"):
    """Years from a venue's first year to its peak."""
    df = ctx.cit("references.csv")
    s = df[(df.venue == venue) & (df.year <= LAST)].set_index("year")["references_mean"]
    return int(s.idxmax() - s.index.min())


@check(citation=True)
def refs_first_year(ctx, venue):
    df = ctx.cit("references.csv")
    return int(df[df.venue == venue].year.min())


@check(citation=True)
def refs_last_range(ctx, year=LAST):
    """(min, max) mean bibliography length over the venues in one year."""
    df = ctx.cit("references.csv")
    s = df[df.year == int(year)]["references_mean"]
    return float(s.min()), float(s.max())


@check
def snapshot_date(ctx, file):
    """The retrieval date of one citation file of the published snapshot
    (citations.snapshot.RETRIEVED)."""
    from citations.snapshot import RETRIEVED
    return RETRIEVED[file]


# ==================================================== generated tables ===

@check
def generated_cell(ctx, table, n):
    """The n-th number (from 0, in the order inventory.py finds them) of a
    table make_macros.py builds ($AA_DATA/tmlr/tables/{table}). The paper's
    copy was generated from the same template, so its n-th number is the
    printed value this is compared with (rule text). check_tables.py
    compares the whole table body when the manuscript is given."""
    import inventory as inv
    path = os.path.join(ctx.data, "tmlr", "tables", table)
    if not os.path.exists(path):
        raise FileNotFoundError(2, "generated table absent", path)
    text = inv.read_text(path)
    norm = inv.Normalised.of(text)
    toks = inv.tokens_in(text)
    t = toks[int(n)]
    return norm.text[norm.pos[t.start]:norm.pos[t.end]]


@check
def topic_cell(ctx, row, col):
    """The papers or Flesch cell of one row (from 0, least to most readable)
    of the topics table, built by make_macros.topic_rows from the regenerated
    $AA_DATA/aggregate/topic_profiles.csv. Needs no citation output, so it is
    compared in every citation mode; only the median-citation column of that
    table depends on the citation counts."""
    sys.path.insert(0, HERE)
    from make_macros import Inputs, topic_rows
    cells = topic_rows(Inputs(ctx.data))[int(row)][1]
    return cells[{"papers": 2, "flesch": 3}[col]].strip()


def is_citation_check(name: str, kw: dict) -> bool:
    """Whether a check reads citation outputs."""
    if name == "generated_cell":
        sys.path.insert(0, HERE)
        from make_macros import CITATION_TABLES
        return kw.get("table") in CITATION_TABLES
    c = REGISTRY.get(name)
    return bool(c and c.citation)
