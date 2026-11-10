#!/usr/bin/env python3
"""Check every regenerated artefact against reference/.

reference/ holds the files that produced the figures in the paper. This
script compares what the pipeline just built against them and exits
non-zero on any mismatch, so a clean-room reproduction either passes or
fails loudly.

Comparisons, for the UncertaiNLP paper (reference/) and the TMLR paper
(reference/tmlr/):

  per-paper metrics          byte-for-byte, every venue in reference/per_paper
  plot-ready CSVs            numeric at atol=0 (NaN equal to NaN), text columns
                             equal as strings
  TMLR analysis CSVs         as plot-ready CSVs
  TMLR inline numbers        the 163 \newcommand macros by name and value,
                             the six generated tables byte-for-byte, and the
                             paper's own copies of both (paper/tmlr/source/)
                             against the same reference
                             (paper/tmlr/check_macros.py)
  TMLR printed numbers       every other number in the manuscript text
                             (paper/tmlr/source/) against paper/tmlr/claims.csv
                             and the outputs (paper/tmlr/check_claims.py);
                             a mismatch, a missing input, an error, an
                             uncovered number and a stale claim each count as
                             a failure; skips are listed by reason
  figure PNG                 byte-for-byte

Incomplete analyses. main.py does not run a command whose inputs are absent
(the --from aggregate route has no processed abstracts) and records it in
$AA_DATA/incomplete.json; make_macros.py records the sections it could not
write in tmlr/skipped.json. Both are listed first, so a reader knows which
analyses did not run before reading the missing outputs they cause. The
missing outputs still count: an incomplete run does not verify.

    python verify.py
"""
from __future__ import annotations

import filecmp
import glob
import importlib.metadata as md
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("AA_DATA", "data")
REF  = os.path.join(HERE, "reference")

ok = fail = missing = 0


def report(name: str, verdict: str, detail: str = "") -> None:
    global ok, fail, missing
    if verdict == "ok":
        ok += 1
    elif verdict == "missing":
        missing += 1
        print(f"  MISSING   {name}  {detail}")
    else:
        fail += 1
        print(f"  MISMATCH  {name}  {detail}")


def check_bytes(name: str, built: str, ref: str) -> None:
    if not os.path.exists(built):
        return report(name, "missing", "(not built)")
    report(name, "ok" if filecmp.cmp(built, ref, shallow=False) else "bad",
           "" if filecmp.cmp(built, ref, shallow=False) else "bytes differ")


def check_csv(name: str, built: str, ref: str) -> None:
    if not os.path.exists(built):
        return report(name, "missing", "(not built)")
    a, b = pd.read_csv(ref), pd.read_csv(built)
    # reference holds exactly the columns the paper's figures read; the run may
    # carry extra ones (an all-NaN pubmed column, for instance) without harm.
    absent = [c for c in a.columns if c not in b.columns]
    if absent:
        return report(name, "bad", f"missing columns {absent}")
    b = b[list(a.columns)]
    if len(a) != len(b):
        return report(name, "bad", f"rows {len(a)} vs {len(b)}")
    num = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c])]
    txt = [c for c in a.columns if c not in num]
    for c in txt:
        if not (a[c].astype(str) == b[c].astype(str)).all():
            return report(name, "bad", f"text column {c!r} differs")
    same = np.isclose(a[num].astype(float), b[num].astype(float),
                      rtol=0, atol=0, equal_nan=True).all()
    if same:
        return report(name, "ok")
    mx = np.nanmax(np.abs(a[num].astype(float).values - b[num].astype(float).values))
    report(name, "bad", f"max|delta|={mx:.3e}")


# The versions reference/ was built with. A mismatch here is the usual cause
# of small numeric differences: textstat has changed its formula
# implementations between releases, and the spaCy model determines parse
# depth, NP density, passive rate and TTR. thinc and blis are spaCy's numeric
# backend: blis 1.3.4 flips one part-of-speech tag in the NeurIPS corpus.
EXPECTED = {
    "pandas": "3.0.2", "numpy": "2.4.4", "matplotlib": "3.10.8",
    "textstat": "0.7.13", "spacy": "3.8.13", "thinc": "8.3.13", "blis": "1.3.3",
    "scikit-learn": "1.9.0",
}


def environment_report() -> None:
    print("\nenvironment (reference/MANIFEST.md records what these were built with)")
    drift = False
    for pkg, want in EXPECTED.items():
        try:
            got = md.version(pkg)
        except md.PackageNotFoundError:
            got = "not installed"
        flag = "" if got == want else "   <- differs"
        drift = drift or bool(flag)
        print(f"  {pkg:<12} expected {want:<9} installed {got}{flag}")
    try:
        import spacy
        got = spacy.load("en_core_web_sm").meta["version"]
    except Exception:
        got = "not loadable"
    flag = "" if got == "3.8.0" else "   <- differs"
    drift = drift or bool(flag)
    print(f"  {'en_core_web_sm':<12} expected {'3.8.0':<9} installed {got}{flag}")
    if drift:
        print("\n  A version difference above is the likely cause. This is a report "
              "about your environment,\n  not evidence that the pipeline is wrong. "
              "Install the pinned versions in requirements.txt\n  to reproduce the "
              "published numbers exactly.")


def citations_section() -> None:
    """Citation outputs, checked only against the authors' snapshot.

    The counts are not distributed. With no local files the section is
    skipped. With files whose hashes match reference/tmlr/citations/SNAPSHOT.md
    every output must match exactly. With any other files (a new fetch) the
    differences are reported but not counted: citation counts change daily, so
    a fresh fetch recomputes the analysis rather than reproducing it.
    """
    global ok, fail, missing
    sys.path.insert(0, os.path.join(HERE, "src"))
    from citations.snapshot import mode
    print("\nTMLR citations")
    m = mode(os.path.join(DATA, "per_paper", "citations"))
    refs = sorted(glob.glob(os.path.join(REF, "tmlr", "citations", "*.csv")))
    if m == "absent":
        print("  skipped: no citation counts in data/per_paper/citations/ (see README)")
        return
    if m == "fresh":
        print("  local citation counts differ from the published snapshot; differences "
              "below are reported, not counted")
        saved = (ok, fail, missing)
    for r in refs:
        base = os.path.basename(r)
        check_csv(f"tmlr/citations/{base}",
                  os.path.join(DATA, "aggregate", "citations", base), r)
    if m == "fresh":
        ok, fail, missing = saved


def macros_section() -> None:
    """The paper's inline numbers and generated tables.

    paper/tmlr/check_macros.py does the comparison; see its docstring. The
    citation-dependent macros and tables follow the citation mode as the
    citation outputs do: compared in strict mode, reported but not counted in
    fresh mode, skipped when the counts are absent.
    """
    global ok, fail, missing
    sys.path.insert(0, os.path.join(HERE, "src"))
    sys.path.insert(0, os.path.join(HERE, "paper", "tmlr"))
    from check_macros import check, citation_mode
    m = citation_mode(DATA)
    print(f"\nTMLR macros and tables (citation mode {m})")
    res = check(os.path.join(DATA, "tmlr"), m)
    for line in res.lines + res.summary():
        print(line)
    ok += res.ok
    fail += res.bad
    missing += res.missing


def claims_section() -> None:
    """Every number the TMLR manuscript prints, outside the macros.

    paper/tmlr/check_claims.py does the work; see its docstring. A match
    counts as ok; a mismatch, a check error, a number with no claims.csv row
    and a row whose quote no longer marks a number each count as a failure.
    A claim whose required input is absent counts as missing. Skipped
    claims (design and literature rows, citation claims outside strict mode,
    the one exempt raw-scrape count) are listed by reason and unverifiable
    ones reported; neither is counted.
    """
    global ok, fail, missing
    sys.path.insert(0, os.path.join(HERE, "src"))
    sys.path.insert(0, os.path.join(HERE, "paper", "tmlr"))
    from check_claims import citation_mode, run
    m = citation_mode(DATA)
    print(f"\nTMLR printed numbers (citation mode {m})")
    rep = run(DATA, m)
    for line in rep.lines() + rep.skip_lines() + rep.summary():
        print(line)
    ok += rep.count("MATCH")
    fail += rep.failures - rep.missing
    missing += rep.missing


def incomplete_section() -> None:
    """The analyses that did not run, and why (see the module docstring)."""
    import json
    items = []
    path = os.path.join(DATA, "incomplete.json")
    if os.path.exists(path):
        with open(path) as fh:
            for rec in json.load(fh).values():
                items.append(f"  not run   {rec['stage']}: {rec['script']}, "
                             f"absent {', '.join(rec['absent'])}")
    path = os.path.join(DATA, "tmlr", "skipped.json")
    if os.path.exists(path):
        with open(path) as fh:
            for rec in json.load(fh).get("incomplete", []):
                items.append(f"  not built macros: section {rec['section']}, "
                             f"absent {rec['input']}")
    if items:
        print("incomplete analyses (their outputs are reported missing below)")
        for line in items:
            print(line)
        print()


def main() -> None:
    print("verifying against reference/\n")
    incomplete_section()

    print("per-paper metrics")
    for ref_path in sorted(glob.glob(os.path.join(REF, "per_paper", "*", "*.csv"))):
        family = os.path.basename(os.path.dirname(ref_path))
        venue = os.path.basename(ref_path)
        check_bytes(f"per_paper/{family}/{venue}",
                    os.path.join(DATA, "per_paper", family, venue),
                    ref_path)

    print("\nplot-ready data")
    for ref_path in sorted(glob.glob(os.path.join(REF, "pgfplots", "*.csv"))):
        base = os.path.basename(ref_path)
        check_csv(f"pgfplots/{base}", os.path.join(DATA, "pgfplots", base), ref_path)

    print("\nTMLR figure data: judge series")
    for ref_path in sorted(glob.glob(os.path.join(REF, "tmlr", "pgfplots", "*.csv"))):
        base = os.path.basename(ref_path)
        check_csv(f"tmlr/pgfplots/{base}", os.path.join(DATA, "pgfplots", "tmlr", base),
                  ref_path)

    print("\nTMLR figure data: per-metric series with the arXiv and PubMed baselines")
    for ref_path in sorted(glob.glob(os.path.join(REF, "tmlr", "pgfplots_full", "*.csv"))):
        base = os.path.basename(ref_path)
        check_csv(f"tmlr/pgfplots_full/{base}",
                  os.path.join(DATA, "pgfplots", "tmlr", base), ref_path)

    print("\nTMLR analyses")
    for ref_path in sorted(glob.glob(os.path.join(REF, "tmlr", "*.csv"))
                           + glob.glob(os.path.join(REF, "tmlr", "analysis", "*.csv"))):
        base = os.path.basename(ref_path)
        rel = os.path.relpath(ref_path, REF)
        check_csv(rel, os.path.join(DATA, "aggregate", base), ref_path)

    citations_section()
    macros_section()
    claims_section()

    print("\nfigures")
    check_bytes("paper/figs/fig_judge_metric_heatmap.png",
                os.path.join(HERE, "paper", "figs", "fig_judge_metric_heatmap.png"),
                os.path.join(REF, "fig_judge_metric_heatmap.png"))

    total = ok + fail + missing
    print(f"\n{ok}/{total} artefacts match reference")
    environment_report()
    if fail or missing:
        sys.exit(f"FAILED: {fail} mismatched, {missing} missing")
    print("reproduction verified")


if __name__ == "__main__":
    main()
