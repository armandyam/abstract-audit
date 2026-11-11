#!/usr/bin/env python3
"""The abstract-audit pipeline. One entry point runs every stage in order.

    python main.py                      # everything, in order
    python main.py --stages metrics
    python main.py --from aggregate     # this stage and all later ones
    python main.py --list

Stages (venue coverage depends on the analysis):

  process    process_{neurips,iclr,icml}  data/raw/{venue} -> data/processed/{venue}
  validate   validate                 every record against the Pydantic schema
  metrics    metrics/*                processed abstracts -> readability, acronyms,
                                      hedging, signposting, narration, hype
  metrics_nlp nlp_features             spaCy: noun chunks, nouns, verbs, numbers
             linguistic_complexity     spaCy: parse depth, NP density, passive, TTR
  aggregate  aggregate_*              per-paper scores -> per-year mean, std, count;
                                      papers per year; judge scores per venue
  export     export_pgfplots_data     aggregates -> plot-ready CSVs, one copy of
                                      every shared series (data/pgfplots)
                                      and UncertaiNLP's own (data/uncertainlp/)
  model_avg  aggregate_llm_model_avg  per-model z-scores -> six-model average
  analysis   judge_feature_correlation  metric vs judge Spearman r
             visual_abstract_data     the two-panel summary series
             latex_robustness         Flesch under LaTeX and URL normalisation
             readability_collinearity correlation and PCA of the 15 readability
                                      measures
  self_audit audit_self               the TMLR paper's own title and abstract,
                                      read from the manuscript; runs only with
                                      $AA_PAPER (the manuscript is not
                                      distributed; see README)
  citations  src/citations/*          citation analyses; runs only with the
                                      reader's own Semantic Scholar counts
  macros     ai_native_academia/      the AI-Native Academia paper's 52 inline
               make_macros, make_tables numbers and five tables -> data/ai_native_academia/,
               check_macros, check_tables compared with its reference/macros.csv
                                      and the manuscript (report only)
             paper/tmlr/make_macros   the TMLR paper's 163 inline numbers and
                                      six generated tables -> data/tmlr/
             paper/tmlr/make_tables   its seven other data-driven tables
             paper/tmlr/check_macros  compared with paper/tmlr/reference/macros.csv
                                      (citation macros: with the manuscript)
             paper/tmlr/check_tables  every table compared with the paper's,
                                      given $AA_PAPER (both report only;
                                      verify is the gate)
  claims     paper/tmlr/check_claims  every other number the TMLR paper prints
                                      (paper/tmlr/claims.csv), checked against
                                      the outputs above (report only)
  figures    make_heatmap             the judge-vs-metric heatmap PNG
             build_figures            renders every figure to paper/uncertainlp/figures.pdf
             tmlr/build_figures       every TMLR figure and table to
                                      data/tmlr/figures.pdf (not distributed)
             ai_native_academia/      the same for the AI-Native Academia
               build_figures          paper, data/ai_native_academia/
  verify     verify                   every output against shared/reference/
                                      and paper/*/reference/

Dependencies. A command whose inputs are absent is not run: main.py prints
what it lacks and records it in $AA_DATA/incomplete.json, and the later
stages carry on with what exists (NEEDS below). The documented route from the
distributed metrics,

    mkdir -p data/per_paper
    cp -R shared/reference/per_paper/. data/per_paper/
    python main.py --from aggregate

has no processed abstracts, so papers per year, the LaTeX normalisation and
the topic analyses are not computed. make_macros.py then writes the sections
it can and lists the others as incomplete, and verify.py reports every
incomplete analysis by name and fails on the outputs they would have written.

The judge scores in shared/judge_scores/ are shipped, not recomputed: scoring 56,805
abstracts on six open-weight models needs a GPU. The other stages regenerate
from data/raw/{neurips,iclr,icml} and the distributed shared/baselines/. The
citation analyses also need the reader's own citation counts, and the checks
against a paper's text a local copy of its manuscript. The scrapers that fill
data/raw are run separately; see README.md.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY_  = sys.executable

VENUES = ["neurips", "iclr", "icml"]
METRICS = ("readability", "acronyms", "hedging", "signposting",
           "active_narration", "sensational_language", "sentence_length")
AGGREGATES = ("readability", "acronyms", "active_narration", "clauses_per_sentence",
              "hedging", "noun_chunks", "nouns", "np_density", "numbers",
              "parse_depth", "passive_rate", "sensational_language",
              "signposting", "ttr", "verbs", "sentence_length", "papers_per_year")
D = os.environ.get("AA_DATA", "data")
PG = f"{D}/pgfplots"
AGG = f"{D}/aggregate"
TOPIC_ASSIGN = f"{AGG}/topic_assignments.csv"
TOPIC_PROFILE = f"{AGG}/topic_profiles.csv"
# The AI-Native Academia paper fits its topics on NeurIPS alone.
TOPIC_ASSIGN_N = f"{AGG}/topic_assignments_neurips.csv"
TOPIC_PROFILE_N = f"{AGG}/topic_profiles_neurips.csv"
CIT_ANA = f"{AGG}/citations/ai_native_academia"
# Citation counts are fetched by the reader (src/citations/fetch_s2.py) and
# are not distributed; the citations stage runs only when all three exist.
CIT_FILES = [f"{D}/per_paper/citations/{v}_s2.csv" for v in VENUES]
# The TMLR manuscript is not distributed; the self-audit reads the paper's
# own title and abstract from a local copy (see paper/tmlr/manuscript.py).
PAPER = os.environ.get("AA_PAPER") or None

PROCESSED = f"{D}/processed/*/*.json"

# What each script needs before it can run, as globs that must each match a
# file. A command not listed needs only what earlier stages always write. A
# key may also be a whole command line, which then takes precedence over the
# script's own entry (the same script run on different inputs).
NEEDS: dict[str, list[str]] = {
    **{f"src/processing/process_{v}.py": [f"{D}/raw/{v}/*"] for v in VENUES},
    "src/validate.py": [PROCESSED],
    **{f"src/metrics/{m}.py": [PROCESSED] for m in METRICS},
    "src/metrics/nlp_features.py": [PROCESSED],
    "src/metrics/linguistic_complexity.py": [PROCESSED],
    "src/aggregate/aggregate_papers_per_year.py": [PROCESSED],
    "src/analysis/latex_robustness.py": [PROCESSED],
    "src/analysis/topic_clusters.py": [PROCESSED],
    "src/analysis/topic_trends.py": [TOPIC_ASSIGN],
    "src/analysis/topic_profiles.py": [TOPIC_ASSIGN],
    "src/analysis/topic_decomposition.py": [TOPIC_ASSIGN],
    # The regressions control for team size, read from the processed records.
    "src/citations/regression.py": [PROCESSED],
    "src/citations/regression_topics.py": [PROCESSED, TOPIC_ASSIGN],
    "src/citations/topic_citations.py": [TOPIC_ASSIGN, TOPIC_PROFILE],
    "paper/ai_native_academia/topics.py": [TOPIC_ASSIGN_N],
    f"src/citations/regression_topics.py --venues neurips --assignments {TOPIC_ASSIGN_N} "
    f"--out-dir {CIT_ANA}": [PROCESSED, TOPIC_ASSIGN_N],
    f"src/citations/topic_citations.py --venues neurips --assignments {TOPIC_ASSIGN_N} "
    f"--profiles {TOPIC_PROFILE_N} --out-dir {CIT_ANA}": [TOPIC_ASSIGN_N, TOPIC_PROFILE_N],
    "src/plotting/make_heatmap.py": [f"{PG}/judge_metric_corr.csv"],
    # The figure sources read ../../data/uncertainlp/pgfplots/ relative to
    # paper/uncertainlp/: the repository's data/ directory, whatever $AA_DATA says.
    "paper/uncertainlp/build_figures.py":
        [f"data/uncertainlp/pgfplots/{f}.csv" for f in (
            "va_flesch", "va_zscore", "readability_flesch_ease")]
        + [f"data/pgfplots/{f}.csv" for f in (
            "llm_scores_model_avg_simple", "llm_scores_standardized_simple")],
    # Likewise ../../data/ relative to paper/tmlr/. The tables and the
    # citation figure that were not built are replaced by notes.
    "paper/tmlr/build_figures.py": [f"data/pgfplots/{f}.csv" for f in (
        "readability_flesch_ease", "sensational_total", "acronyms_title",
        "acronyms_abstract", "papers_per_year", "sentence_length",
        "llm_scores_model_avg_simple", "llm_scores_model_avg_iclr_simple",
        "llm_scores_model_avg_icml_simple")],
    # Likewise ../../data/ relative to paper/ai_native_academia/.
    "paper/ai_native_academia/build_figures.py": [f"data/pgfplots/{f}.csv" for f in (
        "readability_flesch_ease", "sensational_total", "acronyms_title",
        "acronyms_abstract", "papers_per_year", "sentence_length",
        "llm_scores_model_avg_simple", "llm_scores_standardized_simple")]
        + ["shared/figs/fig_judge_metric_heatmap.png"],
}
INCOMPLETE = f"{D}/incomplete.json"

STAGES: list[tuple[str, list[list[str]]]] = [
    ("process",   [[f"src/processing/process_{v}.py",
                    "--raw-dir", f"{D}/raw/{v}",
                    "--processed-dir", f"{D}/processed/{v}"] for v in VENUES]),
    ("validate",  [["src/validate.py", "--venues", *VENUES]]),
    ("metrics",   [[f"src/metrics/{m}.py",
                    "--processed-dir", f"{D}/processed",
                    "--out-dir", f"{D}/per_paper/{m}",
                    "--venues", *VENUES]
                   for m in METRICS]),
    ("metrics_nlp", [["src/metrics/nlp_features.py",
                      "--processed-dir", f"{D}/processed",
                      "--out-base", f"{D}/per_paper", "--venues", *VENUES],
                     ["src/metrics/linguistic_complexity.py",
                      "--processed-dir", f"{D}/processed",
                      "--out-base", f"{D}/per_paper", "--venues", *VENUES]]),
    ("aggregate", [[f"src/aggregate/aggregate_{a}.py"] for a in AGGREGATES]
                  + [["src/aggregate/aggregate_llm_scores.py", "--venue", v]
                     for v in VENUES]),
    ("export",    [["src/plotting/export_pgfplots_data.py", "--baselines"]]),
    ("model_avg", [["src/aggregate/aggregate_llm_model_avg.py", "--venue", v]
                   for v in VENUES]),
    ("analysis",  [["src/analysis/judge_feature_correlation.py"],
                   ["src/analysis/visual_abstract_data.py"],
                   ["src/analysis/latex_robustness.py"],
                   ["src/analysis/readability_collinearity.py"],
                   ["src/analysis/acronym_reuse.py",
                    "--baselines", "shared/baselines/acronym_histograms.csv"],
                   ["src/analysis/acronym_robustness.py"],
                   ["src/analysis/acronym_concentration.py"],
                   ["src/analysis/flesch_decomposition.py"],
                   ["src/analysis/topic_clusters.py"],
                   ["src/analysis/topic_trends.py"],
                   ["src/analysis/topic_profiles.py"],
                   ["src/analysis/topic_decomposition.py"],
                   # AI-Native Academia: topics fitted on NeurIPS alone, and
                   # the judges' agreement and run-to-run stability.
                   ["src/analysis/topic_clusters.py", "--venues", "neurips"],
                   ["paper/ai_native_academia/topics.py"],
                   ["src/analysis/judge_agreement.py", "--venue", "neurips"]]),
    ("self_audit", [["src/metrics/audit_self.py",
                     "--from-tex", os.path.join(PAPER or "", "main.tex"),
                     "--out", f"{AGG}/self_audit.csv"]]),
    ("citations", [["src/citations/snapshot.py"],
                   ["src/citations/coverage.py"],
                   ["src/citations/regression.py", "--venues", *VENUES],
                   ["src/citations/readability_deciles.py", "--venues", *VENUES,
                    "--max-year", "2024"],
                   ["src/citations/judge_deciles.py", "--venues", *VENUES,
                    "--max-year", "2024"],
                   ["src/citations/references.py", "--venues", *VENUES],
                   ["src/citations/regression_topics.py", "--assignments", TOPIC_ASSIGN],
                   ["src/citations/topic_citations.py", "--assignments", TOPIC_ASSIGN,
                    "--profiles", TOPIC_PROFILE],
                   ["src/citations/readability_deciles.py", "--venues", "neurips",
                    "--max-year", "2024"],
                   ["src/citations/regression_topics.py", "--venues", "neurips",
                    "--assignments", TOPIC_ASSIGN_N, "--out-dir", CIT_ANA],
                   ["src/citations/topic_citations.py", "--venues", "neurips",
                    "--assignments", TOPIC_ASSIGN_N, "--profiles", TOPIC_PROFILE_N,
                    "--out-dir", CIT_ANA]]),
    ("macros",    [["paper/tmlr/make_macros.py"],
                   ["paper/tmlr/make_tables.py"],
                   ["paper/tmlr/check_macros.py", "--report-only"],
                   ["paper/tmlr/check_tables.py", "--report-only"],
                   ["paper/ai_native_academia/make_macros.py"],
                   ["paper/ai_native_academia/make_tables.py"],
                   ["paper/ai_native_academia/check_macros.py", "--report-only"],
                   ["paper/ai_native_academia/check_tables.py", "--report-only"]]),
    ("claims",    [["paper/tmlr/check_claims.py", "--report-only"]]),
    ("figures",   [["src/plotting/make_heatmap.py"],
                   ["paper/uncertainlp/build_figures.py"],
                   ["paper/tmlr/build_figures.py"],
                   ["paper/ai_native_academia/build_figures.py"]]),
    ("verify",    [["verify.py"]]),
]


def unmet(cmd: list[str]) -> list[str]:
    """The NEEDS globs of a command that match no file."""
    def found(pattern: str) -> bool:
        p = pattern if os.path.isabs(pattern) else os.path.join(HERE, pattern)
        return bool(glob.glob(p))
    needs = NEEDS.get(" ".join(cmd), NEEDS.get(cmd[0], []))
    return [g for g in needs if not found(g)]


def load_incomplete() -> dict:
    path = os.path.join(HERE, INCOMPLETE)
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return {}


def save_incomplete(rec: dict) -> None:
    path = os.path.join(HERE, INCOMPLETE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(dict(sorted(rec.items())), fh, indent=2)
        fh.write("\n")


def run(stage: str, cmds: list[list[str]], incomplete: dict | None = None) -> None:
    """Run one stage. A command with unmet NEEDS is skipped and recorded in
    `incomplete` (key: the command line); one that runs clears its record."""
    t0 = time.time()
    incomplete = {} if incomplete is None else incomplete
    print(f"\n===== {stage} =====", flush=True)
    if stage == "citations" and not all(os.path.exists(p) for p in CIT_FILES):
        print("  no citation counts under data/per_paper/citations/; skipped "
              "(see README, Citations)", flush=True)
        return
    if stage == "self_audit" and PAPER is None:
        print("  AA_PAPER is not set; skipped. The self-audit reads the TMLR "
              "paper's own abstract, which is not distributed (see README, "
              "The manuscript)", flush=True)
        return
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(HERE, "src") + os.pathsep + env.get("PYTHONPATH", "")
    for cmd in cmds:
        key = " ".join(cmd)
        missing = unmet(cmd)
        if missing:
            print(f"  not run: {cmd[0]} needs {missing}", flush=True)
            incomplete[key] = {"stage": stage, "script": cmd[0], "absent": missing}
            continue
        incomplete.pop(key, None)
        r = subprocess.run([PY_] + cmd, cwd=HERE, env=env)
        if r.returncode != 0:
            sys.exit(f"stage '{stage}' failed in {cmd[0]} (exit {r.returncode})")
    print(f"===== {stage} done in {time.time() - t0:.0f}s =====", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stages", nargs="+", help="run only these stages")
    ap.add_argument("--from", dest="from_", help="run this stage and every later one")
    ap.add_argument("--skip", nargs="*", default=[], help="stages to skip")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    names = [s for s, _ in STAGES]
    if a.list:
        print("\n".join(names))
        return
    sel = names
    if a.stages:
        bad = [s for s in a.stages if s not in names]
        if bad:
            sys.exit(f"unknown stages: {bad}; choose from {names}")
        sel = [s for s in names if s in a.stages]
    if a.from_:
        if a.from_ not in names:
            sys.exit(f"unknown stage: {a.from_}; choose from {names}")
        sel = names[names.index(a.from_):]
    sel = [s for s in sel if s not in a.skip]
    incomplete = load_incomplete()
    for s, cmds in STAGES:
        if s in sel:
            run(s, cmds, incomplete)
            save_incomplete(incomplete)


if __name__ == "__main__":
    main()
