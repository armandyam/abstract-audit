#!/usr/bin/env python3
"""Compare every AI-Native Academia table the release builds with the paper's.

The release writes the paper's five data-driven tables under
$AA_DATA/ai_native_academia/tables/ (make_macros.py: topic_profile.tex;
make_tables.py: the other four). This module compares each with
tables/{name} in the manuscript directory, the way paper/tmlr/check_tables.py
does: the tabular body cell by cell, whitespace collapsed, rules not
compared.

The built tables carry no caption, since the captions are manuscript text.
The numbers the captions print are computed by make_tables.py and listed in
tables.json under "caption_values"; each is looked up in the paper's caption
and counts as a match when its printed form occurs there.

The manuscript is not distributed. Without it (--paper-dir or
$AA_PAPER_AI_NATIVE_ACADEMIA) every table is reported as skipped. The
citation tables follow the citation mode: compared in strict mode, reported
but not counted after a fresh fetch, skipped when the counts are absent.

    AA_PAPER_AI_NATIVE_ACADEMIA=path/to/workshop python paper/ai_native_academia/check_tables.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))


def _load(key: str, path: str):
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return sys.modules[key]


TMS = _load("tmlr_manuscript", os.path.join(REPO, "paper", "tmlr", "manuscript.py"))
TCT = _load("tmlr_check_tables", os.path.join(REPO, "paper", "tmlr", "check_tables.py"))
CM = _load("ai_native_academia_check_macros", os.path.join(HERE, "check_macros.py"))
MM = _load("ai_native_academia_make_macros", os.path.join(HERE, "make_macros.py"))
MT = _load("ai_native_academia_make_tables", os.path.join(HERE, "make_tables.py"))

CITATION = set(MM.CITATION_TABLES) | set(MT.CITATION)
NAME = "ai_native_academia"


def tables() -> list[str]:
    return list(MM.TABLES) + list(MT.TABLES)


def caption_values(built_dir: str) -> dict[str, dict[str, str]]:
    path = os.path.join(os.path.dirname(built_dir.rstrip(os.sep)), "tables.json")
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh).get("caption_values", {})


def check(built_dir: str, mode: str, paper: str | None):
    """Returns paper/tmlr/check_tables.Result."""
    res = TCT.Result()
    captions = caption_values(built_dir)
    for name in tables():
        cit = name in CITATION
        if paper is None:
            res.add(name, "SKIP")
            continue
        if cit and mode == "absent":
            res.add(name, "SKIP", "citation counts absent")
            continue
        counted = not (cit and mode == "fresh")
        path = os.path.join(built_dir, name)
        if not os.path.exists(path):
            res.add(name, "MISSING", "(not built)", counted)
            continue
        with open(path, encoding="utf-8") as fh:
            built = fh.read()
        want = TMS.strip_comments(TMS.read(paper, os.path.join("tables", name)))
        a, b = TMS.tabular_rows(want), TMS.tabular_rows(built)
        res.add(name, "MATCH" if a == b else "MISMATCH",
                "" if a == b else TCT.first_difference(a, b), counted)
        cap = TMS.caption(want)
        for key, value in captions.get(name, {}).items():
            found = value in cap
            res.add(f"{name} caption {key}", "MATCH" if found else "MISMATCH",
                    "" if found else f"{value!r} not in the paper's caption", counted)
    if paper is None:
        res.lines.append(f"  SKIP      every table: {CM.SKIP_REASON}")
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=os.environ.get("AA_DATA", "data"))
    ap.add_argument("--built-dir", default=None, help=f"default: {{data-dir}}/{NAME}/tables")
    ap.add_argument("--mode", choices=["strict", "fresh", "absent"], default=None,
                    help="citation mode; default: from the local citation files")
    ap.add_argument("--paper-dir", default=None,
                    help=f"the manuscript directory (default: ${CM.ENV})")
    ap.add_argument("--report-only", action="store_true",
                    help="exit 0 even on a mismatch (the pipeline stage; verify.py is the gate)")
    a = ap.parse_args()
    paper = CM.paper_dir(a.paper_dir)
    m = a.mode or CM.citation_mode(a.data_dir)
    res = check(a.built_dir or os.path.join(a.data_dir, NAME, "tables"), m, paper)
    print(f"AI-Native Academia tables against the paper, citation mode {m}")
    for line in res.lines + res.summary():
        print(line)
    if (res.bad or res.missing) and not a.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
