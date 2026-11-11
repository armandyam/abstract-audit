# paper/tmlr/reference/ provenance

Added for *Machine Learning Research Has Outpaced Its Communication Norms*
(TMLR). Produced by the upstream research repository at commit `eda2733`,
the camera-ready build of the paper. Checked by `python src/make_manifest.py`.

Built with: python 3.14.3, pandas 3.0.2, numpy 2.4.4, scipy 1.17.1,
matplotlib 3.10.8, textstat 0.7.13, spacy 3.8.13, en_core_web_sm 3.8.0, thinc 8.3.13 and blis 1.3.3. Topic clustering
additionally needs scikit-learn 1.9.0.

## Robustness tables

The paper's figure data (the per-metric series and the judge series) is
shared with the other papers and lives in `shared/reference/pgfplots/`.

- `readability_collinearity.csv`: copied whole. `latex_robustness.csv`, which
  the AI-Native Academia paper also uses, is in `shared/reference/analysis/`.
- `latex_robustness_summary.csv`: computed by this repository's
  `src/analysis/latex_robustness.py`. It holds 35 named values; those the
  paper prints through its macros match them at the paper's rounding.

sha256, first 16 hex:

```
441560718fac44c7  latex_robustness_summary.csv
d519a7059d8b673d  readability_collinearity.csv
```

## Acronym tables, Flesch decomposition, topic analyses

Copied byte for byte from the upstream working tree at `eda2733`, except
`analysis/topic_profiles.csv` (see below).

- `analysis/acronym_robustness.csv`: upstream `data/aggregate/`. The
  acronym reuse table, which the AI-Native Academia paper also uses, is in
  `shared/reference/analysis/`.
- `analysis/{acronym_concentration,acronym_top_terms,flesch_decomposition,
  topic_assignments,topic_terms,topic_stability,topic_trends,topic_profiles,
  topic_decomposition,topic_decomposition_summary,fixed_mix_readability}.csv`:
  upstream `tmlr/analysis/out/`. `topic_profiles.csv` is the upstream file
  without its two citation columns, `median_citations` and
  `n_with_citations`: the other six columns and all 15 rows are the upstream
  strings, unchanged. No citation statistic is distributed.

sha256, first 16 hex:

```
498d4a785a3e68dc  analysis/acronym_concentration.csv
2e1ef078bcd5a534  analysis/acronym_robustness.csv
41e2765db2a36c31  analysis/acronym_top_terms.csv
1deb3285badda1f1  analysis/fixed_mix_readability.csv
c375e91a4335fac3  analysis/flesch_decomposition.csv
a4dfa81dd5b02ea0  analysis/topic_assignments.csv
04486650bc796cf5  analysis/topic_decomposition.csv
3c3e672a21af87e4  analysis/topic_decomposition_summary.csv
fae8a138ced76794  analysis/topic_profiles.csv
52923e414c40fbd5  analysis/topic_stability.csv
4bc880bfc5745590  analysis/topic_terms.csv
2f678b2b0e37d4e6  analysis/topic_trends.csv
```

## Inline numbers

`macros.csv` holds 152 of the 163 values the paper prints through its three
macro files (`generated_round{2,3,4}.tex`): one row per macro, with the file,
the macro name and the printed value. Every value is a computed number or a
computed label (a topic's leading term, the ten commonest acronyms). None is
text from the manuscript. The eleven citation macros
(`make_macros.CITATION_MACROS`) are left out: they are computed from the
citation snapshot, which is not distributed, and the check reads their
printed values from the manuscript. Written at upstream commit `1cc4809` by
`python paper/tmlr/check_macros.py --write-reference` (the macro files are
unchanged since `eda2733`).

sha256, first 16 hex:

```
7062123daec4f2b5  macros.csv
```
