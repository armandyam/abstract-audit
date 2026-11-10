#!/usr/bin/env python3
"""Compare every TMLR table the release builds with the paper's own table.

The release writes the paper's data-driven tables under $AA_DATA/tmlr/tables/
(make_macros.py: six, make_tables.py: seven) and commits the two that carry
no computed value (paper/tmlr/tables/metric_families.tex and nine.tex). This
module compares each with the manuscript's table: tables/{name} in the
manuscript directory, or, for the four tables main.tex prints inline (corpus,
prompts, nine, self_audit), the table environment with that label.

The comparison is the tabular body, cell by cell: every row of every tabular
in the table, with whitespace collapsed and the revision markers (\\rev,
\\revtwo, ...) unwrapped, since they only colour revised text in the review
build. Rules such as \\midrule are layout and not compared. The captions are
compared the same way and reported, not counted: the numbers in them are
checked one by one by check_claims.py.

The manuscript is not distributed. Without it ($AA_PAPER or --paper-dir, see
manuscript.py) every table is reported as skipped. The citation tables
follow the citation mode, as the citation claims do: compared in strict
mode, compared and reported but not counted after a fresh fetch, skipped
when the counts are absent. The self-audit table needs the self_audit stage,
which needs the manuscript; with the manuscript given it is compared like
the others.

    AA_PAPER=path/to/manuscript python paper/tmlr/check_tables.py
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))

import make_macros  # noqa: E402
import make_tables  # noqa: E402
from manuscript import SKIP_REASON, caption, paper_dir, table_source, tabular_rows  # noqa: E402

STATIC_DIR = os.path.join(HERE, "tables")
STATIC = ("metric_families.tex", "nine.tex")
CITATION = make_macros.CITATION_TABLES | set(make_tables.CITATION)


def tables() -> list[str]:
    """Every table the paper prints, by the release's file name."""
    return list(make_macros.TABLES) + list(make_tables.TABLES) + list(STATIC)


def built_path(name: str, built_dir: str) -> str:
    return os.path.join(STATIC_DIR if name in STATIC else built_dir, name)


@dataclass
class Result:
    records: list[tuple[str, str, bool]] = field(default_factory=list)  # name, verdict, counted
    lines: list[str] = field(default_factory=list)

    def add(self, name: str, verdict: str, detail: str = "", counted: bool = True) -> None:
        self.records.append((name, verdict, counted))
        if verdict in ("MATCH", "SKIP") and not detail:
            return
        tag = verdict if counted else f"{verdict} (fresh, not counted)"
        self.lines.append(f"  {tag:<9} tables/{name}" + (f"  {detail}" if detail else ""))

    def count(self, verdict: str) -> int:
        return sum(1 for _, v, c in self.records if v == verdict and c)

    @property
    def ok(self) -> int:
        return self.count("MATCH")

    @property
    def bad(self) -> int:
        return self.count("MISMATCH")

    @property
    def missing(self) -> int:
        return self.count("MISSING")

    def summary(self) -> list[str]:
        n = len(self.records)
        sk = sum(1 for _, v, _ in self.records if v == "SKIP")
        u = sum(1 for *_, c in self.records if not c)
        return [f"  tables: {self.ok} match the paper, {self.bad} differ, "
                f"{self.missing} missing, {sk} skipped (of {n})"
                + (f", {u} compared but not counted (fresh citations)" if u else "")]


def first_difference(a: list[list[str]], b: list[list[str]]) -> str:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"row {i + 1}: paper {' & '.join(x)!r}, built {' & '.join(y)!r}"
    return f"paper has {len(a)} rows, built {len(b)}"


def check(built_dir: str, mode: str, paper: str | None) -> Result:
    res = Result()
    for name in tables():
        cit = name in CITATION
        if paper is None:
            res.add(name, "SKIP")
            continue
        if cit and mode == "absent":
            res.add(name, "SKIP", "citation counts absent")
            continue
        counted = not (cit and mode == "fresh")
        path = built_path(name, built_dir)
        if not os.path.exists(path):
            res.add(name, "MISSING", "(not built)", counted)
            continue
        with open(path, encoding="utf-8") as fh:
            built = fh.read()
        want = table_source(paper, name)
        a, b = tabular_rows(want), tabular_rows(built)
        cap = "" if caption(want) == caption(built) else "(caption text differs; not counted)"
        if a == b:
            res.add(name, "MATCH", cap, counted)
        else:
            res.add(name, "MISMATCH", first_difference(a, b) + (f" {cap}" if cap else ""),
                    counted)
    if paper is None:
        res.lines.append(f"  SKIP      every table: {SKIP_REASON}")
    return res


def citation_mode(data_dir: str) -> str:
    from citations.snapshot import mode
    return mode(os.path.join(data_dir, "per_paper", "citations"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=os.environ.get("AA_DATA", "data"))
    ap.add_argument("--built-dir", default=None, help="default: {data-dir}/tmlr/tables")
    ap.add_argument("--mode", choices=["strict", "fresh", "absent"], default=None,
                    help="citation mode; default: from the local citation files")
    ap.add_argument("--paper-dir", default=None,
                    help="the manuscript directory (default: $AA_PAPER)")
    ap.add_argument("--report-only", action="store_true",
                    help="exit 0 even on a mismatch (the pipeline stage; verify.py is the gate)")
    a = ap.parse_args()
    paper = paper_dir(a.paper_dir)
    m = a.mode or citation_mode(a.data_dir)
    res = check(a.built_dir or os.path.join(a.data_dir, "tmlr", "tables"), m, paper)
    print(f"TMLR tables against the paper, citation mode {m}")
    for line in res.lines + res.summary():
        print(line)
    if (res.bad or res.missing) and not a.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
