#!/usr/bin/env python3
"""
Aggregate hedging language per year per venue (mean ± std).

Reads:  data/per_paper/hedging/{venue}.csv
Writes: data/aggregate/hedging.csv

Run:
  python src/aggregate/aggregate_hedging.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

COLS = ["hedging_per_100"]

if __name__ == "__main__":
    aggregate("hedging", COLS)
