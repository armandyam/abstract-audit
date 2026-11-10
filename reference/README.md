# reference/

The artefacts behind the published figures and tables. `verify.py` compares
what the pipeline builds against these. `MANIFEST.md` records where each set
came from.

`per_paper/` holds the metric files as computed for the papers, one file per
venue: `neurips.csv`, `iclr.csv`, `icml.csv`. Both papers share them.

`pgfplots/` holds the UncertaiNLP paper's plot-ready series. The
`readability_*.csv` files here carry only `year` and `neurips`, the two
columns that paper's figures read, and only the 39 years NeurIPS covers
(1987-2025). Upstream those files spanned 1987-2027 with four further corpora,
because the year index was the union across five corpora and ICLR 2026 and
PubMed ahead-of-print records extend past 2025. Those rows and columns are
empty for NeurIPS and are dropped rather than left here to imply this release
covers them. No value was altered.

`tmlr/` holds the TMLR paper's conference series and analyses.

- `tmlr/pgfplots/` uses the paper's own file names. The per-metric series
  and `papers_per_year.csv` carry `year`, `neurips`, `iclr` and `icml`, and
  the years at least one of those covers (1987-2026). Upstream they also
  carried arXiv and PubMed columns, which this release does not cover, so
  those columns and the rows only they fill are dropped. The judge series are
  conference-only upstream and are copied whole. No value was altered.
- `tmlr/pgfplots_full/` holds the same per-metric series and papers per year
  untrimmed, with the arXiv ML, arXiv non-ML and PubMed columns and all rows
  (1987-2027), plus the sentence length series. They are byte copies of the
  upstream files. The export builds them when the baselines in `baselines/`
  are merged in (`export_pgfplots_data.py --baselines`).
- `tmlr/latex_robustness.csv` and `tmlr/readability_collinearity.csv` are
  copied whole.
- `tmlr/latex_robustness_summary.csv` holds the derived numbers the paper
  quotes from the normalisation analysis. Upstream computed them inside the
  script that writes the paper's LaTeX macros, so there is no upstream CSV.
  This file was computed by `src/analysis/latex_robustness.py` from
  `latex_robustness.csv`, and every value matches the paper's macros at the
  paper's rounding.

Nothing in this directory is an input to the pipeline. To work from the shipped
metrics instead of scraping, copy `reference/per_paper/` into `data/per_paper/`
and run `python main.py --from aggregate`.
