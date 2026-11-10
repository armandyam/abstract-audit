#!/usr/bin/env python3
"""Is the local citation data the snapshot the TMLR paper was computed on?

Citation counts change daily and Semantic Scholar's licence does not allow
them to be redistributed, so the paper's citation numbers can be reproduced
exactly only from the same snapshot of the three {venue}_s2.csv files. This
module compares the local files' SHA-256 against the published snapshot
(reference/tmlr/citations/SNAPSHOT.md) and reports one of three modes:

  strict  all three files match the snapshot. Every citation output must then
          equal reference/tmlr/citations/ exactly.
  fresh   all three files exist and at least one differs: a new fetch. The
          analyses run and their outputs are expected to differ from the
          paper's; verify.py should report them, not fail on them.
  absent  at least one of the three files is missing. The citation stage
          does not run.

    python src/citations/snapshot.py
    python src/citations/snapshot.py --citations-dir path/to/citations
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from citations._common import CIT_DIR, VENUES  # noqa: E402

# The files behind the TMLR paper (upstream commit eda2733). Retrieval dates:
# NeurIPS 2026-05-11, ICLR and ICML 2026-06-11.
SNAPSHOT = {
    "neurips_s2.csv": "551d261f2e8273b24ec2ad38f0e12014cec39bd8f58e927303e9452517eeee88",
    "iclr_s2.csv":    "d93ada5eda606eed8fc7655062590f6813685f081d9534d93d3361cb377f2244",
    "icml_s2.csv":    "12ce8540e661641c6dc0b63ae6389f8e2472e292c25a8ec627e680222b639a64",
}

STRICT, FRESH, ABSENT = "strict", "fresh", "absent"


def sha256(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def status(citations_dir: str | None = None,
           snapshot: dict[str, str] | None = None) -> dict[str, str]:
    """Per file: 'match', 'differs' or 'missing'."""
    citations_dir = citations_dir or CIT_DIR
    snapshot = snapshot or SNAPSHOT
    out = {}
    for name, want in snapshot.items():
        path = os.path.join(citations_dir, name)
        if not os.path.exists(path):
            out[name] = "missing"
        else:
            out[name] = "match" if sha256(path) == want else "differs"
    return out


def mode(citations_dir: str | None = None,
         snapshot: dict[str, str] | None = None) -> str:
    """strict, fresh or absent; see the module docstring."""
    st = status(citations_dir, snapshot)
    if any(v == "missing" for v in st.values()):
        return ABSENT
    if all(v == "match" for v in st.values()):
        return STRICT
    return FRESH


def required_files(citations_dir: str | None = None) -> list[str]:
    return [os.path.join(citations_dir or CIT_DIR, f"{v}_s2.csv") for v in VENUES]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--citations-dir", default=None,
                    help="default: $AA_DATA/per_paper/citations")
    a = ap.parse_args()
    for name, s in status(a.citations_dir).items():
        print(f"  {name:<16} {s}")
    print(mode(a.citations_dir))


if __name__ == "__main__":
    main()
