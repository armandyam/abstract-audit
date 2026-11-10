"""Tests for the TMLR claim check (paper/tmlr/inventory.py, claims.py,
check_claims.py).

verify.py runs the check on the full outputs. What is tested here is what
that run cannot isolate: the tokenizer on LaTeX the manuscript happens not to
contain (or contains only once), the context-hash coverage logic on
deliberately broken rows, the comparison rules, a few check functions on
synthetic series with a known answer, and the committed claims.csv, which
must hold no manuscript text. The manuscript is not distributed; one test
ties claims.csv to it when $AA_PAPER points at a local copy, and is skipped
otherwise.
"""
import os
import re
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "paper", "tmlr"))

import check_claims as cc  # noqa: E402
import claims as C  # noqa: E402
import inventory as inv  # noqa: E402
from manuscript import paper_dir  # noqa: E402


def toks(text, is_main=False):
    norm = inv.Normalised.of(text)
    return [(norm.text[norm.pos[t.start]:norm.pos[t.end]], t.kind)
            for t in inv.tokens_in(text, is_main)]


def texts(text, is_main=False):
    return [t for t, _ in toks(text, is_main)]


# ── tokenizer ───────────────────────────────────────────────────────────

def test_numerals_thousands_decimals_percent_and_signs():
    assert texts(r"NeurIPS (30,595 papers) and 2{,}823{,}623 at 31.2\% and 5%") == \
        ["30,595", "2{,}823{,}623", "31.2\\%", "5%"]
    assert texts(r"& $-16.14$ & \textbf{+1.79} & -0.01 \\") == ["-16.14", "+1.79", "-0.01"]


def test_suffixes_ordinals_decades_plus_and_dates():
    assert texts("the 89.0th and 100th percentile in the 1990s, 1000+ uses") == \
        ["89.0th", "100th", "1990s", "1000+"]
    assert toks("retrieved on 2026-05-11 at the 2026-04 snapshot") == \
        [("2026-05-11", "date"), ("2026-04", "date")]


def test_identifiers_glued_to_letters_are_not_numbers():
    assert texts(r"T1 & 3d, Mixtral-8x7B, Qwen2.5-32B, v0.3, s2, P7") == []
    # a version after a hyphen is kept: it is printed and must be accounted for
    assert texts("Llama-3.1-8B-Instruct") == ["3.1"]


def test_pairs_join_like_numbers_only():
    assert toks("roughly 88 to 90 percent, 2015--2025, three to five") == \
        [("88 to 90", "pair"), ("2015--2025", "pair"), ("three to five", "pair")]
    # a year and a decimal are two numbers, not a range
    assert texts("grows from 3.25 in 1994 to 6.75 in 2021") == ["3.25", "1994 to 6.75"][:1] + \
        ["1994", "6.75", "2021"]


def test_fractions_and_spelled_quantities():
    assert toks("on twelve of fifteen metrics; Fourteen of the 15; 14 of the 15") == \
        [("twelve of fifteen", "fraction"), ("Fourteen of the 15", "fraction"),
         ("14 of the 15", "fraction")]
    got = texts("roughly a quarter, half as much, three quarters, a twelvefold rise, "
                "once and twice, roughly tripling, the ninth, the first percentile")
    assert got == ["quarter", "half", "three quarters", "twelvefold", "once", "twice",
                   "tripling", "ninth", "first"]


def test_enumerating_first_and_second_and_vague_words_are_excluded():
    assert texts("First, the second step; several dozens of papers a decade ago") == []
    assert texts("the first two components") == ["two"]


def test_scaled_numbers_are_one_occurrence():
    assert texts("2.8 million arXiv papers and 7 to 32 billion parameters") == \
        ["2.8 million", "7 to 32 billion"]


def test_structural_latex_is_masked():
    t = (r"see \citet{barnett2020growth} and \cite{a2019, b2020} in "
         r"Table~\ref{tab:x}\label{fig:2} \vspace{2mm} \input{figs/f1.tex} "
         r"\url{https://x.org/2401} \multicolumn{3}{l}{Classical (15)} "
         r"\begin{tabular}{p{0.20\textwidth}lr} \begin{minipage}[t]{0.48\linewidth}")
    assert texts(t) == ["15"]


def test_comments_are_ignored_by_read_text(tmp_path):
    p = tmp_path / "a.tex"
    p.write_text("value 12 % not 13\nescaped 5\\% kept % 7 dropped\n")
    assert texts(inv.read_text(str(p))) == ["12", "5\\%"]


def test_main_preamble_is_masked():
    t = ("\\documentclass[10pt]{article}\\def\\month{11}\n\\begin{document}\n"
         "We find 42 things.\n\\end{document}")
    assert texts(t, is_main=True) == ["42"]
    assert texts(t, is_main=False) == ["11", "42"]     # 10pt is a length


def test_tikz_keeps_visible_text_only():
    t = (r"\begin{tikzpicture}\begin{axis}[ymin=0, ymax=5.5, xtick distance=8, "
         r"title={Panel 2}, ylabel={per 100 words}]"
         r"\addplot[color={rgb,255:red,44;green,160;blue,44}, domain=1987:2025] {2.40};"
         r"\addlegendentry{Barnett 2020 (2.40)}"
         r"\addplot table[x=year]{data/x.csv};"
         r"\draw (axis cs:2022,0) -- (axis cs:2022,100);"
         r"\node[above=1mm of s1] (n) at (3,4) {NeurIPS 1987--2025};"
         r"\end{axis}\end{tikzpicture} caption 7")
    assert texts(t) == ["2", "100", "2.40", "2020", "2.40", "1987--2025", "7"]


def test_macro_definitions_and_parameters_are_masked():
    t = (r"\providecommand{\panel}[2]{\nextgroupplot[title={#1}] "
         r"\draw ({axis cs:2022,0} |- {rel axis cs:0,1});} after 3")
    assert texts(t) == ["3"]


# ── coverage ────────────────────────────────────────────────────────────

@pytest.fixture
def mini_source(tmp_path):
    (tmp_path / "tables").mkdir()
    (tmp_path / "main.tex").write_text(
        "\\begin{document}\nWe count 12 papers and 12 more,\n"
        "then 7 from 2015.\n\\input{tables/t.tex}\n\\end{document}\n")
    (tmp_path / "tables" / "t.tex").write_text("A & 3.5 \\\\\n")
    return str(tmp_path)


def row(file, printed, h="", cat="design", **kw):
    r = {k: "" for k in cc.FIELDS}
    r.update(id=f"{file}-{printed}-{h[:6]}", file=file, printed=printed,
             kind="number", category=cat, context_sha256=h, **kw)
    return r


def rows_for(source):
    """One row per occurrence, with its context hash: a complete claims.csv."""
    occ, norms = inv.inventory(source)
    return [row(o.file, o.text, h) for o, h in zip(occ, inv.context_hashes(occ, norms))], \
        occ, norms


def test_coverage_ties_every_number(mini_source):
    rows, occ, norms = rows_for(mini_source)
    assert [o.text for o in occ] == ["12", "12", "7", "2015", "3.5"]
    cov = cc.match(rows, occ, norms)
    assert len(cov.matched) == 5 and not cov.uncovered and not cov.stale


def test_context_hash_depends_on_the_words_around_the_number(mini_source, tmp_path):
    rows, occ, norms = rows_for(mini_source)
    h = inv.context_hashes(occ, norms)
    assert len(set(h)) == len(h) == 5 and all(len(x) == 64 for x in h)
    # the same text gives the same hashes; a reworded sentence changes them
    assert inv.context_hashes(*inv.inventory(mini_source)) == h
    main = os.path.join(mini_source, "main.tex")
    with open(main) as fh:
        text = fh.read()
    with open(main, "w") as fh:
        fh.write(text.replace("then 7 from", "then seven from"))
    occ2, norms2 = inv.inventory(mini_source)
    cov = cc.match(rows, occ2, norms2)
    # every number within CONTEXT_WORDS of the edit goes stale; the table's does not
    stale = [r["printed"] for i, r in enumerate(rows) if i in dict(cov.stale)]
    assert "7" in stale and "2015" in stale and "3.5" not in stale
    assert "seven" in [o.text for o, _ in cov.uncovered]


def test_coverage_reports_stale_changed_printed_duplicates_and_foreign_files(mini_source):
    rows, occ, norms = rows_for(mini_source)
    rows[1]["context_sha256"] = "0" * 64                 # no such context
    rows[2]["printed"] = "8"                             # the paper prints 7
    rows.append(dict(rows[3], id="dup"))                 # 2015 claimed twice
    rows.append(row("other.tex", "1", "f" * 64))         # not a manuscript file
    cov = cc.match(rows, occ, norms)
    why = dict(cov.stale)
    assert why[1].startswith("context hash not found")
    assert why[2] == "printed '8', manuscript has '7'"
    assert "not part of the manuscript" in why[6]
    assert cov.duplicate == [(3, 5)]
    assert sorted(o.text for o, _ in cov.uncovered) == ["12", "7"]


def test_committed_claims_hold_no_manuscript_text():
    with open(cc.CLAIMS, encoding="utf-8") as fh:
        header = fh.readline().strip().split(",")
    assert header == cc.FIELDS and "quote" not in header
    rows = cc.load()
    assert len({r["id"] for r in rows}) == len(rows)
    assert len({(r["file"], r["context_sha256"]) for r in rows}) == len(rows)
    words = "|".join(sorted(set(inv.CARDINALS) | set(inv.ORDINALS) | set(inv.OTHER_WORDS)
                            | {"first"}, key=len, reverse=True))
    number = (r"[-+]?[\d.,{}]+(?:\\%|%|th|st|nd|rd|s|fold|\+)?(?: million| billion)?"
              r"|\d{4}-\d{2}(?:-\d{2})?|(?:" + words + r")(?:fold)?(?: quarters| thirds)?")
    form = re.compile(rf"(?i)(?:{number})(?:(?: to |--|–| of (?:the )?)(?:{number}))?")
    for r in rows:
        assert re.fullmatch(r"[0-9a-f]{64}", r["context_sha256"]), r["id"]
        assert form.fullmatch(r["printed"]), (r["id"], r["printed"])
        assert r["category"] in cc.CATEGORIES, r["id"]
        assert not r["check"] or r["check"] in C.REGISTRY, r["id"]
        # only literature and design may go unchecked
        assert r["check"] or r["category"] in ("literature", "design", "unverifiable"), r["id"]
    # exactly the two discrepancies the authors kept in the published text
    assert sorted(r["id"] for r in rows if r["known"]) == ["main-88bd9f21", "main-8e45b1be"]


@pytest.mark.skipif(paper_dir() is None, reason="needs the manuscript: set AA_PAPER")
def test_committed_claims_cover_the_manuscript():
    rows = cc.load()
    occ, norms = inv.inventory(paper_dir())
    cov = cc.match(rows, occ, norms)
    assert not cov.uncovered and not cov.stale and not cov.duplicate


# ── printed values and rules ────────────────────────────────────────────

def parts(text, kind="number"):
    return cc.parse_printed(text, kind)


def test_parse_printed_forms():
    assert parts("2{,}823{,}623")[0].value == 2823623
    p = parts("2.8 million")[0]
    assert (p.value, p.decimals, p.scale) == (2.8, 1, 1e6)
    assert [x.value for x in parts("Fourteen of the 15", "fraction")] == [14, 15]
    assert [x.value for x in parts("2015--2025", "pair")] == [2015, 2025]
    assert parts("three quarters", "word")[0].value == 0.75
    assert parts("twelvefold", "word")[0].value == 12
    assert parts("89.0th")[0].value == 89.0 and parts("89.0th")[0].decimals == 1
    assert parts("-0.52")[0].sign and parts("31.2\\%")[0].value == 31.2


def test_compare_rules():
    assert cc.compare("auto", 23.7267, parts("24"))
    assert not cc.compare("auto", 79.55, parts("79"))
    assert cc.compare("auto", 2823623, parts("2.8 million"))
    assert cc.compare("auto", (10.41, 12.49), parts("10 to 12", "pair"))
    assert cc.compare("abs", -1.0701, parts("1.07"))
    assert cc.compare("gt", 3339, parts("3,000")) and not cc.compare("lt", 3339, parts("3,000"))
    assert cc.compare("nearest:10", 79.27, parts("80"))
    assert cc.compare("nearest:0.5", (0.52, 0.62), parts("half", "word"))
    assert cc.compare("approx:1", 9.21, parts("ten", "word"))
    assert cc.compare("round:-2", 5823, parts("5,800"))
    assert cc.compare("within", (57.5, 60.71), parts("57 to 61", "pair"))
    assert not cc.compare("within", (56.9, 60.71), parts("57 to 61", "pair"))
    assert cc.compare("claim:a+b", "a+b", parts("2015")) and not cc.compare("claim:a", "b", parts("1"))
    assert cc.compare("true", True, parts("2025")) and not cc.compare("true", 1, parts("2025"))
    assert cc.compare("exact", "2026-05-11", parts("2026-05-11"))
    with pytest.raises(ValueError):
        cc.compare("bogus", 1, parts("1"))


# ── check functions on synthetic data ───────────────────────────────────

def write_series(root, name, years, cols):
    d = os.path.join(root, "pgfplots", "tmlr")
    os.makedirs(d, exist_ok=True)
    df = pd.DataFrame({"year": years, **cols})
    df.to_csv(os.path.join(d, f"{name}.csv"), index=False)


@pytest.fixture
def synthetic(tmp_path):
    """Readability series 2015..2025 in which every metric gets harder at
    every venue except mean sentence length, and SMOG on ICLR rises by 2 then
    by 1 (no acceleration after 2020)."""
    years = list(range(2015, 2026))
    t = np.arange(len(years), dtype=float)
    for m in C.READABILITY:
        cols = {}
        for v in C.ML + ["arxiv_nonml", "pubmed"]:
            harder = C.HARDER_SIGN[m] * (0.1 * t + 0.02 * t ** 2)
            if m == "avg_sentence_length":
                harder = -harder
            cols[v] = 10 + harder
        if m == "smog":
            cols["iclr"] = np.array([10 + (0.4 * k if k <= 5 else 2 + 0.2 * (k - 5)) for k in t])
        write_series(str(tmp_path), f"readability_{m}", years, cols)
    return C.Ctx(str(tmp_path), "absent")


def test_readability_harder_counts_metrics_harder_everywhere(synthetic):
    assert C.readability_harder(synthetic, venues="neurips+iclr+icml") == (14, 15)
    assert C.readability_harder(synthetic, what="other") == 1


def test_acceleration_exceptions_uses_endpoint_changes(synthetic):
    assert C.acceleration_exceptions(synthetic) == 1
    assert C.acceleration_exceptions(synthetic, venues="neurips+icml") == 0


def test_steepest_fall_and_slope_ratio(tmp_path):
    years = list(range(2010, 2026))
    fl = {"neurips": [30 - (5 if y == 2024 else 0) - 0.5 * i for i, y in enumerate(years)],
          "arxiv_nonml": [30 - 0.25 * i for i in range(len(years))]}
    fl["neurips"] = list(np.cumsum([30] + [-(5 if y == 2024 else 0.5) for y in years[1:]]))
    write_series(str(tmp_path), "readability_flesch_ease", years, fl)
    ctx = C.Ctx(str(tmp_path), "absent")
    assert C.steepest_fall_year(ctx, cols="neurips") == 2024
    s = C.slope(ctx, "readability_flesch_ease", "arxiv_nonml", "neurips")
    assert s == pytest.approx(-0.25)
    assert C.slope_ratio(ctx, "readability_flesch_ease", "neurips", "arxiv_nonml") > 1


def test_style_gap_classification(tmp_path):
    years = list(range(2015, 2026))
    for m in C.STYLE:
        widen = 5.0 if m == "parse_depth" else (-0.2 if m == "numbers" else 0.05)
        ml = [1 + widen * i / 10 for i in range(len(years))]
        if m == "numbers":                       # a gap of 0.2 that closes
            ml = [1.2 - 0.2 * i / 10 for i in range(len(years))]
        cols = {v: ml for v in C.ML}
        # PubMed spreads the metric's SD to about 3 so 0.05 is marginal
        cols.update(arxiv_nonml=[1.0] * len(years), pubmed=list(np.linspace(0, 10, len(years))))
        write_series(str(tmp_path), m, years, cols)
    ctx = C.Ctx(str(tmp_path), "absent")
    assert C.style_gap_set(ctx, "clear") == "parse_depth"
    assert C.style_gap_set(ctx, "narrow") == "numbers"
    assert C.style_gap_count(ctx, "marginal") == 10
    assert C.style_gap_count(ctx, "total") == 12


def test_reuse_share_counts_distinct_acronyms_below_ten(tmp_path):
    pp = tmp_path / "per_paper" / "acronyms"
    pp.mkdir(parents=True)
    for v in C.CONFS:
        pd.DataFrame({"abstract_acronyms": ["|".join(["AB"] * 10), "CD|EF", "CD", ""]}) \
          .to_csv(pp / f"{v}.csv", index=False)
    (tmp_path / "baselines").mkdir()
    pd.DataFrame({"group": ["pubmed", "pubmed"], "occurrences": [1, 12],
                  "acronym_types": [3, 1]}).to_csv(tmp_path / "baselines" / "acronym_histograms.csv",
                                                   index=False)
    ctx = C.Ctx(str(tmp_path), "absent", repo=str(tmp_path))
    assert C.reuse_share(ctx, "neurips") == pytest.approx(200 / 3)   # CD, EF of AB, CD, EF
    assert C.reuse_share(ctx, "pubmed") == pytest.approx(75.0)
    assert C.reuse_share(ctx, "bd") == 79.0


def test_citation_checks_read_the_local_outputs_and_skip_without_counts(tmp_path):
    ctx = C.Ctx(str(tmp_path), "strict")
    assert ctx.cit_dir == os.path.join(str(tmp_path), "aggregate", "citations")
    assert C.is_citation_check("cit_value", {}) and not C.is_citation_check("series", {})
    assert C.is_citation_check("generated_cell", {"table": "topics.tex"})
    assert not C.is_citation_check("generated_cell", {"table": "topic_trends.tex"})
    r = row("main.tex", "2024", cat="citation", check="cit_max_year", rule="exact")
    rec = cc.evaluate(r, C.Ctx(str(tmp_path), "absent"))
    assert (rec["verdict"], rec["why"]) == ("SKIP", cc.CIT_ABSENT)
    # strict: an absent output is a failure, as for any other measured number
    assert cc.evaluate(r, ctx)["verdict"] == "MISSING"
    cit = tmp_path / "aggregate" / "citations"
    cit.mkdir(parents=True)
    pd.DataFrame({"venue": C.CONFS, "max_year": [2024] * 3}).to_csv(
        cit / "citation_coverage.csv", index=False)
    assert cc.evaluate(r, ctx)["verdict"] == "MATCH"
    fresh = cc.evaluate(dict(r, printed="2023"), C.Ctx(str(tmp_path), "fresh"))
    assert (fresh["verdict"], fresh["why"]) == ("SKIP", cc.CIT_FRESH) and fresh["flag"]


def test_evaluate_absent_input_fails_unless_exempt(tmp_path):
    ctx = C.Ctx(str(tmp_path), "absent")
    # the documented exemption: the raw scrape
    r = row("main.tex", "67", cat="computed", check="neurips_fallback_count", rule="exact")
    rec = cc.evaluate(r, ctx)
    assert rec["verdict"] == "SKIP" and rec["why"].startswith("exempt input absent")
    assert "raw/neurips" in rec["why"]
    # the self-audit is skipped without the manuscript, and fails with it
    r = row("main.tex", "67", cat="computed", check="self_audit", args="metric=SMOG")
    rec = cc.evaluate(r, ctx)
    assert rec["verdict"] == "SKIP" and rec["why"].startswith("manuscript absent")
    assert cc.evaluate(r, C.Ctx(str(tmp_path), "absent", paper=str(tmp_path)))["verdict"] \
        == "MISSING"
    # any other absent input is a failure, never a skip
    for check, args in [("series", "metric=readability_flesch_ease;col=neurips;year=2015"),
                        ("generated_cell", "table=topic_trends.tex;n=0"),
                        ("topic_cell", "row=0;col=papers")]:
        r = row("main.tex", "67", cat="computed", check=check, args=args, rule="text")
        rec = cc.evaluate(r, ctx)
        assert rec["verdict"] == "MISSING", (check, rec)
        assert rec["why"].startswith("required input absent")
    r = row("main.tex", "67", cat="computed", check="no_such_check")
    assert cc.evaluate(r, ctx)["verdict"] == "ERROR"
    r = row("main.tex", "67", cat="computed")
    assert cc.evaluate(r, ctx)["verdict"] == "ERROR"
    r = row("main.tex", "67", cat="unverifiable", note="why")
    assert cc.evaluate(r, ctx)["verdict"] == "UNVERIFIABLE"


def test_known_discrepancy_is_reported_not_failed(tmp_path):
    raw = tmp_path / "raw" / "neurips"
    raw.mkdir(parents=True)
    pd.Series([{"title": "t", "abstract": "Abstract Unavailable",
                "full_text": " ".join(["w"] * 30)}]).to_json(
        raw / "neurips_1990_data.json", orient="values")
    ctx = C.Ctx(str(tmp_path), "absent")
    r = row("main.tex", "67", cat="computed", check="neurips_fallback_count", rule="exact",
            known="kept as printed", note="computed 1")
    rec = cc.evaluate(r, ctx)
    assert rec["verdict"] == "KNOWN" and rec["computed"] == "1"
    rep = cc.Report(records=[rec])
    assert rep.failures == 0 and "1 known" in rep.summary()[0]
    assert any("KNOWN" in ln for ln in rep.lines())
    # a known row that matches is flagged so the flag can be cleared
    rec = cc.evaluate(dict(r, printed="1"), ctx)
    assert rec["verdict"] == "MATCH" and "clear" in rec["flag"]


def test_missing_counts_as_failure_and_skips_are_listed_by_reason():
    rep = cc.Report()
    base = {"file": "main.tex", "line": 1, "printed": "1", "category": "computed",
            "check": "c", "computed": ""}
    rep.records = [dict(base, verdict="MISSING", why="required input absent: x"),
                   dict(base, verdict="SKIP", why="design"),
                   dict(base, verdict="SKIP", why="design"),
                   dict(base, verdict="SKIP", why="exempt input absent: raw"),
                   dict(base, verdict="MATCH", why="")]
    assert rep.missing == 1 and rep.failures == 1
    lines = rep.skip_lines()
    assert "  SKIP    2  design" in lines
    i = lines.index("  SKIP    1  exempt input absent: raw")
    assert "main.tex:1" in lines[i + 1]                      # listed, not just counted
    assert any("MISSING" in ln for ln in rep.lines())
    assert "1 missing input" in rep.summary()[0]


def test_only_documented_checks_are_exempt():
    assert {n for n, c in C.REGISTRY.items() if c.exempt} == {"neurips_fallback_count"}


# ── generated tables: cells, and the topics table in every mode ─────────

def _topic_inputs(tmp_path):
    agg = tmp_path / "aggregate"
    agg.mkdir(parents=True, exist_ok=True)
    src = os.path.join(ROOT, "reference", "tmlr", "analysis", "topic_profiles.csv")
    df = pd.read_csv(src)
    df.to_csv(agg / "topic_profiles.csv", index=False)
    return df, agg


@pytest.mark.parametrize("mode", ["strict", "fresh", "absent"])
def test_topic_cells_come_from_the_regenerated_profiles(tmp_path, mode):
    df, agg = _topic_inputs(tmp_path)
    ctx = C.Ctx(str(tmp_path), mode)
    assert not C.is_citation_check("topic_cell", {})
    first = df.sort_values("flesch").iloc[0]
    assert C.topic_cell(ctx, 0, "flesch") == f"{first.flesch:.1f}"
    assert C.topic_cell(ctx, 0, "papers") == f"{int(first.n):,}".replace(",", "{,}")
    rows = [r for r in cc.load() if r["check"] == "topic_cell"]
    printed = {r["args"]: r["printed"] for r in rows}
    assert all(C.topic_cell(ctx, **cc.parse_args(a)) == p for a, p in printed.items())
    df.loc[df.flesch.idxmin(), "n"] += 1                   # one paper count off
    df.to_csv(agg / "topic_profiles.csv", index=False)
    assert C.topic_cell(C.Ctx(str(tmp_path), mode), 0, "papers") != printed["row=0;col=papers"]


def test_generated_cell_is_the_nth_number_of_the_built_table(tmp_path):
    t = tmp_path / "tmlr" / "tables"
    t.mkdir(parents=True)
    (t / "x.tex").write_text("\\begin{tabular}{lr}\nA & 3{,}551 & $-1.5$ \\\\\n"
                             "\\end{tabular}\n\\caption{over 12 years}\n")
    ctx = C.Ctx(str(tmp_path), "absent")
    assert [C.generated_cell(ctx, "x.tex", n) for n in range(3)] == ["3{,}551", "-1.5", "12"]


def test_topics_rows_split_papers_and_flesch_from_median_citations():
    t = [r for r in cc.load() if r["file"] == "tables/topics.tex"]
    cells = [r for r in t if r["check"] == "topic_cell"]
    cit = [r for r in t if r["check"] == "generated_cell"]
    assert len(cells) == 30 and len(cit) == 15
    assert {cc.parse_args(r["args"])["col"] for r in cells} == {"papers", "flesch"}
    assert all(C.is_citation_check("generated_cell", cc.parse_args(r["args"])) for r in cit)


# ── dedicated checks for numbers the generator used to type ─────────────

def test_markup_range_is_checked_from_the_summary(tmp_path):
    agg = tmp_path / "aggregate"
    agg.mkdir()
    pd.DataFrame({"name": ["markup_share_min_pct", "markup_share_max_pct"],
                  "value": [5.16, 6.37]}).to_csv(agg / "latex_robustness_summary.csv", index=False)
    ctx = C.Ctx(str(tmp_path), "absent")
    v = C.latex_summary_pair(ctx, "markup_share_min_pct+markup_share_max_pct")
    assert cc.compare("auto", v, cc.parse_printed("5 to 6", "pair"))
    assert not cc.compare("auto", v, cc.parse_printed("5 to 7", "pair"))
    r = [x for x in cc.load() if x["id"] == "normalisation-3751f743"][0]
    assert (r["category"], r["check"]) == ("computed", "latex_summary_pair")


def test_arxiv_cutoff_from_the_last_identifier():
    sys.path.insert(0, os.path.join(ROOT, "src", "baselines"))
    import arxiv_snapshot as snap
    text = ('{"paper_id": "2501.00007"}, {"paper_id": "2501.20000"}, '
            '{"paper_id": "2502.20000v2"}, {"paper_id": "2503.05000"}, '
            '{"paper_id": "hep-th/9901001"}, {"paper_id": "2412.30000"}')
    m = snap.month_maxima(text, 2025)
    assert m == {1: 20000, 2: 20000, 3: 5000}
    rec = snap.cutoff(m, 2025)
    assert rec["last_id"] == "2503.05000"
    assert rec["cutoff_year_fraction"] == pytest.approx((2 + 0.25) / 12, abs=1e-4)
    assert rec["cutoff_year_fraction_min"] <= rec["cutoff_year_fraction"] <= rec["cutoff_year_fraction_max"]
    # the committed record, from the paper's corpus
    ctx = C.Ctx("unused", "absent")
    assert C.arxiv_year_fraction(ctx) == pytest.approx(0.683, abs=1e-3)
    assert C.arxiv_year_fraction(ctx, "cutoff_year_fraction_max") == 0.75
    r = [x for x in cc.load() if x["id"] == "main-68916d9a"][0]
    assert r["check"] == "arxiv_year_fraction"


# ── empirical statements once filed as design ───────────────────────────

def _line(years, f):
    return [f(y) for y in years]


def test_inflection_and_divergence(tmp_path):
    years = list(range(2005, 2026))
    kink = {"neurips": _line(years, lambda y: 1 + 0.01 * (y - 2005) + 0.2 * max(0, y - 2022)),
            "arxiv_nonml": _line(years, lambda y: 1 + 0.01 * (y - 2005))}
    for v in ("iclr", "icml", "arxiv_ml"):
        kink[v] = kink["neurips"]
    write_series(str(tmp_path), "sensational_total", years, kink)
    ctx = C.Ctx(str(tmp_path), "absent")
    assert C.inflection(ctx, "sensational_total", "neurips+arxiv_ml", 2022, 2015)
    assert not C.inflection(ctx, "sensational_total", "arxiv_nonml", 2022, 2015)
    assert C.divergence_accelerates(ctx, "sensational_total")
    assert not C.divergence_accelerates(ctx, "sensational_total", ml="arxiv_nonml")
    assert C.rises_over(ctx, "sensational_total", "neurips", 2005, 2010)


def _judge_series(root, venue, values_by_prompt, years):
    for p, vals in values_by_prompt.items():
        name = f"llm_scores_model_avg_{p}" if venue == "neurips" else \
            f"llm_scores_model_avg_{venue}_{p}"
        write_series(root, name, years, {"avg_z": vals, "n_models": [6] * len(years)})


def test_judge_rise_small_and_unsettled(tmp_path):
    years = list(range(2010, 2026))
    flat = [0.0 + 0.01 * ((i % 3) - 1) for i in range(len(years) - 3)]
    sharp = flat + [1.0, 2.0, 3.0]
    for v in ("neurips", "icml"):
        _judge_series(str(tmp_path), v, {p: sharp for p in C.PROMPTS}, years)
    zig = {"simple": flat + [-0.3, 0.2, -0.1], "ascb": flat + [0.3, -0.2, 0.4],
           "own_reasoning": flat + [-0.2, 0.3, -0.3]}
    _judge_series(str(tmp_path), "iclr", zig, years)
    ctx = C.Ctx(str(tmp_path), "absent")
    assert C.judge_rises_after(ctx, "neurips+icml")
    assert not C.judge_rises_after(ctx, "iclr")
    assert C.judge_post_small(ctx, "iclr")
    assert C.judge_post_unsettled(ctx, "iclr")
    assert not C.judge_post_unsettled(ctx, "neurips")      # monotone after 2022


def test_comoves_collinearity_and_topics(tmp_path):
    years = list(range(1990, 2000))
    write_series(str(tmp_path), "papers_per_year", years, {"neurips": [100 + 10 * i for i in range(10)]})
    write_series(str(tmp_path), "readability_flesch_ease", years, {"neurips": [30 - i for i in range(10)]})
    write_series(str(tmp_path), "acronyms_abstract", years, {"neurips": [1 + i for i in range(10)]})
    write_series(str(tmp_path), "acronyms_title", years, {"neurips": [1 + i for i in range(10)]})
    agg = tmp_path / "aggregate"
    agg.mkdir()
    pd.DataFrame({"venue": ["neurips", "iclr"], "pc1_var_explained": [0.72, 0.49]}) \
      .to_csv(agg / "readability_collinearity.csv", index=False)
    pd.DataFrame({"flesch_change": [-1, -2], "hype_change": [0.1, 0.2],
                  "acr_abstract_change": [0.3, -0.1], "acr_title_change": [1, 1]}) \
      .to_csv(agg / "topic_trends.csv", index=False)
    ctx = C.Ctx(str(tmp_path), "absent")
    assert C.comoves(ctx)
    assert C.comoves(ctx, falling="acronyms_abstract", rising="") is False
    assert not C.collinearity_one_signal(ctx)              # iclr below a half
    assert C.collinearity_one_signal(ctx, threshold=0.4)
    assert C.topics_all_move(ctx, "flesch+hype")
    assert not C.topics_all_move(ctx, "flesch+hype+acr_abstract")


def test_reclassified_rows_carry_a_check():
    """The empirical statements once filed as design constants (a post-2022
    inflection, a post-2015 inflection, one common signal, ...) are computed
    rows now; none may slip back to an unchecked category."""
    ids = {"main-78d661a5", "main-8e45b1be", "main-b1055726", "main-0aa7b868",
           "main-74a1a6c0", "main-7f0a9e16", "main-d003780e", "main-3f277c1c",
           "main-8270d9e3", "main-b4c4ae9b", "main-44cb42f2", "main-ad6a360d",
           "metric_families-c8e41c85", "fig_sensational_total-7c4cde7b",
           "fig_llm-e4eb1103", "fig_llm-20305e51", "fig_sensational-ad6a360d"}
    rows = {r["id"]: r for r in cc.load()}
    for i in ids:
        assert rows[i]["category"] == "computed" and rows[i]["check"] in C.REGISTRY, i
        assert rows[i]["rule"] == "true"
