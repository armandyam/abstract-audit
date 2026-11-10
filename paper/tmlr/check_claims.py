#!/usr/bin/env python3
"""Check every number the TMLR paper prints against this repository's outputs.

Three files work together:

  inventory.py   finds every number in paper/tmlr/source/ (the manuscript
                 text, see import_source.py), macro invocations excepted:
                 check_macros.py compares the 163 macros value by value.
  claims.csv     one row per number: where it is, what kind of number it is,
                 and how to check it.
  claims.py      the check functions the rows name.

claims.csv columns:

  id        stable identifier, assigned once (file stem and a hash of the
            quote at the time the row was written); never reused
  file      the source file, relative to paper/tmlr/source/
  line      the line the number was on when the row was last synced
            (informational; --sync-lines rewrites it)
  quote     a snippet of the file's text, whitespace collapsed, with the
            number marked <<like this>>. It must occur exactly once in the
            file, and the marked text must be a number the inventory finds
            at that position. This is how a row is tied to its number.
  category  computed     measured, recomputed by `check`
            citation     measured from citation counts, recomputed in strict
                         citation mode, else read from the frozen published
                         outputs (reported as recomputation skipped)
            generated    a cell of a table make_macros.py generates; the
                         check compares the whole table with the built one
            literature   a value quoted from the cited literature (`source`)
            design       a constant of the study design, a scope count, a
                         window bound, a policy threshold or a label;
                         checked against the code when `check` is given
            unverifiable a measured number nothing in the release can
                         reproduce; reported, never silently passed
  check     a function in claims.py (empty for unchecked literature or
            design rows)
  args      its keyword arguments, key=value separated by semicolons; a
            list value joins items with +
  rule      how the computed value is compared with the printed one:
              auto         at the printed precision (default): the computed
                           value formatted with as many decimals as the
                           printed one equals it; a "2.8 million" compares
                           millions; a range or fraction compares element by
                           element
              abs          as auto on the absolute value ("1.07 lower")
              exact        equal
              gt ge lt le  computed > >= < <= printed ("more than 3,000")
              nearest:q    computed rounded to the nearest multiple of q
                           ("approximately 80 percent", nearest:10)
              approx:t     |computed - printed| <= t ("roughly ten")
              round:n      computed rounded to n digits, n may be negative
              within       a computed (min, max) inside the printed range
              claim:text   the check returns a string that must equal text
                           (the paper's named set, e.g. which metrics)
              true         the check returns True
  source    for literature, the work quoted; for design, what the constant
            is; otherwise where the value comes from
  note      anything else, such as a known disagreement awaiting a text fix

Results: MATCH, MISMATCH, SKIP(reason) and UNVERIFIABLE. The coverage check
fails if the inventory finds a number no row claims, or a row's quote no
longer marks a number in the source (stale). verify.py counts mismatches,
errors, uncovered numbers and stale rows as failures.

After the paper text changes:

  1. python paper/tmlr/import_source.py --upstream <research repo>/tmlr
  2. python paper/tmlr/check_claims.py        lists uncovered and stale rows
  3. python paper/tmlr/check_claims.py --suggest
                                              prints a claims.csv row with a
                                              unique quote for every
                                              uncovered number; paste and
                                              fill in category, check, args
  4. fix or delete each stale row (a reworded sentence usually needs only
     a new quote), then python paper/tmlr/check_claims.py --sync-lines

    python paper/tmlr/check_claims.py [--data-dir DIR] [--mode strict|fresh|absent]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
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

CLAIMS = os.path.join(HERE, "claims.csv")
FIELDS = ["id", "file", "line", "quote", "category", "check", "args", "rule",
          "source", "note"]
CATEGORIES = {"computed", "citation", "generated", "literature", "design",
              "unverifiable"}
OPEN, CLOSE = "<<", ">>"


# ============================================================ claims.csv ===

def load(path: str = CLAIMS) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in FIELDS:
            r.setdefault(k, "")
            r[k] = r[k] or ""
    return rows


def save(rows: list[dict], path: str = CLAIMS) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def make_id(file: str, quote: str) -> str:
    stem = os.path.splitext(os.path.basename(file))[0]
    return f"{stem}-{hashlib.sha1(quote.encode()).hexdigest()[:8]}"


def split_quote(quote: str) -> tuple[str, int, str]:
    """(plain text, offset of the marked number in it, marked text)."""
    a = quote.find(OPEN)
    b = quote.find(CLOSE, a + 2)
    if a < 0 or b < 0 or quote.find(OPEN, b) >= 0:
        raise ValueError(f"quote must mark exactly one number: {quote!r}")
    token = quote[a + 2:b]
    return quote[:a] + token + quote[b + 2:], a, token


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
    uncovered: list[inv.Occurrence] = field(default_factory=list)
    duplicate: list[tuple[int, int]] = field(default_factory=list)


def find_all(text: str, sub: str) -> list[int]:
    out, i = [], text.find(sub)
    while i >= 0:
        out.append(i)
        i = text.find(sub, i + 1)
    return out


def match(rows: list[dict], occ: list[inv.Occurrence],
          norms: dict[str, inv.Normalised]) -> Coverage:
    """Tie each row to the occurrence its quote marks; collect the rows that
    tie to none (stale) and the occurrences no row ties to (uncovered)."""
    cov = Coverage()
    by_pos = {(o.file, o.pos): o for o in occ}
    owner: dict[tuple[str, int], int] = {}
    for i, r in enumerate(rows):
        try:
            plain, off, token = split_quote(r["quote"])
        except ValueError as e:
            cov.stale.append((i, str(e)))
            continue
        if r["file"] not in norms:
            cov.stale.append((i, f"file {r['file']} is not part of the manuscript"))
            continue
        hits = find_all(norms[r["file"]].text, plain)
        if not hits:
            cov.stale.append((i, "quote not found"))
            continue
        if len(hits) > 1:
            cov.stale.append((i, f"quote occurs {len(hits)} times; lengthen it"))
            continue
        key = (r["file"], hits[0] + off)
        o = by_pos.get(key)
        if o is None or o.text != token:
            cov.stale.append((i, f"<<{token}>> is not an inventoried number there"
                                 + (f" (found {o.text!r})" if o else "")))
            continue
        if key in owner:
            cov.duplicate.append((owner[key], i))
            continue
        owner[key] = i
        cov.matched[i] = o
    cov.uncovered = [o for o in occ if (o.file, o.pos) not in owner]
    return cov


def suggest_quote(o: inv.Occurrence, norm: inv.Normalised, min_words: int = 3) -> str:
    """A quote around one occurrence that occurs once in the file: at least
    min_words words on each side, widened until unique."""
    t = norm.text
    a, b = o.pos, o.pos + len(o.text)
    spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", t)]
    i0 = next(i for i, (s, e) in enumerate(spans) if e > a)
    i1 = next(i for i, (s, e) in reversed(list(enumerate(spans))) if s < b)
    for k in range(min_words, len(spans) + 1):
        left = spans[max(0, i0 - k)][0]
        right = spans[min(len(spans) - 1, i1 + k)][1]
        if len(find_all(t, t[left:right])) == 1:
            break
    return t[left:a] + OPEN + o.text + CLOSE + t[b:right]


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
    n_occ: int = 0
    n_rows: int = 0
    errors: list[str] = field(default_factory=list)

    def count(self, verdict: str) -> int:
        return sum(1 for r in self.records if r["verdict"] == verdict)

    @property
    def failures(self) -> int:
        cov = self.coverage
        return (self.count("MISMATCH") + self.count("ERROR") + len(self.errors)
                + (len(cov.stale) + len(cov.uncovered) + len(cov.duplicate) if cov else 0))

    def lines(self, verbose: bool = False) -> list[str]:
        out = []
        for r in self.records:
            if verbose or r["verdict"] in ("MISMATCH", "ERROR", "UNVERIFIABLE"):
                tag = r["verdict"] if r["verdict"] != "SKIP" else f"SKIP({r['why']})"
                out.append(f"  {tag:<12} {r['file']}:{r['line']}  {r['printed']!r}"
                           f"  computed {r['computed']}  [{r['check']}]"
                           + (f"  {r['why']}" if r["verdict"] != "SKIP" and r["why"] else ""))
        cov = self.coverage
        if cov:
            for i, why in cov.stale:
                out.append(f"  STALE        row {i + 2} of claims.csv: {why}")
            for a, b in cov.duplicate:
                out.append(f"  DUPLICATE    rows {a + 2} and {b + 2} of claims.csv mark one number")
            for o in cov.uncovered:
                out.append(f"  UNCOVERED    {o.file}:{o.line}  {o.text!r}  ...{o.context}...")
        out += [f"  ERROR        {e}" for e in self.errors]
        return out

    def summary(self) -> list[str]:
        v = Counter(r["verdict"] for r in self.records)
        cats = Counter(r["category"] for r in self.records)
        skips = Counter(r["why"] for r in self.records if r["verdict"] == "SKIP")
        cov = self.coverage
        out = [f"  claims: {v['MATCH']} match, {v['MISMATCH']} mismatch, "
               f"{v['SKIP']} skipped, {v['UNVERIFIABLE']} unverifiable, "
               f"{v['ERROR']} errors"]
        out.append("  by category: " + ", ".join(f"{k} {n}" for k, n in sorted(cats.items())))
        if skips:
            out.append("  skipped: " + ", ".join(f"{k} {n}" for k, n in sorted(skips.items())))
        if cov:
            out.append(f"  coverage: {self.n_occ} numbers in the manuscript, {self.n_rows} rows, "
                       f"{len(cov.matched)} tied, {len(cov.uncovered)} uncovered, "
                       f"{len(cov.stale)} stale, {len(cov.duplicate)} duplicate")
        return out


def evaluate(row: dict, occ: inv.Occurrence, ctx: C.Ctx) -> dict:
    rec = {"id": row["id"], "file": row["file"], "line": occ.line,
           "printed": occ.text, "category": row["category"], "check": row["check"],
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
    try:
        val = fn(ctx, **kw)
    except FileNotFoundError as e:
        what = os.path.relpath(e.filename, ctx.data) if e.filename else str(e)
        rec.update(verdict="SKIP", why=f"input absent: {what}")
        return rec
    except Exception as e:  # noqa: BLE001 - reported, counted as a failure
        rec.update(verdict="ERROR", why=f"{type(e).__name__}: {e}")
        return rec
    rec["computed"] = show(val)
    try:
        ok = compare(row["rule"], val, parse_printed(occ.text, occ.kind))
    except Exception as e:  # noqa: BLE001
        rec.update(verdict="ERROR", why=f"compare: {e}")
        return rec
    frozen = citation and ctx.citation_mode != "strict"
    if ok:
        if frozen:
            rec.update(verdict="SKIP", why="recomputation skipped, frozen reference matches")
        else:
            rec["verdict"] = "MATCH"
    else:
        rec.update(verdict="MISMATCH",
                   why=(row["note"] or "") + (" (against the frozen reference)" if frozen else ""))
    return rec


def run(data_dir: str, mode: str, claims_path: str = CLAIMS,
        source: str = inv.SOURCE) -> Report:
    rows = load(claims_path)
    occ, norms = inv.inventory(source)
    cov = match(rows, occ, norms)
    rep = Report(coverage=cov, n_occ=len(occ), n_rows=len(rows))
    ids = Counter(r["id"] for r in rows)
    rep.errors += [f"id {k} used {n} times" for k, n in ids.items() if n > 1]
    ctx = C.Ctx(data_dir, mode, source=source)
    for i, r in enumerate(rows):
        if i in cov.matched:
            rep.records.append(evaluate(r, cov.matched[i], ctx))
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
    ap.add_argument("--source", default=inv.SOURCE)
    ap.add_argument("--verbose", action="store_true", help="list every claim")
    ap.add_argument("--suggest", action="store_true",
                    help="print claims.csv rows for the uncovered numbers")
    ap.add_argument("--sync-lines", action="store_true",
                    help="rewrite the line column of claims.csv from the source")
    ap.add_argument("--report-only", action="store_true",
                    help="exit 0 even on a failure (the pipeline stage; verify.py is the gate)")
    a = ap.parse_args()

    if a.suggest or a.sync_lines:
        rows = load(a.claims)
        occ, norms = inv.inventory(a.source)
        cov = match(rows, occ, norms)
        if a.sync_lines:
            for i, o in cov.matched.items():
                rows[i]["line"] = str(o.line)
            save(rows, a.claims)
            print(f"synced {len(cov.matched)} rows; {len(cov.stale)} stale rows left as they were")
        if a.suggest:
            w = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
            for o in cov.uncovered:
                q = suggest_quote(o, norms[o.file])
                w.writerow({"id": make_id(o.file, q), "file": o.file, "line": o.line,
                            "quote": q, "category": "", "check": "", "args": "",
                            "rule": "auto", "source": "", "note": ""})
        return

    m = a.mode or citation_mode(a.data_dir)
    rep = run(a.data_dir, m, a.claims, a.source)
    print(f"TMLR claims, citation mode {m}")
    for line in rep.lines(a.verbose) + rep.summary():
        print(line)
    if rep.failures and not a.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
