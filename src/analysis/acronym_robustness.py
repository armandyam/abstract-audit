#!/usr/bin/env python3
"""Is the ML acronym elevation an artefact of a few common terms?

Recomputes NeurIPS 2025 title and abstract acronym density after excluding an
explicit list of 30 established community acronyms (COMMON), and the share of
distinct abstract acronyms used fewer than ten times with and without them.
The TMLR paper quotes these numbers in its appendix.

Density is per paper, acronyms per 100 words, averaged over the year's papers.
Reuse is counted over the whole NeurIPS series, not one year, because an
acronym's reuse count is only meaningful across the full series.

Reads:  data/per_paper/acronyms/neurips.csv
Writes: data/aggregate/acronym_robustness.csv

Run:
  python src/analysis/acronym_robustness.py
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import Counter
from pathlib import Path

_D = os.environ.get("AA_DATA", "data")

# Established community acronyms. Anything on this list is vocabulary a reader
# of an ML venue can be assumed to hold already, so excluding it tests whether
# the density elevation comes from paper-specific coinages. Matching is on the
# upper-cased acronym.
COMMON = {
    "AI", "ML", "DL", "NLP", "CV", "RL", "LLM", "VLM",
    "CNN", "RNN", "LSTM", "GRU", "GNN", "MLP", "GAN", "VAE",
    "BERT", "GPT", "SGD", "ADAM", "SVM", "PCA", "KL", "MSE",
    "MDP", "POMDP", "SOTA", "IID", "ELBO", "MCMC",
}

VENUE = "neurips"
YEAR = 2025


def load_all(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load(path: Path, year: int) -> list[dict]:
    return [r for r in load_all(path) if int(r["year"]) == year]


def density(rows: list[dict], field: str, drop: set[str]) -> float:
    """Mean per-paper acronyms per 100 words, excluding `drop`.

    A paper with an empty field (21 NeurIPS 2025 abstracts) has density zero
    and stays in the mean, as in the main pipeline, which writes 0.0 for it.
    No rows give NaN.
    """
    per_paper = []
    for r in rows:
        words = float(r[f"{field}_word_count"] or 0)
        if words <= 0:
            per_paper.append(0.0)
            continue
        toks = [a for a in (r[f"{field}_acronyms"] or "").split("|") if a]
        kept = [a for a in toks if a.upper() not in drop]
        per_paper.append(100.0 * len(kept) / words)
    return sum(per_paper) / len(per_paper) if per_paper else float("nan")


def reuse_share(rows: list[dict], drop: set[str], threshold: int = 10) -> float:
    """Share of distinct abstract acronyms appearing fewer than `threshold`
    times, excluding `drop`. No acronyms give NaN."""
    counts: Counter[str] = Counter()
    for r in rows:
        for a in (r["abstract_acronyms"] or "").split("|"):
            if a and a.upper() not in drop:
                counts[a] += 1
    if not counts:
        return float("nan")
    rare = sum(1 for c in counts.values() if c < threshold)
    return 100.0 * rare / len(counts)


def robustness(rows_all: list[dict], year: int = YEAR, venue: str = VENUE) -> dict:
    """The output row, from every per-paper row of one venue."""
    rows_year = [r for r in rows_all if int(r["year"]) == year]
    return {
        "venue": venue,
        "year": year,
        "n_papers": len(rows_year),
        "n_excluded_terms": len(COMMON),
        "title_density_all": round(density(rows_year, "title", set()), 2),
        "title_density_excl": round(density(rows_year, "title", COMMON), 2),
        "abstract_density_all": round(density(rows_year, "abstract", set()), 2),
        "abstract_density_excl": round(density(rows_year, "abstract", COMMON), 2),
        "n_unique_abstract_acronyms": len({
            a for r in rows_all for a in (r["abstract_acronyms"] or "").split("|") if a
        }),
        "rare_share_all": round(reuse_share(rows_all, set()), 1),
        "rare_share_excl": round(reuse_share(rows_all, COMMON), 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-paper", type=Path,
                    default=Path(_D, "per_paper", "acronyms"))
    ap.add_argument("--out", type=Path,
                    default=Path(_D, "aggregate", "acronym_robustness.csv"))
    args = ap.parse_args()

    res = robustness(load_all(args.per_paper / f"{VENUE}.csv"))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(res))
        w.writeheader()
        w.writerow(res)

    for k, v in res.items():
        print(f"  {k:32s} {v}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
