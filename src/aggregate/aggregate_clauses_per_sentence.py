#!/usr/bin/env python3
"""
Aggregate subordinate clauses per sentence per year per venue (mean ± std).

Reads:  data/per_paper/clauses_per_sentence/{venue}.csv
Writes: data/aggregate/clauses_per_sentence.csv

Run:
  python src/aggregate/aggregate_clauses_per_sentence.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

if __name__ == "__main__":
    aggregate("clauses_per_sentence", ["clauses_per_sent"])
