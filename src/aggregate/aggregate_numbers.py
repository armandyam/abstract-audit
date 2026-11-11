#!/usr/bin/env python3
"""
Aggregate numeric token density per year per venue (mean ± std).

Reads:  data/per_paper/numbers/{venue}.csv
Writes: data/aggregate/numbers.csv

Run:
  python src/aggregate/aggregate_numbers.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

COLS = ["num_per_100"]

if __name__ == "__main__":
    aggregate("numbers", COLS)
