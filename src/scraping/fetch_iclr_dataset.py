#!/usr/bin/env python3
"""
Fetch ICLR 2017-2025 from the ICLR dataset into data/raw/iclr/.

ICLR 2017-2025 in this release come from version 25v2 of the ICLR dataset by
Rita González-Márquez and Dmitry Kobak (MIT licence), a complete scrape of
OpenReview submissions with their decisions:

  https://github.com/berenslab/iclr-dataset
  González-Márquez and Kobak, Learning representations of learning
  representations, DMLR workshop at ICLR 2024, arXiv:2404.08403.

The file is fetched at a pinned commit and checked against its SHA-256, so a
rerun always starts from the same bytes. Each year is written as
data/raw/iclr/iclr_{year}_data.json in the same record shape scrape_iclr.py
writes for 2026: {year, id, title, abstract, authors (comma-separated),
decision, scores, keywords, labels, author_ids}, in the dataset's order (year,
then OpenReview id). The dataset holds every submission; process_iclr.py keeps
the accepted ones.

Requires: pip install pyarrow   (see requirements-scrape.txt)

Usage:
  python src/scraping/fetch_iclr_dataset.py
  python src/scraping/fetch_iclr_dataset.py --years 2024 2025
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import urllib.request

COMMIT = "c7bd8f1ba4360a73a29c14088219b5d25380ba61"
URL = f"https://github.com/berenslab/iclr-dataset/raw/{COMMIT}/data/iclr25v2.parquet"
SHA256 = "48215679d54ea788b8dfc1177850845f047c5810554708273b617b67ce321859"
YEARS = list(range(2017, 2026))
UA = {"User-Agent": "Mozilla/5.0 (research; abstract-audit)"}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(dest: str) -> str:
    """Fetch the pinned parquet once; verify it every time."""
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        tmp = dest + ".part"
        with urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=120) as r, \
                open(tmp, "wb") as fh:
            fh.write(r.read())
        os.replace(tmp, dest)
    got = sha256(dest)
    if got != SHA256:
        raise SystemExit(f"{dest}: SHA-256 {got} does not match the pinned {SHA256}")
    return dest


def to_record(row: dict) -> dict:
    """One dataset row in the raw ICLR record shape."""
    return {
        "year":       int(row["year"]),
        "id":         row["id"],
        "title":      row["title"],
        "abstract":   row["abstract"],
        "authors":    row["authors"],
        "decision":   row["decision"],
        "scores":     [int(s) for s in row["scores"]],
        "keywords":   [str(k) for k in row["keywords"]],
        "labels":     row["labels"],
        "author_ids": row["author_ids"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=YEARS)
    ap.add_argument("--raw-dir", default="data/raw/iclr")
    args = ap.parse_args()

    import pandas as pd

    path = download(os.path.join(args.raw_dir, "iclr25v2.parquet"))
    df = pd.read_parquet(path)
    for year in args.years:
        rows = df[df["year"] == year].to_dict("records")
        if not rows:
            print(f"  [ICLR {year}] not in the dataset, skipping")
            continue
        out = os.path.join(args.raw_dir, f"iclr_{year}_data.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump([to_record(r) for r in rows], fh, ensure_ascii=False)
        print(f"  [ICLR {year}] {len(rows)} submissions -> {out}")


if __name__ == "__main__":
    main()
