#!/usr/bin/env python3
"""Compare the built TMLR macros and tables with the paper's own files.

make_macros.py writes three macro files and six tables under $AA_DATA/tmlr/.
reference/tmlr/tex/ holds the files the paper was built with, copied byte for
byte from upstream commit eda2733. This module compares them:

  macros   every \\newcommand in each reference file is parsed with full
           brace matching, then the name sets and the values (as strings,
           exactly) are compared file by file. A missing, an extra and a
           differing macro are each a mismatch.
  tables   byte for byte. None of the six was edited by hand after it was
           generated: upstream's generators, rerun on upstream's inputs,
           write all six byte-identical to the paper's copies.

The eleven macros and two tables that need citation outputs
(make_macros.CITATION_MACROS, CITATION_TABLES) follow the citation mode of
src/citations/snapshot.py:

  strict   compared like everything else
  fresh    compared and reported, not counted: a new fetch gives new numbers
  absent   not compared, reported as skipped. make_macros.py must then have
           skipped exactly these (its skipped.json), and nothing else.

verify.py calls `check` for its TMLR macros section. Run alone it prints the
same report and exits non-zero on any mismatch or missing file:

    python paper/tmlr/check_macros.py
    python paper/tmlr/check_macros.py --built-dir path/to/tmlr --mode strict
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))
from make_macros import CITATION_MACROS, CITATION_TABLES, ROUND_FILES, TABLES  # noqa: E402

REF_DIR = os.path.join(REPO, "reference", "tmlr", "tex")
STRICT, FRESH, ABSENT = "strict", "fresh", "absent"


# ================================================================= parser ===

def strip_comment(line: str) -> str:
    """The line up to its first unescaped %. An escaped % (\\%) is text."""
    i = 0
    while i < len(line):
        c = line[i]
        if c == "\\":
            i += 2
            continue
        if c == "%":
            return line[:i]
        i += 1
    return line


def _group(text: str, i: int) -> tuple[str, int]:
    """The content of the brace group opening at text[i], and the index after
    its closing brace. Escaped braces (\\{, \\}) do not count."""
    if i >= len(text) or text[i] != "{":
        raise ValueError(f"expected '{{' at offset {i}")
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    raise ValueError(f"unbalanced braces in group starting at offset {i}")


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def parse_newcommands(text: str) -> dict[str, str]:
    """Name to body of every \\newcommand in `text`, without the backslash.

    Accepts \\newcommand{\\Name}{body}, \\newcommand\\Name{body}, the starred
    form and an optional [n] argument count. Comments are stripped first. The
    body is everything between its outer braces, nested groups included. A
    name defined twice, or a definition without a body, raises ValueError, as
    LaTeX would refuse it.
    """
    body = "\n".join(strip_comment(ln) for ln in text.splitlines())
    out: dict[str, str] = {}
    key = "\\newcommand"
    i = 0
    while True:
        i = body.find(key, i)
        if i < 0:
            return out
        j = i + len(key)
        if j < len(body) and body[j].isalpha():     # \newcommandfoo is not ours
            i = j
            continue
        if j < len(body) and body[j] == "*":
            j += 1
        j = _skip_ws(body, j)
        if j < len(body) and body[j] == "{":
            name, j = _group(body, j)
            name = name.strip()
        elif j < len(body) and body[j] == "\\":
            k = j + 1
            while k < len(body) and body[k].isalpha():
                k += 1
            name, j = body[j:k], k
        else:
            raise ValueError(f"\\newcommand without a name at offset {i}")
        if not name.startswith("\\") or not name[1:].isalpha():
            raise ValueError(f"not a control sequence name: {name!r}")
        j = _skip_ws(body, j)
        if j < len(body) and body[j] == "[":
            k = body.find("]", j)
            if k < 0:
                raise ValueError(f"unclosed argument count after {name}")
            j = _skip_ws(body, k + 1)
        value, j = _group(body, j)
        if name[1:] in out:
            raise ValueError(f"{name} defined twice")
        out[name[1:]] = value
        i = j


# ============================================================= comparison ===

@dataclass
class MacroDiff:
    """The outcome of comparing one built macro file with its reference."""
    matched: list[str] = field(default_factory=list)
    mismatched: list[tuple[str, str, str]] = field(default_factory=list)  # name, ref, built
    missing: list[str] = field(default_factory=list)   # in reference, not built
    extra: list[str] = field(default_factory=list)     # built, not in reference
    skipped: list[str] = field(default_factory=list)   # in reference, not compared

    @property
    def ok(self) -> bool:
        return not (self.mismatched or self.missing or self.extra)


def compare_macros(built: dict[str, str], ref: dict[str, str],
                   skip: frozenset[str] | set[str] = frozenset()) -> MacroDiff:
    """Name sets and values. Names in `skip` are not compared in either
    direction: a skipped name that was built anyway is neither an error nor
    a match."""
    d = MacroDiff()
    for name in sorted(ref):
        if name in skip:
            d.skipped.append(name)
        elif name not in built:
            d.missing.append(name)
        elif built[name] == ref[name]:
            d.matched.append(name)
        else:
            d.mismatched.append((name, ref[name], built[name]))
    d.extra = sorted(n for n in built if n not in ref and n not in skip)
    return d


@dataclass
class Result:
    """Everything check() found: one record per macro or table, and the
    report lines for the ones that did not match."""
    records: list[tuple[str, str, str, bool]] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    def add(self, verdict: str, name: str, detail: str = "", counted: bool = True) -> None:
        """verdict is ok, bad, missing or skipped. An uncounted record is a
        citation item compared in fresh mode: reported, never a failure."""
        kind = "table" if name.startswith("tmlr/tables/") else "macro"
        self.records.append((kind, verdict, name, counted))
        if verdict in ("ok", "skipped"):
            return
        tag = "(fresh)  " if not counted else ("MISSING  " if verdict == "missing"
                                               else "MISMATCH ")
        self.lines.append(f"  {tag} {name}  {detail}")

    def count(self, verdict: str, kind: str | None = None, counted: bool = True) -> int:
        return sum(1 for k, v, _, c in self.records
                   if v == verdict and c == counted and (kind is None or k == kind))

    @property
    def ok(self) -> int:
        return self.count("ok")

    @property
    def bad(self) -> int:
        return self.count("bad")

    @property
    def missing(self) -> int:
        return self.count("missing")

    @property
    def skipped(self) -> int:
        return self.count("skipped")

    @property
    def uncounted(self) -> int:
        return sum(1 for *_, c in self.records if not c)

    def summary(self) -> list[str]:
        out = []
        for kind in ("macro", "table"):
            n = [self.count(v, kind) for v in ("ok", "bad", "missing", "skipped")]
            u = sum(1 for k, *_, c in self.records if k == kind and not c)
            out.append(f"  {kind}s: {n[0]} matched, {n[1]} mismatched, {n[2]} missing, "
                       f"{n[3]} skipped" + (f", {u} compared but not counted "
                                            "(fresh citations)" if u else ""))
        return out


def read_skipped(built_dir: str) -> dict | None:
    path = os.path.join(built_dir, "skipped.json")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def check(built_dir: str, mode: str, ref_dir: str = REF_DIR) -> Result:
    """Compare every macro and table under built_dir with ref_dir, under one
    citation mode (strict, fresh or absent)."""
    if mode not in (STRICT, FRESH, ABSENT):
        raise ValueError(f"unknown citation mode {mode!r}")
    res = Result()
    sk = read_skipped(built_dir)
    if mode == ABSENT and sk is not None:
        # The generator may skip citation items only: any other omission
        # would hide a bug behind the citation exemption. (It may also have
        # skipped none, if citation outputs from an earlier run are present.)
        got = {m for v in sk["macros"].values() for m in v}
        other = sorted(got - CITATION_MACROS) + sorted(set(sk["tables"]) - CITATION_TABLES)
        if other:
            res.add("bad", "tmlr/skipped.json", f"skipped non-citation items {other}")

    for fname in ROUND_FILES.values():
        ref = parse_newcommands(open(os.path.join(ref_dir, fname)).read())
        path = os.path.join(built_dir, fname)
        if not os.path.exists(path):
            for name in ref:
                if mode == ABSENT and name in CITATION_MACROS:
                    res.add("skipped", f"\\{name}")
                else:
                    res.add("missing", f"{fname} \\{name}", "(not built)",
                            counted=not (mode == FRESH and name in CITATION_MACROS))
            continue
        built = parse_newcommands(open(path).read())
        skip = CITATION_MACROS if mode == ABSENT else frozenset()
        d = compare_macros(built, ref, skip)
        for name in d.matched:
            res.add("ok", f"\\{name}", counted=not (mode == FRESH and name in CITATION_MACROS))
        for name, want, got in d.mismatched:
            res.add("bad", f"{fname} \\{name}", f"reference {want!r}, built {got!r}",
                    counted=not (mode == FRESH and name in CITATION_MACROS))
        for name in d.missing:
            res.add("missing", f"{fname} \\{name}", "(not in built file)",
                    counted=not (mode == FRESH and name in CITATION_MACROS))
        for name in d.extra:
            res.add("bad", f"{fname} \\{name}", "(built, not in reference)")
        for name in d.skipped:
            res.add("skipped", f"\\{name}")

    for t in TABLES:
        name = f"tmlr/tables/{t}"
        cit = t in CITATION_TABLES
        if mode == ABSENT and cit:
            res.add("skipped", name)
            continue
        built = os.path.join(built_dir, "tables", t)
        counted = not (mode == FRESH and cit)
        if not os.path.exists(built):
            res.add("missing", name, "(not built)", counted=counted)
            continue
        with open(built, "rb") as a, open(os.path.join(ref_dir, "tables", t), "rb") as b:
            same = a.read() == b.read()
        res.add("ok" if same else "bad", name, "" if same else "bytes differ",
                counted=counted)
    return res


def citation_mode(data_dir: str) -> str:
    from citations.snapshot import mode
    return mode(os.path.join(data_dir, "per_paper", "citations"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=os.environ.get("AA_DATA", "data"))
    ap.add_argument("--built-dir", default=None, help="default: {data-dir}/tmlr")
    ap.add_argument("--mode", choices=[STRICT, FRESH, ABSENT], default=None,
                    help="citation mode; default: from the local citation files")
    ap.add_argument("--report-only", action="store_true",
                    help="exit 0 even on a mismatch (the pipeline stage; "
                         "verify.py is the gate)")
    a = ap.parse_args()
    built = a.built_dir or os.path.join(a.data_dir, "tmlr")
    m = a.mode or citation_mode(a.data_dir)
    res = check(built, m)
    print(f"TMLR macros and tables, citation mode {m}")
    for line in res.lines + res.summary():
        print(line)
    if (res.bad or res.missing) and not a.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
