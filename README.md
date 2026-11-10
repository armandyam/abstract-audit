# Abstract Audit

## About

Writing metrics for research abstracts. The pipeline computes 15 classical
readability formulas, 14 further writing measures, and six open-weight LLM
judge scores over the accepted papers of three machine learning conferences:

```
NeurIPS  1987-2025  30,595 papers
ICLR     2013-2026  16,807 papers
ICML     2008-2025  15,226 papers
```

It reproduces the results of two papers, and `verify.py` compares the
regenerated artefacts against the files behind each paper's figures, tables
and printed numbers:

- *Machine Learning Research Has Outpaced Its Communication Norms*
  (Transactions on Machine Learning Research, 2026). NeurIPS, ICLR and ICML.
- *LLM Judges Agree With Each Other and Disagree With Human-Grounded
  Readability Metrics* (UncertaiNLP 2026, non-archival). NeurIPS only. The tag
  `uncertainlp-2026` marks the release that accompanied that paper.

## Corpus

No abstracts are redistributed here. The scrapers retrieve them from their
sources, and every record carries a `paper_id` that resolves to its origin.

```
NeurIPS  1987-2025  papers.nips.cc                      scrape_neurips.py
ICLR     2013       OpenReview, conference-track accepts  scrape_iclr_openreview_early.py
ICLR     2014-2016  iclr.cc accepted lists, via arXiv   scrape_iclr_arxiv.py
ICLR     2017-2025  ICLR dataset 25v2 (see below)       fetch_iclr_dataset.py
ICLR     2026       OpenReview                          scrape_iclr.py
ICML     2008-2012  icml.cc archive pages               scrape_icml_legacy.py
ICML     2013-2016  PMLR proceedings                    scrape_icml_pmlr.py
ICML     2017-2025  icml.cc export                      download_icml.py
```

ICLR 2017-2025 come from version 25v2 of the ICLR dataset by Rita
González-Márquez and Dmitry Kobak (MIT licence,
<https://github.com/berenslab/iclr-dataset>; *Learning representations of
learning representations*, DMLR workshop at ICLR 2024). `fetch_iclr_dataset.py`
downloads it at a pinned commit and checks its SHA-256. Processing keeps the
accepted papers of every venue.

OpenReview now answers anonymous API requests with a challenge page, so the
two OpenReview scrapers log in with an account's credentials, read from the
environment variables `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD`.

On 10 November 2026 the ICLR and ICML scrapers were rerun against their
sources. ICLR 2014-2025 and ICML 2008-2016 came back as the same records the
published values were computed on. The icml.cc export no longer returns JSON
to `download_icml.py`, so ICML 2017-2025 cannot currently be re-downloaded
with it. ICLR 2013 and 2026 need OpenReview credentials and were not
re-fetched.

## Contents

```
src/            pipeline
tests/          tests, documented in tests/README.md
paper/          UncertaiNLP figure sources and rendered figures.pdf;
                paper/tmlr/ holds the TMLR abstract for the self-audit, the
                macro generator, and the manuscript text (source/) with the
                claim table (claims.csv) that ties every printed number to
                an output
judge_scores/   judge scores, six models, by venue
baselines/      arXiv and PubMed per-year aggregates for the TMLR paper,
                documented in baselines/README.md
reference/      expected pipeline outputs, both papers; MANIFEST.md records
                their provenance and hashes
data/           generated, absent from a fresh clone
```

`judge_scores/` requires a GPU to regenerate and is therefore distributed. It
covers 56,805 papers: NeurIPS 1987-2024 (24,772), all of ICLR (16,807) and all
of ICML (15,226). `baselines/` is distributed because its sources cannot be
fetched again in the form the paper used. `reference/` is the comparison
target for `verify.py`, and also allows the pipeline to run from the
aggregation stage onward without scraping.

## Execution

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm

pip install -r requirements-scrape.txt
export OPENREVIEW_USERNAME=... OPENREVIEW_PASSWORD=...
python src/scraping/scrape_neurips.py --start 1987 --end 2025
python src/scraping/scrape_iclr_openreview_early.py
python src/scraping/scrape_iclr_arxiv.py
python src/scraping/fetch_iclr_dataset.py
python src/scraping/scrape_iclr.py
python src/scraping/scrape_icml_legacy.py
python src/scraping/scrape_icml_pmlr.py
python src/scraping/download_icml.py
python main.py
```

From the distributed metrics, without scraping:

```bash
mkdir -p data/per_paper && cp -R reference/per_paper/. data/per_paper/
python main.py --from aggregate
```

That route skips the `papers_per_year` count and the LaTeX robustness
analysis, which read the processed abstracts, so `verify.py` reports those
as missing.

## Stages

```
process      raw JSON to canonical records
validate     every record against the Pydantic schema
metrics      readability, acronyms, hedging, signposting, narration, hype,
             Hohmann sentence length
metrics_nlp  parse depth, NP density, passive rate, TTR, clause and POS counts
aggregate    per-paper values to per-year mean, standard deviation and count;
             papers per year; judge scores per venue
export       aggregates to plot-ready CSVs: data/pgfplots/ for the UncertaiNLP
             figures, data/pgfplots/tmlr/ for the TMLR figures, with the arXiv
             and PubMed series from baselines/
model_avg    per-model z-scores to the six-model average
analysis     metric against judge Spearman correlation, summary series,
             Flesch under LaTeX and URL normalisation, readability
             collinearity, acronym reuse, robustness and concentration,
             Flesch decomposition, topic clusters, trends, profiles and
             decomposition
self_audit   the TMLR paper's own title and abstract
citations    citation analyses; runs only when the reader's own Semantic
             Scholar counts are present (see Citations)
macros       the TMLR paper's 163 inline numbers and six generated tables,
             written to data/tmlr/ by paper/tmlr/make_macros.py
claims       every other number the TMLR manuscript prints, checked against
             the outputs by paper/tmlr/check_claims.py
figures      heatmap and the rendered figure set
verify       all artefacts against reference/
```

`main.py --list` enumerates the stages. `--stages`, `--from` and `--skip`
select subsets.

## Judges

```
Gemma-3-27B-Instruct    Llama-3.1-8B-Instruct    Mixtral-8x7B-Instruct
Gemma-4-31B-Instruct    Mistral-7B-Instruct      Qwen2.5-32B-Instruct
```

Decoding uses `temperature=0.7`, `do_sample=True` and `max_new_tokens=8`, with
three runs per paper, prompt and model, of which the median is reported. Scores
are standardised per model against the 1987 to 2022 baseline, then averaged
across models. The three prompt templates are in `src/metrics/llm_scores.py`.

## The TMLR paper

The release covers every series, table and number in the TMLR paper:

- the readability, acronym density, sensational language, writing style and
  Hohmann sentence length series for NeurIPS, ICLR and ICML, and papers per
  year, each with the arXiv ML, arXiv non-ML and PubMed columns;
- the judge series and six-model averages for all three venues;
- the LaTeX and URL normalisation analysis (`latex_robustness.csv` and the
  derived numbers in `latex_robustness_summary.csv`);
- the collinearity of the 15 readability formulas;
- the acronym reuse, robustness and concentration tables;
- the Flesch decomposition and the topic analyses (clusters, trends,
  profiles and the topic decomposition);
- the citation analyses, as scripts only (see Citations);
- the self-audit of the paper's own abstract:

```bash
python src/metrics/audit_self.py \
    --title "Machine Learning Research Has Outpaced Its Communication Norms" \
    --abstract-file paper/tmlr/self_audit_abstract.txt
```

The arXiv and PubMed series are computed from per-year aggregates shipped in
`baselines/`, because neither source can be fetched again in the form the
paper used. The scripts that produced them are included and documented there:
`src/scraping/download_arxiv.py`, `src/processing/process_arxiv.py`,
`src/processing/fetch_pubmed.py` and `src/processing/clean_pubmed.py` for the
records, the metric scripts run with `--venues arxiv pubmed` for the
per-paper values, and `src/baselines/make_baselines.py` for the aggregates. The acronym reuse rows
for arXiv and PubMed come from `baselines/acronym_histograms.csv`.

## Citations

Citation counts are not distributed. The Semantic Scholar API licence allows
the data to be used but not redistributed, so `src/citations/fetch_s2.py`
fetches them into `data/per_paper/citations/` (then `fallback.py` and
`enrich.py`; see their docstrings). The citations stage and `verify.py` run in
one of three modes, decided by `src/citations/snapshot.py`:

```
strict   the three local files match the published snapshot's hashes: every
         citation output must equal reference/tmlr/citations/ exactly
fresh    the files exist but differ (a new fetch): outputs are reported, not
         failed, since counts change daily
absent   no files: the citations stage does not run and citation checks are
         skipped
```

`reference/tmlr/citations/SNAPSHOT.md` records the snapshot.

Citation and reference counts come from Semantic Scholar
(<https://www.semanticscholar.org/?utm_source=api>), through the Semantic
Scholar Academic Graph API, under the Semantic Scholar API License Agreement
(<https://api.semanticscholar.org/license/>). The fallback pass and
`fetch_openalex.py` use OpenAlex (<https://openalex.org>), whose data is
released under CC0 1.0.

## Verification

`verify.py` compares 167 files against `reference/` in strict citation mode,
157 otherwise. The 48 per-paper metric files (16 families for each venue) and
the figure PNG are compared byte for byte. The other 118 files, the
plot-ready CSVs and the analysis and citation outputs of both papers, are
compared numerically at `atol=0`, with text columns compared as strings. The
ten citation outputs count only in strict citation mode. It exits non-zero
on any mismatch and reports the installed package versions against those
`reference/` was built with. `python reference/make_manifest.py` checks the
reference files themselves against the hashes in `reference/MANIFEST.md`.

It also checks the TMLR paper's inline numbers. The paper resolves 163 of
them through `\newcommand` macros in three generated files and inputs six
generated tables. `paper/tmlr/make_macros.py` writes all of them from the
pipeline's outputs with the formatting code of the upstream generators, and
`paper/tmlr/check_macros.py` compares them with the paper's own files in
`reference/tmlr/tex/`: macros by name and exact value, tables byte for byte.
Eleven macros and two tables need citation counts. They are compared when the
local counts are the published snapshot, reported but not counted after a
fresh fetch, and skipped when there are none.

Every other number the manuscript prints is checked too. `paper/tmlr/source/`
holds the manuscript text (main.tex and every table and figure it inputs,
without comments or author details), copied from the research repository by
`paper/tmlr/import_source.py`. `paper/tmlr/inventory.py` finds every number in
it: numerals, ranges, fractions such as "14 of the 15", and spelled-out
quantities such as "roughly a quarter". `paper/tmlr/claims.csv` has one row
per number, saying whether it is measured, quoted from the literature, a
design constant or unverifiable, and naming the function in
`paper/tmlr/claims.py` that recomputes it from the pipeline's outputs.
`paper/tmlr/check_claims.py` reports each as MATCH, MISMATCH, SKIP or
UNVERIFIABLE, and fails if a number has no row or a row no longer marks a
number. Citation claims are recomputed in strict citation mode and otherwise
compared with the frozen outputs in `reference/tmlr/citations/`. Its docstring
says how to update `claims.csv` after the manuscript changes.

Two dependencies determine the values and are pinned exactly. The `textstat`
implementations have changed across releases. The spaCy model version
determines parse depth, NP density, passive rate and TTR.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite covers inputs absent from the corpus, the resume logic over
partially written output (including an interrupted PubMed fetch and retried
citation requests), the error paths, the acronym rule, the judge score
parser, the scrapers' parsers for every source, the per-year source dispatch
in processing, the text normalisation rules, the macro and claim checkers,
and the self-audit's manuscript reader. `tests/README.md` states the coverage
criterion.

## Licence

Copyright 2026 Ajay Mandyam Rangarajan and Jeyashree Krishnan.

Code under `src/` and `paper/`: MIT (`LICENSE`). Derived data under
`judge_scores/`, `reference/` and `baselines/`: CC BY 4.0 (`LICENSE-DATA`).
Neither covers the source abstracts (NeurIPS, ICLR, ICML, arXiv, PubMed),
which are not distributed here, or third-party citation counts.

Sources and attribution:

- ICLR 2017-2025: the ICLR dataset by Rita González-Márquez and Dmitry Kobak,
  MIT licence (<https://github.com/berenslab/iclr-dataset>).
- arXiv: arXiv metadata, dedicated to the public domain under CC0 1.0 by
  arXiv.
- PubMed: courtesy of the U.S. National Library of Medicine. The aggregates in
  `baselines/` were computed from the 2026 PubMed baseline and do not reflect
  the most current or accurate data available from NLM. NLM has not endorsed
  this work.
- Citation counts: Semantic Scholar
  (<https://www.semanticscholar.org/?utm_source=api>), under the Semantic
  Scholar API License Agreement (<https://api.semanticscholar.org/license/>).
  Not distributed.
- OpenAlex: CC0 1.0 (<https://openalex.org>).
