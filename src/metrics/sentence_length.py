#!/usr/bin/env python3
"""
Per-paper sentence length metric: words per sentence in abstracts.

Based on Hohmann, Barnett, King & Connell (2025), Scientometrics 130:3349-3366.
DOI: https://doi.org/10.1007/s11192-025-05353-8
Source R code: https://github.com/agbarnett/narrator

Method: count sentence-ending full stops (a period followed by whitespace, or
a final period), then words_per_sentence = n_words / n_sentences. This follows
the narrator paper: "tracking the frequency of full-stops, selecting only for
those used at the end of a sentence." An abstract with no terminating period
counts as one sentence, so the ratio is always defined.

This differs from the `avg_sentence_length` readability column, which uses
textstat's sentence splitter on the raw text. This one runs on the
narrator-preprocessed abstract, like hedging and signposting.

Output: data/per_paper/sentence_length/{venue}.csv
Columns: paper_id, venue, year, n_words, n_sentences, words_per_sentence

Usage:
  python src/metrics/sentence_length.py
  python src/metrics/sentence_length.py --venues neurips iclr
"""

from __future__ import annotations
import argparse
import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from metrics._narrator_utils import (
    preprocess, word_count, count_sentences, run_venue_metric,
)

VENUES = ["neurips", "iclr", "icml"]


def words_per_sentence(abstract: str) -> tuple[int, int, float]:
    """(n_words, n_sentences, words_per_sentence) of a raw abstract."""
    text = preprocess(abstract)
    nw = word_count(text)
    ns = count_sentences(text)
    return nw, ns, round(nw / ns, 4)


def _compute_row(paper: dict) -> dict:
    nw, ns, wps = words_per_sentence(paper.get("abstract", ""))
    return {
        "paper_id":           paper["paper_id"],
        "venue":              paper["venue"],
        "year":               paper["year"],
        "n_words":            nw,
        "n_sentences":        ns,
        "words_per_sentence": wps,
    }


def process_venue(venue: str, processed_dir: str, out_dir: str) -> int:
    return run_venue_metric(venue, processed_dir, out_dir, _compute_row)


def main():
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-dir", default=os.path.join(repo, "data", "processed"))
    parser.add_argument("--out-dir",       default=os.path.join(repo, "data", "per_paper", "sentence_length"))
    parser.add_argument("--venues", nargs="+", default=VENUES)
    args = parser.parse_args()

    total = 0
    for venue in args.venues:
        total += process_venue(venue, args.processed_dir, args.out_dir)
    print(f"\nTotal: {total} papers")


if __name__ == "__main__":
    main()
