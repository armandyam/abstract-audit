# abstract-audit

Writing metrics for research abstracts. The pipeline computes 15 classical
readability formulas, 14 further writing measures, and six open-weight LLM
judge scores over 30,595 NeurIPS abstracts from 1987 to 2025.

It reproduces every figure in *LLM Judges Agree With Each Other and Disagree
With Human-Grounded Readability Metrics* (UncertaiNLP 2026, non-archival).
`verify.py` compares the regenerated artefacts against the files that produced
the published figures.

## Corpus

NeurIPS abstracts are not redistributed here. `src/scraping/scrape_neurips.py`
retrieves them from `papers.nips.cc`. Every record carries a `paper_id` of the
form `{year}_{hash}`, where the hash is the one in the source URL, so each
record resolves to its origin.

```
pre-2020   papers.nips.cc/paper/{year}/file/{hash}-Metadata.json
2020+      papers.nips.cc/paper_files/paper/{year}/hash/{hash}-Abstract.html
```

## Contents

```
src/            pipeline
tests/          269 tests, documented in tests/README.md
paper/          figure sources, their generators, and the rendered figures.pdf
judge_scores/   1.3 M judge scores over 24,772 papers, six models
reference/      expected pipeline outputs
data/           generated, absent from a fresh clone
```

`judge_scores/` requires a GPU to regenerate and is therefore distributed.
`reference/` is the comparison target for `verify.py`, and also allows the
pipeline to run from the aggregation stage onward without scraping.

## Execution

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm

python src/scraping/scrape_neurips.py --start 1987 --end 2025
python main.py
```

From the distributed metrics, without scraping:

```bash
mkdir -p data/per_paper && cp -R reference/per_paper/. data/per_paper/
python main.py --from aggregate
```

## Stages

```
process      raw JSON to canonical records
validate     every record against the Pydantic schema
metrics      readability, acronyms, hedging, signposting, narration, hype
metrics_nlp  parse depth, NP density, passive rate, TTR, clause and POS counts
aggregate    per-paper values to per-year mean, standard deviation and count
export       aggregates to plot-ready CSVs
model_avg    per-model z-scores to the six-model average
analysis     metric against judge Spearman correlation, summary series
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

## Verification

`verify.py` compares 15 per-paper metric files byte for byte, 24 plot-ready
CSVs numerically at `atol=0`, and the figure PNG byte for byte. It exits
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
parser, and the `papers.nips.cc` HTML parsers. `tests/README.md` states the
coverage criterion.

## Licence

Copyright 2026 Ajay Mandyam Rangarajan and Jeyashree Krishnan.

Code under `src/` and `paper/`: MIT (`LICENSE`). Derived data under
`judge_scores/` and `reference/`: CC BY 4.0 (`LICENSE-DATA`). Neither covers
the NeurIPS abstracts, which are not distributed here.
