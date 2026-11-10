#!/usr/bin/env python3
"""
Aggregate noun chunk density per year per venue (mean ± std).

Reads:  data/per_paper/noun_chunks/{venue}.csv
Writes: data/aggregate/noun_chunks.csv

Run:
  python src/aggregate/aggregate_noun_chunks.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

COLS = ["noun_chunks_per_100"]

if __name__ == "__main__":
    aggregate("noun_chunks", COLS)
