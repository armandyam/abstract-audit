#!/usr/bin/env python3
"""Compare the built AI-Native Academia macros with the values the paper prints.

make_macros.py writes generated_round2.tex under
$AA_DATA/ai_native_academia/. The paper resolves 52 inline numbers through
the same macro names. The printed values of the 42 that need no citation
counts are stored in paper/ai_native_academia/reference/macros.csv (file,
name, value): computed numbers and the two computed topic names, never text
from the manuscript. The ten citation macros (make_macros.CITATION_MACROS)
are not stored; their printed values are read from the manuscript itself.
The comparison, the citation modes and the treatment of incomplete sections
are those of paper/tmlr/check_macros.py, whose parser and comparison this
module reuses:

  built   every \\newcommand of the built file against macros.csv by name
          and exact value, and each citation macro against the manuscript's
          value. A missing, an extra and a differing macro are each a
          mismatch.
  paper   with a local copy of the manuscript (--paper-dir or
          $AA_PAPER_AI_NATIVE_ACADEMIA, the folder holding its main.tex and
          generated_round2.tex), macros.csv against the paper's own macro
          file. Without it this comparison and the citation macros are
          reported as skipped.

Citation modes (src/citations/snapshot.py): strict compares the citation
macros, fresh reports them without counting them, absent skips them. In
absent mode make_macros.py may have skipped citation items only (its
skipped.json); it need not have skipped all of them.

macros.csv is written from the manuscript, once per manuscript revision:

    python paper/ai_native_academia/check_macros.py --write-reference --paper-dir path/to/workshop

    python paper/ai_native_academia/check_macros.py
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
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


# paper/tmlr has modules of the same file names, so both folders' modules
# are loaded under names of their own.
TM = _load("tmlr_check_macros", os.path.join(REPO, "paper", "tmlr", "check_macros.py"))
MM = _load("ai_native_academia_make_macros", os.path.join(HERE, "make_macros.py"))

CITATION_MACROS = MM.CITATION_MACROS
CITATION_TABLES = MM.CITATION_TABLES
MACRO_FILE = MM.MACRO_FILE
REF = os.path.join(HERE, "reference", "macros.csv")
STRICT, FRESH, ABSENT = "strict", "fresh", "absent"
CIT_ABSENT = "citation counts absent"
CIT_PAPER = "printed values come from the manuscript, not distributed"
ENV = "AA_PAPER_AI_NATIVE_ACADEMIA"
SKIP_REASON = ("the manuscript is not distributed; set AA_PAPER_AI_NATIVE_ACADEMIA "
               "to a local copy of its LaTeX source to run this check")
NAME = "ai_native_academia"


def paper_dir(arg: str | None = None) -> str | None:
    """The manuscript directory from `arg` or $AA_PAPER_AI_NATIVE_ACADEMIA,
    or None. A given directory without main.tex is an error."""
    d = arg or os.environ.get(ENV) or None
    if d is None:
        return None
    if not os.path.exists(os.path.join(d, "main.tex")):
        raise SystemExit(f"{ENV}={d} has no main.tex; point it at the folder "
                         "that holds the workshop paper's main.tex")
    return d


def load_reference(path: str = REF) -> dict[str, str]:
    """macros.csv as {name: value}. A citation macro listed there is an
    error: its value is not distributed."""
    out: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["file"] != MACRO_FILE:
                raise ValueError(f"{path}: unknown macro file {r['file']!r}")
            if r["name"] in CITATION_MACROS:
                raise ValueError(f"{r['name']} is a citation macro; it must not be in {path}")
            if r["name"] in out:
                raise ValueError(f"{r['name']} listed twice in {path}")
            out[r["name"]] = r["value"]
    return out


def paper_macros(paper: str) -> dict[str, str]:
    with open(os.path.join(paper, MACRO_FILE), encoding="utf-8") as fh:
        return TM.parse_newcommands(fh.read())


def write_reference(paper: str, path: str = REF) -> int:
    rows = [(MACRO_FILE, n, v) for n, v in sorted(paper_macros(paper).items())
            if n not in CITATION_MACROS]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["file", "name", "value"])
        w.writerows(rows)
    return len(rows)


def summary(res) -> list[str]:
    n = [res.count(v, "macro") for v in ("ok", "bad", "missing", "skipped")]
    u = sum(1 for k, *_, c in res.records if k == "macro" and not c)
    out = [f"  macros: {n[0]} matched, {n[1]} mismatched, {n[2]} missing, {n[3]} skipped"
           + (f", {u} compared but not counted (fresh citations)" if u else "")]
    out += [f"  SKIP {k:>4}  {why}" for why, k in sorted(res.skip_reasons.items())]
    if res.paper_checked:
        p = [res.count(v, "paper") for v in ("ok", "bad")]
        out.append(f"  macros.csv against the manuscript's macro file: {p[0]} equal, "
                   f"{p[1]} differ")
    else:
        out.append(f"  macros.csv against the manuscript: skipped ({SKIP_REASON})")
    return out


def check(built_dir: str, mode: str, ref_path: str = REF, paper: str | None = None):
    """Compare the built macro file with macros.csv under one citation mode;
    returns paper/tmlr/check_macros.Result (use summary() for its summary)."""
    if mode not in (STRICT, FRESH, ABSENT):
        raise ValueError(f"unknown citation mode {mode!r}")
    res = TM.Result()
    ref = load_reference(ref_path)
    pm = paper_macros(paper) if paper is not None else None
    if pm is not None:
        res.paper_checked = True
        d = TM.compare_macros(pm, ref, CITATION_MACROS)
        for name in d.matched:
            res.add("ok", f"paper:{MACRO_FILE} \\{name}")
        for name, want, value in d.mismatched:
            res.add("bad", f"paper:{MACRO_FILE} \\{name}",
                    f"macros.csv {want!r}, manuscript {value!r}")
        for name in d.missing:
            res.add("bad", f"paper:{MACRO_FILE} \\{name}", "(in macros.csv, not in the manuscript)")
        for name in d.extra:
            res.add("bad", f"paper:{MACRO_FILE} \\{name}", "(in the manuscript, not in macros.csv)")
        if mode != ABSENT:
            ref = {**ref, **{n: v for n, v in pm.items() if n in CITATION_MACROS}}
    sk = TM.read_skipped(built_dir)
    why_missing = "(not built)"
    if sk and sk.get("incomplete"):
        for item in sk["incomplete"]:
            res.lines.append(f"  INCOMPLETE {item['section']}: input absent {item['input']}")
        why_missing = "(not built: a section's input is absent, see INCOMPLETE above)"
    if mode == ABSENT and sk is not None:
        got = {m for v in sk["macros"].values() for m in v}
        other = sorted(got - CITATION_MACROS) + sorted(set(sk["tables"]) - CITATION_TABLES)
        if other:
            res.add("bad", f"{NAME}/skipped.json", f"skipped non-citation items {other}")

    cit_compared = mode != ABSENT and pm is not None
    if not cit_compared:
        for name in sorted(CITATION_MACROS):
            res.add("skipped", f"\\{name}", CIT_ABSENT if mode == ABSENT else CIT_PAPER)

    def counted(name: str) -> bool:
        return not (mode == FRESH and name in CITATION_MACROS)

    path = os.path.join(built_dir, MACRO_FILE)
    if not os.path.exists(path):
        for name in ref:
            res.add("missing", f"{MACRO_FILE} \\{name}", why_missing, counted=counted(name))
        return res
    with open(path, encoding="utf-8") as fh:
        built = TM.parse_newcommands(fh.read())
    d = TM.compare_macros(built, ref, frozenset() if cit_compared else CITATION_MACROS)
    for name in d.matched:
        res.add("ok", f"\\{name}", counted=counted(name))
    for name, want, got in d.mismatched:
        res.add("bad", f"{MACRO_FILE} \\{name}", f"printed {want!r}, built {got!r}",
                counted=counted(name))
    for name in d.missing:
        res.add("missing", f"{MACRO_FILE} \\{name}",
                "(not in built file)" if why_missing == "(not built)" else why_missing,
                counted=counted(name))
    for name in d.extra:
        res.add("bad", f"{MACRO_FILE} \\{name}", "(built, not in macros.csv)")
    return res


def citation_mode(data_dir: str) -> str:
    from citations.snapshot import mode
    return mode(os.path.join(data_dir, "per_paper", "citations"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=os.environ.get("AA_DATA", "data"))
    ap.add_argument("--built-dir", default=None, help=f"default: {{data-dir}}/{NAME}")
    ap.add_argument("--mode", choices=[STRICT, FRESH, ABSENT], default=None,
                    help="citation mode; default: from the local citation files")
    ap.add_argument("--paper-dir", default=None, help=f"the manuscript directory (default: ${ENV})")
    ap.add_argument("--write-reference", action="store_true",
                    help="write reference/macros.csv from the manuscript's macro file")
    ap.add_argument("--report-only", action="store_true",
                    help="exit 0 even on a mismatch (the pipeline stage; verify.py is the gate)")
    a = ap.parse_args()
    paper = paper_dir(a.paper_dir)
    if a.write_reference:
        if paper is None:
            sys.exit(f"--write-reference needs the manuscript: set {ENV} or pass --paper-dir")
        print(f"wrote {write_reference(paper)} macros to {REF}")
        return
    m = a.mode or citation_mode(a.data_dir)
    res = check(a.built_dir or os.path.join(a.data_dir, NAME), m, paper=paper)
    print(f"AI-Native Academia macros, citation mode {m}")
    for line in res.lines + summary(res):
        print(line)
    if (res.bad or res.missing) and not a.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
