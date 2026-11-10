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
