#!/usr/bin/env python3
"""
Download the arXiv metadata snapshot from Kaggle.

Saves: data/raw/arxiv/arxiv-metadata-oai-snapshot.json  (about 5 GB)

Source: the Kaggle dataset Cornell-University/arxiv
(https://www.kaggle.com/datasets/Cornell-University/arxiv), a JSON-lines
mirror of the arXiv OAI metadata that Cornell refreshes weekly. arXiv
releases the metadata under CC0 1.0.

Which snapshot the TMLR paper used
----------------------------------
The snapshot file was not kept, so its SHA-256 and Kaggle version number are
not known. What is known comes from the processed records it produced:

  - processed 21-22 April 2026 (the date earlier notes give as the
    "2026-04-21 snapshot" is this processing date);
  - the newest record is arXiv:2509.04450, so the snapshot itself is a
    Kaggle version from early September 2025, and arXiv 2025 covers
    January to early September;
  - 2,823,623 records across 1991-2025 after process_arxiv.py's filters.

Regeneration and recomputation
------------------------------
Kaggle keeps only the current file on the default download path, and every
weekly version adds papers and replaces abstracts revised since the last
one. A download today therefore does not regenerate the paper's arXiv
series. It recomputes them on a newer corpus: every year changes a little
(revised abstracts), 2025 gains its last four months, and later years appear.

The arXiv numbers in the paper are shipped as aggregates in baselines/ and
are reproduced from there (src/baselines/make_baselines.py documents how
they were made). Running this script and process_arxiv.py is the route to
recomputing the baselines on a new snapshot. Pass --sha256 to record the
hash of the file you used, so that your own run can be pinned.

Requires the Kaggle CLI and an API token:
  pip install kaggle
  # token from https://www.kaggle.com/settings, API, Create New Token,
  # saved as ~/.kaggle/kaggle.json

Usage:
  python src/scraping/download_arxiv.py
  python src/scraping/download_arxiv.py --out-dir data/raw/arxiv
  python src/scraping/download_arxiv.py --check     # only check the file exists
  python src/scraping/download_arxiv.py --check --sha256
"""

from __future__ import annotations
import argparse
import hashlib
import os
import shutil
import subprocess
import sys

KAGGLE_DATASET = "Cornell-University/arxiv"
SNAPSHOT_NAME  = "arxiv-metadata-oai-snapshot.json"
DATA_DIR       = os.environ.get("AA_DATA", "data")
OUT_DIR        = os.path.join(DATA_DIR, "raw", "arxiv")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(out_dir: str) -> str:
    """Fetch the current snapshot with the Kaggle CLI unless it is present."""
    os.makedirs(out_dir, exist_ok=True)
    snapshot_path = os.path.join(out_dir, SNAPSHOT_NAME)

    if os.path.exists(snapshot_path):
        size_gb = os.path.getsize(snapshot_path) / 1e9
        print(f"Snapshot already exists: {snapshot_path} ({size_gb:.1f} GB)")
        return snapshot_path

    if shutil.which("kaggle") is None:
        sys.exit(
            "kaggle CLI not found. Install with: pip install kaggle\n"
            "and save an API token as ~/.kaggle/kaggle.json, or download the file\n"
            "by hand from https://www.kaggle.com/datasets/Cornell-University/arxiv"
        )
    if not os.path.exists(os.path.expanduser("~/.kaggle/kaggle.json")):
        sys.exit("Kaggle API token not found at ~/.kaggle/kaggle.json")

    print(f"Downloading {KAGGLE_DATASET} to {out_dir} (about 5 GB)")
    ret = subprocess.run(
        ["kaggle", "datasets", "download", KAGGLE_DATASET, "-p", out_dir, "--unzip"]
    ).returncode
    if ret != 0:
        sys.exit("kaggle download failed; check the API token and the connection")
    if not os.path.exists(snapshot_path):
        sys.exit(f"Download finished but {SNAPSHOT_NAME} is not in {out_dir}")

    size_gb = os.path.getsize(snapshot_path) / 1e9
    print(f"Snapshot saved: {snapshot_path} ({size_gb:.1f} GB)")
    print("Next step: python src/processing/process_arxiv.py")
    return snapshot_path


def check(out_dir: str) -> str:
    snapshot_path = os.path.join(out_dir, SNAPSHOT_NAME)
    if not os.path.exists(snapshot_path):
        print(f"MISSING: {snapshot_path}")
        print("Run: python src/scraping/download_arxiv.py")
        sys.exit(1)
    size_gb = os.path.getsize(snapshot_path) / 1e9
    print(f"OK: {snapshot_path} ({size_gb:.1f} GB)")
    return snapshot_path


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", default=OUT_DIR,
                        help="Directory for the snapshot (default: $AA_DATA/raw/arxiv)")
    parser.add_argument("--check", action="store_true",
                        help="Only check the snapshot exists; do not download")
    parser.add_argument("--sha256", action="store_true",
                        help="Print the snapshot's SHA-256, to pin your own run")
    args = parser.parse_args()

    path = check(args.out_dir) if args.check else download(args.out_dir)
    if args.sha256:
        print(f"sha256 {sha256(path)}  {SNAPSHOT_NAME}")


if __name__ == "__main__":
    main()
