#!/usr/bin/env python3
"""The TMLR paper's inline numbers and generated tables, as LaTeX.

The paper resolves 163 inline numbers through three macro files and inputs
six generated tables. Upstream they were written by three scripts, one per
revision round (tmlr/analysis/make_round{2,3,4}_tex.py at commit eda2733).
This script is their port, one section per round, reading this repository's
outputs instead of the upstream ones. The formatting code is kept as it was
upstream: the same macro names, the same rounding, the same table templates,
so the output can be compared with the paper's files in reference/tmlr/tex/
value for value and, for the tables, byte for byte.

Writes, under --out-dir (default $AA_DATA/tmlr):

  generated_round2.tex     59 macros: text normalisation, citation regression
                           with topic controls, topics, topic mix
  generated_round3.tex     66 macros: per-topic trends, Flesch decomposition,
                           acronym concentration
  generated_round4.tex     38 macros: absolute Flesch changes against the
                           baselines, ICML slope, topic decomposition
  tables/normalisation.tex          round 2
  tables/topic_controls.tex         round 2, needs citations
  tables/topics.tex                 round 2, needs citations
  tables/topic_trends.tex           round 3
  tables/acronym_concentration.tex  round 3
  tables/topic_decomposition.tex    round 4
  skipped.json             what was not written, and why: the citation items
                           ("macros", "tables") and, under "incomplete", any
                           section whose input is absent

Inputs (upstream tmlr/analysis/out/X.csv is $AA_DATA/aggregate/X.csv here):

  aggregate/latex_robustness.csv               analysis stage
  aggregate/topic_profiles.csv                 analysis stage, citation-free
  aggregate/topic_stability.csv                analysis stage
  aggregate/fixed_mix_readability.csv          analysis stage
  aggregate/topic_assignments.csv              analysis stage
  aggregate/topic_trends.csv                   analysis stage
  aggregate/flesch_decomposition.csv           analysis stage
  aggregate/acronym_concentration.csv          analysis stage
  aggregate/acronym_top_terms.csv              analysis stage
  aggregate/topic_decomposition_summary.csv    analysis stage
  pgfplots/tmlr/readability_flesch_ease.csv    export stage, with --baselines
  aggregate/citations/citation_regression_topics.csv   citations stage
  aggregate/citations/topic_citations.csv              citations stage

The citation counts are not distributed, so the citations stage runs only for
a reader who has them. The eleven macros and two tables that need citation
outputs (CITATION_MACROS, CITATION_TABLES) are written only when those outputs
exist. Otherwise they are left out and listed in skipped.json, and
check_macros.py does not expect them.

Any other input is required. A section whose input is absent (the --from
aggregate route has no processed abstracts, so no LaTeX normalisation or
topic analysis) is not written: the generator records the section and the
missing input under "incomplete" in skipped.json and carries on with the
others, and check_macros.py then reports that section's macros and tables
missing, a failure. Nothing is silently dropped.

    python paper/tmlr/make_macros.py
    python paper/tmlr/make_macros.py --data-dir path/to/data --out-dir path/to/tmlr
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

VENUE_LABEL = {"neurips": "NeurIPS", "iclr": "ICLR", "icml": "ICML"}
K_PRIMARY = 15    # clustering resolution used throughout
BASE_YEAR = 2015
FIRST, LAST = 2015, 2025          # window used throughout Section 2.1
CONFS = ["neurips", "iclr", "icml"]
ML = CONFS + ["arxiv_ml"]
BASELINES = ["arxiv_nonml", "pubmed"]

ROUND_FILES = {2: "generated_round2.tex", 3: "generated_round3.tex",
               4: "generated_round4.tex"}

# Macros and tables that need the citation outputs. topic_controls() writes
# all of the first group and its table; topics() writes TopicCitCorr and the
# topics table, whose last column is median citations.
TOPIC_CONTROLS_MACROS = ("AttenMax", "AttenMin", "BetaNoTopic", "BetaTopicMax",
                         "BetaTopicMin", "CitClusters", "CitN", "RtwoNoTopic",
                         "RtwoTopicMax", "RtwoTopicMin")
TOPIC_CITATION_MACROS = ("TopicCitCorr",)
CITATION_MACROS = frozenset(TOPIC_CONTROLS_MACROS + TOPIC_CITATION_MACROS)
CITATION_TABLES = frozenset({"topic_controls.tex", "topics.tex"})
TABLES = ("normalisation.tex", "topic_controls.tex", "topics.tex",
          "topic_trends.tex", "acronym_concentration.tex",
          "topic_decomposition.tex")


@dataclass
class Inputs:
    """Every file this script reads, under one data root."""
    data: str

    def agg(self, name: str) -> str:
        return os.path.join(self.data, "aggregate", name)

    def cit(self, name: str) -> str:
        return os.path.join(self.data, "aggregate", "citations", name)

    @property
    def flesch(self) -> str:
        return os.path.join(self.data, "pgfplots", "tmlr", "readability_flesch_ease.csv")


@dataclass
class Round:
    """The macros of one round, and what it skipped."""
    n: int
    macros: dict[str, str] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    incomplete: list[dict] = field(default_factory=list)   # section, input

    def M(self, name: str, value: str) -> None:
        # TeX control sequences are letters only, so a digit in a macro name
        # would silently split it: \MathPre2005 parses as \MathPre followed by
        # "2005".
        if not name.isalpha():
            raise ValueError(f"macro name must be letters only: {name!r}")
        if name in self.macros:
            raise ValueError(f"macro defined twice: {name!r}")
        self.macros[name] = value

    def skip(self, names) -> None:
        self.skipped.extend(names)


@dataclass
class Output:
    tables: str
    written_tables: list[str] = field(default_factory=list)
    skipped_tables: list[str] = field(default_factory=list)

    def table(self, name: str, tex: str) -> None:
        with open(os.path.join(self.tables, name), "w") as fh:
            fh.write(tex)
        self.written_tables.append(name)


class MissingInput(FileNotFoundError):
    """A required input is absent. build() records the section as
    incomplete instead of stopping."""


def require(path: str) -> str:
    if not os.path.exists(path):
        raise MissingInput(f"missing input {path}; run the stage that writes it "
                           "(see the module docstring)", path)
    return path


def section(r: Round, fn, *args) -> None:
    """Run one section; an absent input marks it incomplete (see the module
    docstring) rather than stopping the whole generator."""
    try:
        fn(r, *args)
    except MissingInput as e:
        r.incomplete.append({"section": fn.__name__, "input": e.args[1]})


def thousands(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", "{,}")


def first_term(terms: str) -> str:
    return str(terms).split(", ")[0]


def label(terms: str, budget: int = 50) -> str:
    """Leading terms of a cluster, cut at a term boundary rather than mid-word.

    Upstream round 2 and round 3 each carried a copy of this function, written
    differently but equal on every input: the longest prefix of whole terms
    within `budget` characters, or the first term if even that is too long.
    """
    out: list[str] = []
    for term in str(terms).split(", "):
        candidate = out + [term]
        if len(", ".join(candidate)) > budget:
            break
        out = candidate
    return ", ".join(out or [first_term(terms)])


def topic_ids(inp: Inputs) -> dict[int, str]:
    """Stable T1..Tk identifier per cluster, ranked least to most readable.

    Every table that lists a topic takes its identifier from here, so a
    cluster carries one identifier throughout the paper.
    """
    p = pd.read_csv(require(inp.agg("topic_profiles.csv"))).sort_values("flesch")
    return {int(c): f"T{i}" for i, c in enumerate(p[f"topic_k{K_PRIMARY}"], start=1)}


# =============================================================== round 2 ====

def normalisation(r: Round, inp: Inputs, out: Output) -> None:
    d = pd.read_csv(require(inp.agg("latex_robustness.csv")))
    lines = []
    for venue in ["neurips", "iclr", "icml"]:
        g = d[d.venue == venue].dropna(subset=["flesch_keep"]).sort_values("year")
        a, b = g.iloc[0], g.iloc[-1]
        span = f"{VENUE_LABEL[venue]} {int(a.year)}--{int(b.year)}"
        variants = [("None", "flesch_keep"), ("LaTeX only", "flesch_mathonly"),
                    ("LaTeX and URLs", "flesch_token")]
        if venue != "neurips":
            variants = [variants[0], variants[2]]
        for lab, col in variants:
            lines.append(f"    {lab:<18} & {span:<20} & {a[col]:.2f} & "
                         f"{b[col]:.2f} & ${b[col] - a[col]:.2f}$ \\\\")
        if venue != "icml":
            lines.append(r"    \midrule")

        dk = b.flesch_keep - a.flesch_keep
        dt = b.flesch_token - a.flesch_token
        dm = b.flesch_mathonly - a.flesch_mathonly
        V = VENUE_LABEL[venue]
        r.M(f"Raw{V}Decline", f"{dk:.2f}")
        r.M(f"Norm{V}Decline", f"{dt:.2f}")
        r.M(f"Markup{V}Share", f"{100 * (dk - dt) / dk:.1f}")
        r.M(f"Latex{V}Share", f"{100 * (dk - dm) / dk:.1f}")
        r.M(f"Url{V}Share", f"{100 * (dm - dt) / dk:.1f}")

    # Min and max across venues, so the main text can quote a range without
    # naming a venue at each end and having the ends swap on a rerun.
    shares = []
    for venue in ["neurips", "iclr", "icml"]:
        g = d[d.venue == venue].dropna(subset=["flesch_keep"]).sort_values("year")
        a_, b_ = g.iloc[0], g.iloc[-1]
        dk = b_.flesch_keep - a_.flesch_keep
        dt = b_.flesch_token - a_.flesch_token
        shares.append(100 * (dk - dt) / dk)
    r.M("MarkupMinShare", f"{min(shares):.1f}")
    r.M("MarkupMaxShare", f"{max(shares):.1f}")
    # The caption's whole-percent range, from the same shares (upstream typed
    # it). check_claims.py checks it against latex_robustness_summary.csv.
    markup_range = f"{min(shares):.0f} to {max(shares):.0f}"

    n = d[d.venue == "neurips"]
    r.M("MathPreEarly", f"{n[n.year < 2005].pct_with_math.mean():.1f}")
    r.M("MathTwentyFive", f"{n[n.year == 2025].pct_with_math.iloc[0]:.1f}")
    r.M("UrlTwentyFourteen", f"{n[n.year == 2014].pct_with_url.iloc[0]:.1f}")
    r.M("UrlTwentyTwentyFour", f"{n[n.year == 2024].pct_with_url.iloc[0]:.1f}")
    r.M("NormLevelShift", f"{(d.flesch_token - d.flesch_keep).mean():.2f}")
    r.M("NormVenueYears", str(len(d)))
    r.M("NormShiftPositive", str(int(((d.flesch_token - d.flesch_keep) > 0).sum())))
    # The correction is not uniform: it tracks how much markup a year carries,
    # so it is near zero early and largest in the recent years.
    ng = n.dropna(subset=["flesch_keep"]).sort_values("year")
    r.M("NormShiftFirst", f"{ng.iloc[0].flesch_token - ng.iloc[0].flesch_keep:.2f}")
    r.M("NormShiftLast", f"{ng.iloc[-1].flesch_token - ng.iloc[-1].flesch_keep:.2f}")
    r.M("NormShiftFirstYear", str(int(ng.iloc[0].year)))
    r.M("NormShiftLastYear", str(int(ng.iloc[-1].year)))

    tex = (r"""\begin{table}[h]
  \centering
  \small
  \begin{tabular}{llrrr}
    \toprule
    Normalisation & Venue & First year & Last year & Change \\
    \midrule
""" + "\n".join(lines) + r"""
    \bottomrule
  \end{tabular}
  \caption{\revtwo{Flesch Reading Ease at each venue's first and last year
  under three text normalisations. Markup accounts for """ + markup_range + r""" percent of each
  measured decline, and URLs for more of it than LaTeX.}}
  \label{tab:normalisation}
\end{table}
""")
    out.table("normalisation.tex", tex)


def topic_controls(r: Round, inp: Inputs, out: Output) -> None:
    path = inp.cit("citation_regression_topics.csv")
    if not os.path.exists(path):
        r.skip(TOPIC_CONTROLS_MACROS)
        out.skipped_tables.append("topic_controls.tex")
        return
    before = set(r.macros)
    d = pd.read_csv(path)
    lines = []
    for _, row in d.iterrows():
        lab = ("No topic control" if row.n_topic_dummies == 0
               else f"Topic fixed effects, $k={int(row.n_topic_dummies) + 1}$")
        lines.append(f"    {lab:<32} & {row.beta_flesch:.3f} & {row.se_flesch:.3f} & "
                     f"{row.ci_lo:.3f} to {row.ci_hi:.3f} & {row.r2_within:.3f} \\\\")
    base = d[d.n_topic_dummies == 0].iloc[0]
    fe = d[d.n_topic_dummies > 0]
    r.M("CitN", thousands(base.n))
    r.M("CitClusters", str(int(base.n_clusters)))
    r.M("BetaNoTopic", f"{base.beta_flesch:.3f}")
    r.M("BetaTopicMin", f"{fe.beta_flesch.min():.3f}")
    r.M("BetaTopicMax", f"{fe.beta_flesch.max():.3f}")
    r.M("RtwoNoTopic", f"{base.r2_within:.3f}")
    r.M("RtwoTopicMin", f"{fe.r2_within.min():.3f}")
    r.M("RtwoTopicMax", f"{fe.r2_within.max():.3f}")
    r.M("AttenMin", f"{100 * (1 - fe.beta_flesch.max() / base.beta_flesch):.0f}")
    r.M("AttenMax", f"{100 * (1 - fe.beta_flesch.min() / base.beta_flesch):.0f}")
    assert set(r.macros) - before == set(TOPIC_CONTROLS_MACROS)

    tex = (r"""\begin{table}[h]
  \centering
  \small
  \begin{tabular}{lrrlr}
    \toprule
    Model & $\beta$ & s.e. & 95\% CI & within $R^2$ \\
    \midrule
""" + "\n".join(lines) + r"""
    \bottomrule
  \end{tabular}
  \caption{\revtwo{Standardised coefficient on Flesch Reading Ease in the
  citation regression, with and without topic fixed effects. Venue-year fixed
  effects, abstract length and author count are controlled throughout, and
  standard errors are clustered by venue-year.}}
  \label{tab:topic-controls}
\end{table}
""")
    out.table("topic_controls.tex", tex)


def topic_rows(inp: Inputs, p: pd.DataFrame | None = None) -> list[tuple[int, list[str]]]:
    """(topic, [ID, leading terms, papers, Flesch]) for each row of the topics
    table, least to most readable: every cell but median citations. topics()
    writes the table from these, and check_claims.py compares the paper's
    table with them in every citation mode."""
    col = f"topic_k{K_PRIMARY}"
    if p is None:
        p = pd.read_csv(require(inp.agg("topic_profiles.csv"))).sort_values("flesch")
    ids = topic_ids(inp)
    return [(int(row[col]), [ids[int(row[col])], f"{label(row.top_terms):<54}",
                             thousands(row.n), f"{row.flesch:.1f}"])
            for _, row in p.iterrows()]


def topics(r: Round, inp: Inputs, out: Output) -> None:
    col = f"topic_k{K_PRIMARY}"
    p = pd.read_csv(require(inp.agg("topic_profiles.csv"))).sort_values("flesch")
    r.M("TopicK", str(K_PRIMARY))
    r.M("TopicSpread", f"{p.flesch.max() - p.flesch.min():.1f}")
    r.M("TopicMinFlesch", f"{p.flesch.min():.1f}")
    r.M("TopicMaxFlesch", f"{p.flesch.max():.1f}")
    r.M("TopicMinName", str(p.iloc[0].top_terms).split(", ")[0])
    r.M("TopicMaxName", str(p.iloc[-1].top_terms).split(", ")[0])
    r.M("TopicPapers", thousands(p.n.sum()))

    stab = pd.read_csv(require(inp.agg("topic_stability.csv")))
    s = stab[stab.k == K_PRIMARY].iloc[0]
    r.M("TopicStabAri", f"{s.ari:.2f}")
    r.M("TopicStabAmi", f"{s.ami:.2f}")

    fm = pd.read_csv(require(inp.agg("fixed_mix_readability.csv")))
    a, b = fm.iloc[0], fm.iloc[-1]
    r.M("FixedMixFirstYear", str(int(a.year)))
    r.M("FixedMixLastYear", str(int(b.year)))
    r.M("FixedMixBaseYear", str(BASE_YEAR))
    r.M("RawMixDecline", f"{b.raw - a.raw:.1f}")
    r.M("FixedMixDecline", f"{b.fixed_mix - a.fixed_mix:.1f}")
    _dr, _df = b.raw - a.raw, b.fixed_mix - a.fixed_mix
    r.M("CompositionShare", f"{100 * (_dr - _df) / _dr:.0f}")
    r.M("WithinTopicShare", f"{100 - 100 * (_dr - _df) / _dr:.0f}")

    # The paper's profile carried median citations per topic. Here they come
    # from the citations stage and are joined on the topic, keeping the
    # profile's least-to-most-readable order.
    path = inp.cit("topic_citations.csv")
    if not os.path.exists(path):
        r.skip(TOPIC_CITATION_MACROS)
        out.skipped_tables.append("topics.tex")
        return
    c = pd.read_csv(path)[[col, "median_citations"]]
    p = p.drop(columns=[x for x in ("median_citations",) if x in p.columns])
    p = p.merge(c, on=col, how="left", validate="one_to_one")

    cit = dict(zip(p[col].astype(int), p.median_citations))
    lines = [f"    {' & '.join(cells)} & {cit[t]:.0f} \\\\" for t, cells in topic_rows(inp, p)]
    corr = np.corrcoef(p.flesch, p.median_citations)[0, 1]
    r.M("TopicCitCorr", f"{corr:.2f}")

    tex = (r"""\begin{table}[h]
  \centering
  \small
  \begin{tabular}{llrrr}
    \toprule
    ID & Leading terms & Papers & Flesch & Med.\ cit. \\
    \midrule
""" + "\n".join(lines) + r"""
    \bottomrule
  \end{tabular}
  \caption{\revtwo{The topics induced from the cleaned titles and abstracts of
  all conference papers, ordered from least to most readable, with the leading
  terms of each cluster centroid. Median citations are computed on the papers
  with citation data. Readability spans \TopicSpread{} Flesch points across
  topics and correlates negatively with citations across them
  ($r=\TopicCitCorr$), the opposite sign to the within-topic association.}}
  \label{tab:topics}
\end{table}
""")
    out.table("topics.tex", tex)


def hard_topic_share(r: Round, inp: Inputs) -> None:
    """Share of papers in the least readable topics, first and last year."""
    col = f"topic_k{K_PRIMARY}"
    top = pd.read_csv(require(inp.agg("topic_assignments.csv")), usecols=["year", col])
    prof = pd.read_csv(require(inp.agg("topic_profiles.csv")))
    hard = set(prof.nsmallest(4, "flesch")[col])
    for tag, yr in [("HardShareEarly", BASE_YEAR), ("HardShareLate", 2025)]:
        s = top[top.year == yr]
        r.M(tag, f"{100 * s[col].isin(hard).mean():.1f}")
    r.M("HardShareEarlyYear", str(BASE_YEAR))
    r.M("HardShareLateYear", "2025")


def round2(inp: Inputs, out: Output) -> Round:
    r = Round(2)
    section(r, normalisation, inp, out)
    section(r, topic_controls, inp, out)
    section(r, topics, inp, out)
    section(r, hard_topic_share, inp)
    return r


# =============================================================== round 3 ====

def topic_trends(r: Round, inp: Inputs, out: Output) -> None:
    d = pd.read_csv(require(inp.agg("topic_trends.csv"))).sort_values("flesch_change")
    ids = topic_ids(inp)

    lines = []
    for _, row in d.iterrows():
        lab = label(row.top_terms)
        span = f"{int(row.flesch_first_year)}--{int(row.flesch_last_year)}"
        lines.append(f"    {ids[int(row.topic)]} & {lab:<54} & {thousands(row.n)} & {span} & "
                     f"${row.flesch_change:+.1f}$ & ${row.hype_change:+.2f}$ & "
                     f"${row.acr_abstract_change:+.2f}$ \\\\")

    r.M("TopicsAll", str(len(d)))
    for tag, name, want in [("flesch", "Flesch", "down"),
                            ("hype", "Hype", "up"),
                            ("acr_abstract", "AcrAbstract", "up"),
                            ("acr_title", "AcrTitle", "up")]:
        s = d[f"{tag}_slope"].dropna()
        n_same = int((s < 0).sum()) if want == "down" else int((s > 0).sum())
        r.M(f"Topics{name}Same", str(n_same))
        r.M(f"Topics{name}Total", str(len(s)))
        r.M(f"Topics{name}Sig", str(int(d[f"{tag}_sig_same"].sum())))
        # Magnitudes are reported unsigned in the prose, with the direction
        # given by the surrounding sentence.
        r.M(f"Topics{name}SlopeMin", f"{min(abs(s.min()), abs(s.max())):.2f}"
            if want == "down" else f"{s[s > 0].min():.3f}")
        r.M(f"Topics{name}SlopeMax", f"{max(abs(s.min()), abs(s.max())):.2f}"
            if want == "down" else f"{s.max():.3f}")

    # The prose reports how many of the three-family slopes carry a flag, so
    # both the count and the total come from here rather than being typed.
    flagged = int(sum((~d[f"{t}_sig_same"]).sum()
                      for t in ["flesch", "hype", "acr_abstract"]))
    r.M("TopicsSlopesTotal", str(3 * len(d)))
    r.M("TopicsSlopesFlagged", str(flagged))

    fastest = d.iloc[0]
    slowest = d.dropna(subset=["flesch_slope"]).iloc[-1]
    r.M("TopicFastestName", first_term(fastest.top_terms))
    r.M("TopicFastestSlope", f"{abs(fastest.flesch_slope):.2f}")
    r.M("TopicSlowestName", first_term(slowest.top_terms))
    r.M("TopicSlowestSlope", f"{abs(slowest.flesch_slope):.2f}")

    tex = (r"""\begin{table}[t]
  \centering
  \small
  \begin{tabular}{llrcrrr}
    \toprule
    ID & Leading terms & Papers & Span & $\Delta$Flesch & $\Delta$Hype & $\Delta$Acronyms \\
    \midrule
""" + "\n".join(lines) + r"""
    \bottomrule
  \end{tabular}
  \caption{\revthree{Change in three of the five metric families within each
  topic, measured from the first to the last year in which that topic has at
  least 30 papers within the 2015 to 2025 window. \revfour{Several topics have fewer
  than 30 papers at the start of that window.} Flesch Reading Ease is in points, sensational
  language and acronym density in occurrences per 100 words. Paper
  counts are for the window, so they are lower than the full-corpus counts in
  Table~\ref{tab:topics}, whose identifiers these match.}}
  \label{tab:topic-trends}
\end{table}
""")
    out.table("topic_trends.tex", tex)


def flesch_decomposition(r: Round, inp: Inputs) -> None:
    d = pd.read_csv(require(inp.agg("flesch_decomposition.csv")))
    name = {"conferences": "Conf", "neurips": "NeurIPS"}
    for _, row in d.iterrows():
        p = name[row.corpus]
        r.M(f"Decomp{p}First", str(int(row.first_year)))
        r.M(f"Decomp{p}Last", str(int(row.last_year)))
        r.M(f"Decomp{p}Change", f"{row.fre_change:.1f}")
        r.M(f"Decomp{p}WordShare", f"{row.word_share:.0f}")
        r.M(f"Decomp{p}SentShare", f"{row.sentence_share:.0f}")
        r.M(f"Decomp{p}WordTerm", f"{row.word_term:.1f}")
        r.M(f"Decomp{p}SentTerm", f"{row.sentence_term:+.1f}")
        # Unsigned forms, for sentences that carry the direction in words.
        r.M(f"Decomp{p}WordMag", f"{abs(row.word_term):.1f}")
        r.M(f"Decomp{p}SentMag", f"{abs(row.sentence_term):.1f}")
        r.M(f"Decomp{p}ChangeMag", f"{abs(row.fre_change):.1f}")
        r.M(f"Decomp{p}AswFirst", f"{row.asw_first:.3f}")
        r.M(f"Decomp{p}AswLast", f"{row.asw_last:.3f}")
        r.M(f"Decomp{p}AslFirst", f"{row.asl_first:.1f}")
        r.M(f"Decomp{p}AslLast", f"{row.asl_last:.1f}")


def acronyms(r: Round, inp: Inputs, out: Output) -> None:
    c = pd.read_csv(require(inp.agg("acronym_concentration.csv")))
    t = pd.read_csv(require(inp.agg("acronym_top_terms.csv")), keep_default_na=False)

    r.M("AcrTypes", thousands(c.n_types.iloc[0]))
    r.M("AcrTokens", thousands(c.n_tokens.iloc[0]))
    r.M("AcrSingletonTypeShare", f"{c.singleton_type_share.iloc[0]:.1f}")
    r.M("AcrSingletonTokenShare", f"{c.singleton_token_share.iloc[0]:.1f}")
    for n, tag in [(20, "Twenty"), (100, "Hundred")]:
        row = c[c.top_n == n].iloc[0]
        r.M(f"AcrTop{tag}TypeShare", f"{row.type_share:.2f}")
        r.M(f"AcrTop{tag}TokenShare", f"{row.token_share:.1f}")
    r.M("AcrTopName", str(t.acronym.iloc[0]))
    r.M("AcrTopShare", f"{float(t.token_share.iloc[0]):.1f}")
    r.M("AcrTopTen", ", ".join(t.acronym.head(10)))

    lines = []
    for _, row in c.iterrows():
        lines.append(f"    Top {int(row.top_n):>3} & {row.type_share:.2f} & "
                     f"{row.token_share:.1f} \\\\")
    tex = (r"""\begin{table}[h]
  \centering
  \small
  \begin{tabular}{lrr}
    \toprule
    Acronyms & Share of distinct acronyms (\%) & Share of occurrences (\%) \\
    \midrule
""" + "\n".join(lines) + r"""
    \bottomrule
  \end{tabular}
  \caption{\revthree{Concentration of abstract acronym occurrences at the
  three conferences between 2015 and 2025. The corpus holds \AcrTypes{} distinct
  acronyms over \AcrTokens{} occurrences. A few hundred reused terms account
  for most of what a reader meets, while the \AcrSingletonTypeShare{} percent
  of acronyms that occur once carry only \AcrSingletonTokenShare{} percent of
  occurrences.}}
  \label{tab:acronym-concentration}
\end{table}
""")
    out.table("acronym_concentration.tex", tex)


def round3(inp: Inputs, out: Output) -> Round:
    r = Round(3)
    section(r, topic_trends, inp, out)
    section(r, flesch_decomposition, inp)
    section(r, acronyms, inp, out)
    return r


# =============================================================== round 4 ====

def read_flesch(inp: Inputs) -> pd.DataFrame:
    f = pd.read_csv(require(inp.flesch))
    absent = [c for c in ML + BASELINES if c not in f.columns]
    if absent:
        raise SystemExit(f"{inp.flesch} has no columns {absent}; run "
                         "src/plotting/export_pgfplots_data.py --baselines")
    return f


def absolute_changes(r: Round, inp: Inputs) -> None:
    f = read_flesch(inp).set_index("year")
    a, b = f.loc[FIRST], f.loc[LAST]
    fall = a - b                                   # positive = decline
    r.M("AbsFirstYear", str(FIRST))
    r.M("AbsLastYear", str(LAST))
    r.M("AbsMLFallMin", f"{fall[ML].min():.1f}")
    r.M("AbsMLFallMax", f"{fall[ML].max():.1f}")
    r.M("AbsNonMLFall", f"{fall.arxiv_nonml:.1f}")
    r.M("AbsNonMLFirst", f"{a.arxiv_nonml:.1f}")
    r.M("AbsNonMLLast", f"{b.arxiv_nonml:.1f}")
    r.M("AbsPubMedFall", f"{fall.pubmed:.1f}")
    r.M("AbsPubMedFirst", f"{a.pubmed:.1f}")
    r.M("AbsPubMedLast", f"{b.pubmed:.1f}")
    # PubMed's fall as a fraction of each ML venue's fall.
    ratio = fall.pubmed / fall[ML]
    r.M("AbsPubMedRatioMin", f"{ratio.min():.2f}")
    r.M("AbsPubMedRatioMax", f"{ratio.max():.2f}")
    # Final-year gap of each conference below the nearer of the two baselines
    # (smallest gap) and below the further one (largest gap).
    gap = pd.DataFrame({base: b[base] - b[CONFS] for base in BASELINES})
    r.M("AbsGapMin", f"{gap.min().min():.1f}")
    r.M("AbsGapMax", f"{gap.max().max():.1f}")
    for v, tag in [("neurips", "NeurIPS"), ("iclr", "ICLR"), ("icml", "ICML"),
                   ("arxiv_ml", "ArxivML")]:
        r.M(f"Abs{tag}Fall", f"{fall[v]:.1f}")
        r.M(f"Abs{tag}Last", f"{b[v]:.1f}")


def icml_slope(r: Round, inp: Inputs) -> None:
    """ICML and control Flesch slopes over ICML's own window.

    The two round to the same value at two decimals, which made the
    "marginally shallower" sentence in Section 2.1 unreadable.
    """
    f = read_flesch(inp)
    w = f[(f.year <= LAST) & f.icml.notna()]
    r.M("SlopeICML", f"{np.polyfit(w.year, w.icml, 1)[0]:.3f}")
    r.M("SlopeICMLControl", f"{np.polyfit(w.year, w.arxiv_nonml, 1)[0]:.3f}")


NUMBER_WORDS = ["none", "one", "two", "three", "four"]

LABELS = {
    "base_year_mix": f"Topic mix held at {FIRST}",
    "symmetric": "Mix averaged over both years",
    "last_year_mix": f"Topic mix held at {LAST}",
    "year_adjusted": "Gap to papers of the same year",
}


def topic_decomposition(r: Round, inp: Inputs, out: Output) -> None:
    s = pd.read_csv(require(inp.agg("topic_decomposition_summary.csv")))
    s = s.set_index("method")
    r0 = s.iloc[0]
    r.M("DecTotalMag", f"{-r0.total:.1f}")
    r.M("DecFirstMean", f"{r0.first_mean:.1f}")
    r.M("DecLastMean", f"{r0.last_mean:.1f}")
    r.M("DecTopicsDeclining", str(int(r0.topics_declining)))
    r.M("DecTopics", str(int(r0.topics)))
    r.M("DecWithinShareMin", f"{s.within_share.min():.0f}")
    r.M("DecWithinShareMax", f"{s.within_share.max():.0f}")
    # Composition as a contribution to the decline: positive = adds to it.
    comp = -s["between"]
    r.M("DecCompMaxMag", f"{comp.max():.1f}")            # most it adds
    r.M("DecCompMaxShare", f"{100 * comp.max() / -r0.total:.0f}")
    r.M("DecCompMinMag", f"{-comp.min():.1f}")           # most it offsets
    r.M("DecAdjBetweenMag", f"{abs(s.loc['year_adjusted', 'between']):.1f}")
    r.M("DecAdjWithinMag", f"{-s.loc['year_adjusted', 'within']:.1f}")
    r.M("DecHardBetweenMag", f"{abs(r0.hard_between):.1f}")
    r.M("DecHardStillBottom", NUMBER_WORDS[int(r0.hard_in_adjusted_bottom)])

    def signed(x: float) -> str:
        return f"${x:+.1f}$"

    rows = []
    for m in ["base_year_mix", "symmetric", "last_year_mix", "year_adjusted"]:
        row = s.loc[m]
        # Table 9 is new in round 4, so every cell is marked for the AE.
        cells = [LABELS[m], signed(row['within']), signed(row['between']),
                 f"{row.within_share:.0f}"]
        rows.append("    " + " & ".join(r"\revfour{" + c + "}" for c in cells)
                    + r" \\")
    tex = (r"""\begin{table}[h]
  \centering
  \small
  \begin{tabular}{lrrr}
    \toprule
    \revfour{Weighting} & \revfour{Within topic} & \revfour{Between topic} & \revfour{Within share (\%)} \\
    \midrule
""" + "\n".join(rows) + r"""
    \bottomrule
  \end{tabular}
  \caption{\revfour{The fall of """ + f"{-r0.total:.1f}" + r""" points in mean Flesch
  Reading Ease across the three conferences from """ + f"{FIRST} to {LAST}" + r""",
  split into a part within topics (topics becoming less readable) and a
  part between topics (the field moving between topics). Each row sums to the
  total. The first three rows value each topic at its own mean score and
  differ only in which year's topic mix weights the within-topic change. The
  last row values each topic by its gap to papers of the same year, estimated
  over every year of the window, which avoids topic means that rest on a few
  papers in """ + f"{FIRST}" + r""". A positive between-topic entry means the change in
  topic mix raised readability.}}
  \label{tab:topic-decomposition}
\end{table}
""")
    out.table("topic_decomposition.tex", tex)


def round4(inp: Inputs, out: Output) -> Round:
    r = Round(4)
    section(r, absolute_changes, inp)
    section(r, icml_slope, inp)
    section(r, topic_decomposition, inp, out)
    return r


# ================================================================= output ===

def macro_file(r: Round) -> str:
    """The macro file text: a header, then one \\newcommand per macro, sorted
    by name, as upstream wrote it."""
    lines = [f"% Generated by paper/tmlr/make_macros.py, round {r.n}. Do not edit.\n",
             f"% Every round-{r.n} number in the manuscript resolves through here.\n"]
    lines += [f"\\newcommand{{\\{k}}}{{{r.macros[k]}}}\n" for k in sorted(r.macros)]
    return "".join(lines)


def build(data_dir: str, out_dir: str) -> dict:
    """Write the three macro files, the tables and skipped.json. Returns the
    skipped.json record."""
    inp = Inputs(data_dir)
    tables = os.path.join(out_dir, "tables")
    os.makedirs(tables, exist_ok=True)
    out = Output(tables)
    rounds = [round2(inp, out), round3(inp, out), round4(inp, out)]
    for r in rounds:
        with open(os.path.join(out_dir, ROUND_FILES[r.n]), "w") as fh:
            fh.write(macro_file(r))
    record = {
        "macros": {ROUND_FILES[r.n]: sorted(r.skipped) for r in rounds},
        "tables": sorted(out.skipped_tables),
        "reason": ("citation outputs absent from aggregate/citations/"
                   if any(r.skipped for r in rounds) or out.skipped_tables else ""),
        "incomplete": [i for r in rounds for i in r.incomplete],
        "written": {ROUND_FILES[r.n]: len(r.macros) for r in rounds},
        "written_tables": sorted(out.written_tables),
    }
    with open(os.path.join(out_dir, "skipped.json"), "w") as fh:
        json.dump(record, fh, indent=2)
        fh.write("\n")
    return record


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=os.environ.get("AA_DATA", "data"),
                    help="data root (default: $AA_DATA, else data)")
    ap.add_argument("--out-dir", default=None, help="default: {data-dir}/tmlr")
    a = ap.parse_args()
    out_dir = a.out_dir or os.path.join(a.data_dir, "tmlr")
    rec = build(a.data_dir, out_dir)
    for f, n in rec["written"].items():
        skipped = rec["macros"][f]
        print(f"  {f:<22} {n:>3} macros" + (f", {len(skipped)} skipped" if skipped else ""))
    print(f"  tables: {len(rec['written_tables'])} written"
          + (f", skipped {rec['tables']}" if rec["tables"] else ""))
    for i in rec["incomplete"]:
        print(f"  INCOMPLETE {i['section']}: input absent {i['input']}")
    print(f"wrote {out_dir}")


if __name__ == "__main__":
    main()
