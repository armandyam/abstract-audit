#!/usr/bin/env python3
"""
Scrape ICML 2013-2016 proceedings from PMLR (proceedings.mlr.press), the years
for which the icml.cc download form is unavailable.

PMLR hosts every ICML from 2013 onward as a numbered volume. Each volume index
lists title, authors, and an "abs" link; each per-paper page carries the
abstract in a <div class="abstract">.

Writes data/raw/icml/icml_{year}_pmlr.json, one record per paper in volume
index order: {paper_id, year, title, authors, abs_url, abstract}.
src/processing/process_icml.py turns it into the canonical processed file.

Resumable: the raw file is rewritten every 50 new abstracts and at the end.
A rerun reads it, reuses every record that already has an abstract, fetches
only the missing ones, and rewrites the whole file in index order. A
completed rerun leaves the file unchanged, and a failed index fetch leaves it
untouched.

Usage:
  python src/scraping/scrape_icml_pmlr.py --years 2013 2014 2015 2016
  python src/scraping/scrape_icml_pmlr.py --years 2016 --limit 5   # quick test
"""

from __future__ import annotations
import argparse
import html
import json
import os
import re
import time
import urllib.request

# PMLR volume number for each ICML year.
ICML_VOLUME = {
    2013: 28, 2014: 32, 2015: 37, 2016: 48, 2017: 70, 2018: 80,
    2019: 97, 2020: 119, 2021: 139, 2022: 162, 2023: 202, 2024: 235,
}

BASE = "https://proceedings.mlr.press"
UA = {"User-Agent": "Mozilla/5.0 (research; abstract-audit)"}

PAPER_RE = re.compile(r'<div class="paper">(.*?)</div>', re.S)
TITLE_RE = re.compile(r'<p class="title">(.*?)</p>', re.S)
AUTHORS_RE = re.compile(r'<span class="authors">(.*?)</span>', re.S)
ABSLINK_RE = re.compile(r'href="([^"]+?\.html)"[^>]*>abs</a>')
ABSTRACT_RE = re.compile(r'<div[^>]*class="abstract"[^>]*>(.*?)</div>', re.S)


def _get(url: str, retries: int = 4) -> str:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            time.sleep(2 ** attempt)
    return ""


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)          # strip any inner tags
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_index(html_text: str) -> list[dict]:
    """Volume index -> [{title, authors, abs_url}] in page order."""
    papers = []
    for block in PAPER_RE.findall(html_text):
        t = TITLE_RE.search(block)
        a = AUTHORS_RE.search(block)
        link = ABSLINK_RE.search(block)
        if not t or not link:
            continue
        authors_raw = _clean(a.group(1)) if a else ""
        authors = [x.strip() for x in authors_raw.split(",") if x.strip()]
        url = link.group(1)
        if url.startswith("/"):
            url = BASE + url
        papers.append({"title": _clean(t.group(1)), "authors": authors, "abs_url": url})
    return papers


def parse_abstract(page_html: str) -> str:
    m = ABSTRACT_RE.search(page_html)
    return _clean(m.group(1)) if m else ""


def paper_id(year: int, abs_url: str) -> str:
    key = re.sub(r".*/v\d+/(.+)\.html", r"\1", abs_url)
    return f"{year}_pmlr_{key}"


def load_raw(path: str) -> dict[str, dict]:
    """Existing raw records with a non-empty abstract, keyed by paper_id."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return {r["paper_id"]: r for r in json.load(fh) if (r.get("abstract") or "").strip()}


CHECKPOINT = 50   # rewrite the raw file after this many new abstracts


def merge(year: int, index: list[dict], cached: dict[str, dict], fetch,
          checkpoint=None) -> tuple[list[dict], int]:
    """One raw record per index entry, in index order.

    Records in `cached` are reused unchanged; the rest call fetch(abs_url) for
    the abstract. Every CHECKPOINT fetches, checkpoint(records) receives the
    complete records so far plus the cached ones still ahead, so an
    interrupted run keeps its progress. Returns (records, n_fetched).
    """
    records, fetched = [], 0
    for i, p in enumerate(index):
        pid = paper_id(year, p["abs_url"])
        if pid in cached:
            records.append(cached[pid])
            continue
        records.append({"paper_id": pid, "year": year, "title": p["title"],
                        "authors": p["authors"], "abs_url": p["abs_url"],
                        "abstract": fetch(p["abs_url"])})
        fetched += 1
        if fetched % CHECKPOINT == 0:
            print(f"    [{year}] fetched {fetched} abstracts ...", flush=True)
            if checkpoint:
                ahead = [cached[q] for q in (paper_id(year, x["abs_url"]) for x in index[i + 1:])
                         if q in cached]
                checkpoint(records + ahead)
    return records, fetched


def scrape_year(year: int, raw_dir: str, delay: float, limit: int | None) -> int:
    vol = ICML_VOLUME.get(year)
    if vol is None:
        print(f"  [ICML {year}] no PMLR volume mapped, skipping")
        return 0
    os.makedirs(raw_dir, exist_ok=True)
    path = os.path.join(raw_dir, f"icml_{year}_pmlr.json")

    cached = load_raw(path)
    index = parse_index(_get(f"{BASE}/v{vol}/"))
    if not index:
        # A failed or changed index page must not overwrite cached records.
        raise SystemExit(f"  [ICML {year}] v{vol}: no papers parsed from the index; "
                         f"{path} left unchanged")
    if limit:
        index = index[:limit]
    print(f"  [ICML {year}] v{vol}: {len(index)} papers in index "
          f"({len(cached)} already have an abstract)")

    def fetch(url: str) -> str:
        abstract = parse_abstract(_get(url))
        time.sleep(delay)
        return abstract

    def save(records: list[dict]) -> None:
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(records, fh, ensure_ascii=False)
        os.replace(tmp, path)

    records, _ = merge(year, index, cached, fetch, checkpoint=save)
    save(records)

    n_abs = sum(1 for r in records if r["abstract"].strip())
    print(f"  [ICML {year}] wrote {len(records)} papers, "
          f"{n_abs} with abstract ({100 * n_abs // max(len(records), 1)}%) -> {path}")
    return len(records)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=[2013, 2014, 2015, 2016])
    ap.add_argument("--raw-dir", default="data/raw/icml")
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--limit", type=int, default=None, help="cap papers per year (testing)")
    args = ap.parse_args()

    total = 0
    for y in args.years:
        total += scrape_year(y, args.raw_dir, args.delay, args.limit)
    print(f"ICML PMLR total: {total} papers")


if __name__ == "__main__":
    main()
