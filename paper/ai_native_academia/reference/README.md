# paper/ai_native_academia/reference/

The expected outputs only the AI-Native Academia workshop paper uses. Its
figure data is shared with the other papers and is in
`shared/reference/pgfplots/`, and its text normalisation numbers come from
the NeurIPS rows of `shared/reference/analysis/latex_robustness.csv`.

- `analysis/topic_*_neurips.csv` and `analysis/fixed_mix_neurips.csv` hold
  the NeurIPS-only topic fit and the profile and fixed-mix series built on
  it. `topic_profiles_neurips.csv` lacks the two upstream citation columns.
- `analysis/judge_*_neurips.csv` hold the judges' run-to-run stability, raw
  score levels, scored-paper counts and agreement.
- `macros.csv` holds the values the paper prints through 42 of its 52 macros
  (file, name, value), written from the manuscript's macro file by
  `paper/ai_native_academia/check_macros.py --write-reference`. The other ten
  are citation macros, whose values are not held here.

`MANIFEST.md` records where each file came from and its sha256 hash.

No citation output is held here, and neither is any statistic computed from
the citation counts, including the values the paper prints. They are checked
against the manuscript's own values (`AA_PAPER_AI_NATIVE_ACADEMIA`) when the
reader's counts are the published snapshot (see `src/citations/snapshot.py`),
and skipped otherwise. The manuscript itself is not held here either.
