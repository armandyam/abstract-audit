# reference/

The artefacts behind the published figures and tables. `verify.py` compares
what the pipeline builds against these. `MANIFEST.md` records where each set
came from and its sha256 hashes, and `make_manifest.py` checks them.

`per_paper/` holds the metric files as computed for the papers, one file per
venue: `neurips.csv`, `iclr.csv`, `icml.csv`, for 16 metric families. Both
papers share them.

`pgfplots/` holds the UncertaiNLP paper's plot-ready series. The
`readability_*.csv` files here carry only `year` and `neurips`, the two
columns that paper's figures read, and only the 39 years NeurIPS covers
(1987-2025). Upstream those files spanned 1987-2027 with four further corpora,
because the year index was the union across five corpora and ICLR 2026 and
PubMed ahead-of-print records extend past 2025. Those rows and columns are
empty for NeurIPS and are dropped rather than left here to imply this release
covers them. No value was altered.

`tmlr/` holds the TMLR paper's conference series and analyses.

- `tmlr/pgfplots/` holds the 27 judge series under the paper's own file
  names. They are conference-only upstream and are copied whole.
- `tmlr/pgfplots_full/` holds 41 files, the per-metric series (sentence
  length among them) and papers per year, with the columns `year`, `neurips`, `iclr`,
  `icml`, `arxiv_ml`, `arxiv_nonml` and `pubmed` and every year any of the
  five corpora covers (1987-2027). They are byte copies of the upstream
  files. The export builds them from the conference aggregates and
  `shared/baselines/` (`export_pgfplots_data.py --baselines`).
- `tmlr/latex_robustness.csv` and `tmlr/readability_collinearity.csv` are
  copied whole.
- `tmlr/analysis/` holds the acronym reuse, robustness and concentration
  tables, the Flesch decomposition and the topic analyses, copied whole
  except `topic_profiles.csv`, which lacks the two upstream citation columns
  (`median_citations`, `n_with_citations`). The arXiv and PubMed rows of
  `acronym_reuse_freq.csv` are computed from `shared/baselines/acronym_histograms.csv`.
- `tmlr/latex_robustness_summary.csv` holds the derived numbers the paper
  quotes from the normalisation analysis. Upstream computed them inside the
  script that writes the paper's LaTeX macros, so there is no upstream CSV.
  This file was computed by `src/analysis/latex_robustness.py` from
  `latex_robustness.csv`, and every value matches the paper's macros at the
  paper's rounding.

`tmlr/macros.csv` holds the values the paper prints through 152 of its 163
macros (file, name, value), written from the manuscript's macro files by
`paper/tmlr/check_macros.py --write-reference`. `paper/tmlr/check_macros.py`
compares the built macros with it. The other eleven are the citation macros,
whose values are not held here.

No citation output is held here. The citation counts are not distributed and
neither is any statistic computed from them, including the values the paper
prints: neither `macros.csv` nor `paper/tmlr/claims.csv` stores one. The
citation numbers are checked against the manuscript's own values (`AA_PAPER`)
when the reader's counts are the published snapshot (see
`src/citations/snapshot.py`), and skipped without the manuscript.

The manuscript itself is not held here either. The checks that read it take
a local copy at run time (`AA_PAPER`, see the top-level README).

No file in this directory is an input to the pipeline. To work from the shipped
metrics instead of scraping, copy `shared/reference/per_paper/` into `data/per_paper/`
and run `python main.py --from aggregate`.
