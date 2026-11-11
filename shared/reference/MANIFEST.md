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
