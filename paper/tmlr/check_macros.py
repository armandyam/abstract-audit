#!/usr/bin/env python3
"""Compare the built TMLR macros with the values the paper prints.

make_macros.py writes three macro files under $AA_DATA/tmlr/. The paper
resolves 163 inline numbers through the same macro names. The printed
values of the 152 that need no citation counts are stored in
paper/tmlr/reference/macros.csv (file, name, value): computed numbers and the few
computed labels (a topic's leading term, the ten commonest acronyms), never
text from the manuscript. The eleven citation macros
(make_macros.CITATION_MACROS) are not stored: the citation counts and every
statistic computed from them are not distributed, so their printed values
are read from the manuscript itself. This module compares:

  built     every \\newcommand of each built file, parsed with full brace
            matching, against macros.csv by name and exact value, and each
            citation macro against the manuscript's value. A missing, an
            extra and a differing macro are each a mismatch.
  paper     with a local copy of the manuscript ($AA_PAPER or --paper-dir,
            see manuscript.py), macros.csv against the paper's own
            generated_round{2,3,4}.tex, by name and exact value, in every
            citation mode. Without it this comparison is reported as
            skipped, and so are the citation macros, whose printed values
            only the manuscript holds.

The generated tables are compared by check_tables.py.

A section make_macros.py could not run for lack of an input (the --from
aggregate route has no processed abstracts) is listed in skipped.json under
"incomplete" with the input it missed. Its macros are then reported missing,
with that reason, and count as failures.

The eleven macros that need citation outputs (make_macros.CITATION_MACROS)
follow the citation mode of src/citations/snapshot.py:

  strict   compared with the manuscript's values like everything else
           (skipped without the manuscript)
  fresh    compared and reported, not counted: a new fetch gives new numbers
  absent   not compared, reported as skipped. make_macros.py may then have
           skipped citation items only (its skipped.json); it need not
           have skipped all of them, if outputs from an earlier run remain.

macros.csv is written from the manuscript, once per manuscript revision,
without the citation macros:

    python paper/tmlr/check_macros.py --write-reference --paper-dir path/to/manuscript

verify.py calls `check` for its TMLR macros section. Run alone it prints the
same report and exits non-zero on any mismatch or missing macro:

    python paper/tmlr/check_macros.py
    python paper/tmlr/check_macros.py --built-dir path/to/tmlr --mode strict
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))
from make_macros import CITATION_MACROS, CITATION_TABLES, ROUND_FILES  # noqa: E402
from manuscript import SKIP_REASON, paper_dir  # noqa: E402

REF = os.path.join(HERE, "reference", "macros.csv")
STRICT, FRESH, ABSENT = "strict", "fresh", "absent"
CIT_ABSENT = "citation counts absent"
CIT_PAPER = "printed values come from the manuscript, not distributed"


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
    """Everything check() found: one record per macro, and the report lines
    for the ones that did not match."""
    records: list[tuple[str, str, str, bool]] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    paper_checked: bool = False
    skip_reasons: dict[str, int] = field(default_factory=dict)

    def add(self, verdict: str, name: str, detail: str = "", counted: bool = True) -> None:
        """verdict is ok, bad, missing or skipped. An uncounted record is a
        citation item compared in fresh mode: reported, never a failure. The
        detail of a skipped record is its reason."""
        kind = "paper" if name.startswith("paper:") else "macro"
        self.records.append((kind, verdict, name, counted))
        if verdict == "skipped":
            why = detail or "not compared"
            self.skip_reasons[why] = self.skip_reasons.get(why, 0) + 1
            return
        if verdict == "ok":
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
        n = [self.count(v, "macro") for v in ("ok", "bad", "missing", "skipped")]
        u = sum(1 for k, *_, c in self.records if k == "macro" and not c)
        out = [f"  macros: {n[0]} matched, {n[1]} mismatched, {n[2]} missing, "
               f"{n[3]} skipped" + (f", {u} compared but not counted "
                                    "(fresh citations)" if u else "")]
        out += [f"  SKIP {n:>4}  {why}" for why, n in sorted(self.skip_reasons.items())]
        if self.paper_checked:
            p = [self.count(v, "paper") for v in ("ok", "bad")]
            out.append(f"  macros.csv against the manuscript's macro files: {p[0]} equal, "
                       f"{p[1]} differ")
        else:
            out.append(f"  macros.csv against the manuscript: skipped ({SKIP_REASON})")
        return out


def load_reference(path: str = REF) -> dict[str, dict[str, str]]:
    """macros.csv as {round file: {name: value}}. It holds no citation macro:
    one listed there is an error (their values are not distributed)."""
    out: dict[str, dict[str, str]] = {f: {} for f in ROUND_FILES.values()}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["name"] in CITATION_MACROS:
                raise ValueError(f"{r['name']} is a citation macro; its printed value "
                                 f"comes from the manuscript and must not be in {path}")
            if r["name"] in out.setdefault(r["file"], {}):
                raise ValueError(f"{r['name']} listed twice in {path}")
            out[r["file"]][r["name"]] = r["value"]
    return out


def paper_macros(paper: str) -> dict[str, dict[str, str]]:
    """The manuscript's own macro files, parsed."""
    out = {}
    for fname in ROUND_FILES.values():
        with open(os.path.join(paper, fname), encoding="utf-8") as fh:
            out[fname] = parse_newcommands(fh.read())
    return out


def write_reference(paper: str, path: str = REF) -> int:
    """Write macros.csv from the manuscript's macro files, without the
    citation macros. Returns the number of macros written."""
    rows = [(f, name, value) for f, m in paper_macros(paper).items()
            for name, value in sorted(m.items()) if name not in CITATION_MACROS]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["file", "name", "value"])
        w.writerows(rows)
    return len(rows)


def check_paper(res: Result, ref: dict[str, dict[str, str]],
                pm: dict[str, dict[str, str]]) -> None:
    """macros.csv against the manuscript's macro files `pm`: every macro by
    name and value, except the citation macros, which macros.csv does not
    hold. Counted in every citation mode."""
    res.paper_checked = True
    for fname, got in pm.items():
        d = compare_macros(got, ref.get(fname, {}), CITATION_MACROS)
        for name in d.matched:
            res.add("ok", f"paper:{fname} \\{name}")
        for name, want, value in d.mismatched:
            res.add("bad", f"paper:{fname} \\{name}",
                    f"macros.csv {want!r}, manuscript {value!r}")
        for name in d.missing:
            res.add("bad", f"paper:{fname} \\{name}", "(in macros.csv, not in the manuscript)")
        for name in d.extra:
            res.add("bad", f"paper:{fname} \\{name}", "(in the manuscript, not in macros.csv)")


def read_skipped(built_dir: str) -> dict | None:
    path = os.path.join(built_dir, "skipped.json")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def check(built_dir: str, mode: str, ref_path: str = REF,
          paper: str | None = None) -> Result:
    """Compare every macro under built_dir with macros.csv, under one
    citation mode (strict, fresh or absent), and, given the manuscript
    directory `paper`, macros.csv with the manuscript's own files. The
    citation macros are compared with the manuscript's values; without the
    manuscript they are skipped."""
    if mode not in (STRICT, FRESH, ABSENT):
        raise ValueError(f"unknown citation mode {mode!r}")
    res = Result()
    reference = load_reference(ref_path)
    pm = paper_macros(paper) if paper is not None else None
    if pm is not None:
        check_paper(res, reference, pm)
        if mode != ABSENT:
            # The printed citation values, from the manuscript only.
            reference = {f: {**m, **{n: v for n, v in pm.get(f, {}).items()
                                     if n in CITATION_MACROS}}
                         for f, m in reference.items()}
    sk = read_skipped(built_dir)
    why_missing = "(not built)"
    if sk and sk.get("incomplete"):
        for item in sk["incomplete"]:
            res.lines.append(f"  INCOMPLETE {item['section']}: input absent {item['input']}")
        why_missing = "(not built: a section's input is absent, see INCOMPLETE above)"
    if mode == ABSENT and sk is not None:
        # The generator may skip citation items only: any other omission
        # would hide a bug behind the citation exemption. (It may also have
        # skipped none, if citation outputs from an earlier run are present.)
        got = {m for v in sk["macros"].values() for m in v}
        other = sorted(got - CITATION_MACROS) + sorted(set(sk["tables"]) - CITATION_TABLES)
        if other:
            res.add("bad", "tmlr/skipped.json", f"skipped non-citation items {other}")

    cit_compared = mode != ABSENT and pm is not None
    if not cit_compared:
        for name in sorted(CITATION_MACROS):
            res.add("skipped", f"\\{name}", CIT_ABSENT if mode == ABSENT else CIT_PAPER)
    for fname in ROUND_FILES.values():
        ref = reference.get(fname, {})
        path = os.path.join(built_dir, fname)
        if not os.path.exists(path):
            for name in ref:
                res.add("missing", f"{fname} \\{name}", why_missing,
                        counted=not (mode == FRESH and name in CITATION_MACROS))
            continue
        built = parse_newcommands(open(path).read())
        skip = frozenset() if cit_compared else CITATION_MACROS
        d = compare_macros(built, ref, skip)
        for name in d.matched:
            res.add("ok", f"\\{name}", counted=not (mode == FRESH and name in CITATION_MACROS))
        for name, want, got in d.mismatched:
            res.add("bad", f"{fname} \\{name}", f"printed {want!r}, built {got!r}",
                    counted=not (mode == FRESH and name in CITATION_MACROS))
        for name in d.missing:
            res.add("missing", f"{fname} \\{name}",
                    "(not in built file)" if why_missing == "(not built)" else why_missing,
                    counted=not (mode == FRESH and name in CITATION_MACROS))
        for name in d.extra:
            res.add("bad", f"{fname} \\{name}", "(built, not in macros.csv)")
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
    ap.add_argument("--paper-dir", default=None,
                    help="the manuscript directory (default: $AA_PAPER)")
    ap.add_argument("--write-reference", action="store_true",
                    help="write paper/tmlr/reference/macros.csv from the manuscript's macro files")
    ap.add_argument("--report-only", action="store_true",
                    help="exit 0 even on a mismatch (the pipeline stage; "
                         "verify.py is the gate)")
    a = ap.parse_args()
    paper = paper_dir(a.paper_dir)
    if a.write_reference:
        if paper is None:
            sys.exit("--write-reference needs the manuscript: set AA_PAPER or pass --paper-dir")
        print(f"wrote {write_reference(paper)} macros to {REF}")
        return
    built = a.built_dir or os.path.join(a.data_dir, "tmlr")
    m = a.mode or citation_mode(a.data_dir)
    res = check(built, m, paper=paper)
    print(f"TMLR macros, citation mode {m}")
    for line in res.lines + res.summary():
        print(line)
    if (res.bad or res.missing) and not a.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
