"""Tests for the TMLR macro generator and its checker (paper/tmlr/).

verify.py compares the built macros with the paper's printed values on the
full corpus. What is tested here is what that run cannot isolate: the
\\newcommand parser on input the generator never writes (nested and escaped
braces, comments, other definition forms, malformed definitions), the
comparison logic for missing, extra, differing and skipped names, the
citation modes, the comparison of macros.csv with a manuscript's own macro
files, and the generator's own guards. Two tests run the generator on the
committed reference inputs, which reproduces the paper's printed values
without any pipeline run.
"""
import csv
import json
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "paper", "tmlr"))

import check_macros as cm  # noqa: E402
import make_macros as mm  # noqa: E402

REF = os.path.join(ROOT, "reference", "tmlr")


# ── parser ───────────────────────────────────────────────────────────────

def test_parse_simple_and_sorted_file():
    text = ("% header\n\\newcommand{\\A}{1}\n\\newcommand{\\Bee}{43{,}696}\n")
    assert cm.parse_newcommands(text) == {"A": "1", "Bee": "43{,}696"}


def test_parse_nested_braces_kept_whole():
    text = r"\newcommand{\X}{a {b {c} d} \textbf{e}}"
    assert cm.parse_newcommands(text) == {"X": r"a {b {c} d} \textbf{e}"}


def test_parse_escaped_braces_do_not_count():
    text = r"\newcommand{\X}{\{ open} \newcommand{\Y}{close \}}"
    assert cm.parse_newcommands(text) == {"X": r"\{ open", "Y": r"close \}"}


def test_parse_comments_stripped_but_escaped_percent_kept():
    text = ("\\newcommand{\\X}{5\\%} % trailing comment {\n"
            "% \\newcommand{\\Commented}{1}\n"
            "\\newcommand{\\Y}{a% split across\n b}\n")
    assert cm.parse_newcommands(text) == {"X": r"5\%", "Y": "a\n b"}


def test_parse_other_definition_forms():
    text = (r"\newcommand\Bare{1}" "\n"
            r"\newcommand*{\Star}{2}" "\n"
            r"\newcommand{\Args}[1]{#1!}" "\n"
            r"\newcommand { \Spaced } {3}")
    assert cm.parse_newcommands(text) == {"Bare": "1", "Star": "2",
                                          "Args": "#1!", "Spaced": "3"}


def test_parse_ignores_longer_control_words():
    assert cm.parse_newcommands(r"\newcommandx{\X}{1} \newcommand{\Y}{2}") == {"Y": "2"}


def test_parse_empty_value_and_value_with_signs():
    text = r"\newcommand{\E}{} \newcommand{\S}{$+0.7$}"
    assert cm.parse_newcommands(text) == {"E": "", "S": "$+0.7$"}


def test_parse_unbalanced_value():
    with pytest.raises(ValueError, match="unbalanced"):
        cm.parse_newcommands(r"\newcommand{\X}{unclosed {inner}")


def test_parse_stray_brace_outside_definitions_ignored():
    assert cm.parse_newcommands(r"\newcommand{\X}{a}} {") == {"X": "a"}


@pytest.mark.parametrize("text,msg", [
    (r"\newcommand{\X}{1}\newcommand{\X}{2}", "twice"),
    (r"\newcommand{\X}", "expected"),
    (r"\newcommand{X}{1}", "control sequence"),
    (r"\newcommand{\X2}{1}", "control sequence"),
    (r"\newcommand 5", "without a name"),
    (r"\newcommand{\X}[1{1}", "argument count"),
])
def test_parse_malformed(text, msg):
    with pytest.raises(ValueError, match=msg):
        cm.parse_newcommands(text)


def test_reference_holds_163_printed_values_and_no_prose():
    ref = cm.load_reference()
    assert sum(len(m) for m in ref.values()) == 163
    assert set(ref) == set(mm.ROUND_FILES.values())
    for m in ref.values():
        for name, value in m.items():
            # numbers, or a computed label: a topic's leading term, a number
            # word, the ten commonest acronyms
            assert len(value.split()) <= 3 or name == "AcrTopTen", (name, value)


# ── comparison ───────────────────────────────────────────────────────────

def test_compare_all_match():
    d = cm.compare_macros({"A": "1", "B": "x{y}"}, {"A": "1", "B": "x{y}"})
    assert d.ok and d.matched == ["A", "B"]


def test_compare_missing_extra_and_mismatched():
    d = cm.compare_macros({"A": "1", "B": "2.0", "C": "3"}, {"A": "1", "B": "2", "D": "4"})
    assert d.matched == ["A"]
    assert d.mismatched == [("B", "2", "2.0")]
    assert d.missing == ["D"]
    assert d.extra == ["C"]
    assert not d.ok


def test_compare_values_are_strings_not_numbers():
    # 0.40 and 0.4 are the same number and a different line of the paper
    assert not cm.compare_macros({"A": "0.4"}, {"A": "0.40"}).ok


def test_compare_skipped_names_not_compared_either_way():
    d = cm.compare_macros({"A": "1", "S": "wrong", "T": "extra"},
                          {"A": "1", "S": "right", "U": "absent"}, skip={"S", "T", "U"})
    assert d.ok
    assert d.skipped == ["S", "U"]
    assert d.extra == [] and d.missing == []


# ── check() over a miniature reference ───────────────────────────────────

def _write_macros(path, m):
    path.write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))


def _mini(tmp_path, built_macros, skipped=None):
    """A macros.csv holding one citation macro and one ordinary macro per
    round file, and a built tree as given."""
    cit = sorted(mm.CITATION_MACROS)
    refm = {f: {"Plain" + "abc"[i]: str(i), cit[i]: f"c{i}"}
            for i, f in enumerate(mm.ROUND_FILES.values())}
    ref = tmp_path / "macros.csv"
    with open(ref, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "name", "value"])
        w.writerows((f, k, v) for f, m in refm.items() for k, v in m.items())
    built = tmp_path / "built"
    built.mkdir()
    for f in mm.ROUND_FILES.values():
        _write_macros(built / f, built_macros(refm[f]))
    if skipped is not None:
        (built / "skipped.json").write_text(json.dumps(skipped))
    return str(built), str(ref), refm


def _no_citations(m):
    return {k: v for k, v in m.items() if k not in mm.CITATION_MACROS}


def test_check_absent_skips_citation_items(tmp_path):
    built, ref, _ = _mini(tmp_path, _no_citations,
                          skipped={"macros": {"generated_round2.tex": ["CitN"]},
                                   "tables": ["topics.tex"]})
    r = cm.check(built, "absent", ref)
    assert (r.ok, r.bad, r.missing, r.skipped) == (3, 0, 0, 3)
    assert any("skipped" in ln and "AA_PAPER" in ln for ln in r.summary())


def test_check_strict_needs_citation_items(tmp_path):
    built, ref, _ = _mini(tmp_path, _no_citations)
    r = cm.check(built, "strict", ref)
    assert r.missing == 3 and r.bad == 0 and r.skipped == 0


def test_check_fresh_reports_citation_differences_without_counting(tmp_path):
    def wrong_citations(m):
        return {k: ("other" if k in mm.CITATION_MACROS else v) for k, v in m.items()}
    built, ref, _ = _mini(tmp_path, wrong_citations)
    r = cm.check(built, "fresh", ref)
    assert (r.ok, r.bad, r.missing) == (3, 0, 0)
    assert r.uncounted == 3
    assert any("(fresh)" in ln for ln in r.lines)


def test_check_strict_flags_a_changed_value(tmp_path):
    built, ref, _ = _mini(tmp_path, lambda m: {k: ("9" if k == "Plaina" else v)
                                               for k, v in m.items()})
    r = cm.check(built, "strict", ref)
    assert r.bad == 1
    assert any("Plaina" in ln and "'0'" in ln and "'9'" in ln for ln in r.lines)


def test_check_extra_macro_is_a_mismatch(tmp_path):
    built, ref, _ = _mini(tmp_path, lambda m: {**m, "Surplus": "1"})
    r = cm.check(built, "strict", ref)
    assert r.bad == 3      # once per round file


def test_check_absent_rejects_non_citation_skip(tmp_path):
    built, ref, _ = _mini(tmp_path, _no_citations,
                          skipped={"macros": {"generated_round2.tex": ["Plaina"]},
                                   "tables": ["normalisation.tex"]})
    r = cm.check(built, "absent", ref)
    assert r.bad == 1
    assert any("skipped.json" in ln and "Plaina" in ln for ln in r.lines)


def test_check_unbuilt_file(tmp_path):
    built, ref, _ = _mini(tmp_path, lambda m: m)
    os.remove(os.path.join(built, "generated_round3.tex"))
    assert cm.check(built, "absent", ref).missing == 1          # citation one skipped
    assert cm.check(built, "strict", ref).missing == 2


def test_check_unknown_mode(tmp_path):
    with pytest.raises(ValueError):
        cm.check(str(tmp_path), "sometimes")


# ── macros.csv against a manuscript's own macro files ────────────────────

def _manuscript(tmp_path, refm):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.tex").write_text("\\begin{document}\\end{document}\n")
    for f, m in refm.items():
        _write_macros(paper / f, m)
    return paper


@pytest.mark.parametrize("mode", ["strict", "fresh", "absent"])
def test_manuscript_value_changed_fails_in_every_mode(tmp_path, mode):
    """A printed value that differs from macros.csv fails even where the
    built side is not compared (a citation macro outside strict mode)."""
    built, ref, refm = _mini(tmp_path, lambda m: m)
    paper = _manuscript(tmp_path, refm)
    r = cm.check(built, mode, ref, paper=str(paper))
    assert r.count("ok", "paper") == 6 and r.count("bad", "paper") == 0
    cit = sorted(mm.CITATION_MACROS)[0]
    _write_macros(paper / "generated_round2.tex", {"Plaina": "7", cit: "c0"})
    _write_macros(paper / "generated_round3.tex", {"Plainb": "1"})          # one dropped
    r = cm.check(built, mode, ref, paper=str(paper))
    bad = [ln for ln in r.lines if "paper:" in ln]
    assert r.count("bad", "paper") == 2 and len(bad) == 2
    assert any("Plaina" in ln and "'7'" in ln for ln in bad)
    assert any("not in the manuscript" in ln for ln in bad)


def test_write_reference_round_trips(tmp_path):
    _, _, refm = _mini(tmp_path, lambda m: m)
    paper = _manuscript(tmp_path, refm)
    out = tmp_path / "out.csv"
    assert cm.write_reference(str(paper), str(out)) == 6
    assert cm.load_reference(str(out)) == refm


# ── generator guards ─────────────────────────────────────────────────────

def test_macro_names_letters_only_and_unique():
    r = mm.Round(2)
    r.M("Fine", "1")
    with pytest.raises(ValueError, match="letters only"):
        r.M("Pre2005", "1")
    with pytest.raises(ValueError, match="twice"):
        r.M("Fine", "2")


@pytest.mark.parametrize("terms,want", [
    ("a, b, c", "a, b, c"),
    ("x" * 60 + ", b", "x" * 60),                    # first term alone exceeds budget
    ("aaaaaaaaaa, bbbbbbbbbb, cccccccccc, dddddddddd, eeeeeeeeee",
     "aaaaaaaaaa, bbbbbbbbbb, cccccccccc, dddddddddd"),  # cut at a term boundary
])
def test_label(terms, want):
    assert mm.label(terms) == want


def test_thousands():
    assert mm.thousands(62628) == "62{,}628"
    assert mm.thousands(999.6) == "1{,}000"


def test_round4_requires_baseline_columns(tmp_path):
    d = tmp_path / "pgfplots" / "tmlr"
    d.mkdir(parents=True)
    (d / "readability_flesch_ease.csv").write_text("year,neurips,iclr,icml\n2015,1,2,3\n")
    with pytest.raises(SystemExit, match="--baselines"):
        mm.read_flesch(mm.Inputs(str(tmp_path)))


# ── the generator on the committed reference inputs ──────────────────────

def _reference_inputs(tmp_path):
    """The upstream analysis outputs as committed under reference/tmlr/, laid
    out where make_macros.py reads them. No citation output is distributed."""
    agg = tmp_path / "data" / "aggregate"
    agg.mkdir(parents=True)
    for f in os.listdir(os.path.join(REF, "analysis")):
        shutil.copy(os.path.join(REF, "analysis", f), agg / f)
    shutil.copy(os.path.join(REF, "latex_robustness.csv"), agg)
    pg = tmp_path / "data" / "pgfplots" / "tmlr"
    pg.mkdir(parents=True)
    shutil.copy(os.path.join(REF, "pgfplots_full", "readability_flesch_ease.csv"), pg)
    return str(tmp_path / "data")


def test_build_without_citations_reproduces_every_other_printed_value(tmp_path):
    data = _reference_inputs(tmp_path)
    rec = mm.build(data, os.path.join(data, "tmlr"))
    skipped = {m for v in rec["macros"].values() for m in v}
    assert skipped == mm.CITATION_MACROS
    assert set(rec["tables"]) == mm.CITATION_TABLES
    assert sum(rec["written"].values()) == 163 - len(mm.CITATION_MACROS)
    r = cm.check(os.path.join(data, "tmlr"), "absent")
    assert (r.ok, r.bad, r.missing, r.skipped) == (152, 0, 0, 11), r.lines


# ── absent inputs: incomplete sections, not a stop ───────────────────────

def test_absent_input_marks_section_incomplete_and_fails_its_macros(tmp_path):
    data = _reference_inputs(tmp_path)
    os.remove(os.path.join(data, "aggregate", "latex_robustness.csv"))
    rec = mm.build(data, os.path.join(data, "tmlr"))
    assert [i["section"] for i in rec["incomplete"]] == ["normalisation"]
    assert rec["incomplete"][0]["input"].endswith("latex_robustness.csv")
    assert "normalisation.tex" not in rec["written_tables"]
    assert "topic_trends.tex" in rec["written_tables"]       # the rest still built
    r = cm.check(os.path.join(data, "tmlr"), "absent")
    assert any(ln.startswith("  INCOMPLETE normalisation") for ln in r.lines)
    # the normalisation section's macros are failures, with the reason
    assert r.missing > 0
    assert all("input is absent" in ln for ln in r.lines if "MISSING" in ln)
    # the citation exemption is not stretched to cover them
    assert not any("skipped non-citation" in ln for ln in r.lines)


def test_markup_range_in_caption_comes_from_the_shares(tmp_path):
    import pandas as pd
    data = _reference_inputs(tmp_path)
    path = os.path.join(data, "aggregate", "latex_robustness.csv")
    d = pd.read_csv(path)
    # move the last-year normalised score so that markup explains a tenth of
    # each venue's decline
    for v in ("neurips", "iclr", "icml"):
        g = d[(d.venue == v) & d.flesch_keep.notna()].sort_values("year")
        a, b = g.index[0], g.index[-1]
        dk = d.loc[b, "flesch_keep"] - d.loc[a, "flesch_keep"]
        d.loc[b, "flesch_token"] = d.loc[a, "flesch_token"] + 0.9 * dk
    d.to_csv(path, index=False)
    mm.build(data, os.path.join(data, "tmlr"))
    tex = open(os.path.join(data, "tmlr", "tables", "normalisation.tex")).read()
    assert "Markup accounts for 10 to 10 percent" in " ".join(tex.split())
