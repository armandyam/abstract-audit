#!/usr/bin/env python3
"""The AI-Native Academia paper's inline numbers and its topic profile table.

The workshop paper (NeurIPS only) resolves 52 inline numbers through one
macro file, generated_round2.tex, and inputs a generated topic profile table.
Upstream both were written by src/aggregate/topic_controls_neurips.py at
commit 1922ca3. This script is its port, reading this repository's outputs:
the same macro names, the same rounding and the same table body, so the
output can be compared with the paper's printed values
(paper/ai_native_academia/reference/macros.csv, check_macros.py) value for
value and, for the table, with the paper's own table (check_tables.py) cell
for cell. The table is written without the paper's caption: no manuscript
text is distributed.

Writes, under --out-dir (default $AA_DATA/ai_native_academia):

  generated_round2.tex   52 macros: text normalisation, topics, the
                         citation regression with topic controls, the
                         fixed-mix counterfactual, acronyms per title
  tables/topic_profile.tex   needs citations (its last column is median
                             citations per topic)
  skipped.json           what was not written, and why: the citation items
                         and, under "incomplete", any section whose input
                         is absent

Inputs, under $AA_DATA:

  aggregate/latex_robustness.csv           analysis stage (its NeurIPS rows
                                           are the paper's normalisation)
  aggregate/topic_stability_neurips.csv    analysis stage, topic_clusters.py
                                           --venues neurips
  aggregate/topic_assignments_neurips.csv  the same
  aggregate/topic_profiles_neurips.csv     paper/ai_native_academia/topics.py
  aggregate/fixed_mix_neurips.csv          the same
  per_paper/readability/neurips.csv        metrics stage
  per_paper/acronyms/neurips.csv           metrics stage
  aggregate/citations/ai_native_academia/citation_regression_topics.csv
  aggregate/citations/ai_native_academia/topic_citations.csv
                                           citations stage, NeurIPS only

The citation counts are not distributed, so the citations stage runs only for
a reader who has them. The ten macros and the table that need citation
outputs (CITATION_MACROS, CITATION_TABLES) are written only when those
outputs exist; otherwise they are listed in skipped.json. check_macros.py
skips the citation macros when the counts or the manuscript are absent;
otherwise a missing citation macro is reported, a failure in strict mode and
report-only in fresh mode. Any other absent input marks its section
incomplete, as in paper/tmlr/make_macros.py.

    python paper/ai_native_academia/make_macros.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))


def sibling(name: str):
    """A module of this folder, under a name of its own: paper/tmlr has
    modules with the same file names."""
    key = f"ai_native_academia_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, os.path.join(HERE, f"{name}.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return sys.modules[key]


T = sibling("topics")

VENUE = "neurips"
MACRO_FILE = "generated_round2.tex"
CIT_SUBDIR = os.path.join("citations", "ai_native_academia")

# Macros and the table that need citation outputs.
TOPIC_CONTROLS_MACROS = ("BetaNoTopic", "BetaTopicMax", "BetaTopicMin", "CiLoMin",
                         "CitClusters", "CitN", "RtwoNoTopic", "RtwoTopicMax",
                         "RtwoTopicMin")
TOPIC_CITATION_MACROS = ("TopicCitCorr",)
CITATION_MACROS = frozenset(TOPIC_CONTROLS_MACROS + TOPIC_CITATION_MACROS)
CITATION_TABLES = frozenset({"topic_profile.tex"})
TABLES = ("topic_profile.tex",)
NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


@dataclass
class Inputs:
    data: str

    def agg(self, name: str) -> str:
        return os.path.join(self.data, "aggregate", name)

    def cit(self, name: str) -> str:
        return os.path.join(self.data, "aggregate", CIT_SUBDIR, name)

    def per_paper(self, family: str) -> str:
        return os.path.join(self.data, "per_paper", family, f"{VENUE}.csv")


@dataclass
class Macros:
    macros: dict[str, str] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    incomplete: list[dict] = field(default_factory=list)
    written_tables: list[str] = field(default_factory=list)
    skipped_tables: list[str] = field(default_factory=list)

    def M(self, name: str, value: str) -> None:
        # A digit in a TeX control sequence name would split it.
        if not name.isalpha():
            raise ValueError(f"macro name must be letters only: {name!r}")
        if name in self.macros:
            raise ValueError(f"macro defined twice: {name!r}")
        self.macros[name] = value


class MissingInput(FileNotFoundError):
    """A required input is absent; build() marks the section incomplete."""


def require(path: str) -> str:
    if not os.path.exists(path):
        raise MissingInput(f"missing input {path}", path)
    return path


def section(r: Macros, fn, *args) -> None:
    try:
        fn(r, *args)
    except MissingInput as e:
        r.incomplete.append({"section": fn.__name__, "input": e.args[1]})


def thousands(x) -> str:
    """As upstream: truncated to an integer, TeX-safe thousands separator."""
    return f"{int(x):,}".replace(",", "{,}")


# ============================================================ sections ===

def normalisation(r: Macros, inp: Inputs) -> None:
    """The NeurIPS Flesch decline under LaTeX and URL normalisation."""
    lr = pd.read_csv(require(inp.agg("latex_robustness.csv")))
    lr = lr[lr.venue == VENUE].sort_values("year").reset_index(drop=True)
    a, b = lr.iloc[0], lr.iloc[-1]
    raw = b.flesch_keep - a.flesch_keep
    norm = b.flesch_token - a.flesch_token
    math = b.flesch_mathonly - a.flesch_mathonly
    markup = 100 * (raw - norm) / raw
    latex = 100 * (raw - math) / raw
    r.M("NormFirstYear", str(int(a.year)))
    r.M("NormLastYear", str(int(b.year)))
    r.M("RawDecline", f"{raw:.2f}")
    r.M("NormDecline", f"{norm:.2f}")
    r.M("MarkupShare", f"{markup:.1f}")
    r.M("LatexShare", f"{latex:.1f}")
    r.M("UrlShare", f"{markup - latex:.1f}")
    r.M("MathPreEarly", f"{lr[lr.year < 2005].pct_with_math.mean():.1f}")
    r.M("MathLate", f"{b.pct_with_math:.1f}")
    r.M("UrlEarly", f"{lr[lr.year == 2014].pct_with_url.iloc[0]:.1f}")
    r.M("UrlLate", f"{b.pct_with_url:.1f}")


def read_profile(inp: Inputs) -> pd.DataFrame:
    p = pd.read_csv(require(inp.agg(T.PROFILES)))
    return p.sort_values("flesch").reset_index(drop=True)


def topics(r: Macros, inp: Inputs) -> None:
    prof = read_profile(inp)
    r.M("TopicK", str(T.K))
    r.M("TopicPapers", thousands(prof.n.sum()))
    r.M("TopicSpread", f"{prof.flesch.max() - prof.flesch.min():.1f}")
    r.M("TopicMinFlesch", f"{prof.flesch.iloc[0]:.1f}")
    r.M("TopicMinName", prof.label.iloc[0])
    r.M("TopicMaxFlesch", f"{prof.flesch.iloc[-1]:.1f}")
    r.M("TopicMaxName", prof.label.iloc[-1])
    stab = pd.read_csv(require(inp.agg(T.STABILITY)))
    s = stab[stab.k == T.K].iloc[0]
    r.M("TopicStabAri", f"{s.ari:.2f}")
    r.M("TopicStabAmi", f"{s.ami:.2f}")


def topic_controls(r: Macros, inp: Inputs) -> None:
    """The NeurIPS citation regression with and without topic fixed effects
    (src/citations/regression_topics.py --venues neurips). Citation-gated."""
    path = inp.cit("citation_regression_topics.csv")
    if not os.path.exists(path):
        r.skipped.extend(TOPIC_CONTROLS_MACROS)
        return
    before = set(r.macros)
    d = pd.read_csv(path)
    base = d[d.n_topic_dummies == 0].iloc[0]
    fe = d[d.n_topic_dummies > 0]
    r.M("CitN", thousands(base.n))
    r.M("CitClusters", str(int(base.n_clusters)))
    r.M("BetaNoTopic", f"{base.beta_flesch:.3f}")
    r.M("BetaTopicMin", f"{fe.beta_flesch.min():.3f}")
    r.M("BetaTopicMax", f"{fe.beta_flesch.max():.3f}")
    r.M("CiLoMin", f"{fe.ci_lo.min():.3f}")
    r.M("RtwoNoTopic", f"{base.r2_within:.3f}")
    r.M("RtwoTopicMin", f"{fe.r2_within.min():.3f}")
    r.M("RtwoTopicMax", f"{fe.r2_within.max():.3f}")
    assert set(r.macros) - before == set(TOPIC_CONTROLS_MACROS)


def fixed_mix(r: Macros, inp: Inputs) -> None:
    fm = pd.read_csv(require(inp.agg(T.FIXED_MIX)))
    a, b = fm.iloc[0], fm.iloc[-1]
    d_raw, d_fix = b.raw - a.raw, b.fixed_mix - a.fixed_mix
    comp = 100 * (d_raw - d_fix) / d_raw
    r.M("FixedMixFirstYear", str(int(a.year)))
    r.M("FixedMixLastYear", str(int(b.year)))
    r.M("FixedMixBaseYear", str(T.BASE_YEAR))
    r.M("RawMixDecline", f"{d_raw:.1f}")
    r.M("FixedMixDecline", f"{d_fix:.1f}")
    # unsigned forms, for sentences that carry the direction in words
    r.M("RawMixDeclineAbs", f"{abs(d_raw):.1f}")
    r.M("FixedMixDeclineAbs", f"{abs(d_fix):.1f}")
    r.M("CompositionShare", f"{comp:.0f}")
    r.M("WithinTopicShare", f"{100 - comp:.0f}")

    # The sensitivity check and the hard-topic shares need the per-paper
    # frame: assignments joined to readability.
    require(inp.agg(T.ASSIGNMENTS))
    require(inp.per_paper("readability"))
    prof, d = T.load(inp.data)
    last = int(b.year)
    r.M("CompositionShareAlt", f"{T.composition_share(d, T.ALT_BASE_YEAR, last):.0f}")
    r.M("FixedMixBaseYearAlt", str(T.ALT_BASE_YEAR))
    hard = T.hard_topics(prof)
    r.M("HardTopicCount", NUMBER_WORDS[T.N_HARD])
    r.M("HardShareEarly", f"{T.hard_share(d, hard, T.BASE_YEAR):.1f}")
    r.M("HardShareLate", f"{T.hard_share(d, hard, last):.1f}")
    r.M("HardShareEarlyYear", str(T.BASE_YEAR))
    r.M("HardShareLateYear", str(last))


def acronyms_per_title(r: Macros, inp: Inputs) -> None:
    """Mean acronyms per NeurIPS title, and the percentage of titles with at
    least one, in the first and the last year."""
    ac = pd.read_csv(require(inp.per_paper("acronyms")),
                     usecols=["year", "title_acronym_count"])
    ag = ac.groupby("year").title_acronym_count
    mean = ag.mean()
    share = ag.apply(lambda s: (s > 0).mean())
    first, last = int(ac.year.min()), int(ac.year.max())
    for tag, yr in [("AcroTitleEarly", first), ("AcroTitleLate", last)]:
        r.M(tag, f"{mean[yr]:.2f}")
        r.M(tag + "Share", f"{100 * share[yr]:.0f}")
    r.M("AcroTitleEarlyYear", str(first))
    r.M("AcroTitleLateYear", str(last))


# ============================================================== table ===

def profile_row(row) -> str:
    """One row of the topic profile table. Upstream's formatting is kept as
    printed: in a row of 1,000 papers or more, only the first comma of the
    line (the one between the two leading terms) is braced."""
    terms = ", ".join(str(row.top_terms).split(", ")[:2])
    if int(row.n) >= 1000:
        return (f"{row.label} & {terms} & {int(row.n):,} & "
                f"{row.flesch:.1f} & {row.median_citations:.0f} \\\\\n").replace(",", "{,}", 1)
    return (f"{row.label} & {terms} & {int(row.n)} & "
            f"{row.flesch:.1f} & {row.median_citations:.0f} \\\\\n")


def topic_profile_table(r: Macros, inp: Inputs, tables: str) -> None:
    """The profile with median citations per topic, and TopicCitCorr.
    Citation-gated (src/citations/topic_citations.py --venues neurips)."""
    prof = read_profile(inp)
    path = inp.cit("topic_citations.csv")
    if not os.path.exists(path):
        r.skipped.extend(TOPIC_CITATION_MACROS)
        r.skipped_tables.append("topic_profile.tex")
        return
    col = f"topic_k{T.K}"
    c = pd.read_csv(path)[[col, "median_citations"]]
    prof = prof.drop(columns=[x for x in ("median_citations",) if x in prof.columns])
    prof = prof.merge(c, on=col, how="left", validate="one_to_one")
    r.M("TopicCitCorr", f"{float(np.corrcoef(prof.flesch, prof.median_citations)[0, 1]):.2f}")
    tex = ("\\begin{table}[t]\n\\centering\\footnotesize\n"
           "\\begin{tabular}{llrrr}\n\\toprule\n"
           "Topic & Highest-weight terms & Papers & Flesch & Median cit. \\\\\n"
           "\\midrule\n"
           + "".join(profile_row(row) for _, row in prof.iterrows())
           + "\\bottomrule\n\\end{tabular}\n"
           "\\label{tab:topic-profile}\n\\end{table}\n")
    with open(os.path.join(tables, "topic_profile.tex"), "w", encoding="utf-8") as fh:
        fh.write(tex)
    r.written_tables.append("topic_profile.tex")


# ============================================================= output ===

def macro_file(r: Macros) -> str:
    lines = ["% Generated by paper/ai_native_academia/make_macros.py. Do not edit.\n"]
    lines += [f"\\newcommand{{\\{k}}}{{{r.macros[k]}}}\n" for k in sorted(r.macros)]
    return "".join(lines)


def build(data_dir: str, out_dir: str) -> dict:
    """Write the macro file, the table and skipped.json; return the record."""
    inp = Inputs(data_dir)
    tables = os.path.join(out_dir, "tables")
    os.makedirs(tables, exist_ok=True)
    for name in TABLES:                # never leave a table from an earlier run
        if os.path.exists(os.path.join(tables, name)):
            os.remove(os.path.join(tables, name))
    r = Macros()
    section(r, normalisation, inp)
    section(r, topics, inp)
    section(r, topic_controls, inp)
    section(r, fixed_mix, inp)
    section(r, acronyms_per_title, inp)
    section(r, topic_profile_table, inp, tables)
    with open(os.path.join(out_dir, MACRO_FILE), "w", encoding="utf-8") as fh:
        fh.write(macro_file(r))
    record = {
        "macros": {MACRO_FILE: sorted(r.skipped)},
        "tables": sorted(r.skipped_tables),
        "reason": (f"citation outputs absent from aggregate/{CIT_SUBDIR}/"
                   if r.skipped or r.skipped_tables else ""),
        "incomplete": r.incomplete,
        "written": {MACRO_FILE: len(r.macros)},
        "written_tables": sorted(r.written_tables),
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
    ap.add_argument("--out-dir", default=None, help="default: {data-dir}/ai_native_academia")
    a = ap.parse_args()
    out_dir = a.out_dir or os.path.join(a.data_dir, "ai_native_academia")
    rec = build(a.data_dir, out_dir)
    skipped = rec["macros"][MACRO_FILE]
    print(f"  {MACRO_FILE:<22} {rec['written'][MACRO_FILE]:>3} macros"
          + (f", {len(skipped)} skipped (citations)" if skipped else ""))
    print(f"  tables: {len(rec['written_tables'])} written"
          + (f", skipped {rec['tables']}" if rec["tables"] else ""))
    for i in rec["incomplete"]:
        print(f"  INCOMPLETE {i['section']}: input absent {i['input']}")
    print(f"wrote {out_dir}")


if __name__ == "__main__":
    main()
