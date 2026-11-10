#!/usr/bin/env python3
"""
Aggregate Type-Token Ratio per year per venue (mean ± std).

Reads:  data/per_paper/ttr/{venue}.csv
Writes: data/aggregate/ttr.csv

Run:
  python src/aggregate/aggregate_ttr.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

if __name__ == "__main__":
    aggregate("ttr", ["ttr"])
