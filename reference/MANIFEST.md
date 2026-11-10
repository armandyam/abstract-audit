# reference/ provenance

These files were produced by the upstream research repository at commit
`e291e24` (e291e24dccf3f608ddf4e84ad871008c0a4780f2) and are the artefacts behind the figures in the paper.
The `readability_*.csv` series were trimmed to `year,neurips` and to the
39 years NeurIPS covers; see README.md. No value was altered.

Built with: python 3.14.3, pandas 3.0.2, numpy 2.4.4, scipy 1.17.1,
matplotlib 3.10.8, textstat 0.7.13, spacy 3.8.13, en_core_web_sm 3.8.0.

sha256, first 16 hex:

```
aaa5354c5691c4ac  fig_judge_metric_heatmap.png
1f64aaf772249613  per_paper/acronyms/neurips.csv
4c9c80368737f34c  per_paper/active_narration/neurips.csv
1baac129bc0241f8  per_paper/clauses_per_sentence/neurips.csv
94109fe0a0680bf2  per_paper/hedging/neurips.csv
13d72511b2a06302  per_paper/noun_chunks/neurips.csv
a2e590571de80e68  per_paper/nouns/neurips.csv
59d13a10a242db21  per_paper/np_density/neurips.csv
85b1c70e6d4e171f  per_paper/numbers/neurips.csv
a3e9bc168653e8d6  per_paper/parse_depth/neurips.csv
2e13cf764d433e30  per_paper/passive_rate/neurips.csv
007d4bdd27270e2f  per_paper/readability/neurips.csv
c90d7f060e3c3b44  per_paper/sensational_language/neurips.csv
801ce0239dc7c95a  per_paper/signposting/neurips.csv
1537cd4ea31b6218  per_paper/ttr/neurips.csv
2ed7556fcd3ccfc0  per_paper/verbs/neurips.csv
20649ddaf5f5104a  pgfplots/judge_metric_corr.csv
32f0f5f9ec24b7dc  pgfplots/llm_scores_model_avg_ascb.csv
515adf7829950956  pgfplots/llm_scores_model_avg_own_reasoning.csv
ecd25a1be4133d94  pgfplots/llm_scores_model_avg_simple.csv
cf8a88f99e626b21  pgfplots/llm_scores_standardized_ascb.csv
a9d2ba4d67cbc1f5  pgfplots/llm_scores_standardized_own_reasoning.csv
0d3235e716a8f43c  pgfplots/llm_scores_standardized_simple.csv
6acff22103d87c31  pgfplots/readability_ari.csv
b35f59d51e479303  pgfplots/readability_avg_sentence_length.csv
ed162d06c11cdabb  pgfplots/readability_avg_syllables_per_word.csv
c79735a75652939a  pgfplots/readability_coleman_liau.csv
a8a13eb529b00aa0  pgfplots/readability_dale_chall.csv
f944fa4dacc1d512  pgfplots/readability_flesch_ease.csv
a435ed72a1f4f6d5  pgfplots/readability_flesch_kincaid.csv
c58a6629f44773e2  pgfplots/readability_forcast.csv
833c49000afc9c2a  pgfplots/readability_gunning_fog.csv
8a07f4b4dc112c9e  pgfplots/readability_linsear_write.csv
55e35c00a3c188a5  pgfplots/readability_lix.csv
4977a0da323c4694  pgfplots/readability_powers_sumner_kearl.csv
6154163a340d3dd8  pgfplots/readability_rix.csv
d2ed373c453e0305  pgfplots/readability_smog.csv
49714ce64ca3e75d  pgfplots/readability_spache.csv
96b209daec7cf086  pgfplots/va_flesch.csv
835d4767bbaef127  pgfplots/va_zscore.csv
```

## TMLR paper

Added for *Machine Learning Research Has Outpaced Its Communication Norms*
(TMLR). Produced by the upstream research repository at commit `eda2733`,
the camera-ready build of the paper.

- `per_paper/*/iclr.csv`, `per_paper/*/icml.csv`: the upstream per-paper
  metric files, copied byte for byte.
- `tmlr/pgfplots/`: the paper's `tmlr/data/pgfplots/` files. The per-metric
  series and `papers_per_year.csv` were trimmed to `year,neurips,iclr,icml`
  and to the rows where at least one of those is non-empty; kept cells are the
  original strings. The judge series were copied whole. See README.md.
- `tmlr/latex_robustness.csv`, `tmlr/readability_collinearity.csv`: copied
  whole.
- `tmlr/latex_robustness_summary.csv`: computed by this repository's
  `src/analysis/latex_robustness.py`; its 26 values match the paper's macros
  at the paper's rounding.

Built with the versions above plus thinc 8.3.13 and blis 1.3.3, spaCy's
numeric backend, which the pin list now names because blis 1.3.4 changes one
verb count in `per_paper/verbs/neurips.csv`.

sha256, first 16 hex:

```
8e7ec69f9b24d65d  per_paper/acronyms/iclr.csv
82994bd60ed8b3b3  per_paper/acronyms/icml.csv
978986054509bc53  per_paper/active_narration/iclr.csv
9c0018ca05e9104a  per_paper/active_narration/icml.csv
1561e51605080a55  per_paper/clauses_per_sentence/iclr.csv
355446adad161a04  per_paper/clauses_per_sentence/icml.csv
dd49e46f6debfe2d  per_paper/hedging/iclr.csv
91de2e3534bb7347  per_paper/hedging/icml.csv
1b61370d521cde7a  per_paper/noun_chunks/iclr.csv
f9169529e1118e07  per_paper/noun_chunks/icml.csv
5a8641dea158fc45  per_paper/nouns/iclr.csv
8ef6d4b9284ab874  per_paper/nouns/icml.csv
8d7eaa399c1aefe6  per_paper/np_density/iclr.csv
980d2be7fd2645c4  per_paper/np_density/icml.csv
fde62ed4c181082c  per_paper/numbers/iclr.csv
9902d908af25e50f  per_paper/numbers/icml.csv
51bc6079f9ff47fb  per_paper/parse_depth/iclr.csv
64a10d145bf62566  per_paper/parse_depth/icml.csv
678bb59c337ece84  per_paper/passive_rate/iclr.csv
84abafb391063251  per_paper/passive_rate/icml.csv
73900cc36e084579  per_paper/readability/iclr.csv
5b1c2bc6e0cedc57  per_paper/readability/icml.csv
d0acf22d0a7272dd  per_paper/sensational_language/iclr.csv
7b60b1071a12e548  per_paper/sensational_language/icml.csv
3c3e5747330a9b5e  per_paper/signposting/iclr.csv
07430b735f1477aa  per_paper/signposting/icml.csv
2caa3be202117fb8  per_paper/ttr/iclr.csv
f82d4beea6dc1c99  per_paper/ttr/icml.csv
d66e55daee0fc927  per_paper/verbs/iclr.csv
5cdb5177f84cf381  per_paper/verbs/icml.csv
fada74d095f423dc  tmlr/latex_robustness.csv
441560718fac44c7  tmlr/latex_robustness_summary.csv
04d96473077e6b67  tmlr/pgfplots/acronyms_abstract.csv
4d72cde228c63313  tmlr/pgfplots/acronyms_title.csv
1fbe1d5f80c68e96  tmlr/pgfplots/active_narration.csv
8e267c8a760806a9  tmlr/pgfplots/clauses_per_sent.csv
406fd31c5c67d2fa  tmlr/pgfplots/hedging.csv
43037553b804db56  tmlr/pgfplots/llm_scores_ascb.csv
f221d7a95bb58603  tmlr/pgfplots/llm_scores_iclr_ascb.csv
8fa99b93ed9f3812  tmlr/pgfplots/llm_scores_iclr_own_reasoning.csv
dcdffb1b1e06cead  tmlr/pgfplots/llm_scores_iclr_simple.csv
d753f4fab6afc2cf  tmlr/pgfplots/llm_scores_icml_ascb.csv
40723f6ccb49c86b  tmlr/pgfplots/llm_scores_icml_own_reasoning.csv
c137c2d6cb532206  tmlr/pgfplots/llm_scores_icml_simple.csv
32f0f5f9ec24b7dc  tmlr/pgfplots/llm_scores_model_avg_ascb.csv
a93b3e08b571f170  tmlr/pgfplots/llm_scores_model_avg_iclr_ascb.csv
b943023c5de6f440  tmlr/pgfplots/llm_scores_model_avg_iclr_own_reasoning.csv
0585828f76ea5574  tmlr/pgfplots/llm_scores_model_avg_iclr_simple.csv
2cea7641303faaa9  tmlr/pgfplots/llm_scores_model_avg_icml_ascb.csv
00c9e203d0c830cd  tmlr/pgfplots/llm_scores_model_avg_icml_own_reasoning.csv
812f7d678f3ada70  tmlr/pgfplots/llm_scores_model_avg_icml_simple.csv
515adf7829950956  tmlr/pgfplots/llm_scores_model_avg_own_reasoning.csv
ecd25a1be4133d94  tmlr/pgfplots/llm_scores_model_avg_simple.csv
d302f205fa55c976  tmlr/pgfplots/llm_scores_own_reasoning.csv
99bc248a9caaf395  tmlr/pgfplots/llm_scores_simple.csv
cf8a88f99e626b21  tmlr/pgfplots/llm_scores_standardized_ascb.csv
b5297e3b43a10d05  tmlr/pgfplots/llm_scores_standardized_iclr_ascb.csv
1a3d807eba5eec75  tmlr/pgfplots/llm_scores_standardized_iclr_own_reasoning.csv
c2773d1de10ff242  tmlr/pgfplots/llm_scores_standardized_iclr_simple.csv
b9bcbd889401908d  tmlr/pgfplots/llm_scores_standardized_icml_ascb.csv
6b55ab217b71eaa7  tmlr/pgfplots/llm_scores_standardized_icml_own_reasoning.csv
a3cc0affc3256031  tmlr/pgfplots/llm_scores_standardized_icml_simple.csv
a9d2ba4d67cbc1f5  tmlr/pgfplots/llm_scores_standardized_own_reasoning.csv
0d3235e716a8f43c  tmlr/pgfplots/llm_scores_standardized_simple.csv
49ce10b288ba0cf6  tmlr/pgfplots/noun_chunks.csv
833491ad0d27c0fe  tmlr/pgfplots/nouns.csv
24fccba6b274c60f  tmlr/pgfplots/np_density.csv
2d8c5b61c943329b  tmlr/pgfplots/numbers.csv
9f906a797e1c4c64  tmlr/pgfplots/papers_per_year.csv
70b61fd464b2980e  tmlr/pgfplots/parse_depth.csv
1e99e5325e7da927  tmlr/pgfplots/passive_rate.csv
abd8da38e1a3dd42  tmlr/pgfplots/readability_ari.csv
7fe3124712d73a47  tmlr/pgfplots/readability_avg_sentence_length.csv
4bb476b5e7d019ae  tmlr/pgfplots/readability_avg_syllables_per_word.csv
22a248d5eb79c6e0  tmlr/pgfplots/readability_coleman_liau.csv
860f05fe705f8730  tmlr/pgfplots/readability_dale_chall.csv
9486441ae96b1822  tmlr/pgfplots/readability_flesch_ease.csv
d2d5c0996506dabc  tmlr/pgfplots/readability_flesch_kincaid.csv
c1474c4fced81d72  tmlr/pgfplots/readability_forcast.csv
0acc103ad62faf66  tmlr/pgfplots/readability_gunning_fog.csv
d86b8d44efb38ddb  tmlr/pgfplots/readability_linsear_write.csv
3b5bbc06566708c6  tmlr/pgfplots/readability_lix.csv
895e3abe8e98a227  tmlr/pgfplots/readability_powers_sumner_kearl.csv
900974f1dcab6a5c  tmlr/pgfplots/readability_rix.csv
dbbf3700e1d73db3  tmlr/pgfplots/readability_smog.csv
226d1f5f7ebc2c13  tmlr/pgfplots/readability_spache.csv
189c2e21b3158052  tmlr/pgfplots/sensational_additional.csv
1f15143082997114  tmlr/pgfplots/sensational_attitude.csv
21ca8fda4062323f  tmlr/pgfplots/sensational_importance.csv
46ee55417ac3a799  tmlr/pgfplots/sensational_novelty.csv
465b34728cda932c  tmlr/pgfplots/sensational_problem.csv
9c67c0f3ab1d4345  tmlr/pgfplots/sensational_quality.csv
96673466ec0375f3  tmlr/pgfplots/sensational_rigor.csv
6bd9366a6a506306  tmlr/pgfplots/sensational_scale.csv
1d92096d80383952  tmlr/pgfplots/sensational_total.csv
e4df969913a51278  tmlr/pgfplots/sensational_utility.csv
9b135472740d25ec  tmlr/pgfplots/signposting.csv
124179b58cba5a39  tmlr/pgfplots/ttr.csv
505dad21d478ee8f  tmlr/pgfplots/verbs.csv
d519a7059d8b673d  tmlr/readability_collinearity.csv
```

## TMLR paper: sentence length, acronym tables, topic analyses

Added from the same upstream commit `eda2733`. Every file below was copied byte
for byte from the upstream working tree, which matches that commit, except
`tmlr/pgfplots/sentence_length.csv`, trimmed as the other `tmlr/pgfplots/`
series are (`year,neurips,iclr,icml`, rows where one of those is non-empty,
kept cells the original strings). The trimmed file is byte-identical to the
one `export_pgfplots_data.py` writes.

- `per_paper/sentence_length/{neurips,iclr,icml}.csv`: upstream
  `data/per_paper/sentence_length/` (not tracked upstream; regenerated here
  byte for byte by `src/metrics/sentence_length.py`).
- `tmlr/pgfplots/sentence_length.csv`: upstream
  `tmlr/data/pgfplots/sentence_length.csv`, trimmed.
- `tmlr/analysis/acronym_reuse_freq.csv`, `tmlr/analysis/acronym_robustness.csv`:
  upstream `data/aggregate/`. The reuse file holds all seven upstream rows;
  this release computes the NeurIPS, ICLR, ICML and Barnett and Doubleday
  rows, and the arXiv ML, arXiv non-ML and PubMed rows need their acronym
  frequency histograms.
- `tmlr/analysis/{acronym_concentration,acronym_top_terms,flesch_decomposition,
  topic_assignments,topic_terms,topic_stability,topic_trends,topic_profiles,
  topic_decomposition,topic_decomposition_summary,fixed_mix_readability}.csv`:
  upstream `tmlr/analysis/out/`. `topic_profiles.csv` carries two citation
  columns, `median_citations` and `n_with_citations`, which this release does
  not compute without citation data.

Topic clustering additionally needs scikit-learn 1.9.0.

sha256, first 16 hex:

```
ef870ceb2cd92625  per_paper/sentence_length/neurips.csv
7a01a9a86e51b2ab  per_paper/sentence_length/iclr.csv
5d796220cc68881f  per_paper/sentence_length/icml.csv
4068699f0b65ffc4  tmlr/pgfplots/sentence_length.csv
498d4a785a3e68dc  tmlr/analysis/acronym_concentration.csv
5eeb7980e2dd778a  tmlr/analysis/acronym_reuse_freq.csv
2e1ef078bcd5a534  tmlr/analysis/acronym_robustness.csv
41e2765db2a36c31  tmlr/analysis/acronym_top_terms.csv
1deb3285badda1f1  tmlr/analysis/fixed_mix_readability.csv
c375e91a4335fac3  tmlr/analysis/flesch_decomposition.csv
a4dfa81dd5b02ea0  tmlr/analysis/topic_assignments.csv
04486650bc796cf5  tmlr/analysis/topic_decomposition.csv
3c3e672a21af87e4  tmlr/analysis/topic_decomposition_summary.csv
ec1eca9a7d8b0165  tmlr/analysis/topic_profiles.csv
52923e414c40fbd5  tmlr/analysis/topic_stability.csv
4bc880bfc5745590  tmlr/analysis/topic_terms.csv
2f678b2b0e37d4e6  tmlr/analysis/topic_trends.csv
```

## TMLR paper, citations

Produced from the upstream research repository at commit `eda2733` and the
citation snapshot described in `tmlr/citations/SNAPSHOT.md` (Semantic Scholar,
NeurIPS retrieved 2026-05-11, ICLR and ICML 2026-06-11). The snapshot itself
is not distributed.

Copied byte for byte from upstream, and reproduced byte for byte by
`src/citations/` from the snapshot:

```
tmlr/citations/citation_regression.csv                      data/aggregate/citation_regression.csv
tmlr/citations/citation_readability_top_bottom_combined.csv data/aggregate/citation_readability_top_bottom_combined.csv
tmlr/citations/references.csv                               data/aggregate/references.csv
tmlr/citations/references_per_year.csv                      tmlr/data/pgfplots/references_per_year.csv
tmlr/citations/citation_regression_topics.csv               tmlr/analysis/out/citation_regression_topics.csv
```

Computed by this repository from the snapshot, because upstream wrote these
numbers only to LaTeX, to the terminal, or inside a wider file:

- `citation_llm_top_bottom_combined.csv` (`judge_deciles.py`): the 45 numbers
  of upstream `tmlr/tables/citation_llm_top_bottom_combined.tex`, all equal at
  the table's two decimals.
- `citation_cohens_d.csv` (`regression.py`): the pooled Cohen's d upstream
  `citation_regression.py` printed, equal to full float precision.
- `topic_citations.csv`, `topic_citation_corr.csv` (`topic_citations.py`):
  the columns `topic_k15, n, flesch, median_citations, n_with_citations`
  equal upstream `tmlr/analysis/out/topic_profiles.csv` value for value; the
  Pearson correlation is the paper's TopicCitCorr, -0.59.
- `citation_coverage.csv` (`coverage.py`): coverage through 2024 of 99.8,
  97.0 and 96.3 percent and the 2.1 percent fallback share the paper quotes.

sha256, first 16 hex:

```
fd2c3ef6d22725a9  tmlr/citations/SNAPSHOT.md
09744729bddc0a31  tmlr/citations/citation_cohens_d.csv
d73fdbf40c141f82  tmlr/citations/citation_coverage.csv
70fde10c229bb6e0  tmlr/citations/citation_llm_top_bottom_combined.csv
778fa9031fab4d19  tmlr/citations/citation_readability_top_bottom_combined.csv
ca03a48643809afd  tmlr/citations/citation_regression.csv
343c1fae5cae36e1  tmlr/citations/citation_regression_topics.csv
5d6a75f52fb9a80b  tmlr/citations/references.csv
f568632ce480d5b2  tmlr/citations/references_per_year.csv
99d68b120d904c70  tmlr/citations/topic_citation_corr.csv
c7ae017740db495f  tmlr/citations/topic_citations.csv
```

## TMLR paper, untrimmed figure data

`tmlr/pgfplots_full/` holds the 41 files of the upstream `tmlr/data/pgfplots/`
whose header is `year,neurips,iclr,icml,arxiv_ml,arxiv_nonml,pubmed`, copied
byte for byte from upstream commit `eda2733` (`git show eda2733:<path>`). They
are the untrimmed versions of the per-metric series and `papers_per_year.csv`
in `tmlr/pgfplots/`, plus `sentence_length.csv`, and carry every year any of
the five corpora covers (1987-2027). They are the comparison target for
`src/plotting/export_pgfplots_data.py --baselines`, which builds them from the
conference aggregates and `baselines/`.

sha256, first 16 hex:

```
d07de27c1153dd39  tmlr/pgfplots_full/acronyms_abstract.csv
90b84d9bef5ef680  tmlr/pgfplots_full/acronyms_title.csv
83d1a9c0307b041a  tmlr/pgfplots_full/active_narration.csv
b26de28c5bbb1393  tmlr/pgfplots_full/clauses_per_sent.csv
000b6abeb1326451  tmlr/pgfplots_full/hedging.csv
eead30699fb087ad  tmlr/pgfplots_full/noun_chunks.csv
18b357bf49c890a9  tmlr/pgfplots_full/nouns.csv
aed9ad3df11a75d1  tmlr/pgfplots_full/np_density.csv
7ac795cabe3c6bd2  tmlr/pgfplots_full/numbers.csv
c943607945aa28fc  tmlr/pgfplots_full/papers_per_year.csv
9e15c3e8c0418e17  tmlr/pgfplots_full/parse_depth.csv
4f496b90b294bfc5  tmlr/pgfplots_full/passive_rate.csv
2fe7dac4e84dd4d8  tmlr/pgfplots_full/readability_ari.csv
4d7fdd1dde1a5291  tmlr/pgfplots_full/readability_avg_sentence_length.csv
5c093815e658ed98  tmlr/pgfplots_full/readability_avg_syllables_per_word.csv
aa5cbdce1fd9de77  tmlr/pgfplots_full/readability_coleman_liau.csv
023525172164d891  tmlr/pgfplots_full/readability_dale_chall.csv
ec255156482a56dc  tmlr/pgfplots_full/readability_flesch_ease.csv
f11a35f5a7e5e5fa  tmlr/pgfplots_full/readability_flesch_kincaid.csv
888587e64c438f0d  tmlr/pgfplots_full/readability_forcast.csv
5ac0d7a24de5c5ec  tmlr/pgfplots_full/readability_gunning_fog.csv
15ec6501be8959ce  tmlr/pgfplots_full/readability_linsear_write.csv
fbf2db9ac778e1ae  tmlr/pgfplots_full/readability_lix.csv
2d62750521dc0631  tmlr/pgfplots_full/readability_powers_sumner_kearl.csv
3759c786a0cae842  tmlr/pgfplots_full/readability_rix.csv
0321a2d9c6f8de82  tmlr/pgfplots_full/readability_smog.csv
bcc9b051a47488f8  tmlr/pgfplots_full/readability_spache.csv
eccbe1c4b8f9f9f6  tmlr/pgfplots_full/sensational_additional.csv
5bf0a9109dad1a06  tmlr/pgfplots_full/sensational_attitude.csv
19019704f65f53cb  tmlr/pgfplots_full/sensational_importance.csv
c3bde1c450d7c0d3  tmlr/pgfplots_full/sensational_novelty.csv
69b1b77099dc3d65  tmlr/pgfplots_full/sensational_problem.csv
52f887d3f78a4bab  tmlr/pgfplots_full/sensational_quality.csv
85af2d9299c39db3  tmlr/pgfplots_full/sensational_rigor.csv
41c7c27266d64812  tmlr/pgfplots_full/sensational_scale.csv
b9b9d4636da88743  tmlr/pgfplots_full/sensational_total.csv
d6a51f9c63cb5062  tmlr/pgfplots_full/sensational_utility.csv
d70aca46527f2000  tmlr/pgfplots_full/sentence_length.csv
a09886514aa191f1  tmlr/pgfplots_full/signposting.csv
28f97df9873a2fab  tmlr/pgfplots_full/ttr.csv
1bf5a67df8bc7862  tmlr/pgfplots_full/verbs.csv
```

## TMLR inline numbers and generated tables

`tmlr/tex/` holds the paper's files at upstream commit `eda2733`
(eda27335c0a1887bcf2c93935b612620f1381991), extracted with `git show` byte
for byte: `tmlr/generated_round{2,3,4}.tex` and six tables from
`tmlr/tables/`. They were written upstream by
`tmlr/analysis/make_round{2,3,4}_tex.py`. Rerunning those three scripts on
the upstream inputs at that commit reproduces all nine files byte for byte,
so none was edited by hand. `topic_controls.tex`, `topics.tex` and eleven
macros carry values computed from the citation snapshot.

sha256, first 16 hex:

```
c26f8e853f4e3a44  tmlr/tex/generated_round2.tex
e31c2a0ae623e7de  tmlr/tex/generated_round3.tex
2c6350e5439663b2  tmlr/tex/generated_round4.tex
1f879b1f4d4041f4  tmlr/tex/tables/acronym_concentration.tex
3abbd92dbd367f13  tmlr/tex/tables/normalisation.tex
e290cf23b51dbab8  tmlr/tex/tables/topic_controls.tex
fa7f368620dbba1f  tmlr/tex/tables/topic_decomposition.tex
c3faf0f5685e739b  tmlr/tex/tables/topic_trends.tex
f1126d8984b43752  tmlr/tex/tables/topics.tex
```
