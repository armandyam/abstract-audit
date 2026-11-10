#!/usr/bin/env python3
"""
Scrape ICLR 2014, 2015, and 2016 from the archived iclr.cc accepted lists.

Those years predate structured OpenReview decisions; the archived accepted
pages link each paper to its arXiv record. We extract the arXiv ids and pull
the canonical title, abstract, and authors from the arXiv API. Papers without
an arXiv link (or whose id the API does not resolve) have no retrievable
abstract and are skipped.

The oral papers on the 2015 page are listed twice (once in the orals section,
once in the full list); ids are deduplicated. One paper (1411.7676) appears
on both the 2015 and 2016 accepted lists; it was accepted in 2016, so the
2015 instance is excluded.

Writes data/raw/iclr/iclr_{year}_arxiv.json, one record per resolved paper:
{paper_id, venue, year, title, abstract, authors, arxiv_id}.
src/processing/process_iclr.py turns it into the canonical processed file.

Usage:
  python src/scraping/scrape_iclr_arxiv.py --years 2014 2015 2016
"""

from __future__ import annotations
import argparse
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request

URLS = {
    2014: "https://iclr.cc/archive/2014/conference-proceedings/",
    2015: "https://iclr.cc/archive/www/doku.php%3Fid=iclr2015:accepted-main.html",
    2016: "https://iclr.cc/archive/www/doku.php%3Fid=iclr2016:accepted-main.html",
}

# Papers listed on a year's accepted page that belong to a different year.
# 1411.7676 appears on both the 2015 and 2016 lists; it was accepted in 2016.
EXCLUDE = {2015: {"1411.7676"}}
UA = {"User-Agent": "Mozilla/5.0 (research; abstract-audit)"}
ARXIV_API = "http://export.arxiv.org/api/query"
BATCH = 50
ID_RE = re.compile(r'href="https?://arxiv\.org/(?:abs|pdf)/([0-9]+\.[0-9]+)(?:v\d+)?"', re.I)


def _get(url: str, retries: int = 4) -> str:
    """Fetch a URL; raise after the last retry, so a failure never reads as
    an empty page and never reaches the raw file."""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == retries - 1:
                raise RuntimeError(f"fetch failed after {retries} attempts: {url}") from e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"no attempts made: {url}")


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def arxiv_ids(page_html: str) -> list[str]:
    """arXiv ids linked from an accepted-papers page, first occurrence order."""
    seen = []
    for aid in ID_RE.findall(page_html):
        if aid not in seen:
            seen.append(aid)
    return seen


def parse_arxiv_feed(xml: str) -> dict[str, dict]:
    """{arxiv_id: {title, abstract, authors}} for entries with an abstract."""
    out: dict[str, dict] = {}
    for ent in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        idm = re.search(r"<id>https?://arxiv\.org/abs/([0-9]+\.[0-9]+)", ent)
        tm = re.search(r"<title>(.*?)</title>", ent, re.S)
        sm = re.search(r"<summary>(.*?)</summary>", ent, re.S)
        authors = [_clean(a) for a in re.findall(r"<name>(.*?)</name>", ent, re.S)]
        if idm and tm and sm and _clean(sm.group(1)):
            out[idm.group(1)] = {
                "title": _clean(tm.group(1)),
                "abstract": _clean(sm.group(1)),
                "authors": authors,
            }
    return out


def fetch_arxiv(ids: list[str]) -> dict[str, dict]:
    """Return {arxiv_id: {title, abstract, authors}} for ids the API resolves."""
    out: dict[str, dict] = {}
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        url = f"{ARXIV_API}?" + urllib.parse.urlencode(
            {"id_list": ",".join(chunk), "max_results": len(chunk)})
        out.update(parse_arxiv_feed(_get(url)))
        time.sleep(3.0)  # arXiv API politeness
    return out


def build_records(year: int, ids: list[str], meta: dict[str, dict]) -> list[dict]:
    """One raw record per id the API resolved, in page order."""
    records = []
    for aid in ids:
        m = meta.get(aid)
        if not m:
            continue
        records.append({
            "paper_id": f"{year}_arxiv_{aid}",
            "venue": "iclr", "year": year,
            "title": m["title"], "abstract": m["abstract"], "authors": m["authors"],
            "arxiv_id": aid,
        })
    return records


def scrape_year(year: int, raw_dir: str) -> int:
    os.makedirs(raw_dir, exist_ok=True)
    ids = [a for a in arxiv_ids(_get(URLS[year])) if a not in EXCLUDE.get(year, set())]
    if not ids:
        raise SystemExit(f"  [ICLR {year}] no arXiv links parsed from {URLS[year]}; "
                         f"raw file left unchanged")
    print(f"  [ICLR {year}] {len(ids)} arXiv-linked papers on page")
    meta = fetch_arxiv(ids)
    print(f"  [ICLR {year}] {len(meta)} resolved with abstracts via arXiv API")

    records = build_records(year, ids, meta)
    path = os.path.join(raw_dir, f"iclr_{year}_arxiv.json")
    if not records:
        raise SystemExit(f"  [ICLR {year}] the arXiv API resolved none of {len(ids)} ids; "
                         f"{path} left unchanged")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False)
    print(f"  [ICLR {year}] wrote {len(records)} papers -> {path}")
    return len(records)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=[2014, 2015, 2016])
    ap.add_argument("--raw-dir", default="data/raw/iclr")
    args = ap.parse_args()
    total = sum(scrape_year(y, args.raw_dir) for y in args.years)
    print(f"ICLR arXiv total: {total} papers")


if __name__ == "__main__":
    main()
