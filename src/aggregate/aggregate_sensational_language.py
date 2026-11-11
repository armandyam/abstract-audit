#!/usr/bin/env python3
"""
Aggregate sensational (hype) language per year per venue (mean ± std).

Reads:  data/per_paper/sensational_language/{venue}.csv
Writes: data/aggregate/sensational_language.csv

Run:
  python src/aggregate/aggregate_sensational_language.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation
from aggregate._utils import aggregate

COLS = [
    "hype_importance_per_100",
    "hype_novelty_per_100",
    "hype_rigor_per_100",
    "hype_scale_per_100",
    "hype_utility_per_100",
    "hype_quality_per_100",
    "hype_attitude_per_100",
    "hype_problem_per_100",
    "hype_additional_per_100",
    "hype_total_per_100",
]

if __name__ == "__main__":
    aggregate("sensational_language", COLS)
