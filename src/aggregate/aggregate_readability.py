#!/usr/bin/env python3
"""
Aggregate readability scores per year per venue (mean ± std).

Reads:  data/per_paper/readability/{venue}.csv
Writes: data/aggregate/readability.csv

Run:
  python src/aggregate/aggregate_readability.py
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from aggregate._utils import aggregate

COLS = [
    "word_count",
    "avg_sentence_length",
    "avg_syllables_per_word",
    "flesch_ease",
    "flesch_kincaid",
    "gunning_fog",
    "smog",
    "dale_chall",
    "spache",
    "coleman_liau",
    "ari",
    "linsear_write",
    "lix",
    "rix",
    "forcast",
    "powers_sumner_kearl",
]

if __name__ == "__main__":
    aggregate("readability", COLS)
