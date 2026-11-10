"""Tests for the TMLR claim check (paper/tmlr/inventory.py, claims.py,
check_claims.py, import_source.py).

verify.py runs the check on the full outputs. What is tested here is what
that run cannot isolate: the tokenizer on LaTeX the manuscript happens not to
contain (or contains only once), the coverage logic on deliberately broken
claims, the comparison rules, a few check functions on synthetic series with
a known answer, and the personal-data scrub of the source import. One test
ties the committed claims.csv to the committed source without any data.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "paper", "tmlr"))

import check_claims as cc  # noqa: E402
import claims as C  # noqa: E402
import import_source as imp  # noqa: E402
import inventory as inv  # noqa: E402


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
    assert texts("rises from 2.55 in 1990 to 4.41 in 2025") == ["2.55", "1990 to 4.41"][:1] + \
        ["1990", "4.41", "2025"]


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


# ── import ──────────────────────────────────────────────────────────────

def test_scrub_removes_author_block_and_comments_keeping_lines():
    src = ("\\title{T}\n% a note with a@b.org\n\\author{\\name A B\\thanks{x}\n"
           "  \\email a@b.org \\\\\n  \\addr Somewhere}\n"
           "\\hypersetup{pdfauthor={A B; C D}}\nBody 5\\% % comment\n")
    out = imp.scrub(src)
    assert out.count("\n") == src.count("\n")
    assert "a@b.org" not in out and "Somewhere" not in out and "comment" not in out
    assert "\\author{}" in out and "pdfauthor={}" in out and "Body 5\\%" in out
    assert imp.forbidden_hits(out) == []


def test_author_terms_are_read_from_the_block_and_caught_anywhere():
    src = ("\\author{\\name Ada Lovelace\\thanks{x}\n  \\email ada@example.org \\\\\n"
           "  \\addr Analytical Engine Society\n  \\AND\n  \\name Bo Li \\email b@x.io}\n")
    terms = imp.author_terms(src)
    assert {"Ada", "Lovelace", "ada@example.org", "Analytical Engine Society", "b@x.io"} <= set(terms)
    hits = imp.forbidden_hits("thanks to lovelace and the Analytical Engine Society", terms)
    assert sorted(h[2] for h in hits) == ["Analytical Engine Society", "lovelace"]
    # whole words only: a name inside a longer word is not a hit
    assert imp.forbidden_hits("adaptive", ["Ada"]) == []


def test_forbidden_hits_find_addresses_but_not_column_specs():
    assert imp.forbidden_hits(r"\begin{tabular}{@{}p{3cm}@{}}") == []
    hits = imp.forbidden_hits("mail x.y@example.org or /Users/someone/paper")
    assert {w for _, w, _ in hits} >= {"e-mail address", "local path"}


def test_inputs_of_skips_comments_and_adds_extension():
    assert imp.inputs_of("\\input{a}\n% \\input{b}\n\\input{figs/c.tex}") == ["a.tex", "figs/c.tex"]


# ── coverage ────────────────────────────────────────────────────────────

@pytest.fixture
def mini_source(tmp_path):
    (tmp_path / "tables").mkdir()
    (tmp_path / "main.tex").write_text(
        "\\begin{document}\nWe count 12 papers and 12 more,\n"
        "then 7 from 2015.\n\\input{tables/t.tex}\n\\end{document}\n")
    (tmp_path / "tables" / "t.tex").write_text("A & 3.5 \\\\\n")
    return str(tmp_path)


def row(file, quote, cat="design", **kw):
    r = {k: "" for k in cc.FIELDS}
    r.update(id=cc.make_id(file, quote), file=file, quote=quote, category=cat, **kw)
    return r


def test_coverage_ties_every_number(mini_source):
    occ, norms = inv.inventory(mini_source)
    assert [o.text for o in occ] == ["12", "12", "7", "2015", "3.5"]
    rows = [row("main.tex", "count <<12>> papers"), row("main.tex", "and <<12>> more"),
            row("main.tex", "then <<7>> from"), row("main.tex", "from <<2015>>."),
            row("tables/t.tex", "A & <<3.5>>")]
    cov = cc.match(rows, occ, norms)
    assert len(cov.matched) == 5 and not cov.uncovered and not cov.stale


def test_coverage_reports_uncovered_stale_ambiguous_and_duplicates(mini_source):
    occ, norms = inv.inventory(mini_source)
    rows = [row("main.tex", "<<12>>"),                     # ambiguous: twice in the file
            row("main.tex", "count <<13>> papers"),        # quote no longer occurs
            row("main.tex", "<<then>> 7"),                 # marks no number
            row("main.tex", "then <<7>> from"),
            row("main.tex", "<<7>> from 2015"),            # same number again
            row("other.tex", "x <<1>>")]                   # not a manuscript file
    cov = cc.match(rows, occ, norms)
    why = [w for _, w in cov.stale]
    assert any("occurs 2 times" in w for w in why)
    assert "quote not found" in why
    assert any("not an inventoried number" in w for w in why)
    assert any("not part of the manuscript" in w for w in why)
    assert cov.duplicate == [(3, 4)]
    assert sorted(o.text for o in cov.uncovered) == ["12", "12", "2015", "3.5"]


def test_suggested_quotes_are_unique_and_tie_back(mini_source):
    occ, norms = inv.inventory(mini_source)
    rows = [row(o.file, cc.suggest_quote(o, norms[o.file])) for o in occ]
    cov = cc.match(rows, occ, norms)
    assert len(cov.matched) == len(occ) and not cov.stale


def test_committed_claims_cover_the_committed_source():
    rows = cc.load()
    occ, norms = inv.inventory()
    cov = cc.match(rows, occ, norms)
    assert not cov.uncovered and not cov.stale and not cov.duplicate
    assert len({r["id"] for r in rows}) == len(rows)
    for r in rows:
        assert r["category"] in cc.CATEGORIES, r["id"]
        assert not r["check"] or r["check"] in C.REGISTRY, r["id"]
        # only literature and design may go unchecked
        assert r["check"] or r["category"] in ("literature", "design", "unverifiable"), r["id"]


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


def test_citation_checks_read_the_frozen_reference_outside_strict_mode(tmp_path):
    ctx = C.Ctx(str(tmp_path), "absent")
    assert ctx.cit_dir.endswith(os.path.join("reference", "tmlr", "citations"))
    assert C.cit_max_year(ctx) == 2024
    assert C.is_citation_check("cit_value", {}) and not C.is_citation_check("series", {})
    assert C.is_citation_check("generated_table", {"table": "topics.tex"})


def test_evaluate_reports_absent_input_as_skip(tmp_path):
    ctx = C.Ctx(str(tmp_path), "absent")
    occ = inv.Occurrence("main.tex", 1, 0, "67", "number", "")
    r = row("main.tex", "<<67>>", "computed", check="neurips_fallback_count", rule="exact")
    rec = cc.evaluate(r, occ, ctx)
    assert rec["verdict"] == "SKIP" and "raw/neurips" in rec["why"]
    r = row("main.tex", "<<67>>", "computed", check="no_such_check")
    assert cc.evaluate(r, occ, ctx)["verdict"] == "ERROR"
    r = row("main.tex", "<<67>>", "computed")
    assert cc.evaluate(r, occ, ctx)["verdict"] == "ERROR"
    r = row("main.tex", "<<67>>", "unverifiable", note="why")
    assert cc.evaluate(r, occ, ctx)["verdict"] == "UNVERIFIABLE"
