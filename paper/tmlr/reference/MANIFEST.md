# paper/tmlr/reference/ provenance

Added for *Machine Learning Research Has Outpaced Its Communication Norms*
(TMLR). Produced by the upstream research repository at commit `eda2733`,
the camera-ready build of the paper. Checked by `python src/make_manifest.py`.

Built with: python 3.14.3, pandas 3.0.2, numpy 2.4.4, scipy 1.17.1,
matplotlib 3.10.8, textstat 0.7.13, spacy 3.8.13, en_core_web_sm 3.8.0, thinc 8.3.13 and blis 1.3.3. Topic clustering
additionally needs scikit-learn 1.9.0.

## Judge series and robustness tables

- `pgfplots/llm_scores_*.csv`: the 27 judge series of the paper's
  `tmlr/data/pgfplots/`, copied whole.
- `latex_robustness.csv`, `readability_collinearity.csv`: copied whole.
- `latex_robustness_summary.csv`: computed by this repository's
  `src/analysis/latex_robustness.py`. Its 26 values match the paper's macros
  at the paper's rounding.

sha256, first 16 hex:

```
fada74d095f423dc  latex_robustness.csv
441560718fac44c7  latex_robustness_summary.csv
43037553b804db56  pgfplots/llm_scores_ascb.csv
f221d7a95bb58603  pgfplots/llm_scores_iclr_ascb.csv
8fa99b93ed9f3812  pgfplots/llm_scores_iclr_own_reasoning.csv
dcdffb1b1e06cead  pgfplots/llm_scores_iclr_simple.csv
d753f4fab6afc2cf  pgfplots/llm_scores_icml_ascb.csv
40723f6ccb49c86b  pgfplots/llm_scores_icml_own_reasoning.csv
c137c2d6cb532206  pgfplots/llm_scores_icml_simple.csv
32f0f5f9ec24b7dc  pgfplots/llm_scores_model_avg_ascb.csv
a93b3e08b571f170  pgfplots/llm_scores_model_avg_iclr_ascb.csv
b943023c5de6f440  pgfplots/llm_scores_model_avg_iclr_own_reasoning.csv
0585828f76ea5574  pgfplots/llm_scores_model_avg_iclr_simple.csv
2cea7641303faaa9  pgfplots/llm_scores_model_avg_icml_ascb.csv
00c9e203d0c830cd  pgfplots/llm_scores_model_avg_icml_own_reasoning.csv
812f7d678f3ada70  pgfplots/llm_scores_model_avg_icml_simple.csv
515adf7829950956  pgfplots/llm_scores_model_avg_own_reasoning.csv
ecd25a1be4133d94  pgfplots/llm_scores_model_avg_simple.csv
d302f205fa55c976  pgfplots/llm_scores_own_reasoning.csv
99bc248a9caaf395  pgfplots/llm_scores_simple.csv
cf8a88f99e626b21  pgfplots/llm_scores_standardized_ascb.csv
b5297e3b43a10d05  pgfplots/llm_scores_standardized_iclr_ascb.csv
1a3d807eba5eec75  pgfplots/llm_scores_standardized_iclr_own_reasoning.csv
c2773d1de10ff242  pgfplots/llm_scores_standardized_iclr_simple.csv
b9bcbd889401908d  pgfplots/llm_scores_standardized_icml_ascb.csv
6b55ab217b71eaa7  pgfplots/llm_scores_standardized_icml_own_reasoning.csv
a3cc0affc3256031  pgfplots/llm_scores_standardized_icml_simple.csv
a9d2ba4d67cbc1f5  pgfplots/llm_scores_standardized_own_reasoning.csv
0d3235e716a8f43c  pgfplots/llm_scores_standardized_simple.csv
d519a7059d8b673d  readability_collinearity.csv
```

## Acronym tables, Flesch decomposition, topic analyses

Copied byte for byte from the upstream working tree at `eda2733`, except
`analysis/topic_profiles.csv` (see below).

- `analysis/acronym_reuse_freq.csv`, `analysis/acronym_robustness.csv`:
  upstream `data/aggregate/`. The reuse file holds all seven upstream rows.
  `src/analysis/acronym_reuse.py` computes the NeurIPS, ICLR and ICML rows
  from the per-paper acronyms, the arXiv ML, arXiv non-ML and PubMed rows from
  `shared/baselines/acronym_histograms.csv`, and quotes the Barnett and
  Doubleday row.
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
5eeb7980e2dd778a  analysis/acronym_reuse_freq.csv
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

## Figure data

`pgfplots/` also holds the 41 files of the upstream `tmlr/data/pgfplots/`
whose header is `year,neurips,iclr,icml,arxiv_ml,arxiv_nonml,pubmed`, copied
byte for byte from upstream commit `eda2733`: the per-metric series,
`sentence_length.csv` and `papers_per_year.csv`, over every year any of the
five corpora covers (1987-2027). `src/plotting/export_pgfplots_data.py
--baselines` builds them from the conference aggregates and
`shared/baselines/`.

sha256, first 16 hex:

```
d07de27c1153dd39  pgfplots/acronyms_abstract.csv
90b84d9bef5ef680  pgfplots/acronyms_title.csv
83d1a9c0307b041a  pgfplots/active_narration.csv
b26de28c5bbb1393  pgfplots/clauses_per_sent.csv
000b6abeb1326451  pgfplots/hedging.csv
eead30699fb087ad  pgfplots/noun_chunks.csv
18b357bf49c890a9  pgfplots/nouns.csv
aed9ad3df11a75d1  pgfplots/np_density.csv
7ac795cabe3c6bd2  pgfplots/numbers.csv
c943607945aa28fc  pgfplots/papers_per_year.csv
9e15c3e8c0418e17  pgfplots/parse_depth.csv
4f496b90b294bfc5  pgfplots/passive_rate.csv
2fe7dac4e84dd4d8  pgfplots/readability_ari.csv
4d7fdd1dde1a5291  pgfplots/readability_avg_sentence_length.csv
5c093815e658ed98  pgfplots/readability_avg_syllables_per_word.csv
aa5cbdce1fd9de77  pgfplots/readability_coleman_liau.csv
023525172164d891  pgfplots/readability_dale_chall.csv
ec255156482a56dc  pgfplots/readability_flesch_ease.csv
f11a35f5a7e5e5fa  pgfplots/readability_flesch_kincaid.csv
888587e64c438f0d  pgfplots/readability_forcast.csv
5ac0d7a24de5c5ec  pgfplots/readability_gunning_fog.csv
15ec6501be8959ce  pgfplots/readability_linsear_write.csv
fbf2db9ac778e1ae  pgfplots/readability_lix.csv
2d62750521dc0631  pgfplots/readability_powers_sumner_kearl.csv
3759c786a0cae842  pgfplots/readability_rix.csv
0321a2d9c6f8de82  pgfplots/readability_smog.csv
bcc9b051a47488f8  pgfplots/readability_spache.csv
eccbe1c4b8f9f9f6  pgfplots/sensational_additional.csv
5bf0a9109dad1a06  pgfplots/sensational_attitude.csv
19019704f65f53cb  pgfplots/sensational_importance.csv
c3bde1c450d7c0d3  pgfplots/sensational_novelty.csv
69b1b77099dc3d65  pgfplots/sensational_problem.csv
52f887d3f78a4bab  pgfplots/sensational_quality.csv
85af2d9299c39db3  pgfplots/sensational_rigor.csv
41c7c27266d64812  pgfplots/sensational_scale.csv
b9b9d4636da88743  pgfplots/sensational_total.csv
d6a51f9c63cb5062  pgfplots/sensational_utility.csv
d70aca46527f2000  pgfplots/sentence_length.csv
a09886514aa191f1  pgfplots/signposting.csv
28f97df9873a2fab  pgfplots/ttr.csv
1bf5a67df8bc7862  pgfplots/verbs.csv
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
