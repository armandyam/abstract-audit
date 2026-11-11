# Abstract Audit

## About

Writing metrics for research abstracts. The pipeline computes 15 classical
readability measures (13 formulas, mean sentence length and mean syllables per
word), 15 further families of writing metrics, and six open-weight LLM judge
scores over the accepted papers of three machine learning conferences:

```
NeurIPS  1987-2025  30,595 papers
ICLR     2013-2026  16,807 papers
ICML     2008-2025  15,226 papers
```

It reproduces the results of three papers, and `verify.py` compares the
regenerated artefacts against the files behind each paper's figures, tables
and printed numbers:

- *Machine Learning Research Has Outpaced Its Communication Norms*
  (Transactions on Machine Learning Research, 2026). The full study: NeurIPS,
  ICLR and ICML, with the arXiv ML, arXiv non-ML and PubMed baselines.
- *Measurable Writing Standards for AI-Native Venues* (NeurIPS 2026
  AI-Native Academia workshop). NeurIPS, with the arXiv and PubMed series.
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
src/                    pipeline, shared across papers
tests/                  tests, documented in tests/README.md
shared/                 data shared across papers, one copy each
  judge_scores/         judge scores, six models, by venue
  baselines/            arXiv and PubMed per-year aggregates, documented in
                        shared/baselines/README.md
  figs/                 the judge heatmap PNG two papers include
  reference/            expected outputs shared across papers: per-paper
                        metrics, plot-ready series, analyses; MANIFEST.md
                        records their provenance and hashes
paper/<name>/           one folder per paper: its figure and table sources,
                        the rendered figures.pdf, its generators and checks,
                        and reference/ with the expected outputs only that
                        paper uses (and its own MANIFEST.md)
  uncertainlp/
  tmlr/                 also claims.csv, which ties every printed number to
                        an output
  ai_native_academia/
data/                   generated, absent from a fresh clone: the shared
                        stages at the top (raw/, processed/, per_paper/,
                        aggregate/, pgfplots/), then data/<name>/ per paper
```

`shared/judge_scores/` requires a GPU to regenerate and is therefore distributed. It
covers 56,805 papers: NeurIPS 1987-2024 (24,772), all of ICLR (16,807) and all
of ICML (15,226). `shared/baselines/` is distributed because its sources cannot be
fetched again in the form the papers used. The reference folders are the
comparison target for `verify.py`. `shared/reference/per_paper/` also allows
the pipeline to run from the aggregation stage onward without scraping.

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
mkdir -p data/per_paper && cp -R shared/reference/per_paper/. data/per_paper/
python main.py --from aggregate
```

That route has no abstracts, so every analysis that reads them is skipped
and listed as incomplete: the paper counts, the LaTeX robustness analysis, the
topic analyses, the citation regressions, and the macro sections built from
them. `verify.py` reports their outputs as missing and exits non-zero. Every
other artefact is still checked.

## Stages

```
process      raw JSON to canonical records
validate     every record against the Pydantic schema
metrics      readability, acronyms, hedging, signposting, narration, hype,
             Hohmann sentence length
metrics_nlp  parse depth, NP density, passive rate, TTR, clause and POS counts
aggregate    per-paper values to per-year mean, standard deviation and count;
             papers per year; judge scores per venue
export       aggregates to plot-ready CSVs: data/pgfplots/ for every series
             more than one paper plots, with the arXiv and PubMed series
             from shared/baselines/, and data/uncertainlp/pgfplots/ for the
             UncertaiNLP paper's NeurIPS-only readability series
model_avg    per-model z-scores to the six-model average
analysis     metric against judge Spearman correlation, summary series,
             Flesch under LaTeX and URL normalisation, readability
             collinearity, acronym reuse, robustness and concentration,
             Flesch decomposition, topic clusters, trends, profiles and
             decomposition
self_audit   the TMLR paper's own title and abstract (needs AA_PAPER)
citations    citation analyses; runs only when the reader's own Semantic
             Scholar counts are present (see Citations)
macros       the TMLR paper's 163 inline numbers and its 13 data-driven
             tables, written to data/tmlr/ by paper/tmlr/make_macros.py and
             make_tables.py, and compared with the paper
claims       every other number the TMLR manuscript prints, checked against
             the outputs by paper/tmlr/check_claims.py
figures      heatmap and the rendered figure sets of every paper
verify       all artefacts against shared/reference/ and paper/*/reference/
```

`main.py --list` enumerates the stages. `--stages`, `--from` and `--skip`
select subsets.

## Judges

```
Gemma-3-27B-Instruct    Llama-3.1-8B-Instruct    Mixtral-8x7B-Instruct
Gemma-4-31B-Instruct    Mistral-7B-Instruct      Qwen2.5-32B-Instruct
```

Decoding uses `temperature=0.7`, `do_sample=True` and `max_new_tokens=8`, with
three runs per paper, prompt and model. The yearly series average the scores
over papers and runs for each model and prompt. Each model's yearly means are
standardised against that venue's years up to 2022, then averaged across
models. The agreement analysis scores each paper by each model's median of
its available parsed scores, separately for each prompt. The metric correlation analysis
takes each model's median over all of a paper's scores, across prompts and
runs, and averages those medians across models. The three prompt templates are in `src/metrics/llm_scores.py`.

## The TMLR paper

The release covers every series, table and number in the TMLR paper:

- the readability, acronym density, sensational language, writing style and
  Hohmann sentence length series for NeurIPS, ICLR and ICML, and papers per
  year, each with the arXiv ML, arXiv non-ML and PubMed columns;
- the judge series and six-model averages for all three venues;
- the LaTeX and URL normalisation analysis (`latex_robustness.csv` and the
  derived numbers in `latex_robustness_summary.csv`);
- the collinearity of the 15 readability measures;
- the acronym reuse, robustness and concentration tables;
- the Flesch decomposition and the topic analyses (clusters, trends,
  profiles and the topic decomposition);
- the citation analyses, as scripts only (see Citations);
- the self-audit of the paper's own abstract, from a local copy of the
  manuscript (see The manuscript):

```bash
python src/metrics/audit_self.py --from-tex $AA_PAPER/main.tex
```

Every figure and table of the paper has its source in `paper/tmlr/`: the ten
figure source files in `figs/`, with their captions, read the shared series in
`data/pgfplots/`. The data-driven tables are generated from the
pipeline's outputs into `data/tmlr/tables/`, each from the paper's table as
the template: six by `make_macros.py` with the paper's macros, seven by
`make_tables.py` (acronym reuse, the two citation decile tables, corpus
sizes, the self-audit, the judge prompts and the text normalisation rules).
The two tables that carry no computed value are committed in `tables/`.
`paper/tmlr/build_figures.py` renders all of them to `data/tmlr/figures.pdf`
(the figures stage). A generated table that was not built is replaced by a
note, as is the citation figure without its input, and the citation figure
and tables are always replaced without the reader's citation counts. Every
other figure needs its input, and rendering fails if one is missing. The tracked
`paper/tmlr/figures.pdf` is built with `--public`, which always replaces the
citation figure and tables by notes, since no citation-derived value is
distributed.

The arXiv and PubMed series are computed from per-year aggregates shipped in
`shared/baselines/`, because neither source can be fetched again in the form the
paper used. The scripts that produced them are included and documented there:
`src/scraping/download_arxiv.py`, `src/processing/process_arxiv.py`,
`src/processing/fetch_pubmed.py` and `src/processing/clean_pubmed.py` for the
records, the metric scripts run with `--venues arxiv pubmed` for the
per-paper values, and `src/baselines/make_baselines.py` for the aggregates. The acronym reuse rows
for arXiv and PubMed come from `shared/baselines/acronym_histograms.csv`.

## The AI-Native Academia paper

`paper/ai_native_academia/` holds the paper's eleven figure source files, with their
captions, and the generators and checks for its tables and inline numbers.
The figures read the shared series in `data/pgfplots/` and include the shared
heatmap in `shared/figs/`; the paper holds no figure data of its own.

Two analyses are the paper's own. The topic analysis is fitted on NeurIPS
alone (`src/analysis/topic_clusters.py --venues neurips`, then
`paper/ai_native_academia/topics.py` for the profile, the fixed-mix series and
the paper's topic labels), where the TMLR paper pools three venues.
`src/analysis/judge_agreement.py` computes the judges' run-to-run stability,
raw score levels and agreement. `make_macros.py` writes the paper's 52 inline
numbers and its topic table into `data/ai_native_academia/`, and
`make_tables.py` its acronym reuse, judge stability, judge agreement and
citation decile tables, without their captions; the numbers the captions print
are computed and checked all the same. `check_macros.py` compares 42 macros
with `paper/ai_native_academia/reference/macros.csv`. The other ten are
citation macros and are handled as in the TMLR paper (see Citations).

With a local copy of the manuscript in `AA_PAPER_AI_NATIVE_ACADEMIA`,
`check_tables.py` compares every table and every number in its caption with
the paper. One row differs: the PubMed row of the acronym reuse table prints
1,692,497 acronyms and 48.5 and 3.1 percent, and
`shared/baselines/acronym_histograms.csv` gives 1,679,954, 48.4 and 3.2. The
paper was built from an earlier PubMed histogram that is not part of this
release, and the check reports the row as a mismatch.

## The manuscript

The TMLR manuscript is not distributed with this repository: no part of its
text is shipped, apart from the figure and table sources with their captions
in `paper/tmlr/`. Four checks read it, and take a local copy of its LaTeX
source (the folder with `main.tex`, `generated_round{2,3,4}.tex`, `tables/`
and `figs/`) from the environment variable `AA_PAPER` or `--paper-dir`:

```bash
export AA_PAPER=/path/to/manuscript
python main.py --from self_audit       # or: python verify.py
```

```
self_audit     the paper's own title and abstract, measured by audit_self.py
check_macros   paper/tmlr/reference/macros.csv against the paper's macro files,
               and the citation macros against the paper's values
check_tables   every generated table against the paper's table, cell by cell
check_claims   coverage: every number the paper prints has a row in
               claims.csv, and every row still marks a number; it also
               supplies the printed values of the citation claims
```

Without `AA_PAPER` the self-audit stage is skipped, those checks are
reported as skipped, and everything else runs. The non-citation macros in
`macros.csv` and every non-citation row of `claims.csv` with a check function
are still recomputed and compared, subject to the input exemptions documented
in `paper/tmlr/check_claims.py`; literature and design rows without a check
function are skipped, and unverifiable rows are reported as such. The
citation numbers are the exception: their printed values are not stored (see Citations), so without
the manuscript the citation macros and claims are reported as skipped.

## Citations

Citation counts are not distributed. The Semantic Scholar API licence allows
the data to be used but not redistributed, so `src/citations/fetch_s2.py`
fetches them into `data/per_paper/citations/` (then `fallback.py` and
`enrich.py`; see their docstrings). The citations stage and `verify.py` run in
one of three modes, decided by `src/citations/snapshot.py`:

```
strict   the three local files match the published snapshot's hashes: every
         citation number the paper prints (claims, macros and the four
         citation-dependent tables) must be reproduced exactly
fresh    all three files exist and at least one differs (a new fetch): those
         numbers are reported, not failed, since counts change daily
absent   at least one of the three files is missing: the citations stage does
         not run and citation checks are skipped
```

No statistic computed from the counts is distributed either, not even the
values the paper prints: `paper/tmlr/reference/macros.csv` leaves out the eleven
citation macros, and `paper/tmlr/claims.csv` leaves the printed value blank
on every citation row. The citation checks read those printed values from
the manuscript (`AA_PAPER`) and compare the recomputed outputs with them;
without it they are skipped.
`src/citations/snapshot.py` holds the snapshot's SHA-256 hashes and
retrieval dates.

Citation and reference counts come from Semantic Scholar
(<https://www.semanticscholar.org/?utm_source=api>), through the Semantic
Scholar Academic Graph API, under the Semantic Scholar API License Agreement
(<https://api.semanticscholar.org/license/>). The fallback pass and
`fetch_openalex.py` use OpenAlex (<https://openalex.org>), whose data is
released under CC0 1.0.

## Verification

`verify.py` compares 161 files against `shared/reference/` and the papers'
`reference/` folders. The 48 per-paper metric files (16 families for each
venue) and the heatmap PNG are compared byte for byte. The other 112 files,
the plot-ready CSVs and the analysis outputs of every paper, are compared
numerically at `atol=0`, with text columns compared as strings. It exits non-zero on any mismatch and reports the
installed package versions against those the reference files were built with.
`python src/make_manifest.py` checks the reference files themselves
against the hashes in each reference folder's `MANIFEST.md`.

It also checks every number the TMLR paper prints, in three parts.

The paper resolves 163 inline numbers through `\newcommand` macros in three
generated files. `paper/tmlr/make_macros.py` writes them from the pipeline's
outputs with the formatting code of the upstream generators, and
`paper/tmlr/check_macros.py` compares them by name and exact value with the
printed values in `paper/tmlr/reference/macros.csv`, which holds 152 of them. The
eleven citation macros are compared with the manuscript's own macro files.

`paper/tmlr/check_tables.py` compares every table the release builds (the
thirteen generated tables and the two static ones) with the paper's own
table, cell by cell.

Every other printed number has a row in `paper/tmlr/claims.csv`: the value
as printed (blank for a citation number, which is read from the manuscript),
whether it is measured, quoted from the literature, a design
constant or unverifiable, and, where one applies, the function in
`paper/tmlr/claims.py` that recomputes it from the pipeline's outputs. The file holds no text from the
manuscript; each row is tied to its place in the paper by a SHA-256 hash of
the number and the words around it. `paper/tmlr/check_claims.py` reports
each row as MATCH, MISMATCH, KNOWN, MISSING (an input was not built),
ERROR, SKIP or UNVERIFIABLE; MISMATCH, MISSING and ERROR count as failures. KNOWN marks the two
discrepancies the authors chose to keep in the published text; they are
reported with the computed value and not counted as failures. With the
manuscript (`AA_PAPER`), `paper/tmlr/inventory.py` finds every number it
prints (numerals, ranges, fractions and spelled-out quantities), and the
check fails if a number has no row or a row no longer marks a number. The
docstring of `paper/tmlr/check_claims.py` says how to update `claims.csv` after
the manuscript changes.

Citation numbers (eleven macros, four tables and the citation claims) are
compared when the local counts are the published snapshot, reported but not
counted after a fresh fetch, and skipped when there are none. Their printed
values come from the manuscript, so they are also skipped without `AA_PAPER`.
Without `AA_PAPER` the comparisons with the manuscript are skipped and
reported (see The manuscript).

Reproducing the reference values needs the versions pinned in
`requirements.txt` and `en_core_web_sm` 3.8.0. The readability values depend
on `textstat`, whose implementations have changed across releases. The parsed
features depend on spaCy, its model and its numeric backends (`thinc`,
`blis`). Topic clustering also depends on scikit-learn.

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
`shared/` and `paper/*/reference/`: CC BY 4.0 (`LICENSE-DATA`).
Neither covers the source abstracts (NeurIPS, ICLR, ICML, arXiv, PubMed),
which are not distributed here, or third-party citation counts.

Sources and attribution:

- ICLR 2017-2025: the ICLR dataset by Rita González-Márquez and Dmitry Kobak,
  MIT licence (<https://github.com/berenslab/iclr-dataset>).
- arXiv: arXiv metadata, dedicated to the public domain under CC0 1.0 by
  arXiv.
- PubMed: courtesy of the U.S. National Library of Medicine. The aggregates in
  `shared/baselines/` were computed from the 2026 PubMed baseline and do not reflect
  the most current or accurate data available from NLM. NLM has not endorsed
  this work.
- Citation counts: Semantic Scholar
  (<https://www.semanticscholar.org/?utm_source=api>), under the Semantic
  Scholar API License Agreement (<https://api.semanticscholar.org/license/>).
  Not distributed.
- OpenAlex: CC0 1.0 (<https://openalex.org>).
