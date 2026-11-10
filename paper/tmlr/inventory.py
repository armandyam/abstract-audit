#!/usr/bin/env python3
"""Every number the TMLR manuscript prints, found in paper/tmlr/source/.

The inventory reads main.tex and every file it \\input's (tables and figures),
except the three macro files: the 163 \\newcommand values are compared value
by value by check_macros.py, and a macro invocation in the text is not a
printed number here. Comments are ignored.

What counts as a number (each is one occurrence):

  numerals        30,595  2{,}823{,}623  0.68  -16.14  +0.56  7  2025
                  with an attached \\% or %, ordinal suffix (89.0th, 100th),
                  decade s (1990s), trailing + (1000+), or -fold
  dates           2026-05-11, 2026-04
  scaled          2.8 million, 32 billion
  spelled out     zero to twenty, the tens, hundred(s), thousand(s); ordinals
                  third to twentieth and "first percentile"; half, quarter(s),
                  thirds, once, twice, doubling, tripling, tenfold and the
                  other -fold words; "three quarters" and the like as one
  pairs           two numbers joined by " to ", "--" or an en dash, both years
                  or both not years: 88 to 90, 2015--2025, three to five
  fractions       two numbers joined by " of " or " of the ":
                  twelve of fifteen, fourteen of the 15, 14 of the 15

A digit run glued to a letter on either side is an identifier, not a number
(T1, 3d, 27B, Qwen2.5, v0.3, s2), unless the letters are one of the suffixes
above.

What is not inventoried, and why:

  - the preamble of main.tex (package options, colours, the TMLR month and
    year, the author block): structural;
  - the arguments of \\cite and its variants (citation keys and years),
    \\label, \\ref, \\input, \\url, \\href targets, \\includegraphics,
    \\definecolor, \\color, \\textcolor's colour, \\vspace, \\hspace,
    \\setlength, \\resizebox, \\scalebox, \\rule, the first two arguments of
    \\multicolumn and \\multirow, \\cline, \\cmidrule, \\footnotemark,
    \\pgfplotsset and \\pgfplotslegendfromname, macro definitions
    (\\newcommand, \\providecommand), and the options and column specifiers
    of \\begin{tabular}, {minipage}, {table}, {figure}, {axis} and the like:
    lengths, column specs, colours, keys and numbering;
  - inside a tikzpicture, everything except the text a reader sees: node
    labels, legend entries, title and axis label text, and a constant plot
    expression such as \\addplot {2.40}. Axis limits, tick lists, coordinates,
    domains, colours and sizes are layout;
  - section, figure and table numbering, which LaTeX generates, and the
    enumerating ordinals first and second;
  - vague quantifiers (several, a few, dozens, a decade).

When a case is not covered above it is included.

    python paper/tmlr/inventory.py                 # print every occurrence
    python paper/tmlr/inventory.py --summary
"""
from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "source")
MACRO_FILES = ("generated_round2.tex", "generated_round3.tex", "generated_round4.tex")


# ============================================================ source text ===

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


def read_text(path: str) -> str:
    """The file with comments removed, one output line per input line."""
    with open(path, encoding="utf-8") as fh:
        return "\n".join(strip_comment(ln) for ln in fh.read().split("\n"))


def files_of(source: str = SOURCE) -> list[str]:
    """main.tex, then every file it \\input's except the macro files, as paths
    relative to `source`, in order of first \\input."""
    text = read_text(os.path.join(source, "main.tex"))
    out = ["main.tex"]
    for name in re.findall(r"\\input\{([^}]+)\}", text):
        name = name.strip()
        name = name if name.endswith(".tex") else name + ".tex"
        if os.path.basename(name) in MACRO_FILES or name in out:
            continue
        out.append(name)
    return out


@dataclass
class Normalised:
    """A text with every whitespace run collapsed to one space, and a map
    from each position of the original to its position in the collapsed one.
    Quotes in claims.csv are matched against the collapsed text, so a change
    of line breaks upstream does not make a claim stale."""
    text: str
    pos: list[int]          # original index -> normalised index

    @classmethod
    def of(cls, orig: str) -> "Normalised":
        out, pos, prev_ws = [], [], False
        for c in orig:
            ws = c.isspace()
            if ws and prev_ws:
                pos.append(len(out) - 1)
                continue
            pos.append(len(out))
            out.append(" " if ws else c)
            prev_ws = ws
        pos.append(len(out))
        return cls("".join(out), pos)


# ================================================================ masking ===

# Commands whose arguments are structural. The value is the number of brace
# arguments masked after any [..] or (..) options; None masks a macro
# definition entirely (name, argument count and body).
MASK_ARGS = {
    "cite": 1, "citet": 1, "citep": 1, "citealp": 1, "citealt": 1,
    "citeauthor": 1, "citeyear": 1, "citeyearpar": 1, "nocite": 1,
    "label": 1, "ref": 1, "eqref": 1, "pageref": 1, "autoref": 1, "cref": 1,
    "Cref": 1, "input": 1, "include": 1, "url": 1, "href": 1,
    "includegraphics": 1, "bibliography": 1, "bibliographystyle": 1,
    "usepackage": 1, "usetikzlibrary": 1, "usepgfplotslibrary": 1,
    "definecolor": 3, "color": 1, "textcolor": 1, "colorbox": 1,
    "vspace": 1, "hspace": 1, "setlength": 2, "addtolength": 2,
    "resizebox": 2, "scalebox": 1, "rule": 2, "raisebox": 1,
    "multicolumn": 2, "multirow": 2, "cline": 1, "cmidrule": 1,
    "footnotemark": 0, "addlinespace": 0, "pgfplotsset": 1,
    "pgfplotslegendfromname": 1, "captionsetup": 1, "hypersetup": 1,
    "newcommand": None, "renewcommand": None, "providecommand": None,
}
# Environments whose options and arguments are structural: name -> number
# of brace arguments after the optional [..].
ENV_ARGS = {"tabular": 1, "tabular*": 2, "tabularx": 2, "minipage": 1,
            "table": 0, "table*": 0, "figure": 0, "figure*": 0, "wrapfigure": 2,
            "axis": 0, "groupplot": 0, "tikzpicture": 0, "semilogyaxis": 0,
            "center": 0, "adjustbox": 1}


def _group_end(t: str, i: int, open_c: str = "{", close_c: str = "}") -> int:
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
    return len(t)


def _skip_ws(t: str, i: int) -> int:
    while i < len(t) and t[i].isspace():
        i += 1
    return i


def _skip_options(t: str, i: int) -> int:
    """Past any run of [..] and (..) option groups, and a star."""
    while True:
        k = _skip_ws(t, i)
        if k < len(t) and t[k] == "*":
            i = k + 1
            continue
        if k < len(t) and t[k] == "[":
            i = _group_end(t, k, "[", "]")
            continue
        if k < len(t) and t[k] == "(":
            i = _group_end(t, k, "(", ")")
            continue
        return i


def _skip_groups(t: str, i: int, n: int) -> int:
    for _ in range(n):
        k = _skip_ws(t, i)
        if k >= len(t) or t[k] != "{":
            return i
        i = _group_end(t, k)
    return i


def _definition_end(t: str, i: int) -> int:
    """Past a macro definition starting after its command name."""
    k = _skip_ws(t, i)
    if k < len(t) and t[k] == "*":
        k += 1
    k = _skip_ws(t, k)
    if k < len(t) and t[k] == "{":
        k = _group_end(t, k)
    elif k < len(t) and t[k] == "\\":
        k += 1
        while k < len(t) and t[k].isalpha():
            k += 1
    k = _skip_options(t, k)
    return _skip_groups(t, k, 1)


def _tikz_keep(body: str) -> list[tuple[int, int]]:
    """Spans of a tikzpicture body a reader sees as text: node labels, legend
    entries, title and axis-label text, constant plot expressions."""
    keep = []
    for m in re.finditer(r"\\addlegendentry\s*\{", body):
        e = _group_end(body, m.end() - 1)
        keep.append((m.end(), e - 1))
    for m in re.finditer(r"\b(?:title|xlabel|ylabel)\s*=\s*\{", body):
        e = _group_end(body, m.end() - 1)
        keep.append((m.end(), e - 1))
    for m in re.finditer(r"\\node\b", body):
        k = m.end()
        while True:                     # options, (name), at (x,y)
            k2 = _skip_options(body, k)
            k3 = _skip_ws(body, k2)
            if body.startswith("at", k3):
                k = k3 + 2
                continue
            k = k3
            break
        if k < len(body) and body[k] == "{":
            keep.append((k + 1, _group_end(body, k) - 1))
    for m in re.finditer(r"\\addplot\b\+?", body):
        k = _skip_ws(body, _skip_options(body, m.end()))
        if k < len(body) and body[k] == "{":
            keep.append((k + 1, _group_end(body, k) - 1))
    return keep


def mask(text: str, is_main: bool) -> str:
    """text with every structural region replaced by spaces of equal length,
    so positions are preserved (see the module docstring)."""
    m = list(text)

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, len(m))):
            if m[k] != "\n":
                m[k] = " "

    if is_main:
        b = text.find("\\begin{document}")
        if b >= 0:
            blank(0, b + len("\\begin{document}"))

    # tikzpicture bodies: keep only the visible text. The kept spans are
    # restored after the environment options are masked (a title= inside
    # \begin{axis}[...] is visible text), and command masking runs after
    # that, so a \cite inside a node label is still masked.
    keep_abs = []
    for bm in re.finditer(r"\\begin\{tikzpicture\}", text):
        e = text.find("\\end{tikzpicture}", bm.end())
        e = len(text) if e < 0 else e
        body = text[bm.end():e]
        keep = sorted(_tikz_keep(body))
        cur = 0
        for a, b in keep:
            if a < cur:
                continue
            blank(bm.end() + cur, bm.end() + a)
            keep_abs.append((bm.end() + a, bm.end() + b))
            cur = b
        blank(bm.end() + cur, e)

    for em in re.finditer(r"\\(begin|end)\{([A-Za-z*]+)\}", text):
        end = em.end()
        if em.group(1) == "begin" and em.group(2) in ENV_ARGS:
            end = _skip_groups(text, _skip_options(text, end), ENV_ARGS[em.group(2)])
        blank(em.start(), end)
    for a, b in keep_abs:
        m[a:b] = list(text[a:b])

    for cm in re.finditer(r"\\([A-Za-z]+)", text):
        name = cm.group(1)
        if name not in MASK_ARGS:
            continue
        n = MASK_ARGS[name]
        if n is None:
            end = _definition_end(text, cm.end())
        else:
            end = _skip_groups(text, _skip_options(text, cm.end()), n)
        blank(cm.start(), end)

    for pm in re.finditer(r"#\d|\\\\\[[^\]]*\]", text):      # #1, \\[2pt]
        blank(pm.start(), pm.end())
    return "".join(m)


# ============================================================== tokenising ===

CARDINALS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90, "hundred": 100, "hundreds": 100, "thousand": 1000,
    "thousands": 1000,
}
ORDINALS = {
    "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
    "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
    "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17,
    "eighteenth": 18, "nineteenth": 19, "twentieth": 20,
}
OTHER_WORDS = {
    "half": 0.5, "halves": 0.5, "quarter": 0.25, "quarters": 0.25,
    "thirds": 1 / 3, "once": 1, "twice": 2, "doubling": 2,
    "doubled": 2, "tripling": 3, "tripled": 3,
}
FOLD_PREFIX = {**CARDINALS}

_NUM = (r"(?P<sign>(?<=[\s$({=&~])[-+\u2212])?"
        r"(?<![A-Za-z0-9_.\\])"
        r"(?P<int>\d{1,3}(?:(?:\{,\}|,)\d{3})+|\d+)(?P<dec>\.\d+)?"
        r"(?P<suf>\\%|%|th|st|nd|rd|s|fold|\+)?"
        r"(?![A-Za-z0-9])(?!\\(?:linewidth|textwidth|columnwidth|tabcolsep))")
NUM_RE = re.compile(_NUM)
DATE_RE = re.compile(r"(?<![A-Za-z0-9.\\])\d{4}-\d{2}(?:-\d{2})?(?![A-Za-z0-9])")
WORDS = sorted(list(CARDINALS) + list(ORDINALS) + list(OTHER_WORDS), key=len, reverse=True)
WORD_RE = re.compile(r"(?<![A-Za-z\\])(?:" + "|".join(WORDS) + r")(?![A-Za-z])", re.I)
FOLD_RE = re.compile(r"(?<![A-Za-z\\])(?:" + "|".join(FOLD_PREFIX) + r")fold(?![A-Za-z])", re.I)
COMPOUND_RE = re.compile(r"(?<![A-Za-z\\])(?:" + "|".join(CARDINALS) + r")\s+(?:quarters|thirds|halves)(?![A-Za-z])", re.I)
FIRST_PCT_RE = re.compile(r"(?<![A-Za-z\\])first(?= percentile)", re.I)
SCALE_RE = re.compile(r"\s+(million|billion)\b")


@dataclass
class Token:
    start: int          # offsets in the original (comment-stripped) text
    end: int
    kind: str           # number, date, word, pair, fraction
    year: bool = False  # a plain integer between 1900 and 2100


def _raw_tokens(masked: str) -> list[Token]:
    toks = []
    taken = [False] * len(masked)

    def add(a: int, b: int, kind: str, year: bool = False) -> None:
        if any(taken[a:b]):
            return
        for k in range(a, b):
            taken[k] = True
        toks.append(Token(a, b, kind, year))

    for m in DATE_RE.finditer(masked):
        add(m.start(), m.end(), "date")
    for m in NUM_RE.finditer(masked):
        if m.group("suf") == "s" and not (len(m.group("int")) == 4 and m.group("int").endswith("0")):
            continue                        # only decades take a plain s
        start = m.start("sign") if m.group("sign") else m.start("int")
        plain = (m.group("dec") is None and m.group("suf") is None
                 and not m.group("sign") and "," not in m.group("int"))
        year = plain and 1900 <= int(m.group("int")) <= 2100
        end = m.end()
        sm = SCALE_RE.match(masked, end)
        if sm:
            end = sm.end()
        add(start, end, "number", year)
    for rx in (COMPOUND_RE, FOLD_RE, FIRST_PCT_RE, WORD_RE):
        for m in rx.finditer(masked):
            add(m.start(), m.end(), "word")
    toks.sort(key=lambda t: t.start)
    return toks


_PAIR_SEP = re.compile(r"\s+to\s+|--|\u2013")
_FRAC_SEP = re.compile(r"\s+of\s+(?:the\s+)?")


def _merge(toks: list[Token], masked: str) -> list[Token]:
    """Join fractions (12 of 15) and pairs (88 to 90, 2015--2025)."""
    def joinable(sep: re.Pattern, a: Token, b: Token) -> bool:
        gap = masked[a.end:b.start]
        return sep.fullmatch(gap) is not None

    out: list[Token] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if i + 1 < len(toks):
            u = toks[i + 1]
            if (t.kind in ("number", "word") and u.kind in ("number", "word")
                    and joinable(_FRAC_SEP, t, u)):
                out.append(Token(t.start, u.end, "fraction"))
                i += 2
                continue
            if (t.kind in ("number", "word") and u.kind in ("number", "word")
                    and t.year == u.year and joinable(_PAIR_SEP, t, u)):
                out.append(Token(t.start, u.end, "pair", t.year))
                i += 2
                continue
        out.append(t)
        i += 1
    return out


@dataclass(frozen=True)
class Occurrence:
    """One printed number. `pos` is its offset in the file's normalised text,
    `text` the printed form with whitespace collapsed."""
    file: str
    line: int
    pos: int
    text: str
    kind: str
    context: str


def tokens_in(text: str, is_main: bool = False) -> list[Token]:
    """Every number in a comment-stripped LaTeX text (see the module docstring)."""
    masked = mask(text, is_main)
    return _merge(_raw_tokens(masked), masked)


def occurrences(rel: str, source: str = SOURCE, width: int = 40) -> tuple[list[Occurrence], Normalised]:
    """Every number in one source file, and the file's normalised text."""
    text = read_text(os.path.join(source, rel))
    norm = Normalised.of(text)
    out = []
    for t in tokens_in(text, rel == "main.tex"):
        a, b = norm.pos[t.start], norm.pos[t.end]
        printed = norm.text[a:b]
        line = text.count("\n", 0, t.start) + 1
        ctx = norm.text[max(0, a - width):b + width]
        out.append(Occurrence(rel, line, a, printed, t.kind, ctx))
    return out, norm


def inventory(source: str = SOURCE) -> tuple[list[Occurrence], dict[str, Normalised]]:
    """Every occurrence in every source file, and each file's normalised text."""
    occ, norms = [], {}
    for rel in files_of(source):
        o, n = occurrences(rel, source)
        occ += o
        norms[rel] = n
    return occ, norms


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=SOURCE)
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    occ, _ = inventory(a.source)
    if a.summary:
        from collections import Counter
        for f, n in Counter(o.file for o in occ).items():
            print(f"  {f:<50} {n:>4}")
        print(f"{len(occ)} occurrences")
        return
    for o in occ:
        print(f"{o.file}:{o.line}\t{o.kind}\t{o.text}\t{o.context}")


if __name__ == "__main__":
    main()
