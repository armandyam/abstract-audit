#!/usr/bin/env python3
"""Check or refresh the sha256 lists in reference/MANIFEST.md.

MANIFEST.md is prose, one section per set of reference files, and each
section ends in a fenced list of `<first 16 hex of sha256>  <path>` lines,
introduced by the line "sha256, first 16 hex:". This script reads those lists
and compares them with the files in reference/:

  - a listed path that does not exist is an error;
  - a listed hash that differs from the file's is an error (fixed by --write);
  - a file under reference/ that no list names is an error (it needs a
    section saying where it came from, so it has to be added by hand);
  - a path listed twice is an error.

    python reference/make_manifest.py            # check, exit 1 on any error
    python reference/make_manifest.py --write    # rewrite the hashes in place

--write changes only the hashes, never the prose or which paths are listed,
and refuses to write while a listed path is missing or a file is unlisted.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "MANIFEST.md")
INTRO = "sha256, first 16 hex:"
LINE = re.compile(r"^([0-9a-f]{16})  (\S+)$")
# Files in reference/ that describe the others and are not themselves listed.
NOT_LISTED = {"MANIFEST.md", "README.md", "make_manifest.py"}
IGNORED_PARTS = {"__pycache__", ".DS_Store"}


def sha16(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def listed_lines(text: str) -> list[tuple[int, str, str]]:
    """(line index, hash, path) of every entry in a hash list."""
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == INTRO:
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            j += 1                                   # past the opening fence
            while j < len(lines) and not lines[j].startswith("```"):
                m = LINE.match(lines[j])
                if not m:
                    raise ValueError(f"MANIFEST.md line {j + 1}: not '<hash>  <path>': "
                                     f"{lines[j]!r}")
                out.append((j, m.group(1), m.group(2)))
                j += 1
            i = j
        i += 1
    return out


def files_on_disk(root: str) -> set[str]:
    found = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_PARTS]
        for f in filenames:
            if f in IGNORED_PARTS:
                continue
            rel = os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/")
            if rel not in NOT_LISTED:
                found.add(rel)
    return found


def check(text: str, root: str) -> tuple[list[str], list[tuple[int, str]]]:
    """Errors other than stale hashes, and the stale hashes as
    (line index, new line)."""
    entries = listed_lines(text)
    errors: list[str] = []
    stale: list[tuple[int, str]] = []
    seen: set[str] = set()
    for idx, digest, rel in entries:
        if rel in seen:
            errors.append(f"listed twice: {rel}")
        seen.add(rel)
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            errors.append(f"listed but missing: {rel}")
            continue
        actual = sha16(path)
        if actual != digest:
            stale.append((idx, f"{actual}  {rel}"))
    for rel in sorted(files_on_disk(root) - seen):
        errors.append(f"not listed: {rel}")
    return errors, stale


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true",
                    help="rewrite stale hashes in MANIFEST.md")
    ap.add_argument("--manifest", default=MANIFEST)
    a = ap.parse_args(argv)
    root = os.path.dirname(os.path.abspath(a.manifest))
    with open(a.manifest, encoding="utf-8") as fh:
        text = fh.read()
    errors, stale = check(text, root)
    n = len(listed_lines(text))
    for e in errors:
        print(f"  ERROR  {e}")
    if a.write:
        if errors:
            print("not written: fix the errors above first")
            return 1
        lines = text.split("\n")
        for idx, new in stale:
            lines[idx] = new
        with open(a.manifest, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print(f"{n} entries, {len(stale)} hashes updated")
        return 0
    for idx, new in stale:
        print(f"  STALE  {new.split()[1]}  (line {idx + 1}; run with --write)")
    print(f"{n} entries, {len(errors)} errors, {len(stale)} stale hashes")
    return 1 if errors or stale else 0


if __name__ == "__main__":
    sys.exit(main())
