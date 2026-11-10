#!/usr/bin/env python3
"""
Aggregate passive voice rate per year per venue (mean ± std).

Reads:  data/per_paper/passive_rate/{venue}.csv
Writes: data/aggregate/passive_rate.csv

Run:
  python src/aggregate/aggregate_passive_rate.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

if __name__ == "__main__":
    aggregate("passive_rate", ["passive_rate"])
