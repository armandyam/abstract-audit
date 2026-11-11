#!/usr/bin/env python3
"""
Aggregate verb density per year per venue (mean ± std).

Reads:  data/per_paper/verbs/{venue}.csv
Writes: data/aggregate/verbs.csv

Run:
  python src/aggregate/aggregate_verbs.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

COLS = ["verb_per_100"]

if __name__ == "__main__":
    aggregate("verbs", COLS)
