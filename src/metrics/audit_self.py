#!/usr/bin/env python3
"""
Audit one title and abstract with the pipeline's own per-paper metrics.

Runs the same code that produced every per-paper metric file on a single
title and abstract, and reports each value with its percentile in the NeurIPS
per-paper distribution (data/per_paper/{metric}/neurips.csv, so run the
pipeline or copy reference/per_paper/ there first).

The TMLR paper audits its own title and abstract this way (Appendix E,
Table tab:self-audit). To reproduce that table:

  python src/metrics/audit_self.py \\
      --title "Machine Learning Research Has Outpaced Its Communication Norms" \\
      --abstract-file paper/tmlr/self_audit_abstract.txt

The table's sentence-length row (Hohmann) is not reproduced: that per-paper
metric is not part of this release. The two novel-acronym counts in the table
are a judgment against the paper's approved-term list, not a computed value;
this script prints the acronyms it finds so the judgment can be checked.

Usage:
  python src/metrics/audit_self.py --title "..." --abstract-file abstract.txt
  python src/metrics/audit_self.py --from-tex paper.tex
  python src/metrics/audit_self.py ... --out audit.csv
"""

from __future__ import annotations
import argparse
import os
import re
import sys

import pandas as pd
from scipy.stats import percentileofscore

_SRC = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _SRC)  # allows direct invocation

import metrics.acronyms as acronyms  # noqa: E402
import metrics.nlp_features as nlp_features  # noqa: E402
import metrics.readability as readability  # noqa: E402
from metrics._narrator_utils import (  # noqa: E402
    HYPE_CATEGORIES, count_hedging, count_hype, count_signposting, has_narrator,
    preprocess, word_count,
)
from metrics.linguistic_complexity import _compute as lc_compute  # noqa: E402

PP = os.path.join(os.environ.get("AA_DATA", "data"), "per_paper")

READABILITY = [
    ("Flesch Reading Ease", "flesch_ease"), ("Flesch-Kincaid Grade", "flesch_kincaid"),
    ("Gunning Fog", "gunning_fog"), ("SMOG", "smog"), ("Dale-Chall", "dale_chall"),
    ("Spache", "spache"), ("Coleman-Liau", "coleman_liau"), ("ARI", "ari"),
    ("Linsear Write", "linsear_write"), ("LIX", "lix"), ("RIX", "rix"),
    ("FORCAST", "forcast"), ("Powers-Sumner-Kearl", "powers_sumner_kearl"),
    ("Words per sentence", "avg_sentence_length"),
    ("Syllables per word", "avg_syllables_per_word"),
]


def pct(metric_dir: str, col: str, value, per_paper: str = PP) -> float:
    """Percentile of `value` in the NeurIPS per-paper distribution for `col`."""
    if value is None:
        return float("nan")
    path = os.path.join(per_paper, metric_dir, "neurips.csv")
    s = pd.read_csv(path, usecols=[col])[col].dropna()
    return round(percentileofscore(s.values, value, kind="rank"), 1)


def _strip_tex(t: str) -> str:
    """Reduce LaTeX to the words a reader actually sees."""
    t = re.sub(r"(?<!\\)%.*", "", t)                # comments, not an escaped \\%
    t = re.sub(r"\\cite[tp]?\*?(\[[^]]*\])*\{[^}]*\}", "", t)   # citations
    t = re.sub(r"\\(ref|label|input)\{[^}]*\}", "", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^]]*\])*\{([^{}]*)\}", r"\2", t)  # \textbf{x} -> x
    t = re.sub(r"\\[a-zA-Z]+", " ", t)              # bare macros
    t = t.replace("~", " ").replace("\\%", "%")
    t = re.sub(r"[{}$]", "", t)
    return " ".join(t.split())


def _braced_arg(src: str, command: str) -> str:
    """The balanced {...} argument that follows the first `command{`."""
    i = src.index(command + "{") + len(command) + 1
    depth = 1
    for j in range(i, len(src)):
        c = src[j]
        if c == "{" and src[j - 1] != "\\":
            depth += 1
        elif c == "}" and src[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return src[i:j]
    raise SystemExit(f"unbalanced braces after {command}")


def read_from_tex(path: str) -> tuple[str, str]:
    """Pull \\title{...} and the abstract environment out of a manuscript.

    Macros defined in \\input{generated_*} files next to the manuscript are
    expanded first, so numbers produced by a generator are audited as printed.
    """
    src = open(path, encoding="utf-8").read()
    src = re.sub(r"(?m)^\s*%.*$", "", src)
    here = os.path.dirname(os.path.abspath(path))
    for name in re.findall(r"\\input\{(generated_[^}]*)\}", src):
        f = os.path.join(here, name if name.endswith(".tex") else name + ".tex")
        defs = re.findall(r"\\newcommand\{\\([A-Za-z]+)\}\{(.*)\}\s*$",
                          open(f, encoding="utf-8").read(), re.M)
        for macro, value in defs:
            src = re.sub(r"\\" + macro + r"(?![A-Za-z])(\{\})?",
                         lambda _m, v=value: v, src)
    title = _strip_tex(_braced_arg(src, "\\title")) if "\\title{" in src else ""
    a = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", src, re.S)
    if not a:
        raise SystemExit(f"no abstract environment found in {path}")
    return title, _strip_tex(a.group(1))


def audit(title: str, abstract: str, nlp, per_paper: str = PP) -> pd.DataFrame:
    """One row per metric: family, metric, title value, abstract value, and the
    abstract value's percentile among NeurIPS abstracts."""
    rows = []

    def add(family, label, t, a, metric_dir, col):
        rows.append({"family": family, "metric": label, "title": t, "abstract": a,
                     "percentile": pct(metric_dir, col, a, per_paper)})

    # Classical readability, on the raw text as readability.py scores it.
    rd_t, rd_a = readability.compute(title), readability.compute(abstract)
    for label, col in READABILITY:
        add("readability", label, rd_t.get(col), rd_a.get(col), "readability", col)

    # Writing style. linguistic_complexity.py parses the raw abstract;
    # nlp_features.py and the narrator family use the preprocessed abstract.
    pa = preprocess(abstract)
    nw = word_count(pa)

    def per100(c):
        return round(c / (nw or 1) * 100, 4)

    lc = lc_compute(nlp(abstract))
    doc = nlp(pa)
    nouns = sum(1 for t in doc if t.pos_ == "NOUN")
    verbs = sum(1 for t in doc if t.pos_ == "VERB")
    nums = sum(1 for t in doc if t.pos_ == "NUM")
    chunks = nlp_features._noun_chunks(doc)
    style = [
        ("Parse depth", lc["parse_depth"], "parse_depth", "parse_depth"),
        ("NP density", lc["np_density"], "np_density", "np_density"),
        ("Noun chunks /100", per100(chunks), "noun_chunks", "noun_chunks_per_100"),
        ("Nouns /100", per100(nouns), "nouns", "noun_per_100"),
        ("Verbs /100", per100(verbs), "verbs", "verb_per_100"),
        ("Numbers /100", per100(nums), "numbers", "num_per_100"),
        ("Sign posting /100", per100(count_signposting(pa)), "signposting", "signposting_per_100"),
        ("Hedging /100", per100(count_hedging(pa)), "hedging", "hedging_per_100"),
        ("Active narration", float(has_narrator(pa)), "active_narration", "has_narrator"),
        ("Passive rate", lc["passive_rate"], "passive_rate", "passive_rate"),
        ("Type-token ratio", lc["ttr"], "ttr", "ttr"),
    ]
    for label, value, metric_dir, col in style:
        add("style", label, None, value, metric_dir, col)

    # Sensational language, per category and in total.
    sens = count_hype(pa)
    for cat in HYPE_CATEGORIES:
        add("sensational", cat.capitalize(), None, per100(sens[cat]),
            "sensational_language", f"hype_{cat}_per_100")
    add("sensational", "Total", None, per100(sum(sens.values())),
        "sensational_language", "hype_total_per_100")

    # Acronym density, title and abstract, as acronyms.py computes it.
    acr = acronyms.compute_row({"paper_id": "audit", "venue": "neurips", "year": 0,
                                "title": title, "abstract": abstract,
                                "arxiv_primary_category": ""})
    add("acronyms", "Acronym density /100", acr["title_acronym_density"],
        acr["abstract_acronym_density"], "acronyms", "abstract_acronym_density")
    out = pd.DataFrame(rows)
    out.attrs["title_acronyms"] = acr.get("title_acronyms", "")
    out.attrs["abstract_acronyms"] = acr.get("abstract_acronyms", "")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--title", default="", help="Title to audit")
    ap.add_argument("--abstract-file", help="Plain-text file holding the abstract only")
    ap.add_argument("--from-tex", help="Read \\title and the abstract environment from "
                                       "a manuscript .tex (overrides the other two)")
    ap.add_argument("--out", help="Also write the results to this CSV")
    args = ap.parse_args()

    if args.from_tex:
        title, abstract = read_from_tex(args.from_tex)
    elif args.abstract_file:
        title = args.title
        abstract = " ".join(open(args.abstract_file, encoding="utf-8").read().split())
    else:
        ap.error("give --abstract-file (with --title) or --from-tex")
    if not abstract:
        sys.exit("the abstract is empty")
    print(f"auditing title:    {title}")
    print(f"auditing abstract: {len(abstract.split())} words\n")

    import spacy
    df = audit(title, abstract, spacy.load("en_core_web_sm"))

    def f(v):
        return "--" if v is None or pd.isna(v) else f"{v:.2f}"
    for family, g in df.groupby("family", sort=False):
        print(f"{family}")
        for r in g.itertuples():
            print(f"  {r.metric:25s} title {f(r.title):>7}  abstract {f(r.abstract):>7}  "
                  f"NeurIPS percentile {r.percentile}")
    print(f"\nacronyms found: title [{df.attrs['title_acronyms']}]  "
          f"abstract [{df.attrs['abstract_acronyms']}]")
    if args.out:
        df.to_csv(args.out, index=False)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
