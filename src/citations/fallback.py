#!/usr/bin/env python3
"""Second linking pass for the papers fetch_s2.py left unmatched.

For each row of {venue}_s2.csv with match_type=unmatched, try in order:

  1. Semantic Scholar title search, top ten results, accepting the result
     with the highest difflib similarity ratio between normalised titles when
     that ratio is at least 0.88. match_type becomes s2_fuzzy.
  2. OpenAlex full-text search (search=, top five), accepting the first
     result with ratio at least 0.88. match_type becomes openalex, and the
     OpenAlex work id goes into the s2_paper_id column.

Rows still unmatched after both stay as they are. The CSV is rewritten in
place with its original columns, so run enrich.py afterwards: a recovered row
has no percentile until it is re-enriched.

The upstream project ran this pass once, for NeurIPS, before the 2026-05-11
snapshot: it recovered 385 papers by fuzzy title and 266 by OpenAlex, 2.1
percent of the 30,595 NeurIPS papers. ICLR and ICML were not passed through
it, and their published counts are exact-title matches only.

The Semantic Scholar key is read from S2_API_KEY; an OpenAlex polite-pool
address from OPENALEX_MAILTO. Both are optional.

    python src/citations/fallback.py --venue neurips
    python src/citations/fallback.py --venue neurips --dry-run
"""
from __future__ import annotations

import argparse
import csv
import difflib
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
    load_processed, normalise_title, update_provenance,
)

S2_BASE = "https://api.semanticscholar.org/graph/v1"
S2_FIELDS = "paperId,title,citationCount,referenceCount,year"
OA_BASE = "https://api.openalex.org/works"
MAX_RETRIES = 4
THRESHOLD = 0.88
SLEEP_S2 = 1.05
SLEEP_OA = 0.12


def ratio(a: str, b: str) -> float:
    """difflib similarity of the two normalised titles, in [0, 1]."""
    return difflib.SequenceMatcher(None, normalise_title(a), normalise_title(b)).ratio()


def _get(url: str, headers: dict | None = None) -> dict:
    """GET a JSON document; {} on any HTTP error other than 429 and after the
    last retry."""
    h = {"User-Agent": USER_AGENT, **(headers or {})}
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** (attempt + 2))
            else:
                return {}
        except Exception:
            time.sleep(2 ** attempt)
    return {}


def best_fuzzy(results: list[dict], title: str, threshold: float = THRESHOLD) -> dict | None:
    """The result with the highest ratio, if that ratio reaches threshold.
    The first of equally good results wins."""
    best_r, best = 0.0, None
    for result in results or []:
        r = ratio(title, result.get("title") or "")
        if r > best_r:
            best_r, best = r, result
    return best if best_r >= threshold else None


def first_fuzzy(results: list[dict], title: str, threshold: float = THRESHOLD) -> dict | None:
    """The first result whose ratio reaches threshold (OpenAlex order)."""
    for result in results or []:
        if ratio(title, result.get("title") or "") >= threshold:
            return result
    return None


def lookup_s2_fuzzy(title: str, api_key: str | None, threshold: float = THRESHOLD,
                    get=_get) -> dict | None:
    if len(normalise_title(title).split()) < 3:
        return None
    url = (f"{S2_BASE}/paper/search?query={urllib.parse.quote(title)}"
           f"&fields={S2_FIELDS}&limit=10")
    data = get(url, {"x-api-key": api_key} if api_key else {})
    return best_fuzzy(data.get("data", []), title, threshold)


def openalex_url(title: str, mailto: str | None = None) -> str:
    url = (f"{OA_BASE}?search={urllib.parse.quote(title)}"
           f"&select=id,title,cited_by_count,referenced_works_count&per-page=5")
    if mailto:
        url += f"&mailto={urllib.parse.quote(mailto)}"
    return url


def lookup_openalex(title: str, threshold: float = THRESHOLD, mailto: str | None = None,
                    get=_get) -> dict | None:
    work = first_fuzzy(get(openalex_url(title, mailto)).get("results", []), title, threshold)
    if work is None:
        return None
    return {"oa_id": work.get("id", ""),
            "citationCount": work.get("cited_by_count", ""),
            "referenceCount": work.get("referenced_works_count", "")}


def recover(row: dict, title: str, api_key: str | None, threshold: float = THRESHOLD,
            mailto: str | None = None, get=_get, sleep: bool = True) -> dict | None:
    """A replacement for one unmatched row, or None if both sources fail."""
    result = lookup_s2_fuzzy(title, api_key, threshold, get=get)
    if sleep:
        time.sleep(SLEEP_S2)
    if result:
        return {**row,
                "n_citations": result.get("citationCount", ""),
                "n_references": result.get("referenceCount", ""),
                "s2_paper_id": result.get("paperId", ""),
                "match_type": "s2_fuzzy"}
    oa = lookup_openalex(title, threshold, mailto, get=get)
    if sleep:
        time.sleep(SLEEP_OA)
    if oa:
        return {**row,
                "n_citations": oa.get("citationCount", ""),
                "n_references": oa.get("referenceCount", ""),
                "s2_paper_id": oa.get("oa_id", ""),
                "match_type": "openalex"}
    return None


def run(rows: list[dict], titles: dict[str, str], api_key: str | None,
        threshold: float = THRESHOLD, mailto: str | None = None,
        get=_get, sleep: bool = True) -> tuple[list[dict], dict]:
    """Return the rows with recovered matches replaced, and the counts."""
    out = list(rows)
    counts = {"unmatched_before": 0, "s2_fuzzy": 0, "openalex": 0, "no_title": 0}
    for i, r in enumerate(rows):
        if r.get("match_type") != "unmatched":
            continue
        counts["unmatched_before"] += 1
        title = titles.get(r["paper_id"], "")
        if not title:
            counts["no_title"] += 1
            continue
        new = recover(r, title, api_key, threshold, mailto, get=get, sleep=sleep)
        if new:
            # clear any enrichment of the old row; enrich.py recomputes it
            for k in ("citation_percentile", "mncs"):
                if k in new:
                    new[k] = ""
            out[i] = new
            counts[new["match_type"]] += 1
    return out, counts


def load_csv(path: str) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        return list(rd.fieldnames or S2_FIELDNAMES), list(rd)


def save_csv(path: str, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, restval="")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venue", default="neurips")
    ap.add_argument("--csv", default=None,
                    help="default: $AA_DATA/per_paper/citations/{venue}_s2.csv")
    ap.add_argument("--processed-dir", default=None,
                    help="default: $AA_DATA/processed/{venue}")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    path = a.csv or os.path.join(CIT_DIR, f"{a.venue}_s2.csv")
    if not os.path.exists(path):
        sys.exit(f"missing input: {path} (run fetch_s2.py first)")
    fields, rows = load_csv(path)
    titles = {p["paper_id"]: p.get("title", "")
              for p in load_processed(a.processed_dir or os.path.join(PROCESSED_DIR, a.venue))}
    new_rows, counts = run(rows, titles, os.environ.get("S2_API_KEY"), a.threshold,
                           os.environ.get("OPENALEX_MAILTO"))
    print(f"  {counts['unmatched_before']} unmatched; recovered "
          f"{counts['s2_fuzzy']} by S2 fuzzy title, {counts['openalex']} by OpenAlex; "
          f"{counts['no_title']} without a title")
    if a.dry_run:
        print("  dry run, nothing written")
        return
    save_csv(path, fields, new_rows)
    update_provenance(path, "fallback", {
        "script": "src/citations/fallback.py", "threshold": a.threshold,
        "sources": [f"{S2_BASE}/paper/search", OA_BASE], **counts})
    print(f"  rewrote {path}; run enrich.py next")


if __name__ == "__main__":
    main()
