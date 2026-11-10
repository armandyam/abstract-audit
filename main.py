#!/usr/bin/env python3
"""The abstract-audit pipeline. One entry point runs every stage in order.

    python main.py                      # everything, in order
    python main.py --stages metrics
    python main.py --from aggregate     # this stage and all later ones
    python main.py --list

Stages (each runs over NeurIPS, ICLR and ICML):

  process    process_{neurips,iclr,icml}  data/raw/{venue} -> data/processed/{venue}
  validate   validate                 every record against the Pydantic schema
  metrics    metrics/*                processed abstracts -> readability, acronyms,
                                      hedging, signposting, narration, hype
  metrics_nlp nlp_features             spaCy: noun chunks, nouns, verbs, numbers
             linguistic_complexity     spaCy: parse depth, NP density, passive, TTR
  aggregate  aggregate_*              per-paper scores -> per-year mean, std, count;
                                      papers per year; judge scores per venue
  export     export_pgfplots_data     aggregates -> plot-ready CSVs, one set per
                                      paper (data/pgfplots, data/pgfplots/tmlr)
  model_avg  aggregate_llm_model_avg  per-model z-scores -> six-model average
  analysis   judge_feature_correlation  metric vs judge Spearman r
             visual_abstract_data     the two-panel summary series
             latex_robustness         Flesch under LaTeX and URL normalisation
             readability_collinearity correlation and PCA of the 15 formulas
  self_audit audit_self               the TMLR paper's own title and abstract
  citations  src/citations/*          citation analyses; runs only with the
                                      reader's own Semantic Scholar counts
  macros     paper/tmlr/make_macros   the TMLR paper's 163 inline numbers and
                                      six generated tables -> data/tmlr/
             paper/tmlr/check_macros  compared with reference/tmlr/tex/
                                      (report only; verify is the gate)
  figures    make_heatmap             the judge-vs-metric heatmap PNG
             build_figures            renders every figure to paper/figures.pdf
  verify     verify                   every output against reference/

The judge scores in judge_scores/ are shipped, not recomputed: scoring 56,805
abstracts on six open-weight models needs a GPU. Everything else regenerates
from data/raw/{neurips,iclr,icml} alone. The scrapers that fill data/raw are
run separately; see README.md.
"""
from __future__ import annotations

import argparse
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
TMLR_PG = f"{D}/pgfplots/tmlr"
AGG = f"{D}/aggregate"
TOPIC_ASSIGN = f"{AGG}/topic_assignments.csv"
TOPIC_PROFILE = f"{AGG}/topic_profiles.csv"
# Citation counts are fetched by the reader (src/citations/fetch_s2.py) and
# are not distributed; the citations stage runs only when all three exist.
CIT_FILES = [f"{D}/per_paper/citations/{v}_s2.csv" for v in VENUES]
TMLR_TITLE = "Machine Learning Research Has Outpaced Its Communication Norms"

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
    ("model_avg", [["src/aggregate/aggregate_llm_model_avg.py", "--venue", "neurips"]]
                  + [["src/aggregate/aggregate_llm_model_avg.py", "--venue", v,
                      "--in-dir", TMLR_PG, "--out-dir", TMLR_PG] for v in VENUES]),
    ("analysis",  [["src/analysis/judge_feature_correlation.py"],
                   ["src/analysis/visual_abstract_data.py"],
                   ["src/analysis/latex_robustness.py"],
                   ["src/analysis/readability_collinearity.py"],
                   ["src/analysis/acronym_reuse.py",
                    "--baselines", "baselines/acronym_histograms.csv"],
                   ["src/analysis/acronym_robustness.py"],
                   ["src/analysis/acronym_concentration.py"],
                   ["src/analysis/flesch_decomposition.py"],
                   ["src/analysis/topic_clusters.py"],
                   ["src/analysis/topic_trends.py"],
                   ["src/analysis/topic_profiles.py"],
                   ["src/analysis/topic_decomposition.py"]]),
    ("self_audit", [["src/metrics/audit_self.py", "--title", TMLR_TITLE,
                     "--abstract-file", "paper/tmlr/self_audit_abstract.txt",
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
                    "--profiles", TOPIC_PROFILE]]),
    ("macros",    [["paper/tmlr/make_macros.py"],
                   ["paper/tmlr/check_macros.py", "--report-only"]]),
    ("figures",   [["paper/analysis/make_heatmap.py"],
                   ["paper/build_figures.py"]]),
    ("verify",    [["verify.py"]]),
]


def run(stage: str, cmds: list[list[str]]) -> None:
    t0 = time.time()
    print(f"\n===== {stage} =====", flush=True)
    if stage == "citations" and not all(os.path.exists(p) for p in CIT_FILES):
        print("  no citation counts under data/per_paper/citations/; skipped "
              "(see README, Citations)", flush=True)
        return
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(HERE, "src") + os.pathsep + env.get("PYTHONPATH", "")
    for cmd in cmds:
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
    for s, cmds in STAGES:
        if s in sel:
            run(s, cmds)


if __name__ == "__main__":
    main()
