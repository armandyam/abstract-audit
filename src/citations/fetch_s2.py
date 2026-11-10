#!/usr/bin/env python3
"""Fetch citation and reference counts from Semantic Scholar by title.

For each paper in data/processed/{venue}, query the Semantic Scholar
/paper/search endpoint with the title and accept the first of the top five
results whose normalised title equals the paper's (lowercase, non-alphanumeric
characters to spaces, whitespace collapsed). Titles of fewer than three
normalised words are not queried and are recorded as unmatched.

Each row records match_type:

  title      exact normalised-title match
  unmatched  no exact match in the top five, a definitive non-match
  error      the request failed (rate limit or network); retried on re-run

The file is appended to and flushed per row, and a re-run skips every
paper_id already present except the error rows, so an interrupted fetch
resumes where it stopped. After the run a provenance sidecar
{venue}_s2.provenance.json records the retrieval date and row counts.

The order for one venue is fetch_s2.py, then fallback.py (fuzzy title and
OpenAlex, for the unmatched rows), then enrich.py (within-year percentiles).

An API key is read from the environment variable S2_API_KEY and is optional.
Semantic Scholar's API licence permits use of the data but not its
redistribution, so the resulting CSV stays local.

    python src/citations/fetch_s2.py --venue neurips
    python src/citations/fetch_s2.py --venue iclr --years 2020 2021

Writes data/per_paper/citations/{venue}_s2.csv and its provenance sidecar.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from citations._common import (  # noqa: E402
    CIT_DIR, PROCESSED_DIR, S2_FIELDNAMES, USER_AGENT,
    load_processed, normalise_title, write_provenance,
)

S2_BASE = "https://api.semanticscholar.org/graph/v1"
S2_FIELDS = "paperId,title,citationCount,referenceCount,year"
MAX_RETRIES = 5
SLEEP = 1.5   # ~0.67 req/s: /paper/search answers 429 intermittently even at
              # the nominal 1 req/s with a key, so stay under the cap.

FIELDNAMES = S2_FIELDNAMES
_ERROR = object()  # sentinel: lookup failed transiently, retry on a later run


def _headers(api_key: str | None) -> dict:
    h = {"User-Agent": USER_AGENT}
    if api_key:
        h["x-api-key"] = api_key
    return h


def _get(url: str, api_key: str | None) -> dict | None:
    """GET a JSON document. Returns {} on 400/404 (no such result), and None
    when retries are exhausted, which the caller records as an error row and
    not as a non-match.

    429 responses have their own budget of 20 short waits (Retry-After when
    the server sends one, capped at 5 s) that do not consume a normal retry.
    """
    rl_budget = 20
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            req = urllib.request.Request(url, headers=_headers(api_key))
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                if rl_budget <= 0:
                    return None
                rl_budget -= 1
                ra = e.headers.get("Retry-After") if e.headers else None
                wait = float(ra) if (ra and ra.replace(".", "", 1).isdigit()) else 1.5
                time.sleep(min(wait, 5.0))
                continue
            elif e.code in (400, 404):
                return {}
            else:
                time.sleep(1.0)
        except Exception:
            time.sleep(1.0)
        attempt += 1
    return None


def search_url(title: str, limit: int = 5) -> str:
    return (f"{S2_BASE}/paper/search?query={urllib.parse.quote(title)}"
            f"&fields={S2_FIELDS}&limit={limit}")


def match_exact(data: dict, title: str) -> dict | None:
    """The first search result whose normalised title equals the query's."""
    norm = normalise_title(title)
    for result in (data or {}).get("data", []) or []:
        if normalise_title(result.get("title") or "") == norm:
            return result
    return None


def lookup(title: str, api_key: str | None, get=_get):
    """Search Semantic Scholar by title.

    Returns the matching result dict, None for a definitive non-match, or the
    _ERROR sentinel when the request failed transiently.
    """
    if len(normalise_title(title).split()) < 3:
        return None
    data = get(search_url(title), api_key)
    if data is None:
        return _ERROR
    return match_exact(data, title)


def already_fetched_ids(out_csv: str) -> set[str]:
    """paper_ids already in the output, error rows excluded so they retry."""
    done: set[str] = set()
    if not os.path.exists(out_csv):
        return done
    with open(out_csv, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("match_type") != "error":
                done.add(row["paper_id"])
    return done


def make_row(p: dict, result) -> dict:
    if result is not None and result is not _ERROR:
        return {
            "paper_id": p["paper_id"], "venue": p.get("venue", "neurips"),
            "year": p["year"],
            "n_citations": result.get("citationCount", ""),
            "n_references": result.get("referenceCount", ""),
            "s2_paper_id": result.get("paperId", ""),
            "match_type": "title",
        }
    return {
        "paper_id": p["paper_id"], "venue": p.get("venue", "neurips"),
        "year": p["year"], "n_citations": "", "n_references": "",
        "s2_paper_id": "",
        "match_type": "error" if result is _ERROR else "unmatched",
    }


def fetch(papers: list[dict], out_csv: str, api_key: str | None,
          years: list[int] | None = None, get=_get, sleep: float = SLEEP) -> dict:
    """Fetch every paper not yet in out_csv, appending one row per paper.

    Returns {"matched": n, "unmatched": n} for this run (errors count as
    unmatched here, as upstream reported them).
    """
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    done = already_fetched_ids(out_csv)
    if years is None:
        years = sorted({p["year"] for p in papers})
    is_new = not os.path.exists(out_csv)
    total = {"matched": 0, "unmatched": 0}
    with open(out_csv, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        if is_new:
            w.writeheader()
        for year in sorted(set(years)):
            todo = [p for p in papers if p["year"] == year and p["paper_id"] not in done]
            matched = unmatched = 0
            for i, p in enumerate(todo):
                result = lookup(p["title"], api_key, get=get)
                w.writerow(make_row(p, result))
                fh.flush()
                if result is not None and result is not _ERROR:
                    matched += 1
                else:
                    unmatched += 1
                if (i + 1) % 50 == 0:
                    print(f"  [{year}] {i + 1}/{len(todo)}  matched={matched}", flush=True)
                if sleep:
                    time.sleep(sleep)
            if todo:
                print(f"  [{year}] done: {matched}/{matched + unmatched} matched", flush=True)
            total["matched"] += matched
            total["unmatched"] += unmatched
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venue", default="neurips", help="neurips, iclr or icml")
    ap.add_argument("--years", nargs="+", type=int, default=None,
                    help="years to fetch (default: every year in the corpus)")
    ap.add_argument("--processed-dir", default=None,
                    help="default: $AA_DATA/processed/{venue}")
    ap.add_argument("--out", default=None,
                    help="default: $AA_DATA/per_paper/citations/{venue}_s2.csv")
    a = ap.parse_args()

    processed = a.processed_dir or os.path.join(PROCESSED_DIR, a.venue)
    out = a.out or os.path.join(CIT_DIR, f"{a.venue}_s2.csv")
    api_key = os.environ.get("S2_API_KEY")
    papers = load_processed(processed)
    if not papers:
        sys.exit(f"no processed records in {processed}")
    print(f"  {len(papers)} {a.venue} papers, "
          f"{len(already_fetched_ids(out))} already fetched; "
          f"API key {'set' if api_key else 'not set'} (S2_API_KEY)")
    t = fetch(papers, out, api_key, a.years)
    print(f"\n  {t['matched']} matched, {t['unmatched']} not matched in this run")
    prov = write_provenance(out, "Semantic Scholar Academic Graph API",
                            f"{S2_BASE}/paper/search", "src/citations/fetch_s2.py")
    print(f"  wrote {out}\n  wrote {prov}")


if __name__ == "__main__":
    main()
