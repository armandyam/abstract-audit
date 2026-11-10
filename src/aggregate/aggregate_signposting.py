#!/usr/bin/env python3
"""
Aggregate signposting language per year per venue (mean ± std).

Reads:  data/per_paper/signposting/{venue}.csv
Writes: data/aggregate/signposting.csv

Run:
  python src/aggregate/aggregate_signposting.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

COLS = ["signposting_per_100"]

if __name__ == "__main__":
    aggregate("signposting", COLS)
