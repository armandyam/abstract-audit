#!/usr/bin/env python3
"""
Aggregate active narration (use of "we/us") per year per venue.

has_narrator is binary (0/1), so mean = proportion of papers using first-person
narration, std = standard deviation of that binary variable.

Reads:  data/per_paper/active_narration/{venue}.csv
Writes: data/aggregate/active_narration.csv

Run:
  python src/aggregate/aggregate_active_narration.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

COLS = ["has_narrator"]

if __name__ == "__main__":
    aggregate("active_narration", COLS)
