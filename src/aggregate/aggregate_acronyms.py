#!/usr/bin/env python3
"""
Aggregate acronym density per year per venue (mean ± std).

Reads:  data/per_paper/acronyms/{venue}.csv
Writes: data/aggregate/acronyms.csv
Columns: year, {venue}_title_acronym_density_{mean|std},
              {venue}_abstract_acronym_density_{mean|std}

Run:
  python src/aggregate/aggregate_acronyms.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

COLS = ["title_acronym_density", "abstract_acronym_density"]

if __name__ == "__main__":
    aggregate("acronyms", COLS)
