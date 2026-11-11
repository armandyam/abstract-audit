# paper/uncertainlp/reference/

The expected outputs only the UncertaiNLP paper uses. The judge series, the
judge-metric correlations and the heatmap it also plots are shared with the
other papers and are in `shared/reference/`.

`pgfplots/readability_*.csv` carry only `year` and `neurips`, the two columns
this paper's figures read, and only the 39 years NeurIPS covers (1987-2025).
Upstream those files spanned 1987-2027 with four further corpora, because the
year index was the union across five corpora and ICLR 2026 and PubMed
ahead-of-print records extend past 2025. Those rows and columns are empty for
NeurIPS and are dropped rather than left here to imply this release covers
them. No value was altered.

`pgfplots/va_flesch.csv` and `va_zscore.csv` are the two summary series of the
visual abstract (`src/analysis/visual_abstract_data.py`).
