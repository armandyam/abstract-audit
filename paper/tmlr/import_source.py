#!/usr/bin/env python3
"""Copy the TMLR manuscript text into paper/tmlr/source/, without personal data.

paper/tmlr/check_claims.py reads every number the paper prints. It reads them
from paper/tmlr/source/, which this script fills from the upstream manuscript
directory (the research repository's tmlr/ folder):

  main.tex                    the manuscript
  generated_round{2,3,4}.tex  the macro files main.tex \\input's
  tables/*.tex, figs/*.tex    every table and figure main.tex \\input's

Each file is copied line for line, so line numbers stay those of upstream,
with three changes:

  comments    the text of every comment is removed (an unescaped % to the end
              of its line). Comments are never typeset, and upstream's carry
              working notes. A line that held only a comment stays as an
              empty line.
  \\author    the author block (names, e-mail addresses, affiliations) is
              replaced by an empty \\author{}, padded with empty lines to the
              same length.
  pdfauthor   the hyperref author field is emptied.

Afterwards every copied file is scanned for e-mail addresses, local
filesystem paths, author-block commands, and every name, address and
affiliation the upstream author block held, and the script fails if any
remain. SOURCE.md records the upstream commit, whether the
upstream files differed from it, and the SHA-256 of each upstream file and
each written copy.

Finally the self-audit abstract (paper/tmlr/self_audit_abstract.txt) is
regenerated from the copy with audit_self.read_from_tex and must be unchanged:
the self-audit stage measures exactly the abstract this copy prints.

    python paper/tmlr/import_source.py --upstream ../jargon_analysis/tmlr
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "source")
ABSTRACT = os.path.join(HERE, "self_audit_abstract.txt")
sys.path.insert(0, os.path.join(REPO, "src"))

ROUND_FILES = ("generated_round2.tex", "generated_round3.tex", "generated_round4.tex")

# Anything matching one of these in a copied file stops the import. The
# tabular column specifier @{} is not an address, so an address needs a
# dotted domain after the @. The authors' names, addresses and affiliations
# are not listed here: they are read from the upstream author block itself
# (author_terms), so this file carries none of them.
FORBIDDEN = [
    (r"[\w.+-]+@[\w-]+\.[\w.-]+", "e-mail address"),
    (r"/Users/|/home/|/private/|[A-Z]:\\\\", "local path"),
    (r"\\email\b|\\addr\b|\\name\b|\\affiliation\b", "author block command"),
]


def author_terms(text: str) -> list[str]:
    """The personal strings of an upstream author block: every word of each
    \\name, each \\email address and each \\addr line. The copy must contain
    none of them."""
    m = re.search(r"\\author\s*\{", text)
    if not m:
        return []
    lines = text[m.start():].split("\n")
    block = "\n".join(lines[:_block_end(lines, 0) + 1])
    terms = []
    for name in re.findall(r"\\name\s+([^\\\n]+)", block):
        terms += [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", name)]
    terms += re.findall(r"\\email\s+([^\s\\}]+)", block)
    terms += [a.strip() for a in re.findall(r"\\addr\s+([^\\\n}]+)", block)]
    return sorted(set(t for t in terms if t))


def strip_comment(line: str) -> str:
    """The line up to its first unescaped %, with trailing whitespace removed.
    An escaped % (\\%) is text."""
    i = 0
    while i < len(line):
        c = line[i]
        if c == "\\":
            i += 2
            continue
        if c == "%":
            return line[:i].rstrip()
        i += 1
    return line.rstrip()


def _block_end(lines: list[str], start: int) -> int:
    """The index of the line on which the brace group opened on lines[start]
    closes. Escaped braces do not count."""
    depth = 0
    for k in range(start, len(lines)):
        j, s = 0, lines[k]
        while j < len(s):
            c = s[j]
            if c == "\\":
                j += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return k
            j += 1
    raise ValueError(f"unbalanced braces in the block opened on line {start + 1}")


def scrub(text: str) -> str:
    """Comments removed, the author block and the PDF author field emptied.
    The number of lines is unchanged."""
    lines = [strip_comment(ln) for ln in text.split("\n")]
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("\\author"):
            end = _block_end(lines, i)
            indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
            lines[i] = indent + "\\author{}"
            for k in range(i + 1, end + 1):
                lines[k] = ""
            i = end + 1
            continue
        lines[i] = re.sub(r"pdfauthor\s*=\s*\{[^{}]*\}", "pdfauthor={}", lines[i])
        i += 1
    return "\n".join(lines)


def inputs_of(main_text: str) -> list[str]:
    """The files main.tex \\input's, in order, with .tex appended where the
    argument has no extension. Comments are ignored."""
    body = "\n".join(strip_comment(ln) for ln in main_text.split("\n"))
    out = []
    for name in re.findall(r"\\input\{([^}]+)\}", body):
        name = name.strip()
        out.append(name if name.endswith(".tex") else name + ".tex")
    return out


def forbidden_hits(text: str, personal: list[str] = ()) -> list[tuple[int, str, str]]:
    """(line, what, matched text) for every forbidden pattern in text, and
    every occurrence of one of the `personal` strings (whole words, any
    case)."""
    pats = list(FORBIDDEN) + [(r"(?<!\w)" + re.escape(p) + r"(?!\w)", "author detail")
                              for p in personal]
    hits = []
    for n, line in enumerate(text.split("\n"), 1):
        for pat, what in pats:
            for m in re.finditer(pat, line, re.I):
                hits.append((n, what, m.group(0)))
    return hits


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(upstream: str, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", upstream, *args], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def check_abstract(main_path: str, expected_path: str = ABSTRACT) -> tuple[bool, str]:
    """Regenerate the self-audit abstract from main_path; (unchanged, text)."""
    from metrics.audit_self import read_from_tex
    _, abstract = read_from_tex(main_path)
    want = open(expected_path, encoding="utf-8").read().strip()
    return abstract.strip() == want, abstract


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--upstream", required=True,
                    help="the upstream manuscript directory (research repo tmlr/)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    up = os.path.abspath(a.upstream)
    main_src = open(os.path.join(up, "main.tex"), encoding="utf-8").read()
    files = ["main.tex"] + [f for f in inputs_of(main_src) if f not in ("main.tex",)]
    missing = [f for f in files if not os.path.exists(os.path.join(up, f))]
    if missing:
        sys.exit(f"upstream files not found: {missing}")

    personal = author_terms(main_src)
    records, problems = [], []
    for rel in files:
        raw = open(os.path.join(up, rel), "rb").read()
        clean = scrub(raw.decode("utf-8"))
        for n, what, hit in forbidden_hits(clean, personal):
            problems.append(f"{rel}:{n}: {what} {hit!r}")
        dst = os.path.join(a.out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(clean)
        records.append((rel, sha256(raw), sha256(clean.encode("utf-8"))))
    if problems:
        sys.exit("personal data left in the copy:\n  " + "\n  ".join(problems))

    ok, text = check_abstract(os.path.join(a.out, "main.tex"))
    if not ok:
        sys.exit("the abstract in the copied main.tex differs from "
                 f"{os.path.relpath(ABSTRACT, REPO)}; regenerated:\n{text}")

    commit = git(up, "rev-parse", "HEAD") or "unknown"
    rel_up = git(up, "rev-parse", "--show-prefix").rstrip("/") or os.path.basename(up)
    dirty = git(up, "status", "--porcelain", "--", *files)
    lines = [
        "# paper/tmlr/source/",
        "",
        "The TMLR manuscript text that `check_claims.py` reads, written by",
        "`paper/tmlr/import_source.py`. Do not edit these files by hand: change the",
        "manuscript upstream and rerun the import.",
        "",
        f"Upstream commit: `{commit}` (directory `{rel_up}/`).",
        ("Upstream working tree: clean for every file below."
         if not dirty else
         "Upstream working tree: these files differed from the commit:\n\n```\n"
         + dirty + "\n```"),
        "",
        "Each file is a line-for-line copy with comment text removed, the author",
        "block replaced by an empty `\\author{}` and the PDF author field emptied.",
        "Line numbers are those of upstream.",
        "",
        "| file | upstream sha256 | copy sha256 |",
        "|---|---|---|",
    ]
    lines += [f"| `{r}` | `{u}` | `{c}` |" for r, u, c in records]
    with open(os.path.join(a.out, "SOURCE.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"copied {len(records)} files from {commit[:7] or '?'} to "
          f"{os.path.relpath(a.out, REPO)}; self-audit abstract unchanged")


if __name__ == "__main__":
    main()
