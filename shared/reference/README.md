# shared/reference/

The expected outputs every paper uses, one copy each. `verify.py` compares
what the pipeline builds against these. `MANIFEST.md` records where each set
came from and its sha256 hashes, and `python src/make_manifest.py` checks them.
Each paper's own expected outputs are in `paper/<name>/reference/`.

`per_paper/` holds the metric files as computed for the papers, one file per
venue: `neurips.csv`, `iclr.csv`, `icml.csv`, for 16 metric families.

`pgfplots/` holds every plot-ready series more than one paper reads:

- 41 per-metric files and `papers_per_year.csv`, with the columns `year`,
  `neurips`, `iclr`, `icml`, `arxiv_ml`, `arxiv_nonml` and `pubmed` and every
  year any of the five corpora covers (1987-2027). They are byte copies of the
  upstream files. The export builds them from the conference aggregates and
  `shared/baselines/` (`export_pgfplots_data.py --baselines`). The TMLR and
  AI-Native Academia papers plot them.
- 27 judge series (`llm_scores_*.csv`), raw, standardised and six-model
  averaged, for the three venues. The files without a venue suffix are
  NeurIPS. All three papers plot the NeurIPS ones.
- `judge_metric_corr.csv`, the Spearman correlation of each writing metric
  with each judge, from which `src/plotting/make_heatmap.py` renders
  `fig_judge_metric_heatmap.png` (the copy here is the comparison target for
  the tracked `shared/figs/` PNG). The UncertaiNLP and AI-Native Academia
  papers include it.

`analysis/latex_robustness.csv` is the Flesch score of every venue and year
before and after LaTeX and URL normalisation. The TMLR paper reports it for
all three conferences, the AI-Native Academia paper for NeurIPS.
`analysis/acronym_reuse_freq.csv` is the acronym reuse table both papers
print; its arXiv and PubMed rows come from `shared/baselines/`.

No citation output is held here, and no file in this directory is an input to
the pipeline. To work from the shipped metrics instead of scraping, copy
`shared/reference/per_paper/` into `data/per_paper/` and run
`python main.py --from aggregate`.
