"""Shared paths and helpers for the citation fetchers and analyses.

The citation counts come from third-party services (Semantic Scholar and
OpenAlex) and are not redistributed with this repository. Every fetcher
writes its CSV under data/per_paper/citations/ and, next to it, a provenance
sidecar `{name}.provenance.json` that records when and from where the rows
were retrieved. The analyses read those CSVs and write their outputs under
data/aggregate/citations/.

The data root is the AA_DATA environment variable, default `data`, as for
every other stage of the pipeline.
"""
from __future__ import annotations

import csv
import datetime as _dt
import glob
import json
import os
import re
import sys
from collections import Counter

D = os.environ.get("AA_DATA", "data")
CIT_DIR = os.path.join(D, "per_paper", "citations")
READ_DIR = os.path.join(D, "per_paper", "readability")
PROCESSED_DIR = os.path.join(D, "processed")
OUT_DIR = os.path.join(D, "aggregate", "citations")
JUDGE_DIR = os.environ.get("AA_JUDGE", "shared/judge_scores")

VENUES = ["neurips", "iclr", "icml"]

# A generic client name. No contact details go into requests.
USER_AGENT = "Mozilla/5.0 (research; abstract-audit)"

# Columns of {venue}_s2.csv as the fetcher writes it. enrich.py appends
# citation_percentile and mncs.
S2_FIELDNAMES = ["paper_id", "venue", "year", "n_citations",
                 "n_references", "s2_paper_id", "match_type"]
OPENALEX_FIELDNAMES = ["paper_id", "venue", "year", "n_citations",
                       "n_references", "openalex_id", "match_type"]


def normalise_title(title: str) -> str:
    """Lowercase, replace every character outside [a-z0-9 whitespace] with a
    space, collapse whitespace. Two titles match exactly when their normalised
    forms are equal."""
    t = (title or "").lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def load_processed(processed_dir: str) -> list[dict]:
    """Every record of every *.json file in one venue's processed directory."""
    papers: list[dict] = []
    for path in sorted(glob.glob(os.path.join(processed_dir, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            papers.extend(json.load(fh))
    return papers


def s2_csv(venue: str, cit_dir: str | None = None) -> str:
    return os.path.join(cit_dir or CIT_DIR, f"{venue}_s2.csv")


def require(path: str) -> str:
    """Return path if it exists; otherwise exit with a message naming it.

    The analyses need every requested venue's file. A missing one is an
    error to report, not a venue to drop silently from a pooled estimate.
    """
    if not os.path.exists(path):
        sys.exit(f"missing input: {path}")
    return path


def one_row_per_paper(rows: list[dict]) -> list[dict]:
    """Collapse repeated paper_id rows to one, in first-seen order.

    A fetch appends a fresh row when it retries an error row, so a paper can
    appear twice until the file is compacted. The last row that is not an
    error wins; a paper with only error rows keeps its last one.
    """
    order: list[str] = []
    best: dict[str, dict] = {}
    for r in rows:
        pid = r["paper_id"]
        if pid not in best:
            order.append(pid)
            best[pid] = r
        elif r.get("match_type") != "error" or best[pid].get("match_type") == "error":
            best[pid] = r
    return [best[pid] for pid in order]


def duplicated_ids(ids) -> list[str]:
    seen, dup = set(), []
    for pid in ids:
        if pid in seen:
            dup.append(pid)
        seen.add(pid)
    return dup


def require_unique(ids, path: str) -> None:
    """Exit if a citation CSV holds more than one row for a paper. Coverage,
    percentiles and every analysis assume one row per paper."""
    dup = duplicated_ids(ids)
    if dup:
        sys.exit(f"{path}: {len(dup)} repeated paper_id rows (first: {dup[0]}). "
                 "Run fetch_s2.py on it once more, which compacts the file to "
                 "one row per paper.")


def read_citations(path: str, usecols: list[str] | None = None, **kw):
    """A {venue}_s2.csv as a DataFrame, after checking it has one row per
    paper_id."""
    import pandas as pd
    cols = None if usecols is None else list(dict.fromkeys(["paper_id", *usecols]))
    df = pd.read_csv(require(path), usecols=cols, **kw)
    require_unique(df["paper_id"].astype(str), path)
    return df if usecols is None else df[usecols]


def provenance_path(csv_path: str) -> str:
    return os.path.splitext(csv_path)[0] + ".provenance.json"


def write_provenance(csv_path: str, source: str, endpoint: str,
                     script: str, extra: dict | None = None,
                     today: _dt.date | None = None) -> str:
    """Write the sidecar `{csv}.provenance.json` for a fetched CSV.

    Records the retrieval date (UTC), the source and endpoint, the script,
    the number of data rows, and the count of each match_type. On a resumed
    fetch the date is that of the latest run, which is the latest date any
    row in the file can have been retrieved.
    """
    rows = 0
    match = Counter()
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                rows += 1
                match[row.get("match_type", "")] += 1
    rec = {
        "file": os.path.basename(csv_path),
        "source": source,
        "endpoint": endpoint,
        "script": script,
        "retrieved": (today or _dt.datetime.now(_dt.timezone.utc).date()).isoformat(),
        "n_rows": rows,
        "match_type": dict(sorted(match.items())),
    }
    if extra:
        rec.update(extra)
    out = provenance_path(csv_path)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2)
        fh.write("\n")
    return out


def update_provenance(csv_path: str, key: str, value: dict,
                      today: _dt.date | None = None) -> str:
    """Add a later step (the fallback pass) to an existing sidecar.

    Keeps the original retrieval record, stores `value` under `key` with its
    own retrieval date, and recounts n_rows and match_type from the CSV as it
    now stands.
    """
    out = provenance_path(csv_path)
    rec: dict = {}
    if os.path.exists(out):
        with open(out, encoding="utf-8") as fh:
            rec = json.load(fh)
    rows = 0
    match = Counter()
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows += 1
            match[row.get("match_type", "")] += 1
    rec.setdefault("file", os.path.basename(csv_path))
    rec["n_rows"] = rows
    rec["match_type"] = dict(sorted(match.items()))
    rec[key] = {"retrieved": (today or _dt.datetime.now(_dt.timezone.utc).date()).isoformat(),
                **value}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2)
        fh.write("\n")
    return out
