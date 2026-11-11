# paper/ai_native_academia/reference/ provenance

Added for the AI-Native Academia workshop paper (NeurIPS 2026 workshop,
NeurIPS only). Produced by the upstream research repository at commit
`1922ca3`, the camera-ready build of the paper. Checked by
`python src/make_manifest.py`.

Built with: python 3.14.3, pandas 3.0.2, numpy 2.4.4, scipy 1.17.1,
textstat 0.7.13 and scikit-learn 1.9.0.

The paper's figure data is shared with the other papers and lives in
`shared/reference/pgfplots/`. Its text normalisation numbers come from the
NeurIPS rows of `shared/reference/analysis/latex_robustness.csv`, which
equal in every value the upstream NeurIPS-only file
`data/aggregate/latex_robustness_neurips.csv` that the paper used, so no copy
is held here.

## Topics

The NeurIPS-only topic fit (upstream `src/aggregate/topic_clusters_neurips.py`,
here `src/analysis/topic_clusters.py --venues neurips`) and the profile and
fixed-mix series built on it (upstream
`src/aggregate/topic_controls_neurips.py`, here
`paper/ai_native_academia/topics.py`).

- `analysis/topic_assignments_neurips.csv`: upstream
  `data/aggregate/topic_assignments_neurips.csv.gz`, decompressed, otherwise
  unchanged. The regenerated file adds a `venue` column; verify.py compares
  the reference columns.
- `analysis/topic_terms_neurips.csv`, `analysis/topic_stability_neurips.csv`:
  upstream `data/aggregate/topic_terms.csv` and `topic_stability.csv`, the
  NeurIPS-only fit, renamed with the `_neurips` suffix so they do not collide
  with the TMLR paper's pooled fit. Contents unchanged.
- `analysis/fixed_mix_neurips.csv`: upstream `data/aggregate/`, unchanged.
- `analysis/topic_profiles_neurips.csv`: written by
  `paper/ai_native_academia/topics.py`. It equals, byte for byte, the
  upstream `data/aggregate/topic_profiles_neurips.csv` with its two citation
  columns (`median_citations`, `n_with_citations`) removed. No citation
  statistic is distributed.

The regenerated assignments, terms, stability and fixed-mix files are equal
to these (the assignments in every reference column).

sha256, first 16 hex:

```
9cdc87a06776e436  analysis/fixed_mix_neurips.csv
4b160d7a7e36614e  analysis/topic_assignments_neurips.csv
48a641ad8ce520c5  analysis/topic_profiles_neurips.csv
f0a50a9342b8b208  analysis/topic_stability_neurips.csv
fab9b7e4eccd9d9d  analysis/topic_terms_neurips.csv
```

## Judge agreement and stability

Upstream `uncertainlp/analysis/judge_agreement.py`, here
`src/analysis/judge_agreement.py`, over the six judges' NeurIPS scores in
`shared/judge_scores/neurips/`.

- `analysis/judge_{run_stability,raw_levels,pairwise_agreement,cronbach_alpha}_neurips.csv`:
  upstream `uncertainlp/analysis/out/{run_stability,raw_levels,
  pairwise_agreement,cronbach_alpha}.csv` at `1922ca3`, renamed, contents
  unchanged. The regenerated files are byte-identical to them.
- `analysis/judge_scored_papers_neurips.csv`: written by
  `src/analysis/judge_agreement.py`. Upstream had no such file: the counts it
  holds (papers each judge scored in 1987 and in 2024) were typed into a
  caption. make_tables.py computes the caption's numbers from it.

sha256, first 16 hex:

```
29f4f682e1800900  analysis/judge_cronbach_alpha_neurips.csv
bac86a93e575605d  analysis/judge_pairwise_agreement_neurips.csv
1fac4e0b18e1223c  analysis/judge_raw_levels_neurips.csv
1df8ed3cbb6148d4  analysis/judge_run_stability_neurips.csv
0c4e7d354f68208b  analysis/judge_scored_papers_neurips.csv
```

## Inline numbers

`macros.csv` holds 42 of the 52 values the paper prints through its macro
file (`generated_round2.tex`): one row per macro, with the file, the macro
name and the printed value. Every value is a computed number, a year, a
number word, or one of two topic names that `topics.py` assigns from
`TOPIC_LABELS`. None is text from the manuscript. The ten citation macros
(`make_macros.CITATION_MACROS`) are left out: they are computed from the
citation snapshot, which is not distributed, and the check reads their
printed values from the manuscript. Written from the manuscript at upstream
commit `1922ca3` by
`python paper/ai_native_academia/check_macros.py --write-reference`.

sha256, first 16 hex:

```
e7d69eb0394145ef  macros.csv
```
