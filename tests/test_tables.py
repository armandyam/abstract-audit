"""Tests for the TMLR table generators and the table check (paper/tmlr/).

verify.py compares every generated table with the paper's own when a local
copy of the manuscript is given. What is tested here is what that run cannot
isolate: the tabular parser on markup the paper's tables use (revision
markers, multicolumn cells, escaped ampersands, two tabulars in one table),
the inline-table lookup by label, the check's verdicts and citation modes on
a miniature manuscript, and the generators whose output comes from code
rather than data (the prompts, the normalisation examples).
"""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "paper", "tmlr"))

import check_tables as ct  # noqa: E402
import claims as C  # noqa: E402
import make_tables as mt  # noqa: E402
import manuscript as ms  # noqa: E402


# ── parsing ──────────────────────────────────────────────────────────────

def test_tabular_rows_unwrap_revisions_and_drop_rules():
    t = (r"\begin{table}\begin{tabular}{lrr}\toprule A & B \\ \midrule"
         "\n" r"x & \revfour{\textbf{1.0\%}} & y \& z \\ % note & 9" "\n"
         r"\multicolumn{3}{l}{\small $n=4$} \\ \addlinespace \bottomrule"
         r"\end{tabular}\caption{\revtwo{Cap  tion}}\end{table}")
    assert ms.tabular_rows(t) == [["A", "B"], ["x", r"\textbf{1.0\%}", r"y \& z"],
                                  [r"\multicolumn{3}{l}{\small $n=4$}"]]
    assert ms.caption(t) == "Cap tion"


def test_tabular_rows_read_every_tabular_and_whitespace_is_not_content():
    one = "\\begin{tabular}{l}\na \\\\\n\\end{tabular}\\begin{tabular}{l}b\\\\\\end{tabular}"
    assert ms.tabular_rows(one) == [["a"], ["b"]]
    spec = r"\begin{tabular}{@{}p{\dimexpr\linewidth-2\tabcolsep\relax}@{}}x  \newline" \
           "\n  y \\\\\\end{tabular}"
    assert ms.tabular_rows(spec) == [[r"x \newline y"]]


def test_inline_table_found_by_label(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\begin{document}\n\\begin{table}[h]\\begin{tabular}{l}A\\\\\\end{tabular}"
        "\\label{tab:other}\\end{table}\n"
        "\\begin{table}[t]\\begin{tabular}{l}B\\\\\\end{tabular}"
        "\\label{tab:corpus}\\end{table}\n\\end{document}\n")
    env = ms.table_source(str(tmp_path), "corpus.tex")
    assert env.startswith("\\begin{table}[t]") and ms.tabular_rows(env) == [["B"]]
    with pytest.raises(KeyError):
        ms.environment(env, "tab:absent")


def test_paper_dir_from_environment(tmp_path, monkeypatch):
    monkeypatch.delenv(ms.ENV, raising=False)
    assert ms.paper_dir() is None
    monkeypatch.setenv(ms.ENV, str(tmp_path))
    with pytest.raises(SystemExit, match="no main.tex"):
        ms.paper_dir()
    (tmp_path / "main.tex").write_text("")
    assert ms.paper_dir() == str(tmp_path)


# ── the check on a miniature manuscript ──────────────────────────────────

def _table(body, cap="Cap."):
    return ("\\begin{table}[h]\n\\begin{tabular}{lr}\n\\toprule\n" + body
            + "\n\\bottomrule\n\\end{tabular}\n\\caption{" + cap + "}\n\\end{table}\n")


@pytest.fixture
def mini(tmp_path, monkeypatch):
    """A manuscript and a built tree in which every table is one row."""
    paper, built = tmp_path / "paper", tmp_path / "built"
    (paper / "tables").mkdir(parents=True)
    built.mkdir()
    inline = ""
    for name in ct.tables():
        t = _table(f"{name} & 1 \\\\")
        if name in ms.INLINE_TABLES:
            inline += t.replace("\\end{table}", f"\\label{{{ms.INLINE_TABLES[name]}}}\\end{{table}}")
        else:
            (paper / "tables" / name).write_text(t)
        if name not in ct.STATIC:
            (built / name).write_text(t)
    (paper / "main.tex").write_text("\\begin{document}\n" + inline + "\\end{document}\n")
    static = tmp_path / "static"
    static.mkdir()
    for name in ct.STATIC:
        (static / name).write_text(_table(f"{name} & 1 \\\\"))
    monkeypatch.setattr(ct, "STATIC_DIR", str(static))
    return str(paper), str(built)


def test_every_table_matches(mini):
    paper, built = mini
    r = ct.check(built, "strict", paper)
    assert (r.ok, r.bad, r.missing) == (15, 0, 0) and not r.lines


def test_a_changed_cell_and_an_absent_table_fail(mini):
    paper, built = mini
    p = os.path.join(built, "topic_trends.tex")
    with open(p) as fh:
        text = fh.read()
    with open(p, "w") as fh:
        fh.write(text.replace("& 1 \\\\", "& 2 \\\\"))
    os.remove(os.path.join(built, "corpus.tex"))
    r = ct.check(built, "strict", paper)
    assert (r.bad, r.missing) == (1, 1)
    assert any("topic_trends.tex" in ln and "'topic_trends.tex & 1'" in ln for ln in r.lines)


def test_a_changed_caption_is_a_mismatch(mini):
    paper, built = mini
    p = os.path.join(built, "prompts.tex")
    with open(p) as fh:
        text = fh.read()
    with open(p, "w") as fh:
        fh.write(text.replace("Cap.", "Other."))
    r = ct.check(built, "strict", paper)
    assert r.bad == 1 and any("caption text differs" in ln for ln in r.lines)


def test_citation_tables_follow_the_mode(mini):
    paper, built = mini
    for name in ct.CITATION:
        os.remove(os.path.join(built, name))
    r = ct.check(built, "absent", paper)
    assert (r.ok, r.missing) == (15 - len(ct.CITATION), 0)
    r = ct.check(built, "fresh", paper)
    assert r.missing == 0 and sum(1 for *_, c in r.records if not c) == len(ct.CITATION)
    assert ct.check(built, "strict", paper).missing == len(ct.CITATION)


def test_without_the_manuscript_every_table_is_skipped(mini):
    _, built = mini
    r = ct.check(built, "strict", None)
    assert (r.ok, r.bad, r.missing) == (0, 0, 0)
    assert any("AA_PAPER" in ln for ln in r.lines)


# ── generators whose content is code ─────────────────────────────────────

def test_prompt_tex_marks_newlines_dashes_and_placeholders():
    got = mt.prompt_tex("Rate it. \n\nGuide: \n- Be brief. \nScore: <score> \nText: {SUMMARY}")
    assert " ".join(got.split()) == (
        r"Rate it. \texttt{\textbackslash n \textbackslash n} \newline Guide: "
        r"\texttt{\textbackslash n} \newline {\textendash} Be brief. "
        r"\texttt{\textbackslash n} \newline Score: \texttt{<score>} "
        r"\texttt{\textbackslash n} \newline Text: \texttt{\{SUMMARY\}}")


def test_prompts_table_has_one_block_per_template():
    from metrics.llm_scores import PROMPTS
    rows = ms.tabular_rows(mt.prompts(None))
    assert len(rows) == 2 * len(PROMPTS)
    assert [r[0] for r in rows[::2]] == [r"\textbf{" + mt.PROMPT_TITLE[p] + "}" for p in PROMPTS]


def test_normalisation_examples_are_escaped_and_cleaned():
    assert mt.tt(r"a $\x{y}$ & é" + mt.SOFT) == r"\texttt{a \$\textbackslash x\{y\}\$ \& \'e\-}"
    rows = ms.tabular_rows(mt.normalisation_rules(None))
    assert rows[0] == ["Element", "Before", "After"]
    assert len(rows) == 1 + len(mt.RULE_EXAMPLES)
    assert rows[7] == ["Ampersands", r"\texttt{speed \& accuracy}", r"\texttt{speed and accuracy}"]


def test_build_records_what_it_could_not_write(tmp_path):
    data = tmp_path / "data"
    (data / "aggregate").mkdir(parents=True)
    rec = mt.build(str(data), str(data / "tmlr" / "tables"))
    assert set(rec["written"]) == {"prompts.tex", "normalisation_rules.tex"}
    assert set(rec["skipped"]) == set(mt.CITATION) | {"self_audit.tex"}
    assert set(rec["incomplete"]) == {"acronym_reuse_freq.tex", "corpus.tex"}
    assert os.path.exists(data / "tmlr" / "tables.json")


def test_citation_llm_bold_marks_only_a_positive_gap(tmp_path):
    cit = tmp_path / "aggregate" / "citations"
    cit.mkdir(parents=True)
    pd.DataFrame({"prompt": ["simple", "simple"], "venue": ["neurips", "iclr"],
                  "top_mean": [2.5, 2.0], "top_ci": [0.1, 0.1], "bottom_mean": [2.2, 2.1],
                  "bottom_ci": [0.1, 0.1], "delta": [0.3, -0.1], "n_models": [6, 6]}) \
        .to_csv(cit / "citation_llm_top_bottom_combined.csv", index=False)
    pd.DataFrame({"venue": C.CONFS, "max_year": [2024] * 3}).to_csv(
        cit / "citation_coverage.csv", index=False)
    rows = ms.tabular_rows(mt.citation_llm(C.Ctx(str(tmp_path), "strict")))
    assert rows[2][-1] == r"\textbf{+0.30}" and rows[3][-1] == "-0.10"
