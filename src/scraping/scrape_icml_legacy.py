#!/usr/bin/env python3
"""
Scrape pre-2013 ICML proceedings from the year-specific icml.cc archive pages.

Each year uses a different HTML layout, so there is one parser per year. Only
papers with a non-empty abstract are kept (title and authors alone are not
enough). Years whose archive pages carry no abstracts (2005, 2007) are not
covered here, and 2006 has no archived listing.

Sources:
  2012 https://icml.cc/Conferences/2012/papers.1.html
  2011 https://icml.cc/Conferences/2011/papers.php.html
  2010 https://icml.cc/Conferences/2010/abstracts.html
  2009 https://icml.cc/Conferences/2009/abstracts.html
  2008 https://icml.cc/Conferences/2008/abstracts.shtml.html

Writes data/raw/icml/icml_{year}_legacy.json, one record per paper with an
abstract: {paper_id, year, title, authors, abstract}.
src/processing/process_icml.py turns it into the canonical processed file.

Usage:
  python src/scraping/scrape_icml_legacy.py --years 2008 2009 2010 2011 2012
"""

from __future__ import annotations
import argparse
import html
import json
import os
import re
import urllib.request

URLS = {
    2012: "https://icml.cc/Conferences/2012/papers.1.html",
    2011: "https://icml.cc/Conferences/2011/papers.php.html",
    2010: "https://icml.cc/Conferences/2010/abstracts.html",
    2009: "https://icml.cc/Conferences/2009/abstracts.html",
    2008: "https://icml.cc/Conferences/2008/abstracts.shtml.html",
}
UA = {"User-Agent": "Mozilla/5.0 (research; abstract-audit)"}
MIN_ABSTRACT_CHARS = 20


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    # These archive pages are a mix of UTF-8 and Windows-1252; try strict UTF-8
    # first and fall back so accented author names survive.
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _text(s: str) -> str:
    """Strip tags and normalise whitespace/entities."""
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


# Trailing navigation-link junk that the year-page layouts append after the
# abstract text (anchors stripped by _text leave their link labels behind).
_TRAILING_JUNK = [
    re.compile(r"\[\s*(?:Full|Corrected)\s+paper\s*\].*$", re.I | re.S),
    re.compile(r"\[\s*Discussion\s*\].*$", re.I | re.S),
    re.compile(r"\bdiscussion\+video\b.*$", re.I | re.S),
    re.compile(r"\bICML version \(pdf\).*$", re.I | re.S),
]


def _strip_trailing_junk(abstract: str) -> str:
    for pat in _TRAILING_JUNK:
        abstract = pat.sub("", abstract)
    return abstract.strip()


_AFFILIATION_RE = re.compile(
    r"\b(Universit|Institute|Department|Laborator|College|School of|"
    r"Research Cent|INRIA|CNRS|ETH\b|MIT\b|Microsoft|Google|IBM|Yahoo)",
    re.I)


def _authors(raw: str) -> list[str]:
    a = _text(raw)
    a = re.sub(r"\([^)]*\)", "", a)          # drop affiliations (2010)
    a = a.replace(" and ", ";").replace(",", ";")
    names = [x.strip() for x in a.split(";") if x.strip()]
    # 2011 lists affiliations without parentheses; drop institution tokens.
    return [n for n in names if not _AFFILIATION_RE.search(n)]


# --- per-year parsers: each returns list of (paper_id, title, authors, abstract)

def parse_2008(h: str) -> list[tuple]:
    out = []
    for m in re.finditer(
        r'paper ID:\s*(\d+)\s*</p>\s*<h3>(.*?)</h3>\s*<p><i>(.*?)</i>.*?</p>(.*?)'
        r'(?=<a name=|<p>paper ID:|</div>|$)', h, re.S):
        pid, title, auth, rest = m.groups()
        out.append((pid, _text(title), _authors(auth), _text(rest)))
    return out


def parse_2009(h: str) -> list[tuple]:
    # Restrict to the proceedings section; the sidebar nav reuses
    # <h3><a name="10"> anchors that would otherwise pollute the first record.
    cut = h.find("ICML 2009 Proceedings")
    if cut > 0:
        h = h[cut:]
    out = []
    for m in re.finditer(
        r'<h3><a name="(\d+)"></a>([^<]*?)</h3>\s*<p><i>(.*?)</i></p>\s*'
        r'<p>\s*paper ID:.*?</p>(.*?)(?=<h3><a name=|<hr|</div>|$)', h, re.S):
        pid, title, auth, rest = m.groups()
        out.append((pid, _text(title), _authors(auth), _text(rest)))
    return out


def parse_2010(h: str) -> list[tuple]:
    # Anchor on the "Paper ID:" line so sidebar <h3> nav headers are excluded.
    out = []
    for m in re.finditer(
        r'<a name="(\d+)"></a>\s*<p>\s*Paper ID:[^<]*</p>\s*<h3>(.*?)</h3>\s*'
        r'<p><em>(.*?)</em></p>\s*<p class="abstracts">(.*?)</p>', h, re.S):
        pid, title, auth, abs = m.groups()
        out.append((pid, _text(title), _authors(auth), _text(abs)))
    return out


def parse_2011(h: str) -> list[tuple]:
    out = []
    for m in re.finditer(
        r"<a name='(\d+)'>\s*<h3[^>]*>(.*?)</h3>\s*<span class='name'>(.*?)</span>\s*"
        r"<p[^>]*>\s*<span[^>]*>\s*Abstract:?\s*</span>(.*?)</p>", h, re.S):
        pid, title, auth, abs = m.groups()
        out.append((pid, _text(title), _authors(auth), _text(abs)))
    return out


def parse_2012(h: str) -> list[tuple]:
    out = []
    for m in re.finditer(
        r'<div class="paper" id="paper-(\d+)">(.*?)(?=<div class="paper"|<div id=|</body|$)',
        h, re.S):
        pid, block = m.groups()
        t = re.search(r"<h2>(.*?)</h2>", block, re.S)
        au = re.search(r'<p class="authors">(.*?)(?=<p |</div|$)', block, re.S)
        # The <p class="abstract"> tag is not closed in this layout, so capture
        # through to the paper-div close rather than a </p>.
        ab = re.search(r'<p class="abstract">\s*<strong>\s*Abstract:?\s*</strong>'
                       r'(.*?)(?=</div>|<p class="|$)', block, re.S)
        if t:
            out.append((pid, _text(t.group(1)),
                        _authors(au.group(1)) if au else [],
                        _text(ab.group(1)) if ab else ""))
    return out


PARSERS = {2008: parse_2008, 2009: parse_2009, 2010: parse_2010,
           2011: parse_2011, 2012: parse_2012}


def build_records(year: int, parsed: list[tuple]) -> tuple[list[dict], int]:
    """Raw records for papers with a title and an abstract; (records, n_dropped)."""
    records, dropped = [], 0
    for pid, title, authors, abstract in parsed:
        abstract = _strip_trailing_junk(abstract)
        if not title or len(abstract) < MIN_ABSTRACT_CHARS:
            dropped += 1
            continue
        records.append({"paper_id": f"{year}_icmlcc_{pid}", "year": year,
                        "title": title, "authors": authors, "abstract": abstract})
    return records, dropped


def scrape_year(year: int, raw_dir: str) -> int:
    if year not in PARSERS:
        print(f"  [ICML {year}] no legacy parser, skipping")
        return 0
    os.makedirs(raw_dir, exist_ok=True)
    records, dropped = build_records(year, PARSERS[year](_get(URLS[year])))
    path = os.path.join(raw_dir, f"icml_{year}_legacy.json")
    if not records:
        raise SystemExit(f"  [ICML {year}] no papers parsed from {URLS[year]}; "
                         f"{path} left unchanged")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False)
    print(f"  [ICML {year}] {len(records)} papers with abstract kept, "
          f"{dropped} dropped (no/short abstract) -> {path}")
    return len(records)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=[2008, 2009, 2010, 2011, 2012])
    ap.add_argument("--raw-dir", default="data/raw/icml")
    args = ap.parse_args()
    total = sum(scrape_year(y, args.raw_dir) for y in args.years)
    print(f"ICML legacy total: {total} papers")


if __name__ == "__main__":
    main()
