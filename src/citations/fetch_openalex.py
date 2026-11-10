#!/usr/bin/env python3
"""Fetch citation and reference counts from OpenAlex by title.

For each paper in data/processed/{venue}, query OpenAlex /works with a
title.search filter and accept the first of the top five results whose
normalised title equals the paper's. The year is not used to filter:
conference papers are often indexed under their preprint year. Commas are
removed from the query, because OpenAlex reads a comma inside a filter value
as a filter separator, which would make every comma-containing title
unmatchable. Titles of fewer than three normalised words are not queried.

The published analyses read the Semantic Scholar counts (fetch_s2.py), not
these. This fetcher is kept as the independent second source the upstream
project used to cross-check Semantic Scholar. OpenAlex data is CC0.

Each row records match_type:

  title      exact normalised-title match
  unmatched  the search succeeded and no exact match is in the top five
  error      the request failed (network, timeout, HTTP 5xx, or 429 after
             every retry); retried on re-run

A 400 or 404 answer is a definitive empty result. Every other failure is
retried with backoff within the run, and if it still fails the paper gets an
error row, never an unmatched one.

Rows are appended and flushed one at a time, to the merged file and to one
file per year. A re-run skips every paper_id that has a non-error row in
either, and retries the rest. At the start and end of every run both files
are compacted to one row per paper_id (the last non-error row wins), so a
retried paper is never counted twice.
After the run a provenance sidecar records the retrieval date and row counts.

OpenAlex needs no key. An address for its polite pool may be given in the
environment variable OPENALEX_MAILTO; nothing is sent otherwise.

    python src/citations/fetch_openalex.py --venue iclr

Writes data/per_paper/citations/{venue}_openalex.csv,
       data/per_paper/citations/openalex/{venue}_{year}.csv,
       and the provenance sidecar of the merged file.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from citations._common import (  # noqa: E402
    CIT_DIR, OPENALEX_FIELDNAMES, PROCESSED_DIR, USER_AGENT,
    load_processed, normalise_title, one_row_per_paper, write_provenance,
)

OPENALEX_BASE = "https://api.openalex.org"
SLEEP = 0.15    # ~6 req/s
MAX_RETRIES = 5
FIELDNAMES = OPENALEX_FIELDNAMES
_ERROR = object()  # sentinel: lookup failed transiently, retry on a later run


def works_url(params: dict, mailto: str | None = None) -> str:
    params = dict(params)
    if mailto:
        params["mailto"] = mailto
    return f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


def _get(url: str) -> dict | None:
    """GET a JSON document.

    Returns {} on 400/404, which OpenAlex answers for a query it cannot
    satisfy: a definitive empty result. Returns None when every retry failed
    (network error, timeout, an unreadable body, HTTP 429 or 5xx), which the
    caller records as an error row and not as a non-match.
    """
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return {}
            time.sleep(2 ** (attempt + 1))
        except Exception:
            time.sleep(2 ** attempt)
    return None


def query_params(title: str) -> dict:
    return {
        "filter": f"title.search:{title.replace(',', ' ')}",
        "select": "id,title,cited_by_count,referenced_works_count",
        "per-page": "5",
    }


def match_exact(data: dict, title: str) -> dict | None:
    norm = normalise_title(title)
    for r in (data or {}).get("results", []) or []:
        if normalise_title(r.get("title") or "") == norm:
            return r
    return None


def lookup(title: str, mailto: str | None = None, get=_get):
    """The matching work, None for a definitive non-match, or the _ERROR
    sentinel when the request failed."""
    if len(normalise_title(title).split()) < 3:
        return None
    data = get(works_url(query_params(title), mailto))
    if data is None:
        return _ERROR
    return match_exact(data, title)


def _paths(out_merged: str, out_dir_yearly: str, venue: str) -> list[str]:
    return [out_merged] + sorted(glob.glob(os.path.join(out_dir_yearly, f"{venue}_*.csv")))


def already_fetched_ids(out_merged: str, out_dir_yearly: str, venue: str) -> set[str]:
    """paper_ids with a non-error row in the merged or a yearly file."""
    done: set[str] = set()
    for path in _paths(out_merged, out_dir_yearly, venue):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("match_type") != "error":
                    done.add(row["paper_id"])
    return done


def compact(path: str) -> int:
    """Rewrite one output file with one row per paper_id, through a
    temporary file. Returns the rows removed."""
    if not os.path.exists(path):
        return 0
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        fields = list(rd.fieldnames or FIELDNAMES)
        rows = list(rd)
    kept = one_row_per_paper(rows)
    if len(kept) == len(rows):
        return 0
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, restval="", extrasaction="ignore")
        w.writeheader()
        w.writerows(kept)
    os.replace(tmp, path)
    return len(rows) - len(kept)


def make_row(p: dict, result) -> dict:
    if result is _ERROR:
        return {"paper_id": p["paper_id"], "venue": p.get("venue", "neurips"),
                "year": p["year"], "n_citations": "", "n_references": "",
                "openalex_id": "", "match_type": "error"}
    if result:
        return {
            "paper_id": p["paper_id"], "venue": p.get("venue", "neurips"),
            "year": p["year"],
            "n_citations": result.get("cited_by_count", ""),
            "n_references": result.get("referenced_works_count", ""),
            "openalex_id": result.get("id", ""),
            "match_type": "title",
        }
    return {"paper_id": p["paper_id"], "venue": p.get("venue", "neurips"),
            "year": p["year"], "n_citations": "", "n_references": "",
            "openalex_id": "", "match_type": "unmatched"}


def _writer(path: str):
    is_new = not os.path.exists(path)
    fh = open(path, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(fh, fieldnames=FIELDNAMES)
    if is_new:
        w.writeheader()
    return fh, w


def fetch(papers: list[dict], venue: str, out_merged: str, out_dir_yearly: str,
          years: list[int] | None = None, mailto: str | None = None,
          get=_get, sleep: float = SLEEP) -> dict:
    os.makedirs(out_dir_yearly, exist_ok=True)
    os.makedirs(os.path.dirname(out_merged) or ".", exist_ok=True)
    for path in _paths(out_merged, out_dir_yearly, venue):
        compact(path)
    done = already_fetched_ids(out_merged, out_dir_yearly, venue)
    if years is None:
        years = sorted({p["year"] for p in papers})
    total = {"matched": 0, "unmatched": 0, "error": 0}
    mfh, mw = _writer(out_merged)
    try:
        for year in sorted(set(years)):
            todo = [p for p in papers if p["year"] == year and p["paper_id"] not in done]
            yfh, yw = _writer(os.path.join(out_dir_yearly, f"{venue}_{year}.csv"))
            try:
                for p in todo:
                    result = lookup(p["title"], mailto, get=get)
                    row = make_row(p, result)
                    yw.writerow(row); yfh.flush()
                    mw.writerow(row); mfh.flush()
                    total["error" if result is _ERROR
                          else "matched" if result else "unmatched"] += 1
                    if sleep:
                        time.sleep(sleep)
            finally:
                yfh.close()
    finally:
        mfh.close()
    for path in _paths(out_merged, out_dir_yearly, venue):
        compact(path)
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venue", default="neurips", help="neurips, iclr or icml")
    ap.add_argument("--years", nargs="+", type=int, default=None)
    ap.add_argument("--processed-dir", default=None,
                    help="default: $AA_DATA/processed/{venue}")
    ap.add_argument("--out", default=None,
                    help="default: $AA_DATA/per_paper/citations/{venue}_openalex.csv")
    ap.add_argument("--out-dir-yearly", default=None,
                    help="default: $AA_DATA/per_paper/citations/openalex")
    a = ap.parse_args()

    processed = a.processed_dir or os.path.join(PROCESSED_DIR, a.venue)
    out = a.out or os.path.join(CIT_DIR, f"{a.venue}_openalex.csv")
    yearly = a.out_dir_yearly or os.path.join(CIT_DIR, "openalex")
    papers = load_processed(processed)
    if not papers:
        sys.exit(f"no processed records in {processed}")
    t = fetch(papers, a.venue, out, yearly, a.years,
              mailto=os.environ.get("OPENALEX_MAILTO"))
    print(f"  {t['matched']} matched, {t['unmatched']} not matched, "
          f"{t['error']} failed (retried on the next run) in this run")
    prov = write_provenance(out, "OpenAlex", f"{OPENALEX_BASE}/works",
                            "src/citations/fetch_openalex.py")
    print(f"  wrote {out}\n  wrote {prov}")


if __name__ == "__main__":
    main()
