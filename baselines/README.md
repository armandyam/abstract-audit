# baselines/

Per-year aggregates and pooled acronym frequency histograms for the two
comparison corpora of the TMLR paper: arXiv, split into machine learning and
the rest by primary category, and PubMed. The aggregates are inputs to the
TMLR export (`src/plotting/export_pgfplots_data.py --baselines`), which merges
them with the conference aggregates into the paper's six-column figure data.
The histograms are inputs to the acronym reuse table
(`src/analysis/acronym_reuse.py`).

They are shipped because they cannot be rebuilt in the form the paper used.
The per-paper metric files they come from run to 13 GB, the arXiv snapshot was
a Kaggle version that is no longer the current download, and NLM replaces the
PubMed baseline every year. `src/baselines/make_baselines.py` wrote every file
here from those per-paper files, with the pipeline's own aggregation code, and
each one equals the upstream research repository's aggregate value for value.

## Contents

```
aggregate/{family}.csv                  year; pubmed_{col}_{mean,std,count};
                                        arxiv_{col}_{mean,std,count}
aggregate/{family}_arxiv_by_category.csv
                                        year, arxiv_primary_category,
                                        {col}_{mean,std,count}
papers_per_year.csv                     year, arxiv_ml, arxiv_nonml,
                                        pubmed_scored, pubmed_records
acronym_histograms.csv                  group, occurrences, acronym_types
```

There are 16 metric families. PubMed has no per-paper file for the nine spaCy
families (clauses per sentence, noun chunks, nouns, NP density, numbers, parse
depth, passive rate, TTR, verbs), so those carry arXiv only.

The arXiv ML group is the eleven primary categories in
`src/arxiv_categories.py`. Its series is the count-weighted mean over those
categories' rows in `{family}_arxiv_by_category.csv`, and the non-ML series
the same over every other category.

PubMed years run to 2027. The 2026 and 2027 rows are ahead-of-print records,
which belong to no publication year, and the export cuts PubMed at 2025.

## Using locally computed baselines

The export takes arXiv and PubMed only from the directory given to
`--baselines`, and ignores any `arxiv_*` and `pubmed_*` columns in
`data/aggregate/` (written there when `AA_BASELINES` is set). To plot
baselines computed from local per-paper files, write them to a directory of
their own and point the export at it:

```bash
python src/baselines/make_baselines.py --out-dir data/baselines_local
python src/plotting/export_pgfplots_data.py --baselines data/baselines_local
```

## Two PubMed denominators

`papers_per_year.csv` gives PubMed twice.

- `pubmed_scored` counts abstracts with a readability score, that is with at
  least ten words (the guard in `src/metrics/readability.py`). It is the
  count the paper plots. 24,301,259 abstracts for 1990-2025.
- `pubmed_records` counts every cleaned record, the sentence length count.
  24,306,644 for 1990-2025, and 156,564 more dated 2026 and 2027, for
  24,463,208 in all.

Every PubMed metric other than readability is averaged over
`pubmed_records`.

The arXiv columns count records per group: the sum of
`title_acronym_density_count` over the group's categories, which every arXiv
record has. 442,829 ML and 2,380,794 non-ML records, 2,823,623 in all.

## Acronym histograms

For each of `arxiv_ml`, `arxiv_nonml` and `pubmed`, `acronym_types` is the
number of distinct abstract acronyms that occur exactly `occurrences` times
across the group's abstracts. The acronym reuse table follows from it: the
number of unique acronyms is the sum of `acronym_types`, and the share used
once, 2-9, 10-99, 100-999 and 1000 or more times is the sum over those
occurrence counts divided by it (`reuse_row` in `make_baselines.py`). PubMed
is limited to records dated up to 2025, as in the paper's table. arXiv has no
year limit.

## Sources

- arXiv: the Kaggle dataset `Cornell-University/arxiv`, a mirror of the arXiv
  OAI metadata. arXiv releases its metadata under CC0 1.0. The snapshot used
  ends at arXiv:2509.04450 (early September 2025) and was processed in April
  2026 into 2,823,623 records for 1991-2025. See
  `src/scraping/download_arxiv.py`.
- PubMed: the 2026 MEDLINE/PubMed baseline, files `pubmed26n0001.xml.gz` to
  `pubmed26n1334.xml.gz`, English abstracts of at least six words dated 1990
  or later, with structured abstract headings removed. See
  `src/processing/fetch_pubmed.py` and `src/processing/clean_pubmed.py`.

## Licence and attribution

The files in this directory are derived data, licensed under CC BY 4.0
(`LICENSE-DATA`). They hold per-year aggregates and acronym frequency
histograms pooled over each group's abstracts. They hold no abstract text and
no per-paper value.

PubMed data courtesy of the U.S. National Library of Medicine. These
aggregates were computed from the 2026 PubMed baseline and do not reflect the
most current or accurate data available from NLM. NLM has not endorsed this
work.

arXiv metadata is dedicated to the public domain under CC0 1.0 by arXiv.
