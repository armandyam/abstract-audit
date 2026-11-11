#!/usr/bin/env python3
"""Check every number the TMLR paper prints against this repository's outputs.

The manuscript is not distributed with this repository. paper/tmlr/claims.csv
holds one row per number it prints, with the number itself and how to check
it, but none of the text around it. The check therefore runs in two parts:

  values    every row's check function (claims.py) recomputes the number
            from the pipeline's outputs and compares it with the printed
            value stored in the row. Needs no manuscript, except for the
            citation rows: their printed value is not stored (see below).
  coverage  with a local copy of the manuscript ($AA_PAPER or --paper-dir,
            see manuscript.py), inventory.py finds every number it prints,
            macro invocations excepted (check_macros.py compares the 163
            macros). Each occurrence is tied to its row by context_sha256, a
            hash of the number and the words around it. A number no row ties
            to (uncovered), a row that ties to no number (stale, usually a
            reworded sentence) and a row whose printed value differs from
            the manuscript's fail the check. Without AA_PAPER the coverage
            check is reported as skipped.

claims.csv columns:

  id              stable identifier, assigned once; never reused
  file            the manuscript file, relative to its directory
  line            the line the number was on when the row was last synced
                  (informational; --sync-lines rewrites it)
  printed         the number as printed, whitespace collapsed ("30,595",
                  "41 to 47", "7 of the 9", "three quarters"). Blank for
                  every row whose check reads citation outputs (category
                  citation, and the generated cells of the citation tables,
                  claims.is_citation_check): the citation counts and every
                  statistic computed from them are not distributed, so the
                  printed value is taken from the manuscript, from the
                  occurrence the row's context_sha256 ties it to. Without
                  the manuscript such a row is skipped. A blank printed value
                  on any other row, and a stored one on a citation row, are
                  errors.
  kind            number, date, word, pair or fraction (inventory.py)
  category        computed     measured, recomputed by `check`
                  citation     measured from citation counts: recomputed and
                               compared in strict citation mode, compared and
                               reported but not counted after a fresh fetch,
                               skipped when the counts are absent
                  generated    a cell of a table make_macros.py generates,
                               compared with the same cell of the built table
                  literature   a value quoted from the cited literature
                  design       a constant of the study design, a scope count,
                               a window bound, a policy threshold or a label;
                               checked against the code when `check` is given
                  unverifiable a measured number nothing in the release can
                               reproduce; reported, never silently passed
  check           a function in claims.py (empty for unchecked literature or
                  design rows)
  args            its keyword arguments, key=value separated by semicolons;
                  a list value joins items with +
  rule            how the computed value is compared with the printed one:
                    auto         at the printed precision (default): the
                                 computed value formatted with as many
                                 decimals as the printed one equals it; a
                                 "2.8 million" compares millions; a range or
                                 fraction compares element by element
                    abs          as auto on the absolute value
                    exact        equal
                    gt ge lt le  computed > >= < <= printed
                    nearest:q    computed rounded to the nearest multiple of q
                    approx:t     |computed - printed| <= t
                    round:n      computed rounded to n digits
                    within       a computed (min, max) inside the printed range
                    claim:text   the check returns a string equal to text
                    true         the check returns True
                    text         the check returns the printed text itself
                                 (a cell of a generated table)
  known           non-empty for a discrepancy the authors accepted: the
                  printed value stays as it is in the published paper. Such
                  a row is reported KNOWN with its computed value and not
                  counted as a failure. If it ever matches, it is reported
                  so that the flag can be cleared.
  source          for literature, the work quoted; for design, what the
                  constant is; otherwise where the value comes from
  note            anything else
  context_sha256  sha256 of the file, the number and its context
                  (inventory.context_hashes); no text is stored

Results: MATCH, MISMATCH, KNOWN, MISSING, SKIP(reason) and UNVERIFIABLE.
verify.py counts mismatches, missing inputs, errors, and, with the
manuscript, uncovered numbers, stale rows and printed values that differ, as
failures.

Missing inputs. A computed, citation or generated claim whose input file is
absent is MISSING, a failure. The exemptions are explicit, and each is
reported as SKIP with its reason:

  design, literature   rows without a check
  citation counts      absent: the counts are not distributed, so citation
                       claims are skipped
  citation printed     without the manuscript: the printed value of a
                       citation claim is not stored, so the claim is skipped
  manuscript absent    the self-audit measures the paper's own abstract,
                       which the release does not ship; its claims are
                       skipped when AA_PAPER is unset and the self-audit
                       output is absent (claims.PAPER_EXEMPT)
  exempt input         neurips_fallback_count re-reads the raw NeurIPS
                       scrape, which the --from aggregate route does not
                       have (claims.RAW_EXEMPT)

After the paper text changes (needs AA_PAPER):

  1. python paper/tmlr/check_claims.py           lists uncovered and stale rows
  2. python paper/tmlr/check_claims.py --suggest  prints a claims.csv row for
                                                  every uncovered number (the
                                                  context goes to stderr, for
                                                  the author only); paste the
                                                  rows and fill in category,
                                                  check and args, and blank
                                                  the printed value of a
                                                  citation row
  3. delete the stale rows a new row replaces, then
     python paper/tmlr/check_claims.py --sync-lines

    python paper/tmlr/check_claims.py [--data-dir DIR] [--mode strict|fresh|absent]
                                      [--paper-dir DIR]
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))

import claims as C  # noqa: E402
import inventory as inv  # noqa: E402
from manuscript import SKIP_REASON, paper_dir  # noqa: E402

CLAIMS = os.path.join(HERE, "claims.csv")
FIELDS = ["id", "file", "line", "printed", "kind", "category", "check", "args", "rule",
          "known", "source", "note", "context_sha256"]
CATEGORIES = {"computed", "citation", "generated", "literature", "design",
              "unverifiable"}
CIT_ABSENT = "citation counts absent"
CIT_FRESH = "citation counts are a fresh fetch: compared, not counted"
FROM_PAPER = "printed value comes from the manuscript"
NOT_IN_PAPER = ("printed value comes from the manuscript, and the row ties to no "
                "number there (see STALE)")
# Skip reasons verify.py reports as counts; any other reason lists its claims.
PAPER_ABSENT = f"manuscript absent: {C.PAPER_EXEMPT}"
COUNTED_SKIPS = {"design", "literature", CIT_ABSENT, CIT_FRESH, PAPER_ABSENT, FROM_PAPER}


# ============================================================ claims.csv ===

def load(path: str = CLAIMS) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in FIELDS:
            r[k] = r.get(k) or ""
    return rows


def save(rows: list[dict], path: str = CLAIMS) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def parse_args(s: str) -> dict:
    out = {}
    for part in [p for p in s.split(";") if p.strip()]:
        k, _, v = part.partition("=")
        out[k.strip()] = v.strip()
    return out


# ============================================================= coverage ===

@dataclass
class Coverage:
    matched: dict[int, inv.Occurrence] = field(default_factory=dict)   # row -> occ
    stale: list[tuple[int, str]] = field(default_factory=list)         # row, why
    uncovered: list[tuple[inv.Occurrence, str]] = field(default_factory=list)  # occ, hash
    duplicate: list[tuple[int, int]] = field(default_factory=list)


def match(rows: list[dict], occ: list[inv.Occurrence],
          norms: dict[str, inv.Normalised]) -> Coverage:
    """Tie each row to the occurrence with its file and context hash; collect
    the rows that tie to none or whose printed value differs (stale) and the
    occurrences no row ties to (uncovered). A blank printed value (a
    citation row) is taken from the manuscript, so only the hash ties it."""
    cov = Coverage()
    hashes = inv.context_hashes(occ, norms)
    by_hash = {(o.file, h): (i, o) for i, (o, h) in enumerate(zip(occ, hashes))}
    owner: dict[int, int] = {}
    for i, r in enumerate(rows):
        if r["file"] not in norms:
            cov.stale.append((i, f"file {r['file']} is not part of the manuscript"))
            continue
        hit = by_hash.get((r["file"], r["context_sha256"]))
        if hit is None:
            cov.stale.append((i, "context hash not found: the text around the "
                                 "number changed, or the number was removed"))
            continue
        k, o = hit
        if r["printed"] and o.text != r["printed"]:
            cov.stale.append((i, f"printed {r['printed']!r}, manuscript has {o.text!r}"))
            continue
        if k in owner:
            cov.duplicate.append((owner[k], i))
            continue
        owner[k] = i
        cov.matched[i] = o
    cov.uncovered = [(o, h) for k, (o, h) in enumerate(zip(occ, hashes)) if k not in owner]
    return cov


# ======================================================== printed value ===

SCALES = {"million": 1e6, "billion": 1e9}
WORDS = {**inv.CARDINALS, **inv.ORDINALS, **inv.OTHER_WORDS, "first": 1}


@dataclass
class Part:
    value: float | str
    decimals: int = 0
    scale: float = 1.0
    sign: bool = False      # printed with an explicit + or -


def parse_part(s: str) -> Part:
    s = s.strip().replace("{,}", ",").replace("−", "-").strip("$")
    if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", s):
        return Part(s)
    low = re.sub(r"\s+", " ", s.lower())
    m = re.fullmatch(r"([a-z]+) (quarters|thirds|halves)", low)
    if m and m.group(1) in inv.CARDINALS:
        return Part(inv.CARDINALS[m.group(1)] * inv.OTHER_WORDS[m.group(2)], 2)
    if low in WORDS:
        return Part(float(WORDS[low]))
    m = re.fullmatch(r"([a-z]+)fold", low)
    if m and m.group(1) in inv.CARDINALS:
        return Part(float(inv.CARDINALS[m.group(1)]))
    scale = 1.0
    for w, f in SCALES.items():
        if low.endswith(" " + w):
            scale, s = f, s[: -len(w) - 1].strip()
    s = re.sub(r"(\\%|%|th|st|nd|rd|fold|\+)$", "", s)
    if re.fullmatch(r"\d{4}s", s):
        s = s[:-1]
    sign = s[:1] in "+-"
    num = s.replace(",", "")
    dec = len(num.split(".")[1]) if "." in num else 0
    return Part(float(num), dec, scale, sign)


def parse_printed(text: str, kind: str) -> list[Part]:
    """The printed number(s) of one occurrence."""
    if kind == "fraction":
        parts = re.split(r"\s+of\s+(?:the\s+)?", text, maxsplit=1)
    elif kind == "pair":
        parts = re.split(r"\s+to\s+|--|–", text, maxsplit=1)
    else:
        parts = [text]
    return [parse_part(p) for p in parts]


# ============================================================ comparing ===

def _fmt(x: float, dec: int) -> float:
    return float(f"{x:.{dec}f}")


def compare(rule: str, computed, printed: list[Part]) -> bool:
    """Whether a computed value supports the printed one under `rule`."""
    rule = rule or "auto"
    if rule.startswith("claim:"):
        return str(computed) == rule[len("claim:"):]
    if rule == "true":
        return computed is True
    vals = list(computed) if isinstance(computed, (tuple, list)) else [computed]
    if rule == "within":
        lo, hi = vals
        return printed[0].value <= lo and hi <= printed[-1].value
    if len(vals) != len(printed):
        if len(vals) == 1:
            vals = vals * len(printed)
        elif len(printed) == 1:
            printed = printed * len(vals)     # every computed value must fit
        else:
            raise ValueError(f"{len(vals)} computed values for {len(printed)} printed")
    ok = True
    for c, p in zip(vals, printed):
        if isinstance(p.value, str) or isinstance(c, str):
            ok &= str(c) == str(p.value)
            continue
        c = float(c) / p.scale
        if rule == "abs":
            ok &= _fmt(abs(c), p.decimals) == abs(p.value)
        elif rule == "auto":
            ok &= _fmt(c, p.decimals) == p.value
        elif rule == "exact":
            ok &= c == p.value
        elif rule == "gt":
            ok &= c > p.value
        elif rule == "ge":
            ok &= c >= p.value
        elif rule == "lt":
            ok &= c < p.value
        elif rule == "le":
            ok &= c <= p.value
        elif rule.startswith("nearest:"):
            q = float(rule.split(":", 1)[1])
            ok &= abs(round(c / q) * q - p.value) < 1e-9
        elif rule.startswith("approx:"):
            ok &= abs(c - p.value) <= float(rule.split(":", 1)[1]) + 1e-12
        elif rule.startswith("round:"):
            ok &= round(c, int(rule.split(":", 1)[1])) == p.value
        else:
            raise ValueError(f"unknown rule {rule!r}")
    return bool(ok)


def show(v) -> str:
    if isinstance(v, (tuple, list)):
        return " to ".join(show(x) for x in v)
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


# ================================================================== run ===

@dataclass
class Report:
    records: list[dict] = field(default_factory=list)
    coverage: Coverage | None = None
    paper: str | None = None
    n_occ: int = 0
    n_rows: int = 0
    errors: list[str] = field(default_factory=list)

    def count(self, verdict: str) -> int:
        return sum(1 for r in self.records if r["verdict"] == verdict)

    @property
    def missing(self) -> int:
        """Claims whose required input is absent (counted as failures)."""
        return self.count("MISSING")

    @property
    def failures(self) -> int:
        cov = self.coverage
        return (self.count("MISMATCH") + self.count("ERROR") + self.missing + len(self.errors)
                + (len(cov.stale) + len(cov.uncovered) + len(cov.duplicate) if cov else 0))

    def skip_lines(self) -> list[str]:
        """Every skip, grouped by reason. The large documented groups are
        counted; any other reason lists its claims."""
        by: dict[str, list[dict]] = {}
        for r in self.records:
            if r["verdict"] == "SKIP":
                by.setdefault(r["why"], []).append(r)
        out = []
        for why in sorted(by):
            out.append(f"  SKIP {len(by[why]):>4}  {why}")
            if why in COUNTED_SKIPS:
                continue
            out += [f"             {r['file']}:{r['line']}  {r['printed']!r}  [{r['check']}]"
                    for r in by[why]]
        if self.coverage is None:
            out.append(f"  SKIP  coverage of the manuscript: {SKIP_REASON}")
        return out

    def lines(self, verbose: bool = False) -> list[str]:
        out = []
        for r in self.records:
            if verbose or r["verdict"] in ("MISMATCH", "MISSING", "ERROR", "UNVERIFIABLE",
                                           "KNOWN") or r.get("flag"):
                tag = r["verdict"] if r["verdict"] != "SKIP" else f"SKIP({r['why']})"
                out.append(f"  {tag:<12} {r['file']}:{r['line']}  {r['printed']!r}"
                           f"  computed {r['computed']}  [{r['check']}]"
                           + (f"  {r['why']}" if r["verdict"] != "SKIP" and r["why"] else "")
                           + (f"  {r['flag']}" if r.get("flag") else ""))
        cov = self.coverage
        if cov:
            for i, why in cov.stale:
                out.append(f"  STALE        row {i + 2} of claims.csv: {why}")
            for a, b in cov.duplicate:
                out.append(f"  DUPLICATE    rows {a + 2} and {b + 2} of claims.csv mark one number")
            for o, _ in cov.uncovered:
                out.append(f"  UNCOVERED    {o.file}:{o.line}  {o.text!r}")
        out += [f"  ERROR        {e}" for e in self.errors]
        return out

    def summary(self) -> list[str]:
        v = Counter(r["verdict"] for r in self.records)
        cats = Counter(r["category"] for r in self.records)
        skips = Counter(r["why"] for r in self.records if r["verdict"] == "SKIP")
        cov = self.coverage
        out = [f"  claims: {v['MATCH']} match, {v['MISMATCH']} mismatch, "
               f"{v['KNOWN']} known (author-accepted), "
               f"{v['MISSING']} missing input, "
               f"{v['SKIP']} skipped, {v['UNVERIFIABLE']} unverifiable, "
               f"{v['ERROR']} errors"]
        out.append("  by category: " + ", ".join(f"{k} {n}" for k, n in sorted(cats.items())))
        if skips:
            out.append("  skipped: " + ", ".join(f"{k} {n}" for k, n in sorted(skips.items())))
        if cov:
            out.append(f"  coverage: {self.n_occ} numbers in the manuscript, {self.n_rows} rows, "
                       f"{len(cov.matched)} tied, {len(cov.uncovered)} uncovered, "
                       f"{len(cov.stale)} stale, {len(cov.duplicate)} duplicate")
        else:
            out.append(f"  coverage: not checked ({self.n_rows} rows; no manuscript, "
                       "set AA_PAPER)")
        return out


def evaluate(row: dict, ctx: C.Ctx, line: int | str | None = None) -> dict:
    rec = {"id": row["id"], "file": row["file"], "line": line or row["line"],
           "printed": row["printed"], "category": row["category"], "check": row["check"],
           "computed": "", "verdict": "", "why": ""}
    cat = row["category"]
    if cat not in CATEGORIES:
        rec.update(verdict="ERROR", why=f"unknown category {cat!r}")
        return rec
    if cat == "unverifiable":
        rec.update(verdict="UNVERIFIABLE", why=row["note"] or row["source"])
        return rec
    if not row["check"]:
        if cat in ("literature", "design"):
            rec.update(verdict="SKIP", why=cat)
        else:
            rec.update(verdict="ERROR", why=f"a {cat} number needs a check")
        return rec
    fn = C.REGISTRY.get(row["check"])
    if fn is None:
        rec.update(verdict="ERROR", why=f"no check function {row['check']!r}")
        return rec
    kw = parse_args(row["args"])
    citation = C.is_citation_check(row["check"], kw)
    if not citation and not row["printed"]:
        rec.update(verdict="ERROR", why="no printed value")
        return rec
    if citation and ctx.citation_mode == "absent":
        rec.update(verdict="SKIP", why=CIT_ABSENT)
        return rec
    if not row["printed"]:
        rec.update(verdict="SKIP", why=FROM_PAPER if ctx.paper is None else NOT_IN_PAPER)
        return rec
    try:
        val = fn(ctx, **kw)
    except FileNotFoundError as e:
        what = os.path.relpath(e.filename, ctx.data) if e.filename else str(e)
        if fn.paper and ctx.paper is None:
            rec.update(verdict="SKIP", why=PAPER_ABSENT)
        elif fn.exempt:
            rec.update(verdict="SKIP", why=f"exempt input absent: {fn.exempt}")
        else:
            rec.update(verdict="MISSING", why=f"required input absent: {what}")
        return rec
    except Exception as e:  # noqa: BLE001 - reported, counted as a failure
        rec.update(verdict="ERROR", why=f"{type(e).__name__}: {e}")
        return rec
    rec["computed"] = show(val)
    try:
        if row["rule"] == "text":
            ok = " ".join(str(val).split()) == row["printed"]
        else:
            ok = compare(row["rule"], val, parse_printed(row["printed"], row["kind"]))
    except Exception as e:  # noqa: BLE001
        rec.update(verdict="ERROR", why=f"compare: {e}")
        return rec
    if citation and ctx.citation_mode != "strict":
        rec.update(verdict="SKIP", why=CIT_FRESH)
        if not ok:
            rec["flag"] = "(fresh citations: differs from the printed value)"
        return rec
    if ok:
        rec["verdict"] = "MATCH"
        if row["known"]:
            rec["flag"] = "(a known discrepancy now matches: clear its known flag)"
    elif row["known"]:
        rec.update(verdict="KNOWN", why=f"{row['known']}; {row['note']}".rstrip("; "))
    else:
        rec.update(verdict="MISMATCH", why=row["note"] or "")
    return rec


def run(data_dir: str, mode: str, claims_path: str = CLAIMS,
        paper: str | None = None) -> Report:
    """Every row's value check; with `paper` (the manuscript directory) also
    the coverage check."""
    rows = load(claims_path)
    rep = Report(n_rows=len(rows), paper=paper)
    ids = Counter(r["id"] for r in rows)
    rep.errors += [f"id {k} used {n} times" for k, n in ids.items() if n > 1]
    lines: dict[int, int] = {}
    if paper is not None:
        occ, norms = inv.inventory(paper)
        rep.coverage = match(rows, occ, norms)
        rep.n_occ = len(occ)
        lines = {i: o.line for i, o in rep.coverage.matched.items()}
    ctx = C.Ctx(data_dir, mode, paper=paper)
    for i, r in enumerate(rows):
        citation = bool(r["check"]) and C.is_citation_check(r["check"], parse_args(r["args"]))
        if r["printed"] and citation:
            rep.errors.append(f"row {i + 2} of claims.csv ({r['id']}) stores a citation "
                              "value; blank its printed field, it comes from the "
                              "manuscript")
            continue
        if not r["printed"] and not citation:
            rep.errors.append(f"row {i + 2} of claims.csv ({r['id']}) has no printed "
                              "value; only citation rows take theirs from the manuscript")
            continue
        if not r["printed"] and rep.coverage and i in rep.coverage.matched:
            # a citation row: the printed value is the manuscript's
            r = {**r, "printed": rep.coverage.matched[i].text}
        rep.records.append(evaluate(r, ctx, lines.get(i)))
    return rep


def citation_mode(data_dir: str) -> str:
    from citations.snapshot import mode
    return mode(os.path.join(data_dir, "per_paper", "citations"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=os.environ.get("AA_DATA", "data"))
    ap.add_argument("--mode", choices=["strict", "fresh", "absent"], default=None,
                    help="citation mode; default: from the local citation files")
    ap.add_argument("--claims", default=CLAIMS)
    ap.add_argument("--paper-dir", default=None,
                    help="the manuscript directory (default: $AA_PAPER)")
    ap.add_argument("--verbose", action="store_true", help="list every claim")
    ap.add_argument("--suggest", action="store_true",
                    help="print claims.csv rows for the uncovered numbers (needs the manuscript)")
    ap.add_argument("--sync-lines", action="store_true",
                    help="rewrite the line column of claims.csv (needs the manuscript)")
    ap.add_argument("--report-only", action="store_true",
                    help="exit 0 even on a failure (the pipeline stage; verify.py is the gate)")
    a = ap.parse_args()
    paper = paper_dir(a.paper_dir)

    if a.suggest or a.sync_lines:
        if paper is None:
            sys.exit("--suggest and --sync-lines need the manuscript: set AA_PAPER "
                     "or pass --paper-dir")
        rows = load(a.claims)
        occ, norms = inv.inventory(paper)
        cov = match(rows, occ, norms)
        if a.sync_lines:
            for i, o in cov.matched.items():
                rows[i]["line"] = str(o.line)
            save(rows, a.claims)
            print(f"synced {len(cov.matched)} rows; {len(cov.stale)} stale rows left as they were")
        if a.suggest:
            w = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
            for o, h in cov.uncovered:
                stem = os.path.splitext(os.path.basename(o.file))[0]
                print(f"{o.file}:{o.line}  ...{o.context}...", file=sys.stderr)
                w.writerow({"id": f"{stem}-{h[:8]}", "file": o.file, "line": o.line,
                            "printed": o.text, "kind": o.kind, "category": "", "check": "",
                            "args": "", "rule": "auto", "known": "", "source": "",
                            "note": "", "context_sha256": h})
        return

    m = a.mode or citation_mode(a.data_dir)
    rep = run(a.data_dir, m, a.claims, paper)
    print(f"TMLR claims, citation mode {m}"
          + ("" if paper else ", no manuscript (coverage skipped)"))
    for line in rep.lines(a.verbose) + rep.skip_lines() + rep.summary():
        print(line)
    if rep.failures and not a.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
