#!/usr/bin/env python3
"""
Aggregate words per sentence (Hohmann) per year per venue (mean, std, count).

Reads:  data/per_paper/sentence_length/{venue}.csv
Writes: data/aggregate/sentence_length.csv

Run:
  python src/aggregate/aggregate_sentence_length.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

COLS = ["n_words", "words_per_sentence"]

if __name__ == "__main__":
    aggregate("sentence_length", COLS)
