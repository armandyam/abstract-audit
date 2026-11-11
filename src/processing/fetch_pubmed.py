#!/usr/bin/env python3
"""
Download the PubMed baseline from NLM and parse it into per-year JSON.

Source: the annual MEDLINE/PubMed baseline,
        https://ftp.ncbi.nlm.nih.gov/pubmed/baseline/
        gzipped XML, about 30,000 PubmedArticle records per file.
Pinned: the 2026 baseline, files pubmed26n0001.xml.gz to pubmed26n1334.xml.gz
        (released 29 January 2026). --baseline-prefix selects the release;
        each file is checked against the .md5 NLM publishes beside it.
        The daily update files (updatefiles/) are not used.

Filters (as Hohmann et al. 2025):
  - English only (the article's Language is "eng" or "en", or absent);
  - title non-empty and a publication year determinable;
  - year at least --start-year;
  - abstract of at least six words;
  - no "published erratum" or "this corrects the article" in title or abstract.

Year: Journal/JournalIssue/PubDate/Year, else PubDate/Year, else ArticleDate,
else the leading four digits of MedlineDate. There is no upper bound, so
ahead-of-print records dated after the baseline year are kept (156,564
records dated 2026 and 2027 in the 2026 baseline). Every figure caps PubMed
at 2025 downstream.

Output: data/processed/pubmed_parsed/pubmed_{year}.json
Fields: paper_id ("pmid_" + PMID), venue ("pubmed"), year, title, abstract,
        authors

The metrics do not read this directory. clean_pubmed.py strips structured
abstract headings from these files and writes data/processed/pubmed/, which
is what every metric script reads.

The run behind the TMLR paper used --start-year 1990: every PubMed per-paper
metric file starts in 1990, so that is the default here (upstream's default
was 1950). After cleaning it gave 24,463,208 records dated 1990-2027.

Regeneration and recomputation: NLM replaces the baseline every year, and
the old one leaves the FTP site. Within 2026 this script refetches the same
files the paper used (the md5 check confirms it). Once the 2027 baseline is
out, a run recomputes on a new corpus: records are added, corrected and
withdrawn, and the year counts change. The PubMed numbers in the paper are
shipped in shared/baselines/ for that reason.

Resumable: each baseline file is parsed into its own shard
(data/processed/pubmed_parsed/.shards/<file>.jsonl.gz, written atomically)
before it is listed as done in the state file
(data/processed/pubmed_parsed/.processed_files.json). The year files are
rebuilt from the shards at the end of every run, so an interruption loses at
most the file in progress and a rerun never duplicates records. The state file
records --baseline-prefix, --start-year and --years; a rerun with other values
against the same --out-base is refused.

Usage:
  python src/processing/fetch_pubmed.py                    # whole baseline
  python src/processing/fetch_pubmed.py --max-files 10     # first ten files
  python src/processing/fetch_pubmed.py --years 2010 2015
"""

from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from schema import make_paper, save_processed, sanitize_text

FTP_BASE        = "https://ftp.ncbi.nlm.nih.gov/pubmed/baseline"
BASELINE_PREFIX = "pubmed26n"
START_YEAR      = 1990
DATA_DIR        = os.environ.get("AA_DATA", "data")
OUT_BASE        = os.path.join(DATA_DIR, "processed", "pubmed_parsed")
CACHE_DIR       = os.path.join(DATA_DIR, "raw", "pubmed")
STATE_NAME      = ".processed_files.json"
MAX_RETRIES     = 5
SLEEP           = 0.5
UA              = {"User-Agent": "Mozilla/5.0 (research; abstract-audit)"}

ERRATUM_PATTERNS = [
    re.compile(r"published erratum", re.IGNORECASE),
    re.compile(r"this corrects the article", re.IGNORECASE),
]


# ── HTTP ─────────────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _download(url: str, dest: str, retries: int = 0) -> None:
    try:
        tmp = dest + ".part"
        with open(tmp, "wb") as fh:
            fh.write(_get(url, timeout=300))
        os.replace(tmp, dest)
    except Exception as e:
        if retries < MAX_RETRIES:
            wait = 2 ** retries * 5
            print(f"    Download error ({e}), retry in {wait}s", flush=True)
            time.sleep(wait)
            _download(url, dest, retries + 1)
        else:
            raise


def baseline_files(html: str, prefix: str = BASELINE_PREFIX) -> list[str]:
    """Sorted, de-duplicated .xml.gz names of one baseline release in an
    FTP index page. The .md5 companions and other releases are excluded."""
    names = set(re.findall(r'(pubmed\d+n\d+\.xml\.gz)(?!\.md5)', html))
    return sorted(n for n in names if n.startswith(prefix))


def list_baseline_files(prefix: str = BASELINE_PREFIX) -> list[str]:
    for attempt in range(MAX_RETRIES):
        try:
            html = _get(f"{FTP_BASE}/", timeout=30).decode(errors="replace")
            break
        except Exception:
            time.sleep(2 ** attempt * 3)
    else:
        sys.exit("Failed to list the FTP baseline directory")
    return baseline_files(html, prefix)


def parse_md5(text: str) -> str:
    """The digest from an NLM checksum line, "MD5(name)= <hex>"."""
    m = re.search(r"=\s*([0-9a-fA-F]{32})\s*$", text.strip())
    if not m:
        raise ValueError(f"unrecognised md5 line: {text!r}")
    return m.group(1).lower()


def md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── XML parsing ──────────────────────────────────────────────────────────────

# Known limitation, kept on purpose: both helpers read one level of child
# elements, so text nested two levels deep (e.g. <i>a <b>b</b> c</i>) loses
# its inner part. The published PubMed baselines were computed with exactly
# this parser, so changing it would stop the regeneration from reproducing
# them. A fresh study should use "".join(node.itertext()).

def _text(elem, path: str) -> str:
    node = elem.find(path)
    if node is None:
        return ""
    # All inner text, so mixed content (italics, sub- and superscripts) is kept
    parts = [node.text or ""]
    for child in node:
        parts.append(child.text or "")
        parts.append(child.tail or "")
    return " ".join(parts).strip()


def _abstract_text(article_elem) -> str:
    """Every AbstractText element joined; a labelled section of a structured
    abstract is written "LABEL: text"."""
    parts = []
    for at in article_elem.findall(".//AbstractText"):
        label = at.get("Label", "")
        inner = (at.text or "") + "".join((c.text or "") + (c.tail or "") for c in at)
        inner = inner.strip()
        if label and inner:
            parts.append(f"{label}: {inner}")
        elif inner:
            parts.append(inner)
    return " ".join(parts)


def _parse_year(article_elem) -> int | None:
    for path in [
        ".//Journal/JournalIssue/PubDate/Year",
        ".//PubDate/Year",
        ".//ArticleDate/Year",
    ]:
        node = article_elem.find(path)
        if node is not None and node.text:
            try:
                return int(node.text.strip())
            except ValueError:
                pass
    # MedlineDate, e.g. "2021 Jan-Feb"
    for path in [".//Journal/JournalIssue/PubDate/MedlineDate", ".//PubDate/MedlineDate"]:
        node = article_elem.find(path)
        if node is not None and node.text:
            m = re.match(r"(\d{4})", node.text.strip())
            if m:
                return int(m.group(1))
    return None


def _parse_authors(article_elem) -> list[str]:
    authors = []
    for author in article_elem.findall(".//AuthorList/Author"):
        last  = _text(author, "LastName")
        fore  = _text(author, "ForeName")
        coll  = _text(author, "CollectiveName")
        if coll:
            authors.append(coll)
        elif last:
            authors.append(f"{fore} {last}".strip() if fore else last)
    return authors


def parse_file(gz_path: str, year_filter: set[int] | None,
               start_year: int) -> dict[int, list[dict]]:
    """Parse one .xml.gz file into {year: [paper, ...]}.

    A record that fails to parse is skipped, as upstream did."""
    buckets: dict[int, list[dict]] = defaultdict(list)

    with gzip.open(gz_path, "rb") as fh:
        for _, elem in ET.iterparse(fh, events=("end",)):
            if elem.tag != "PubmedArticle":
                continue

            try:
                medline  = elem.find("MedlineCitation")
                article  = medline.find("Article") if medline is not None else None
                if medline is None or article is None:
                    continue

                lang_node = article.find("Language")
                if lang_node is not None and lang_node.text:
                    if lang_node.text.strip().lower() not in ("eng", "en"):
                        continue

                pmid_node = medline.find("PMID")
                if pmid_node is None or not pmid_node.text:
                    continue
                pmid = pmid_node.text.strip()

                title    = sanitize_text(_text(article, "ArticleTitle"))
                abstract = sanitize_text(_abstract_text(article))
                year     = _parse_year(article)

                if not title or year is None:
                    continue
                if year < start_year:
                    continue
                if year_filter and year not in year_filter:
                    continue
                if len(abstract.split()) < 6:
                    continue
                if any(p.search(abstract) or p.search(title) for p in ERRATUM_PATTERNS):
                    continue

                buckets[year].append(make_paper(
                    paper_id=f"pmid_{pmid}",
                    venue="pubmed",
                    year=year,
                    title=title,
                    abstract=abstract,
                    authors=_parse_authors(article),
                ))
            except Exception:
                pass
            finally:
                elem.clear()

    return buckets


# ── State and shards ─────────────────────────────────────────────────────────
#
# Each baseline file is parsed into its own shard, written atomically, before
# the file is recorded as done. The per-year output is then rebuilt from all
# completed shards, so an interrupted run loses at most the file in progress
# and a rerun never duplicates records. The state file also records the
# extraction settings; a resume with different settings is refused, because
# the shards already written would not match them.

STATE_VERSION = 2
SHARD_DIR     = ".shards"


def extraction_settings(baseline_prefix: str, start_year: int,
                        years: list[int] | None) -> dict:
    """The settings that decide which records a shard holds."""
    return {"baseline_prefix": baseline_prefix,
            "start_year": int(start_year),
            "years": sorted({int(y) for y in years}) if years else None}


def _atomic_write(path: str, write) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    write(tmp)
    os.replace(tmp, path)


def load_state(state_file: str, settings: dict) -> set[str]:
    """Completed file names, after checking the run's settings match."""
    if not os.path.exists(state_file):
        return set()
    with open(state_file) as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("version") != STATE_VERSION:
        sys.exit(f"{state_file} was written by an earlier version of this script, "
                 "which kept no per-file shards and cannot be resumed safely. "
                 "Use a new --out-base, or remove that directory and start again.")
    if data.get("settings") != settings:
        sys.exit(f"{state_file} was written with settings {data.get('settings')}, "
                 f"but this run asks for {settings}. Resuming would mix the two. "
                 "Use a new --out-base, or rerun with the original settings.")
    return set(data.get("done", []))


def save_state(state_file: str, settings: dict, done: set[str]) -> None:
    payload = {"version": STATE_VERSION, "settings": settings, "done": sorted(done)}

    def write(tmp):
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=1)
    _atomic_write(state_file, write)


def shard_path(shard_dir: str, fname: str) -> str:
    stem = fname[:-len(".xml.gz")] if fname.endswith(".xml.gz") else fname
    return os.path.join(shard_dir, f"{stem}.jsonl.gz")


def write_shard(path: str, buckets: dict[int, list[dict]]) -> None:
    """One file's kept records as gzipped JSON lines, written atomically."""
    def write(tmp):
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            for year in sorted(buckets):
                for paper in buckets[year]:
                    fh.write(json.dumps(paper, ensure_ascii=False) + "\n")
    _atomic_write(path, write)


def read_shard(path: str):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def assemble(out_base: str, shard_dir: str, done: list[str]) -> dict[int, int]:
    """Rebuild every pubmed_{year}.json from the shards of the completed
    files, in file order. Each year file is replaced atomically, so a rerun
    after an interruption here gives the same result."""
    missing = [f for f in done if not os.path.exists(shard_path(shard_dir, f))]
    if missing:
        sys.exit(f"{len(missing)} completed files have no shard in {shard_dir} "
                 f"(first: {missing[0]}). Remove their names from the state "
                 "file to parse them again.")
    spool = os.path.join(out_base, ".assemble")
    os.makedirs(spool, exist_ok=True)
    handles = {}
    try:
        for fname in done:
            for paper in read_shard(shard_path(shard_dir, fname)):
                year = int(paper["year"])
                if year not in handles:
                    handles[year] = open(os.path.join(spool, f"{year}.jsonl"),
                                         "w", encoding="utf-8")
                handles[year].write(json.dumps(paper, ensure_ascii=False) + "\n")
    finally:
        for fh in handles.values():
            fh.close()

    counts: dict[int, int] = {}
    for year in sorted(handles):
        part = os.path.join(spool, f"{year}.jsonl")
        with open(part, encoding="utf-8") as fh:
            papers = [json.loads(line) for line in fh if line.strip()]
        _atomic_write(os.path.join(out_base, f"pubmed_{year}.json"),
                      lambda tmp: save_processed(papers, tmp))
        counts[year] = len(papers)
        os.remove(part)
    os.rmdir(spool)
    return counts


# ── Main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-base",   default=OUT_BASE)
    parser.add_argument("--cache-dir",  default=CACHE_DIR,
                        help="Where the downloaded .xml.gz files are kept")
    parser.add_argument("--state-file", default=None,
                        help=f"Default: <out-base>/{STATE_NAME}")
    parser.add_argument("--baseline-prefix", default=BASELINE_PREFIX,
                        help="Baseline release to read (default: pubmed26n)")
    parser.add_argument("--years",      nargs="+", type=int, default=None)
    parser.add_argument("--start-year", type=int, default=START_YEAR,
                        help="Ignore records dated before this year (default: 1990)")
    parser.add_argument("--max-files",  type=int, default=None,
                        help="Process at most N files (for testing)")
    parser.add_argument("--keep-cache", action="store_true",
                        help="Keep the .xml.gz files after parsing")
    parser.add_argument("--no-md5", action="store_true",
                        help="Skip the check against NLM's published md5")
    args = parser.parse_args(argv)
    state_file = args.state_file or os.path.join(args.out_base, STATE_NAME)
    shard_dir  = os.path.join(args.out_base, SHARD_DIR)

    os.makedirs(args.out_base,  exist_ok=True)
    os.makedirs(args.cache_dir, exist_ok=True)

    settings    = extraction_settings(args.baseline_prefix, args.start_year, args.years)
    year_filter = set(settings["years"]) if settings["years"] else None
    if not os.path.exists(state_file):
        stale = [f for f in os.listdir(args.out_base)
                 if f.startswith("pubmed_") and f.endswith(".json")]
        if stale:
            sys.exit(f"{args.out_base} already holds {len(stale)} year files but no "
                     f"state file; they were not produced from shards and would be "
                     "overwritten. Use a new --out-base.")
    done_files = load_state(state_file, settings)
    save_state(state_file, settings, done_files)

    print("Listing PubMed baseline files", flush=True)
    all_files = list_baseline_files(args.baseline_prefix)
    if not all_files:
        sys.exit(f"No {args.baseline_prefix}*.xml.gz files on {FTP_BASE}/; NLM has "
                 "probably replaced that baseline. See the docstring.")
    print(f"Found {len(all_files)} files ({all_files[0]} to {all_files[-1]})", flush=True)

    to_process = [f for f in all_files if f not in done_files]
    if args.max_files:
        to_process = to_process[:args.max_files]
    print(f"{len(to_process)} files to process ({len(done_files)} already done)\n",
          flush=True)

    for i, fname in enumerate(to_process):
        url     = f"{FTP_BASE}/{fname}"
        gz_path = os.path.join(args.cache_dir, fname)
        pct     = 100 * (i + 1) / len(to_process)
        print(f"[{i+1}/{len(to_process)} {pct:.1f}%] {fname}", flush=True)

        if not os.path.exists(gz_path):
            print("  Downloading", flush=True)
            _download(url, gz_path)
            time.sleep(SLEEP)
        if not args.no_md5:
            want = parse_md5(_get(url + ".md5", timeout=30).decode())
            got = md5(gz_path)
            if got != want:
                os.remove(gz_path)
                sys.exit(f"{fname}: md5 {got} does not match NLM's {want}; "
                         "removed, rerun to fetch it again")

        file_buckets = parse_file(gz_path, year_filter, settings["start_year"])
        total_in_file = sum(len(v) for v in file_buckets.values())
        print(f"  {total_in_file:,} papers kept ({len(file_buckets)} years)", flush=True)

        # Data first, then the completion record, then the cache
        write_shard(shard_path(shard_dir, fname), file_buckets)
        done_files.add(fname)
        save_state(state_file, settings, done_files)

        if not args.keep_cache:
            os.remove(gz_path)

    done_in_order = [f for f in all_files if f in done_files]
    done_in_order += sorted(done_files - set(all_files))
    print(f"\nAssembling year files from {len(done_in_order)} shards", flush=True)
    counts = assemble(args.out_base, shard_dir, done_in_order)

    print("\nOutput files:")
    for year, n in sorted(counts.items()):
        print(f"  pubmed_{year}.json: {n:,}")
    print(f"\nTotal: {sum(counts.values()):,} papers")
    print(f"The shards in {shard_dir} hold the same records; keep them to resume "
          "or extend this run.")
    print("Next step: python src/processing/clean_pubmed.py")


if __name__ == "__main__":
    main()
