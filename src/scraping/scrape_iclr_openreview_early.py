#!/usr/bin/env python3
"""
Scrape ICLR 2013 from the OpenReview v1 API into data/raw/iclr/.

2013 predates the Blind_Submission model the main scrape_iclr.py uses; its
notes live under the `/-/submission` invitation and carry the abstract,
author list, and a decision field. Only CONFERENCE-TRACK ACCEPTED papers are
kept (decision ends in "-conference"), so the cohort matches the
accepted-papers populations of every other ICLR year. Workshop-track papers
and rejects are excluded.

ICLR 2014 is NOT handled here: its OpenReview notes carry no decisions
("submitted, no decision"), so 2014 is scraped from the archived
conference-proceedings page by scrape_iclr_arxiv.py instead.

OpenReview answers anonymous API requests with a challenge page (HTTP 403),
so the scraper logs in with credentials from the environment, which are never
written anywhere: OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD.

Writes data/raw/iclr/iclr_{year}_openreview.json, one record per accepted
paper: {paper_id, venue, year, title, abstract, authors, decision}.
src/processing/process_iclr.py turns it into the canonical processed file.

Usage:
  python src/scraping/scrape_iclr_openreview_early.py --years 2013
"""

from __future__ import annotations
import argparse
import json
import os
import urllib.parse
import urllib.request

BASE = "https://api.openreview.net"
UA = {"User-Agent": "Mozilla/5.0 (research; abstract-audit)"}


def auth_headers() -> dict:
    """Request headers, with a bearer token when credentials are set."""
    user = os.environ.get("OPENREVIEW_USERNAME")
    password = os.environ.get("OPENREVIEW_PASSWORD")
    if not user or not password:
        return dict(UA)
    body = json.dumps({"id": user, "password": password}).encode()
    req = urllib.request.Request(f"{BASE}/login", data=body, method="POST",
                                 headers={**UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return {**UA, "Authorization": f"Bearer {json.loads(r.read())['token']}"}


def fetch_notes(year: int) -> list[dict]:
    inv = f"ICLR.cc/{year}/conference/-/submission"
    url = f"{BASE}/notes?" + urllib.parse.urlencode({"invitation": inv, "limit": 1000})
    req = urllib.request.Request(url, headers=auth_headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("notes", [])


def _authors(content: dict) -> list[str]:
    a = content.get("authors", [])
    if isinstance(a, str):
        a = [x.strip() for x in a.split(",")]
    return [str(x).strip() for x in a if str(x).strip()]


def notes_to_records(notes: list[dict], year: int) -> tuple[list[dict], int]:
    """Keep conference-track accepts with a title and an abstract.

    Returns (records, n_dropped).
    """
    records, dropped = [], 0
    for n in notes:
        c = n.get("content", {}) or {}
        title = str(c.get("title", "")).strip()
        abstract = str(c.get("abstract", "")).strip()
        decision = str(c.get("decision", "")).strip()
        # Conference-track accepts only (e.g. "conferenceOral-iclr2013-conference").
        if not decision.endswith("-conference"):
            dropped += 1
            continue
        if not title or len(abstract) < 20:
            dropped += 1
            continue
        records.append({
            "paper_id": f"{year}_openreview_{n.get('id', '')}",
            "venue": "iclr", "year": year,
            "title": title, "abstract": abstract, "authors": _authors(c),
            "decision": c.get("decision", ""),
        })
    return records, dropped


def scrape_year(year: int, raw_dir: str) -> int:
    os.makedirs(raw_dir, exist_ok=True)
    records, dropped = notes_to_records(fetch_notes(year), year)
    path = os.path.join(raw_dir, f"iclr_{year}_openreview.json")
    if not records:
        raise SystemExit(f"  [ICLR {year}] no accepted papers returned; {path} left unchanged")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False)
    print(f"  [ICLR {year}] {len(records)} papers kept, {dropped} dropped "
          f"(not a conference accept, or no/short abstract) -> {path}")
    return len(records)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=[2013])
    ap.add_argument("--raw-dir", default="data/raw/iclr")
    args = ap.parse_args()
    total = sum(scrape_year(y, args.raw_dir) for y in args.years)
    print(f"ICLR OpenReview early total: {total} papers")


if __name__ == "__main__":
    main()
