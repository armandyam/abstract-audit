#!/usr/bin/env python3
"""Check every regenerated artefact against the reference files.

shared/reference/ holds the per-paper metrics every paper uses, and
paper/<paper>/reference/ the files behind that paper's figures. This
script compares what the pipeline just built against them and exits
non-zero on any mismatch, so a clean-room reproduction either passes or
fails loudly.

Comparisons, for both papers (shared/reference/), the UncertaiNLP paper
(paper/uncertainlp/reference/) and the TMLR paper (paper/tmlr/reference/):

  per-paper metrics          byte-for-byte, every venue in shared/reference/per_paper
  plot-ready CSVs            numeric at atol=0 (NaN equal to NaN), text columns
                             equal as strings
  TMLR analysis CSVs         as plot-ready CSVs
  TMLR inline numbers        the 163 \newcommand macros by name and value
                             against paper/tmlr/reference/macros.csv, the eleven
                             citation macros against the manuscript's values
                             (paper/tmlr/check_macros.py)
  TMLR tables                every table the release builds against the
                             paper's own, cell by cell
                             (paper/tmlr/check_tables.py)
  TMLR printed numbers       every other number the manuscript prints,
                             recomputed and compared with the printed value in
                             paper/tmlr/claims.csv, or for a citation number
                             in the manuscript (paper/tmlr/check_claims.py);
                             a mismatch, a missing input and an error each
                             count as a failure; skips are listed by reason;
                             author-accepted discrepancies are listed as KNOWN
  figure PNG                 byte-for-byte

The manuscript is not distributed. Given a local copy of its LaTeX source
($AA_PAPER, see paper/tmlr/manuscript.py), three more checks run: the macro
values in macros.csv against the paper's own macro files, every table
against the paper's table, and the coverage of claims.csv (an uncovered
number, a stale row and a printed value that differs each count as a
failure). Without it these are reported as skipped.

Citations. The citation counts and every statistic computed from them are not
distributed. With the published snapshot of the counts (strict mode) the
citation macros, tables and claims are compared like everything else; after a
fresh fetch they are reported, not counted; without counts they are skipped.
Their printed values are not stored in the repository either: they are read
from the manuscript, so without AA_PAPER they are skipped too.

Incomplete analyses. main.py does not run a command whose inputs are absent
(the --from aggregate route has no processed abstracts) and records it in
$AA_DATA/incomplete.json; make_macros.py records the sections it could not
write in tmlr/skipped.json, and make_tables.py the tables in
tmlr/tables.json. All are listed first, so a reader knows which analyses did
not run before reading the missing outputs they cause. The
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
SHARED_REF = os.path.join(HERE, "shared", "reference")
UNC_REF    = os.path.join(HERE, "paper", "uncertainlp", "reference")
TMLR_REF   = os.path.join(HERE, "paper", "tmlr", "reference")
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, os.path.join(HERE, "paper", "tmlr"))

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


# The versions the reference files were built with. A mismatch here is the usual cause
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
    print("\nenvironment (the reference MANIFEST.md files record what these were built with)")
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


def citations_section(paper: str | None) -> str:
    """The citation mode, reported. No citation output is compared here:
    none is distributed. The citation numbers the paper prints are compared
    by the macros, tables and claims sections below."""
    from citations.snapshot import mode
    print("\nTMLR citations")
    m = mode(os.path.join(DATA, "per_paper", "citations"))
    print({"absent": "  no citation counts in data/per_paper/citations/: citation "
                     "macros, tables and claims are skipped (see README)",
           "fresh": "  local citation counts differ from the published snapshot: "
                    "citation macros, tables and claims are reported, not counted",
           "strict": "  local citation counts are the published snapshot: citation "
                     "macros, tables and claims are compared"}[m])
    return m


def macros_section(m: str, paper: str | None) -> None:
    """The paper's inline numbers; paper/tmlr/check_macros.py, see its
    docstring."""
    global ok, fail, missing
    from check_macros import check
    print(f"\nTMLR macros (citation mode {m})")
    res = check(os.path.join(DATA, "tmlr"), m, paper=paper)
    for line in res.lines + res.summary():
        print(line)
    ok += res.ok
    fail += res.bad
    missing += res.missing


def tables_section(m: str, paper: str | None) -> None:
    """Every table against the paper's own; paper/tmlr/check_tables.py."""
    global ok, fail, missing
    from check_tables import check
    print(f"\nTMLR tables (citation mode {m})")
    res = check(os.path.join(DATA, "tmlr", "tables"), m, paper)
    for line in res.lines + res.summary():
        print(line)
    ok += res.ok
    fail += res.bad
    missing += res.missing


def claims_section(m: str, paper: str | None) -> None:
    """Every number the TMLR manuscript prints, outside the macros.

    paper/tmlr/check_claims.py does the work; see its docstring. A match
    counts as ok; a mismatch and a check error count as failures, and, with
    the manuscript, so do an uncovered number, a stale row and a printed
    value that differs. A claim whose required input is absent counts as
    missing. Skipped claims are listed by reason, and unverifiable and
    author-accepted (KNOWN) ones reported; none of these is counted.
    """
    global ok, fail, missing
    from check_claims import run
    print(f"\nTMLR printed numbers (citation mode {m})")
    rep = run(DATA, m, paper=paper)
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
    path = os.path.join(DATA, "tmlr", "tables.json")
    if os.path.exists(path):
        with open(path) as fh:
            for name, what in json.load(fh).get("incomplete", {}).items():
                items.append(f"  not built table: {name}, absent {what}")
    if items:
        print("incomplete analyses (their outputs are reported missing below)")
        for line in items:
            print(line)
        print()


def main() -> None:
    print("verifying against shared/reference/ and paper/*/reference/\n")
    incomplete_section()

    print("per-paper metrics")
    for ref_path in sorted(glob.glob(os.path.join(SHARED_REF, "per_paper", "*", "*.csv"))):
        family = os.path.basename(os.path.dirname(ref_path))
        venue = os.path.basename(ref_path)
        check_bytes(f"per_paper/{family}/{venue}",
                    os.path.join(DATA, "per_paper", family, venue),
                    ref_path)

    print("\nUncertaiNLP figure data")
    for ref_path in sorted(glob.glob(os.path.join(UNC_REF, "pgfplots", "*.csv"))):
        base = os.path.basename(ref_path)
        check_csv(f"uncertainlp/pgfplots/{base}",
                  os.path.join(DATA, "uncertainlp", "pgfplots", base), ref_path)

    print("\nshared figure data: per-metric series with the arXiv and PubMed "
          "baselines, judge series, judge-metric correlations")
    for ref_path in sorted(glob.glob(os.path.join(SHARED_REF, "pgfplots", "*.csv"))):
        base = os.path.basename(ref_path)
        check_csv(f"pgfplots/{base}", os.path.join(DATA, "pgfplots", base), ref_path)

    print("\nTMLR analyses")
    for ref_path in sorted(glob.glob(os.path.join(TMLR_REF, "*.csv"))
                           + glob.glob(os.path.join(TMLR_REF, "analysis", "*.csv"))):
        base = os.path.basename(ref_path)
        if base == "macros.csv":            # the printed macro values: macros section
            continue
        rel = "tmlr/" + os.path.relpath(ref_path, TMLR_REF)
        check_csv(rel, os.path.join(DATA, "aggregate", base), ref_path)

    from manuscript import ENV, paper_dir
    paper = paper_dir()
    print(f"\nTMLR manuscript: {paper}" if paper else
          f"\nTMLR manuscript: not given ({ENV} unset); the checks that read it "
          "are skipped")
    m = citations_section(paper)
    macros_section(m, paper)
    tables_section(m, paper)
    claims_section(m, paper)

    print("\nfigures")
    check_bytes("shared/figs/fig_judge_metric_heatmap.png",
                os.path.join(HERE, "shared", "figs", "fig_judge_metric_heatmap.png"),
                os.path.join(SHARED_REF, "fig_judge_metric_heatmap.png"))

    total = ok + fail + missing
    print(f"\n{ok}/{total} artefacts match reference")
    environment_report()
    if fail or missing:
        sys.exit(f"FAILED: {fail} mismatched, {missing} missing")
    print("reproduction verified")


if __name__ == "__main__":
    main()
