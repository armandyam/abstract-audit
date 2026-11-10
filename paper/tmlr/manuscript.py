"""Where the TMLR manuscript is, for the checks that need it.

The manuscript is not distributed with this repository. The checks that read
it (the claim coverage, the comparison of the generated tables and macros with
the paper's own files, the self-audit) take its directory at run time:

    export AA_PAPER=/path/to/manuscript     # the folder holding main.tex
    python verify.py

or --paper-dir on the scripts that accept it. The folder is the paper's LaTeX
source as the authors built it: main.tex, generated_round{2,3,4}.tex,
tables/*.tex and figs/*.tex. Nothing is copied from it into the repository.

Without AA_PAPER those checks are skipped and reported as skipped. Every
check that compares a recomputed value with a printed one still runs, from
the numbers stored in paper/tmlr/claims.csv and reference/tmlr/macros.csv.
"""
from __future__ import annotations

import os
import re

ENV = "AA_PAPER"
SKIP_REASON = ("the manuscript is not distributed; set AA_PAPER to a local copy "
               "of its LaTeX source to run this check")

# Tables that main.tex prints inline rather than \input-ing, by the name the
# generators and paper/tmlr/tables/ use, with the label that finds them.
INLINE_TABLES = {"corpus.tex": "tab:corpus", "prompts.tex": "tab:prompts",
                 "nine.tex": "tab:nine", "self_audit.tex": "tab:self-audit"}


def paper_dir(arg: str | None = None) -> str | None:
    """The manuscript directory from `arg` or $AA_PAPER, or None when neither
    is given. A given directory without main.tex is an error."""
    d = arg or os.environ.get(ENV) or None
    if d is None:
        return None
    if not os.path.exists(os.path.join(d, "main.tex")):
        raise SystemExit(f"{ENV}={d} has no main.tex; point it at the folder "
                         "that holds the manuscript's main.tex")
    return d


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


def strip_comments(text: str) -> str:
    """Comments removed, one output line per input line."""
    return "\n".join(strip_comment(ln) for ln in text.split("\n"))


def read(paper: str, rel: str) -> str:
    with open(os.path.join(paper, rel), encoding="utf-8") as fh:
        return fh.read()


def group_end(t: str, i: int, open_c: str = "{", close_c: str = "}") -> int:
    """Index after the group opening at t[i]. Escaped delimiters do not count."""
    depth, j = 0, i
    while j < len(t):
        c = t[j]
        if c == "\\":
            j += 2
            continue
        if c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise ValueError(f"unbalanced group at offset {i}")


def environment(text: str, label: str) -> str:
    """The table or figure environment of `text` that holds \\label{label}."""
    k = text.find("\\label{" + label + "}")
    if k < 0:
        raise KeyError(f"\\label{{{label}}} not found")
    starts = [m for m in re.finditer(r"\\begin\{(table\*?|figure\*?)\}", text)
              if m.start() < k]
    if not starts:
        raise KeyError(f"no table or figure environment around {label}")
    m = starts[-1]
    end = text.find("\\end{" + m.group(1) + "}", k)
    return text[m.start():end + len("\\end{" + m.group(1) + "}")]


def table_source(paper: str, name: str) -> str:
    """The paper's own table `name` (comments removed): tables/{name}, or the
    inline table of main.tex for the four names in INLINE_TABLES."""
    if name in INLINE_TABLES:
        return environment(strip_comments(read(paper, "main.tex")), INLINE_TABLES[name])
    return strip_comments(read(paper, os.path.join("tables", name)))


# ============================================================ table body ===

REV = re.compile(r"\\rev(?:two|three|four)?\{")


def unwrap_rev(text: str) -> str:
    """\\rev{x}, \\revtwo{x}, \\revthree{x}, \\revfour{x} replaced by x. They
    only colour revised text in the review build."""
    while True:
        m = REV.search(text)
        if not m:
            return text
        e = group_end(text, m.end() - 1)
        text = text[:m.start()] + text[m.end():e - 1] + text[e:]


RULES = re.compile(r"\\(toprule|midrule|bottomrule|addlinespace|hline)(\[[^\]]*\])?")


def _split_unescaped(s: str, sep: str) -> list[str]:
    out, cur, i, depth = [], [], 0, 0
    while i < len(s):
        c = s[i]
        if c == "\\" and not s.startswith(sep, i):
            cur.append(s[i:i + 2])
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if depth == 0 and s.startswith(sep, i):
            out.append("".join(cur))
            cur = []
            i += len(sep)
            continue
        cur.append(c)
        i += 1
    out.append("".join(cur))
    return out


def tabular_rows(text: str) -> list[list[str]]:
    """Every row of every tabular in `text`, as lists of cells with
    whitespace collapsed and the revision markers unwrapped. Rules
    (\\toprule, \\midrule, ...) and empty rows are dropped."""
    text = unwrap_rev(strip_comments(text))
    rows: list[list[str]] = []
    for m in re.finditer(r"\\begin\{tabular\*?\}", text):
        i = m.end()
        # skip the column specification (and the width of tabular*)
        while i < len(text) and text[i] in " \n{[":
            if text[i] in "{[":
                i = group_end(text, i, text[i], "}" if text[i] == "{" else "]")
                break
            i += 1
        end = text.find("\\end{tabular", i)
        body = RULES.sub(" ", text[i:end])
        for row in _split_unescaped(body, "\\\\"):
            cells = [" ".join(c.split()) for c in _split_unescaped(row, "&")]
            if any(cells):
                rows.append(cells)
    return rows


def caption(text: str) -> str:
    """The caption of a table environment, whitespace collapsed, revision
    markers unwrapped."""
    text = unwrap_rev(strip_comments(text))
    m = re.search(r"\\caption\{", text)
    if not m:
        return ""
    return " ".join(text[m.end():group_end(text, m.end() - 1) - 1].split())
