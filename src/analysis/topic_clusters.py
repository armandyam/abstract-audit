#!/usr/bin/env python3
"""Assign a topic to every conference abstract.

Topics are derived from the text of the papers themselves (titles and
abstracts), since the conference records have no topic field. The TMLR paper uses them as a
subfield control (Section 5 and Appendix) and to locate the readability trend
within the field.

Method follows Weisser et al. (2020, MethodsX 10.1016/j.mex.2020.100831), who
cluster an abstract corpus with TF-IDF features and k-means. TF-IDF is reduced
with truncated SVD (LSA, 150 dimensions) before clustering, which keeps
k-means in a dense, lower-noise space. Clustering runs at k = 10, 15, 20 and
30; the paper's primary resolution is 15.

Text is the title and abstract, normalised with
processing/text_cleaning.clean_abstract (LaTeX resolved, URLs stripped,
non-ASCII removed). Residual link fragments and code-availability boilerplate
are removed as well: left in, they form a large "github, https, code
available" cluster that is not a subfield.

Every paper gets a cluster, including ICLR 2026, so nothing drops downstream.
Seeds are fixed. Stability is measured by clustering two disjoint thirds of
the corpus and comparing their labels on the held-out third (adjusted Rand
and adjusted mutual information).

Reads:  data/processed/{neurips,iclr,icml}/*.json
Writes: data/aggregate/topic_assignments.csv   paper_id, venue, year, topic_k*
        data/aggregate/topic_terms.csv         top ten terms per cluster
        data/aggregate/topic_stability.csv     split-sample reproducibility

Run:
  python src/analysis/topic_clusters.py
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import Normalizer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from processing.text_cleaning import clean_abstract  # noqa: E402

_D = os.environ.get("AA_DATA", "data")
PROCESSED = os.path.join(_D, "processed")
OUT = os.path.join(_D, "aggregate")

VENUES = ["neurips", "iclr", "icml"]
K_VALUES = [10, 15, 20, 30]
N_COMPONENTS = 150
SEED = 0

_URL_RE = re.compile(r"https?://\S+|www\.\S+|\b[\w.-]+\.(?:com|org|io|net|edu)\b")
_BOILER = ["github", "https", "http", "www", "com", "org", "io", "code",
           "available", "publicly", "released", "release", "url", "anonymous",
           "supplementary", "appendix"]


def load_conference_papers(processed: str = PROCESSED,
                           venues: list[str] = VENUES) -> pd.DataFrame:
    """Every processed record, in venue order, then file order, then record order.

    The order matters: it fixes the rows k-means sees and the permutation the
    stability check draws.
    """
    rows = []
    for venue in venues:
        for path in sorted(glob.glob(os.path.join(processed, venue, "*.json"))):
            with open(path, encoding="utf-8") as fh:
                for p in json.load(fh):
                    rows.append({"paper_id": p["paper_id"], "venue": venue,
                                 "year": int(p["year"]), "title": p.get("title") or "",
                                 "abstract": p.get("abstract") or ""})
    return pd.DataFrame(rows, columns=["paper_id", "venue", "year", "title", "abstract"])


def clustering_text(title: str, abstract: str) -> str:
    """Normalised "title. abstract" with link fragments removed."""
    t = clean_abstract(title, math="token")
    a = clean_abstract(abstract, math="token")
    return _URL_RE.sub(" ", f"{t}. {a}").strip()


def build_features(text: pd.Series, n_components: int = N_COMPONENTS,
                   min_df: int = 5):
    """TF-IDF on unigrams and bigrams, then LSA with unit-length rows."""
    vec = TfidfVectorizer(
        lowercase=True, strip_accents="unicode",
        stop_words=list(ENGLISH_STOP_WORDS) + _BOILER,
        ngram_range=(1, 2), min_df=min_df, max_df=0.4, sublinear_tf=True,
        max_features=200_000,
    )
    X = vec.fit_transform(text)
    lsa = make_pipeline(TruncatedSVD(n_components=n_components, random_state=SEED),
                        Normalizer(copy=False))
    Z = lsa.fit_transform(X)
    print(f"tf-idf {X.shape[0]:,} x {X.shape[1]:,}  ->  svd {Z.shape[1]} dims, "
          f"{100 * lsa[0].explained_variance_ratio_.sum():.1f}% variance")
    return Z, lsa, np.array(vec.get_feature_names_out())


def cluster(Z: np.ndarray, lsa, terms: np.ndarray, k_values: list[int] = K_VALUES):
    """Labels for each k, and the top ten terms of each cluster centroid."""
    labels, term_rows = {}, []
    for k in k_values:
        km = MiniBatchKMeans(n_clusters=k, random_state=SEED, n_init=10,
                             batch_size=4096, max_iter=300)
        lab = km.fit_predict(Z)
        labels[k] = lab
        sizes = pd.Series(lab).value_counts()
        print(f"  k={k:3d}  cluster sizes {sizes.min():,}-{sizes.max():,}")
        centroids = lsa[0].inverse_transform(km.cluster_centers_)
        for c in range(k):
            top = terms[np.argsort(centroids[c])[::-1][:10]]
            term_rows.append({"k": k, "cluster": c, "n": int(sizes.get(c, 0)),
                              "top_terms": ", ".join(top)})
    return labels, pd.DataFrame(term_rows)


def stability(Z: np.ndarray, k_values: list[int] = K_VALUES) -> list[dict]:
    """Cluster two disjoint thirds, compare their labels on the held-out third.

    Structure that reproduces on data neither run saw is not an artefact of
    one sample or one seed.
    """
    rng = np.random.default_rng(SEED)
    idx = rng.permutation(len(Z))
    n = len(Z) // 3
    A, B, H = idx[:n], idx[n:2 * n], idx[2 * n:]
    rows = []
    for k in k_values:
        ka = MiniBatchKMeans(k, random_state=1, n_init=10, batch_size=4096).fit(Z[A])
        kb = MiniBatchKMeans(k, random_state=2, n_init=10, batch_size=4096).fit(Z[B])
        la, lb = ka.predict(Z[H]), kb.predict(Z[H])
        rows.append({"k": k, "n_heldout": len(H),
                     "ari": adjusted_rand_score(la, lb),
                     "ami": adjusted_mutual_info_score(la, lb)})
        print(f"  k={k:3d}  ARI={rows[-1]['ari']:.3f}  AMI={rows[-1]['ami']:.3f}")
    return rows


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    df = load_conference_papers()
    if df.empty:
        # The pipeline run from the shipped per-paper metrics has no abstracts.
        print(f"  no processed abstracts under {PROCESSED}; skipping")
        return
    print(f"conference papers: {len(df):,}\n")

    text = pd.Series([clustering_text(t, a) for t, a in zip(df["title"], df["abstract"])])
    Z, lsa, terms = build_features(text)

    labels, term_df = cluster(Z, lsa, terms)
    for k, lab in labels.items():
        df[f"topic_k{k}"] = lab

    print("\nsplit-sample stability:")
    stab = stability(Z)

    keep = ["paper_id", "venue", "year"] + [f"topic_k{k}" for k in K_VALUES]
    df[keep].to_csv(os.path.join(OUT, "topic_assignments.csv"), index=False)
    term_df.to_csv(os.path.join(OUT, "topic_terms.csv"), index=False)
    pd.DataFrame(stab).to_csv(os.path.join(OUT, "topic_stability.csv"), index=False)
    print(f"\nwrote topic_assignments.csv, topic_terms.csv, topic_stability.csv to {OUT}")


if __name__ == "__main__":
    main()
