#!/usr/bin/env python3
"""Render every AI-Native Academia figure and table source.

A pipeline run writes the full render to data/ai_native_academia/figures.pdf, which is not
distributed. `--public` writes the tracked paper/ai_native_academia/figures.pdf with the
citation figure and tables replaced by notes, because no citation-derived
value is distributed; always build the tracked copy with it.

Proves the figure and table sources in this repository compile against the
data the pipeline just produced, without the manuscript. The figures read
../../data/pgfplots/ and the generated tables ../../data/ai_native_academia/tables/,
relative to paper/ai_native_academia/: the repository's data/ directory, whatever $AA_DATA
says, as for paper/uncertainlp/build_figures.py. A generated table that was
not built, and the citation figure without its input, are replaced by notes
(see figures.tex); every other figure needs its input. When the local
citation counts are absent the citation figure and tables are always
replaced, so outputs left from an earlier run are not rendered. Skips with a clear message if
pdflatex is absent, since the rest of the pipeline does not need LaTeX.

    python paper/ai_native_academia/build_figures.py            # data/ai_native_academia/figures.pdf
    python paper/ai_native_academia/build_figures.py --public   # paper/ai_native_academia/figures.pdf
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
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--public", action="store_true",
                    help="write the tracked paper/ai_native_academia/figures.pdf, citation content off")
    args = ap.parse_args()
    if shutil.which("pdflatex") is None:
        print("pdflatex not found, skipping figure rendering "
              "(the pipeline and verify.py do not require it)")
        return
    from citations.snapshot import mode
    absent = (args.public
              or mode(os.path.join(REPO, "data", "per_paper", "citations")) == "absent")
    pre = r"\def\aacitationsabsent{1}" if absent else ""
    out_dir = HERE if args.public else os.path.join(REPO, "data", "ai_native_academia")
    os.makedirs(out_dir, exist_ok=True)

    # A fixed timestamp, so the same sources and the same TeX Live give a
    # byte-identical PDF (see paper/uncertainlp/build_figures.py).
    env = dict(os.environ, SOURCE_DATE_EPOCH="0", FORCE_SOURCE_DATE="1")
    for i in range(2):  # second pass resolves references
        r = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
             f"-output-directory={out_dir}",
             "-jobname=figures", pre + r"\input{figures.tex}"],
            cwd=HERE, capture_output=True, text=True, env=env)
        if r.returncode != 0:
            tail = "\n".join(r.stdout.strip().split("\n")[-25:])
            sys.exit(f"pdflatex failed on pass {i + 1}:\n{tail}")

    pdf = os.path.join(out_dir, "figures.pdf")
    if not os.path.exists(pdf):
        sys.exit("pdflatex reported success but figures.pdf is missing")
    print(f"wrote {pdf} ({os.path.getsize(pdf):,} bytes)"
          + (", citation figure and tables replaced by notes" if absent else ""))


if __name__ == "__main__":
    main()
