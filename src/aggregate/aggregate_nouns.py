#!/usr/bin/env python3
"""
Aggregate noun density per year per venue (mean ± std).

Reads:  data/per_paper/nouns/{venue}.csv
Writes: data/aggregate/nouns.csv

Run:
  python src/aggregate/aggregate_nouns.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

COLS = ["noun_per_100"]

if __name__ == "__main__":
    aggregate("nouns", COLS)
