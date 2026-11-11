# paper/tmlr/reference/

The expected outputs only the TMLR paper uses. Its figure data (the
per-metric series with the arXiv and PubMed columns, and the judge series) is
shared with the other papers and is in `shared/reference/pgfplots/`.

- `readability_collinearity.csv` is copied whole from upstream. The
  normalisation series itself, `latex_robustness.csv`, is shared with the
  AI-Native Academia paper and is in `shared/reference/analysis/`.
- `latex_robustness_summary.csv` holds the derived numbers the paper quotes
  from the normalisation analysis. Upstream computed them inside the script
  that writes the paper's LaTeX macros, so there is no upstream CSV. This file
  was computed by `src/analysis/latex_robustness.py` from
  `shared/reference/analysis/latex_robustness.csv`, and every value matches the paper's macros at the
  paper's rounding.
- `analysis/` holds the acronym robustness and concentration tables,
  the Flesch decomposition and the topic analyses, copied whole except
  `topic_profiles.csv`, which lacks the two upstream citation columns
  (`median_citations`, `n_with_citations`). The acronym reuse table is
  shared with the AI-Native Academia paper and is in
  `shared/reference/analysis/`.
- `macros.csv` holds the values the paper prints through 152 of its 163
  macros (file, name, value), written from the manuscript's macro files by
  `paper/tmlr/check_macros.py --write-reference`. `paper/tmlr/check_macros.py`
  compares the built macros with it. The other eleven are the citation
  macros, whose values are not held here.

No citation output is held here. The citation counts are not distributed and
neither is any statistic computed from them, including the values the paper
prints: neither `macros.csv` nor `paper/tmlr/claims.csv` stores one. The
citation numbers are checked against the manuscript's own values (`AA_PAPER`)
when the reader's counts are the published snapshot (see
`src/citations/snapshot.py`), and skipped without the manuscript. The
manuscript itself is not held here either.
