#!/usr/bin/env python3
"""
Aggregate noun phrase density per year per venue (mean ± std).

Reads:  data/per_paper/np_density/{venue}.csv
Writes: data/aggregate/np_density.csv

Run:
  python src/aggregate/aggregate_np_density.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

if __name__ == "__main__":
    aggregate("np_density", ["np_density"])
