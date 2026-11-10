# tests

668 tests covering what the pipeline run cannot (one runs only with
the manuscript, `AA_PAPER`).

## What these are for

`verify.py` already compares 157 files against `reference/`, 49 of them byte
for byte, over 62,628 real papers, and checks the TMLR paper's 163 macros,
its 15 tables and the 1,166 numbers its manuscript prints. As a regression test that is stronger than any unit test
could be, and tests that re-walk the same happy path would add lines without
adding information.

So these tests target what an end-to-end run structurally cannot reach:

- **Inputs absent from the corpus.** Empty abstracts, single sentences, text
  with no terminator, heavy LaTeX, non-ASCII. The premise of this repository
  is that other people measure their own abstracts, and every one of those is
  a live path for them and a dead path for NeurIPS.
- **Stateful resume logic.** A partially written output CSV. The docstring in
  `schema.py` records the bug this replaced: a year with any rows at all was
  treated as finished, so an interrupted run dropped the rest of that year
  permanently and looked complete. The PubMed fetch is interrupted at each
  point between parsing a file and recording it, and resumed with the same
  and with different settings. The citation fetchers retry failed requests
  without counting a paper twice.
- **Error paths.** A missing venue file, a missing column, a malformed record.
- **Domain logic that is not self-evident.** The acronym rule, and the judge
  score parser.
- **Third-party markup.** The parsers for papers.nips.cc, OpenReview, the
  arXiv API, the iclr.cc and icml.cc archive pages, PMLR and the ICLR dataset
  are the only things here that can break with no change to this code.
  The Semantic Scholar and OpenAlex citation fetchers are tested the same
  way, against hand-written responses in `fixtures/citations/`, with the
  network disabled.
- **Citation rules.** Tied citation counts share a percentile, the decile
  cut-offs are inclusive, immature years, zero-length bibliographies and
  authorless records are excluded, and the snapshot check tells the
  published citation data from a fresh fetch.
- **Macro checking.** The `\newcommand` parser on nested and escaped
  braces, comments and malformed definitions; missing, extra, differing and
  skipped names; the three citation modes; `macros.csv` against a
  manuscript's own macro files. The generator is also run on the committed
  reference inputs, which reproduces every printed value except the eleven
  citation ones.
- **Table checking.** The tabular parser on the markup the paper's tables
  use, the inline tables found by label, the check's verdicts and citation
  modes on a miniature manuscript, and the generators whose content is code
  (the judge prompts, the normalisation examples).
- **Claim checking.** The tokenizer that finds the TMLR paper's printed
  numbers (ranges, fractions, spelled-out quantities, identifiers that are
  not numbers, masked LaTeX structure and figure code); coverage on
  deliberately broken claims (uncovered, stale, a changed printed value,
  duplicate) tied by context hash; the comparison rules; the KNOWN and
  citation verdicts; check functions on synthetic series with a known
  answer. One test checks that the committed `claims.csv` holds no
  manuscript text; one ties it to the manuscript when `AA_PAPER` points at a
  local copy, and is skipped otherwise.
- **Source dispatch.** Each ICLR and ICML year reads one raw source, and the
  early sources pass their text through unchanged.
- **Reference provenance.** `reference/MANIFEST.md` lists every file in
  `reference/` with its current hash, and the checker fails on a missing,
  unlisted, duplicated or changed file.

## What is deliberately not tested

The fifteen readability formulas from `textstat`, and the spaCy-derived
features. Testing those tests someone else's library. What is tested is the
two formulas implemented here by hand, and the guard that decides whether an
abstract is scored at all.

## Coverage

About 68% of `src/` by statement. That number is low on purpose and the shape
matters more: nearly all of the remainder is `main()` functions, file-reading
loops, the GPU scoring path and network fetching. Those are exercised by a
full pipeline run, which checks them against the reference files rather than
against a mock.

The criterion held here is not a percentage but this: every branch that
handles malformed or edge-case input has a test, because those are exactly
the branches 62,628 well-formed papers never enter.

## Running

    pip install -r requirements-dev.txt
    pytest

    pytest --cov=src --cov-report=term-missing     # with coverage
    pytest tests/test_acronyms.py -v               # one module

The tests do not gate the pipeline. `python main.py` never invokes them.
