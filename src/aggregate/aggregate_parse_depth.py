#!/usr/bin/env python3
"""
Aggregate parse depth per year per venue (mean ± std).

Reads:  data/per_paper/parse_depth/{venue}.csv
Writes: data/aggregate/parse_depth.csv

Run:
  python src/aggregate/aggregate_parse_depth.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

if __name__ == "__main__":
    aggregate("parse_depth", ["parse_depth"])
