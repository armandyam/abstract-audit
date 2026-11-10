#!/usr/bin/env python3
"""Render every TMLR figure and table source to paper/tmlr/figures.pdf.

Proves the figure and table sources in this repository compile against the
data the pipeline just produced, without the manuscript. The figures read
../../data/pgfplots/tmlr/ and the generated tables ../../data/tmlr/tables/,
relative to paper/tmlr/: the repository's data/ directory, whatever $AA_DATA
says, as for paper/build_figures.py. A figure or table whose input was not
built is replaced by a note (see figures.tex); when the local citation counts
are absent the citation figure and tables are always replaced, so outputs
left from an earlier run are not rendered. Skips with a clear message if
pdflatex is absent, since the rest of the pipeline does not need LaTeX.

    python paper/tmlr/build_figures.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))


def main() -> None:
    if shutil.which("pdflatex") is None:
        print("pdflatex not found, skipping figure rendering "
              "(the pipeline and verify.py do not require it)")
        return
    from citations.snapshot import mode
    absent = mode(os.path.join(REPO, "data", "per_paper", "citations")) == "absent"
    pre = r"\def\aacitationsabsent{1}" if absent else ""

    # A fixed timestamp, so the same sources and the same TeX Live give a
    # byte-identical PDF (see paper/build_figures.py).
    env = dict(os.environ, SOURCE_DATE_EPOCH="0", FORCE_SOURCE_DATE="1")
    for i in range(2):  # second pass resolves references
        r = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
             "-jobname=figures", pre + r"\input{figures.tex}"],
            cwd=HERE, capture_output=True, text=True, env=env)
        if r.returncode != 0:
            tail = "\n".join(r.stdout.strip().split("\n")[-25:])
            sys.exit(f"pdflatex failed on pass {i + 1}:\n{tail}")

    pdf = os.path.join(HERE, "figures.pdf")
    if not os.path.exists(pdf):
        sys.exit("pdflatex reported success but figures.pdf is missing")
    print(f"wrote {pdf} ({os.path.getsize(pdf):,} bytes)"
          + (", citation figure and tables replaced by notes (counts absent)" if absent else ""))


if __name__ == "__main__":
    main()
