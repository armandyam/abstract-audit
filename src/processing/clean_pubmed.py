#!/usr/bin/env python3
"""
Clean parsed PubMed abstracts as Hohmann et al. (2025) did, for the metrics.

  1. Strip structured abstract headings ("OBJECTIVES:", "MATERIALS AND
     METHODS:", "BACKGROUND/AIMS:", ...): an upper-case run of letters,
     digits, spaces and / ( ) & , - followed by a colon.
  2. Replace & with "and".
  3. Remove characters outside printable ASCII (tab and newline are kept).
  4. Collapse whitespace.
  5. Drop an abstract left with fewer than six words.

Titles are not changed.

Reads:  data/processed/pubmed_parsed/pubmed_{year}.json  (fetch_pubmed.py)
Writes: data/processed/pubmed/pubmed_{year}.json

The output directory is the one every metric script reads for the venue
"pubmed". The per-paper PubMed metrics behind the TMLR paper were computed on
cleaned text: for sampled structured abstracts, the shipped readability
values match the cleaned abstract and not the parsed one.

Usage:
  python src/processing/clean_pubmed.py
  python src/processing/clean_pubmed.py --in-dir DIR --out-dir DIR
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys

DATA_DIR = os.environ.get("AA_DATA", "data")
IN_DIR   = os.path.join(DATA_DIR, "processed", "pubmed_parsed")
OUT_DIR  = os.path.join(DATA_DIR, "processed", "pubmed")
MIN_WORDS = 6

# Structured abstract headings: one or more upper-case words, optionally with
# spaces, slashes, parentheses and digits, followed by a colon.
_HEADING_RE = re.compile(
    r'\b[A-Z][A-Z0-9\s/()&,-]{1,60}:\s*',
)

# Anything outside printable ASCII (0x20-0x7E), tab and newline
_NON_ASCII_RE = re.compile(r'[^\x09\x0A\x20-\x7E]')


def clean_abstract(text: str) -> str:
    text = _HEADING_RE.sub(' ', text)
    text = text.replace('&', 'and')
    text = _NON_ASCII_RE.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_papers(papers: list[dict]) -> list[dict]:
    """Cleaned copies of the papers whose abstract keeps at least six words."""
    cleaned = []
    for p in papers:
        abstract = clean_abstract(p.get('abstract') or '')
        if len(abstract.split()) < MIN_WORDS:
            continue
        p = dict(p)
        p['abstract'] = abstract
        cleaned.append(p)
    return cleaned


def process_file(in_path: str, out_path: str) -> tuple[int, int]:
    with open(in_path, encoding='utf-8') as fh:
        papers = json.load(fh)

    cleaned = clean_papers(papers)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(cleaned, fh, ensure_ascii=False)

    return len(papers), len(cleaned)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--in-dir',  default=IN_DIR)
    parser.add_argument('--out-dir', default=OUT_DIR)
    args = parser.parse_args()

    if os.path.abspath(args.in_dir) == os.path.abspath(args.out_dir):
        sys.exit('--in-dir and --out-dir must differ; cleaning in place would '
                 'lose the parsed text')
    if not os.path.isdir(args.in_dir):
        sys.exit(f'{args.in_dir} not found; run src/processing/fetch_pubmed.py first')
    files = sorted(f for f in os.listdir(args.in_dir)
                   if f.endswith('.json') and not f.startswith('.'))
    if not files:
        sys.exit(f'No JSON files found in {args.in_dir}')

    print(f'Cleaning {len(files)} files -> {args.out_dir}')
    total_in = total_out = 0
    for fname in files:
        n_in, n_out = process_file(os.path.join(args.in_dir, fname),
                                   os.path.join(args.out_dir, fname))
        print(f'  {fname}: {n_in:,} -> {n_out:,}  (dropped {n_in - n_out:,})')
        total_in  += n_in
        total_out += n_out

    print(f'\nTotal: {total_in:,} -> {total_out:,}  (dropped {total_in - total_out:,})')


if __name__ == '__main__':
    main()
