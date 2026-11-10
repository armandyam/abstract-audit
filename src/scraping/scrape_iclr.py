#!/usr/bin/env python3
"""
Download ICLR 2026 accepted papers from the OpenReview API (v2).

ICLR 2017-2025 come from the ICLR dataset instead (fetch_iclr_dataset.py),
which is how the published values were computed. 2026 postdates that
dataset, so it is scraped here. Only accepted papers are publicly listed
under the venue id in API v2, and each carries its track (Poster, Oral,
Spotlight) in the venue label.

Saves: data/raw/iclr/iclr_{year}_data.json, the same record shape as the
dataset years:
  {year, id, title, abstract, authors (comma-sep str), author_ids (comma-sep str),
   decision, scores (list[int]), keywords (list[str]), labels (str)}

OpenReview answers anonymous API requests with a challenge page (HTTP 403),
so the scraper logs in. Credentials come from the environment and are never
written anywhere:

  export OPENREVIEW_USERNAME=...   # the e-mail of an OpenReview account
  export OPENREVIEW_PASSWORD=...

Requires: pip install requests   (see requirements-scrape.txt)

Usage:
  python src/scraping/scrape_iclr.py
  python src/scraping/scrape_iclr.py --start 2026 --end 2026
"""

import argparse
import json
import os
import time

try:
    import requests
except ImportError:
    import sys; sys.exit("pip install requests")

OR_API_V2 = "https://api2.openreview.net"
HEADERS  = {"User-Agent": "Mozilla/5.0 (research; abstract-audit)"}

# OpenReview venue ids for the years this scraper covers.
VENUE_IDS = {
    2026: "ICLR.cc/2026/Conference",
}


def auth_headers() -> dict:
    """Request headers, with a bearer token when credentials are set."""
    user = os.environ.get("OPENREVIEW_USERNAME")
    password = os.environ.get("OPENREVIEW_PASSWORD")
    if not user or not password:
        return dict(HEADERS)
    r = requests.post(f"{OR_API_V2}/login", json={"id": user, "password": password},
                      headers=HEADERS, timeout=30)
    r.raise_for_status()
    return {**HEADERS, "Authorization": f"Bearer {r.json()['token']}"}


def fetch_notes(venue_id: str, headers: dict, offset: int = 0,
                limit: int = 1000) -> list[dict]:
    params = {
        "content.venueid": venue_id,
        "details":         "replyCount",
        "limit":           limit,
        "offset":          offset,
    }
    r = requests.get(f"{OR_API_V2}/notes", params=params, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json().get("notes", [])


def fetch_all_notes(venue_id: str, headers: dict) -> list[dict]:
    """Page through all notes for a venue."""
    all_notes = []
    offset = 0
    limit  = 1000
    while True:
        batch = fetch_notes(venue_id, headers, offset, limit)
        all_notes.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
        time.sleep(0.5)
    return all_notes


def note_to_record(note: dict, year: int) -> dict:
    content = note.get("content", {})

    # Decision: may be in content directly or in a separate meta-review note
    decision = content.get("decision", "")
    if isinstance(decision, dict):           # newer OR format wraps in {value: ...}
        decision = decision.get("value", "")

    # Scores: reviewer ratings
    scores = []
    rating = content.get("rating") or content.get("score") or []
    if isinstance(rating, list):
        scores = [int(s) for s in rating if str(s).lstrip("-").isdigit()]
    elif isinstance(rating, (int, float)):
        scores = [int(rating)]

    def _val(field):
        v = content.get(field, "")
        return v.get("value", v) if isinstance(v, dict) else v

    authors    = _val("authors")
    author_ids = _val("authorids")

    return {
        "year":       year,
        "id":         note.get("id", ""),
        "title":      _val("title"),
        "abstract":   _val("abstract"),
        "authors":    ", ".join(authors) if isinstance(authors, list) else str(authors),
        "author_ids": ", ".join(author_ids) if isinstance(author_ids, list) else str(author_ids),
        "decision":   decision,
        "scores":     scores,
        "keywords":   _val("keywords") if isinstance(_val("keywords"), list) else [],
        "labels":     _val("venue"),
    }


def download_year(year: int, out_dir: str) -> int:
    venue_id = VENUE_IDS.get(year)
    if not venue_id:
        print(f"  [ICLR {year}] no venue id configured, skipping "
              f"(2017-2025: use fetch_iclr_dataset.py)")
        return 0

    print(f"  [ICLR {year}] fetching from {venue_id} (API v2) ...")
    try:
        notes = fetch_all_notes(venue_id, auth_headers())
    except Exception as e:
        print(f"  [ICLR {year}] API error: {e}")
        if "403" in str(e) and "OPENREVIEW_USERNAME" not in os.environ:
            print("  OpenReview refuses anonymous requests; set OPENREVIEW_USERNAME "
                  "and OPENREVIEW_PASSWORD")
        return 0

    records = [note_to_record(n, year) for n in notes if n.get("content")]
    records = [r for r in records if r["title"]]   # drop empty
    if not records:
        print(f"  [ICLR {year}] no papers returned; raw file left unchanged")
        return 0

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"iclr_{year}_data.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False)
    print(f"  [ICLR {year}] {len(records)} papers -> {path}")
    return len(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   type=int, default=2026)
    parser.add_argument("--end",     type=int, default=2026)
    parser.add_argument("--raw-dir", default="data/raw/iclr")
    args = parser.parse_args()

    total = 0
    for year in range(args.start, args.end + 1):
        total += download_year(year, args.raw_dir)
        time.sleep(1)
    print(f"ICLR total: {total} papers")


if __name__ == "__main__":
    main()
