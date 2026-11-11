#!/usr/bin/env python3
"""Text normalization for conference abstracts, extending the PubMed cleaner.

`clean_pubmed.py` strips structured headings, maps & to and, drops non-ASCII
and collapses whitespace. Conference abstracts need all of that plus LaTeX
handling, which no stage of the pipeline currently does: NeurIPS, ICLR and
ICML abstracts reach textstat with raw markup such as

    ($\\texttt{FWC}$)
    Let $n,T,\\bar{d}$ denote the dimensionality
    a $\\underline{Co}$llabo$\\underline{ra}$tive cognitive diagnosis

Markup like this is tokenized as long, many-syllable words, and its
prevalence is not stable over time (about 0-3% of NeurIPS abstracts before
2005, about 18% by 2024), so it is a candidate confound for any readability
trend measured across that window.

This module is deliberately NOT wired into the existing processing scripts.
Importing it changes nothing; call clean_abstract() explicitly.

Math handling is a choice, so it is exposed rather than hard-coded:

  math="token"  replace each expression with a single short word. Closest to
                how a reader processes an inline symbol, and keeps the
                sentence's word count sane. Default.
  math="drop"   delete expressions entirely. Sensitivity check.
  math="keep"   leave them in place, i.e. current pipeline behaviour.
"""

from __future__ import annotations

import re

# Display and inline math, longest delimiters first so $$ wins over $.
# The negative lookbehind keeps escaped \$ (a literal dollar sign) intact.
_MATH_PATTERNS = [
    re.compile(r"(?<!\\)\$\$.+?(?<!\\)\$\$", re.DOTALL),   # $$ ... $$
    re.compile(r"(?<!\\)\$.+?(?<!\\)\$", re.DOTALL),       # $ ... $
    re.compile(r"\\\[.+?\\\]", re.DOTALL),                  # \[ ... \]
    re.compile(r"\\\(.+?\\\)", re.DOTALL),                  # \( ... \)
]

# \emph{x}, \textit{x}, \texttt{x} ... keep the argument, drop the command.
_TEXT_CMD_RE = re.compile(r"\\[a-zA-Z]+\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}")

# Any surviving control sequence, e.g. \alpha or \\ with no argument.
_BARE_CMD_RE = re.compile(r"\\[a-zA-Z]+\*?|\\\\")

# Left-over grouping braces once commands are gone.
_BRACE_RE = re.compile(r"[{}]")

# URLs. A link is not prose: textstat scores it as one very long, many-syllable
# "difficult word", and its prevalence in these abstracts rises from under 1
# percent before 2016 to about 24 percent by 2024 as code sharing became normal.
# Left in, it is a time-varying confound on every surface readability measure.
_URL_RE = re.compile(r"https?://\S+|www\.\S+|\b(?:doi|arxiv)\s*:\s*\S+", re.I)

# Same heading rule as clean_pubmed.py. Conference abstracts rarely carry
# structured headings, but a few older NeurIPS ones do.
_HEADING_RE = re.compile(r"\b[A-Z][A-Z0-9\s/()&,-]{1,60}:\s*")

_NON_ASCII_RE = re.compile(r"[^\x09\x0A\x20-\x7E]")

# Stand-in for a removed math expression. One syllable, one word, no
# punctuation, and not a "difficult word" under Dale-Chall.
_MATH_TOKEN = "x"


def strip_latex(text: str, math: str = "token") -> str:
    """Remove LaTeX markup, leaving readable prose."""
    if math not in {"token", "drop", "keep"}:
        raise ValueError(f"math must be token, drop or keep; got {math!r}")

    if math != "keep":
        repl = f" {_MATH_TOKEN} " if math == "token" else " "

        def _sub(m: re.Match) -> str:
            # Math spliced inside a word, as in
            #   $\underline{Co}$llabo$\underline{ra}$tive
            # is typography rather than mathematics. Splicing in a token would
            # shatter one word into three. Keep the letters instead.
            s, e = m.start(), m.end()
            before = text[s - 1] if s > 0 else " "
            after = text[e] if e < len(text) else " "
            if before.isalnum() or after.isalnum():
                inner = _BRACE_RE.sub("", _BARE_CMD_RE.sub("", m.group(0).strip("$")))
                letters = re.sub(r"[^A-Za-z]", "", inner)
                if letters:
                    return letters
            return repl

        for pat in _MATH_PATTERNS:
            text = pat.sub(_sub, text)

    # Unwrap text-mode commands repeatedly, so \emph{\textbf{x}} fully resolves.
    for _ in range(5):
        new = _TEXT_CMD_RE.sub(r"\1", text)
        if new == text:
            break
        text = new

    text = _BARE_CMD_RE.sub(" ", text)
    text = _BRACE_RE.sub("", text)
    return text


def clean_abstract(text: str, math: str = "token", headings: bool = True,
                   urls: bool = True) -> str:
    """Full normalization for one conference abstract."""
    if not text:
        return ""
    text = strip_latex(text, math=math)
    if urls:
        text = _URL_RE.sub(" ", text)
    if headings:
        text = _HEADING_RE.sub(" ", text)
    text = text.replace("&", "and")
    text = _NON_ASCII_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


if __name__ == "__main__":  # pragma: no cover
    samples = [
        r"We present fair Wasserstein coresets ($\texttt{FWC}$), a novel approach.",
        r"Let $n,T,\bar{d}$ denote the dimensionality, time horizon, and rank.",
        r"A model trained on a $19\times 19$ Go board cannot play a smaller one.",
        r"We present Coral, a $\underline{Co}$llabo$\underline{ra}$tive framework.",
    ]
    for s in samples:
        print("raw  :", s)
        print("token:", clean_abstract(s, math="token"))
        print("drop :", clean_abstract(s, math="drop"))
        print()
