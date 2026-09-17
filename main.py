#!/usr/bin/env python3
"""The abstract-audit pipeline. One entry point runs every stage in order.

    python main.py                      # everything, in order
    python main.py --stages metrics
    python main.py --from aggregate     # this stage and all later ones
    python main.py --list

Stages:

  process    process_neurips          data/raw/neurips -> data/processed/neurips
  validate   validate                 every record against the Pydantic schema
  metrics    metrics/*                processed abstracts -> readability, acronyms,
                                      hedging, signposting, narration, hype
  metrics_nlp nlp_features             spaCy: noun chunks, nouns, verbs, numbers
             linguistic_complexity     spaCy: parse depth, NP density, passive, TTR
  aggregate  aggregate_readability    per-paper scores -> per-year mean, std, count
             aggregate_llm_scores     per-paper judge scores -> per-year, per-model
  export     export_pgfplots_data     aggregates -> plot-ready CSVs
  model_avg  aggregate_llm_model_avg  per-model z-scores -> six-model average
  analysis   judge_feature_correlation  metric vs judge Spearman r
             visual_abstract_data     the two-panel summary series
  figures    make_heatmap             the judge-vs-metric heatmap PNG
             build_figures            renders every figure to paper/figures.pdf
  verify     verify                   every output against reference/

The judge scores in judge_scores/ are shipped, not recomputed:
scoring 30,595 abstracts on six open-weight models needs a GPU. Everything
else regenerates from data/raw/neurips alone.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY_  = sys.executable

STAGES: list[tuple[str, list[list[str]]]] = [
    ("process",   [["src/processing/process_neurips.py",
                    "--raw-dir", "data/raw/neurips",
                    "--processed-dir", "data/processed/neurips"]]),
    ("validate",  [["src/validate.py", "--venues", "neurips"]]),
    ("metrics",   [[f"src/metrics/{m}.py",
                    "--processed-dir", "data/processed",
                    "--out-dir", f"data/per_paper/{m}",
                    "--venues", "neurips"]
                   for m in ("readability", "acronyms", "hedging", "signposting",
                             "active_narration", "sensational_language")]),
    ("metrics_nlp", [["src/metrics/nlp_features.py",
                      "--processed-dir", "data/processed",
                      "--out-base", "data/per_paper", "--venues", "neurips"],
                     ["src/metrics/linguistic_complexity.py",
                      "--processed-dir", "data/processed",
                      "--out-base", "data/per_paper", "--venues", "neurips"]]),
    ("aggregate", [["src/aggregate/aggregate_readability.py"],
                   ["src/aggregate/aggregate_llm_scores.py", "--venue", "neurips"]]),
    ("export",    [["src/plotting/export_pgfplots_data.py"]]),
    ("model_avg", [["src/aggregate/aggregate_llm_model_avg.py", "--venue", "neurips"]]),
    ("analysis",  [["src/analysis/judge_feature_correlation.py"],
                   ["src/analysis/visual_abstract_data.py"]]),
    ("figures",   [["paper/analysis/make_heatmap.py"],
                   ["paper/build_figures.py"]]),
    ("verify",    [["verify.py"]]),
]


def run(stage: str, cmds: list[list[str]]) -> None:
    t0 = time.time()
    print(f"\n===== {stage} =====", flush=True)
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
