#!/usr/bin/env python3
"""
Download ICML paper data from icml.cc/Downloads/{year} using form submission.

Saves: data/raw/icml/icml_{year}_data.json
Schema: {type, name, virtualsite_url, speakers/authors, abstract}

Requires: pip install requests beautifulsoup4

Usage:
  python src/scraping/download_icml.py --start 2017 --end 2025
  python src/scraping/download_icml.py --start 2024 --end 2024
"""

import argparse
import json
import os
import time

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import sys
    sys.exit("pip install requests beautifulsoup4")

BASE_URL = "https://icml.cc/Downloads/"
HEADERS  = {"User-Agent": "Mozilla/5.0 (research; abstract-audit)"}


def get_csrf_and_action(session: requests.Session, year: int) -> tuple[str | None, str | None]:
    url = f"{BASE_URL}{year}"
    r = session.get(url, timeout=30)
    if r.status_code != 200:
        print(f"  [ICML {year}] page unavailable ({r.status_code})")
        return None, None
    soup = BeautifulSoup(r.text, "html.parser")
    form = soup.find("form", action=lambda a: a and "/Downloads/" in a)
    if not form:
        print(f"  [ICML {year}] no download form found")
        return None, None
    csrf_input = form.find("input", {"name": "csrfmiddlewaretoken"})
    csrf = csrf_input["value"] if csrf_input else None
    action = form["action"]
    if action and not action.startswith("http"):
        action = f"https://icml.cc{action}"
    return csrf, action


def normalise(item: dict) -> dict:
    """One export entry under consistent field names, whichever ones ICML used."""
    return {
        "type":             item.get("type", ""),
        "name":             item.get("title", item.get("name", "")),
        "virtualsite_url":  item.get("url",   item.get("virtualsite_url", "")),
        "speakers/authors": item.get("authors", item.get("speakers/authors", "")),
        "abstract":         item.get("abstract", ""),
    }


def download_year(year: int, out_dir: str, delay: float) -> int:
    session = requests.Session()
    session.headers.update(HEADERS)

    csrf, action = get_csrf_and_action(session, year)
    if not csrf or not action:
        return 0

    form_data = {
        "csrfmiddlewaretoken": csrf,
        "file_format": "5",   # JSON
        "posters":     "on",
        "tutorials":   "on",
        "invited_talks": "on",
        "workshops":   "on",
        "demonstrations": "on",
    }
    post_headers = {
        **HEADERS,
        "Referer":      f"{BASE_URL}{year}",
        "Origin":       "https://icml.cc",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    r = session.post(action, data=form_data, headers=post_headers, timeout=60)
    if r.status_code != 200:
        print(f"  [ICML {year}] download failed ({r.status_code})")
        return 0

    try:
        raw = r.json()
    except Exception:
        print(f"  [ICML {year}] response is not valid JSON")
        return 0

    if not isinstance(raw, list) or not raw:
        print(f"  [ICML {year}] export is empty or not a list; raw file left unchanged")
        return 0
    records = [normalise(item) for item in raw]

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"icml_{year}_data.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False)
    print(f"  [ICML {year}] {len(records)} papers → {path}")
    return len(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   type=int, default=2017)
    parser.add_argument("--end",     type=int, default=2025)
    parser.add_argument("--raw-dir", default="data/raw/icml")
    parser.add_argument("--delay",   type=float, default=1.0)
    args = parser.parse_args()

    total = 0
    for year in range(args.start, args.end + 1):
        total += download_year(year, args.raw_dir, args.delay)
        time.sleep(args.delay)
    print(f"ICML total: {total} papers")


if __name__ == "__main__":
    main()
