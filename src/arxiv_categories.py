"""The arXiv primary categories counted as machine learning.

The TMLR paper splits arXiv into an ML group and a non-ML control group by a
paper's primary category, the first entry of its `categories` field in the
arXiv metadata. The ML group is these eleven categories. Every other primary
category, and a paper with no primary category, is non-ML.

Upstream this set lived in src/plotting/_utils.py and was shared by the
export, the arXiv-by-category aggregation and the acronym reuse table. It is
a module of its own here so that those consumers import one definition.
"""

from __future__ import annotations

import pandas as pd

ARXIV_ML_CATEGORIES: frozenset[str] = frozenset({
    "cs.LG",    # Machine Learning
    "cs.AI",    # Artificial Intelligence
    "cs.CV",    # Computer Vision and Pattern Recognition
    "cs.CL",    # Computation and Language
    "cs.NE",    # Neural and Evolutionary Computing
    "cs.RO",    # Robotics
    "cs.IR",    # Information Retrieval
    "cs.MA",    # Multiagent Systems
    "cs.HC",    # Human-Computer Interaction
    "cs.CY",    # Computers and Society
    "stat.ML",  # Statistics, Machine Learning
})


def is_ml(categories: pd.Series) -> pd.Series:
    """Boolean mask, True where the primary category is one of the eleven.

    A missing category is False, so it falls in the non-ML group, as it did
    upstream (`Series.isin` is False for NaN).
    """
    return categories.isin(ARXIV_ML_CATEGORIES)
