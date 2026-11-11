# shared/reference/ provenance

The per-paper metric files both papers share. Every hash list below is checked
against the files by `python src/make_manifest.py`, which fails on a listed
path that is missing, a hash that differs and a file no list names; `--write`
refreshes the hashes.

Built with: python 3.14.3, pandas 3.0.2, numpy 2.4.4, scipy 1.17.1,
matplotlib 3.10.8, textstat 0.7.13, spacy 3.8.13, en_core_web_sm 3.8.0, thinc 8.3.13 and blis 1.3.3. blis is spaCy's numeric
backend, and blis 1.3.4 changes one verb count in `per_paper/verbs/neurips.csv`.

## NeurIPS

Produced by the upstream research repository at commit `e291e24`
(e291e24dccf3f608ddf4e84ad871008c0a4780f2) for the UncertaiNLP paper.

sha256, first 16 hex:

```
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
```

## ICLR and ICML

Added for the TMLR paper from upstream commit `eda2733`, the camera-ready
build of that paper, copied byte for byte.

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
```

## Sentence length

`per_paper/sentence_length/{neurips,iclr,icml}.csv`: upstream
`data/per_paper/sentence_length/` at `eda2733` (not tracked upstream;
regenerated here byte for byte by `src/metrics/sentence_length.py`).

sha256, first 16 hex:

```
ef870ceb2cd92625  per_paper/sentence_length/neurips.csv
7a01a9a86e51b2ab  per_paper/sentence_length/iclr.csv
5d796220cc68881f  per_paper/sentence_length/icml.csv
```

## Figure data shared by the papers

`pgfplots/` holds every plot-ready series more than one paper reads, one copy
each. `src/plotting/export_pgfplots_data.py --baselines` and
`src/aggregate/aggregate_llm_model_avg.py` build them into `data/pgfplots/`.

The 41 per-metric files, `sentence_length.csv` and `papers_per_year.csv`
among them, carry the header `year,neurips,iclr,icml,arxiv_ml,arxiv_nonml,pubmed`
and every year any of the five corpora covers (1987-2027). They are byte
copies of the upstream `tmlr/data/pgfplots/` at commit `eda2733`, built from
the conference aggregates and `shared/baselines/`. The TMLR and AI-Native
Academia papers plot them.

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

The 27 judge series (`llm_scores_*.csv`) are copied whole from the same
upstream directory. The NeurIPS files without a venue suffix are byte
identical to those the UncertaiNLP paper shipped from upstream commit
`e291e24`. All three papers plot them.

sha256, first 16 hex:

```
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
```

`pgfplots/judge_metric_corr.csv` (the metric against judge Spearman
correlations, `src/analysis/judge_feature_correlation.py`) and
`fig_judge_metric_heatmap.png` (rendered from it by
`src/plotting/make_heatmap.py`) come from upstream commit `e291e24`. The
UncertaiNLP and AI-Native Academia papers include the heatmap.

sha256, first 16 hex:

```
aaa5354c5691c4ac  fig_judge_metric_heatmap.png
20649ddaf5f5104a  pgfplots/judge_metric_corr.csv
```
