"""Tests for the analyses added for the TMLR paper.

verify.py checks every output of these on the full corpus. What is tested
here is the contract a full run cannot isolate: the TMLR export keeps one
column per conference and the years any of them covers; papers per year
marks uncovered years as gaps; the collinearity and robustness summaries
compute what their docstrings say; the self-audit reads a manuscript.
"""
import json
import os

import numpy as np
import pandas as pd
import pytest

import plotting.export_pgfplots_data as export
from aggregate._utils import aggregate
from aggregate.aggregate_papers_per_year import count_papers_by_year
from analysis.latex_robustness import summary, year_row
from analysis.readability_collinearity import METRICS, analyse_frame
from metrics.audit_self import read_from_tex

ABS = "We propose a method and show that it works well in practice for everyone."


# ── TMLR export ──────────────────────────────────────────────────────────

def test_tmlr_export_one_column_per_conference_and_union_of_years(tmp_path, monkeypatch):
    pp = tmp_path / "per_paper" / "readability"
    pp.mkdir(parents=True)
    pd.DataFrame({"year": [2020, 2021], "flesch_ease": [10.0, 12.0]}).to_csv(pp / "neurips.csv", index=False)
    pd.DataFrame({"year": [2021, 2026], "flesch_ease": [8.0, 6.0]}).to_csv(pp / "iclr.csv", index=False)
    agg = tmp_path / "aggregate"
    aggregate("readability", ["flesch_ease"], venues=["neurips", "iclr", "icml"],
              per_paper_dir=str(tmp_path / "per_paper"), out_dir=str(agg))
    monkeypatch.setattr(export, "AGG", str(agg))
    out = tmp_path / "tmlr"
    export.export_metric("readability", "flesch_ease", "readability_flesch_ease", out=str(out))
    df = pd.read_csv(out / "readability_flesch_ease.csv")
    assert list(df.columns) == ["year", "neurips", "iclr"]      # no empty icml column
    assert df.year.tolist() == [2020, 2021, 2026]
    assert np.isnan(df.loc[df.year == 2026, "neurips"]).all()


def test_uncertainlp_readability_export_stays_neurips_only(tmp_path, monkeypatch):
    """The UncertaiNLP figures read year,neurips; ICLR 2026 must not add a row."""
    agg = tmp_path / "aggregate"
    agg.mkdir()
    pd.DataFrame({"year": [2025, 2026], "neurips_flesch_ease_mean": [7.6, np.nan],
                  "iclr_flesch_ease_mean": [12.5, 7.9]}).to_csv(agg / "readability.csv", index=False)
    monkeypatch.setattr(export, "AGG", str(agg))
    monkeypatch.setattr(export, "OUT", str(tmp_path / "pg"))
    monkeypatch.setattr(export, "READABILITY", ["flesch_ease"])
    export.export_readability()
    df = pd.read_csv(tmp_path / "pg" / "readability_flesch_ease.csv")
    assert list(df.columns) == ["year", "neurips"] and df.year.tolist() == [2025]


def test_papers_per_year_zero_becomes_gap(tmp_path, monkeypatch):
    agg = tmp_path / "aggregate"
    agg.mkdir()
    pd.DataFrame({"year": [2012, 2013], "neurips": [10, 12], "iclr": [0, 5],
                  "icml": [3, 4]}).to_csv(agg / "papers_per_year.csv", index=False)
    monkeypatch.setattr(export, "AGG", str(agg))
    export.export_papers_per_year(out=str(tmp_path / "tmlr"))
    df = pd.read_csv(tmp_path / "tmlr" / "papers_per_year.csv")
    assert np.isnan(df.iclr.iloc[0]) and df.iclr.iloc[1] == 5


def test_count_papers_by_year(tmp_path):
    d = tmp_path / "icml"
    d.mkdir()
    (d / "icml_2010.json").write_text(json.dumps([{"year": 2010}, {"year": 2010}]))
    (d / "icml_2011.json").write_text(json.dumps([{"year": 2011}]))
    (d / "notes.txt").write_text("ignored")
    assert count_papers_by_year("icml", str(tmp_path)) == {2010: 2, 2011: 1}
    assert count_papers_by_year("iclr", str(tmp_path)) == {}


# ── collinearity ─────────────────────────────────────────────────────────

def test_collinearity_of_perfectly_correlated_metrics():
    x = np.arange(1.0, 51.0)
    df = pd.DataFrame({m: x * (i + 1) for i, m in enumerate(METRICS)})
    r = analyse_frame(df, "v")
    assert r["mean_abs_pairwise_corr"] == 1.0 and r["pc1_var_explained"] == 1.0
    assert r["n_pairs"] == 105


def test_collinearity_drops_incomplete_rows():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({m: rng.normal(size=40) for m in METRICS})
    df.loc[0, "smog"] = np.nan
    df.loc[1, "lix"] = np.inf
    r = analyse_frame(df, "v")
    assert r["n_papers_total"] == 40 and r["n_papers_complete"] == 38
    assert r["mean_abs_pairwise_corr"] < 0.5


# ── LaTeX and URL robustness ─────────────────────────────────────────────

def test_year_row_counts_markup_and_scores_every_variant():
    papers = [{"year": 2024, "abstract": ABS + " See https://github.com/a/b for code."},
              {"year": 2024, "abstract": ABS + r" Let $x_i$ be the input of each step."},
              {"year": 2024, "abstract": "too short"}]
    r = year_row("neurips", papers)
    assert r["n"] == 3 and r["year"] == 2024
    assert r["pct_with_math"] == pytest.approx(100 / 3)
    assert r["pct_with_url"] == pytest.approx(100 / 3)
    for v in ("keep", "mathonly", "token", "drop"):
        assert r[f"n_scored_{v}"] == 2        # the short abstract is never scored


def test_summary_shares_and_shift():
    rows = []
    for venue, keep, token, mathonly in [("neurips", (20.0, 10.0), (20.0, 11.0), (20.0, 10.5)),
                                         ("iclr", (18.0, 8.0), (18.0, 8.5), (18.0, 8.2)),
                                         ("icml", (19.0, 9.0), (19.0, 9.8), (19.0, 9.3))]:
        for i, year in enumerate((2004, 2025) if venue == "neurips" else (2013, 2025)):
            rows.append({"venue": venue, "year": year, "flesch_keep": keep[i],
                         "flesch_token": token[i], "flesch_mathonly": mathonly[i],
                         "pct_with_math": 1.0 if year < 2005 else 20.0,
                         "pct_with_url": 0.5})
    d = pd.DataFrame(rows)
    d = pd.concat([d, pd.DataFrame([{**rows[0], "year": 2014}, {**rows[1], "year": 2024}])])
    s = dict(zip(*summary(d).T.values))
    assert s["neurips_raw_decline"] == -10.0 and s["neurips_norm_decline"] == -9.0
    assert s["neurips_markup_share_pct"] == pytest.approx(10.0)
    assert s["neurips_latex_share_pct"] == pytest.approx(5.0)
    assert s["neurips_url_share_pct"] == pytest.approx(5.0)
    assert s["markup_share_min_pct"] == pytest.approx(5.0)     # iclr: 0.5 of 10
    assert s["markup_share_max_pct"] == pytest.approx(10.0)
    assert s["neurips_math_pct_mean_before_2005"] == 1.0


# ── self-audit ───────────────────────────────────────────────────────────

def test_read_from_tex_expands_generated_macros_and_strips_markup(tmp_path):
    (tmp_path / "generated_round1.tex").write_text("\\newcommand{\\NPapers}{30,595}\n")
    (tmp_path / "paper.tex").write_text(r"""
\input{generated_round1.tex}
\title{A \emph{Short} Title}

\begin{abstract}
% a comment line
We study \NPapers{} papers~\citep{key} and find a 5\% \textbf{drop}.
\end{abstract}
""")
    title, abstract = read_from_tex(str(tmp_path / "paper.tex"))
    assert title == "A Short Title"
    assert abstract == "We study 30,595 papers and find a 5% drop."


def test_read_from_tex_title_next_to_author_with_nested_braces(tmp_path):
    (tmp_path / "p.tex").write_text(
        "\\title{A {\\em Nested} Title}\n\\author{Someone}\n\n"
        "\\begin{abstract}Words here.\\end{abstract}\n")
    title, _ = read_from_tex(str(tmp_path / "p.tex"))
    assert title == "A Nested Title"


def test_read_from_tex_without_abstract_exits(tmp_path):
    (tmp_path / "p.tex").write_text("\\title{T}\n\n")
    with pytest.raises(SystemExit):
        read_from_tex(str(tmp_path / "p.tex"))


def test_audit_runs_on_a_short_abstract(tmp_path):
    spacy = pytest.importorskip("spacy")
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        pytest.skip("en_core_web_sm not installed")
    from metrics.audit_self import audit
    pp = tmp_path / "per_paper"
    cols = {"readability": ["flesch_ease", "flesch_kincaid", "gunning_fog", "smog",
                            "dale_chall", "spache", "coleman_liau", "ari", "linsear_write",
                            "lix", "rix", "forcast", "powers_sumner_kearl",
                            "avg_sentence_length", "avg_syllables_per_word"],
            "sentence_length": ["words_per_sentence"],
            "parse_depth": ["parse_depth"], "np_density": ["np_density"],
            "noun_chunks": ["noun_chunks_per_100"], "nouns": ["noun_per_100"],
            "verbs": ["verb_per_100"], "numbers": ["num_per_100"],
            "signposting": ["signposting_per_100"], "hedging": ["hedging_per_100"],
            "active_narration": ["has_narrator"], "passive_rate": ["passive_rate"],
            "ttr": ["ttr"], "acronyms": ["abstract_acronym_density"],
            "sensational_language": [f"hype_{c}_per_100" for c in
                                     ("importance", "novelty", "rigor", "scale", "utility",
                                      "quality", "attitude", "problem", "additional", "total")]}
    for d, cs in cols.items():
        os.makedirs(pp / d)
        pd.DataFrame({c: [0.0, 1.0, 100.0] for c in cs}).to_csv(pp / d / "neurips.csv", index=False)
    text = ("We propose a new method for training neural networks with SGD. "
            "It is faster than prior work. We show it on three benchmarks.")
    df = audit("A Title", text, nlp, per_paper=str(pp))
    assert set(df.family) == {"readability", "style", "sensational", "acronyms"}
    assert len(df) == 15 + 12 + 10 + 1
    assert df.percentile.between(0, 100).all()
    assert "SGD" in df.attrs["abstract_acronyms"]
    # Three sentences of 11, 6 and 6 words after preprocessing.
    row = df[df.metric == "Sentence length (Hohmann)"].iloc[0]
    assert row.abstract == pytest.approx(23 / 3)
