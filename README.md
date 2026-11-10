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

It reproduces the conference results of two papers, and `verify.py` compares
the regenerated artefacts against the files behind each paper's figures and
tables:

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
                paper/tmlr/ holds the TMLR abstract for the self-audit
judge_scores/   judge scores, six models, by venue
reference/      expected pipeline outputs, both papers
data/           generated, absent from a fresh clone
```

`judge_scores/` requires a GPU to regenerate and is therefore distributed. It
covers 56,805 papers: NeurIPS 1987-2024 (24,772), all of ICLR (16,807) and all
of ICML (15,226). `reference/` is the comparison target for `verify.py`, and
also allows the pipeline to run from the aggregation stage onward without
scraping.

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
metrics      readability, acronyms, hedging, signposting, narration, hype
metrics_nlp  parse depth, NP density, passive rate, TTR, clause and POS counts
aggregate    per-paper values to per-year mean, standard deviation and count;
             papers per year; judge scores per venue
export       aggregates to plot-ready CSVs: data/pgfplots/ for the UncertaiNLP
             figures, data/pgfplots/tmlr/ for the TMLR figures
model_avg    per-model z-scores to the six-model average
analysis     metric against judge Spearman correlation, summary series,
             Flesch under LaTeX and URL normalisation, readability collinearity
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

The release reproduces every conference-side series and number in the TMLR
paper within this scope:

- the readability, acronym density, sensational language and writing style
  series for NeurIPS, ICLR and ICML, and papers per year;
- the judge series and six-model averages for all three venues;
- the LaTeX and URL normalisation analysis (`latex_robustness.csv` and the
  derived numbers in `latex_robustness_summary.csv`);
- the collinearity of the 15 readability formulas;
- the self-audit of the paper's own abstract:

```bash
python src/metrics/audit_self.py \
    --title "Machine Learning Research Has Outpaced Its Communication Norms" \
    --abstract-file paper/tmlr/self_audit_abstract.txt
```

The paper's arXiv and PubMed baselines, citation analyses, topic analyses,
acronym reuse tables and Hohmann sentence length series are not part of this
release, so the self-audit omits the sentence length row.

## Verification

`verify.py` compares the per-paper metric files of every venue byte for byte,
the plot-ready CSVs and analysis outputs of both papers numerically at
`atol=0` (text columns as strings), and the figure PNG byte for byte. It exits
non-zero on any mismatch and reports the installed package versions against
those `reference/` was built with.

Two dependencies determine the values and are pinned exactly. The `textstat`
implementations have changed across releases. The spaCy model version
determines parse depth, NP density, passive rate and TTR.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite covers inputs absent from the corpus, the resume logic over
partially written output, the error paths, the acronym rule, the judge score
parser, the scrapers' parsers for every source, the per-year source dispatch
in processing, the text normalisation rules, and the self-audit's manuscript
reader. `tests/README.md` states the coverage criterion.

## Licence

Copyright 2026 Ajay Mandyam Rangarajan and Jeyashree Krishnan.

Code under `src/` and `paper/`: MIT (`LICENSE`). Derived data under
`judge_scores/` and `reference/`: CC BY 4.0 (`LICENSE-DATA`). Neither covers
the conference abstracts, which are not distributed here.
