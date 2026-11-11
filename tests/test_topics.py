"""Tests for the topic analyses and the Flesch decomposition.

verify.py compares every output on the full corpus. What is tested here is
what the corpus cannot isolate: that clustering is deterministic and gives
every paper a label; that the decompositions close exactly and recover known
answers on constructed data; that topics thin in some years are handled as
documented (NaN slope, zero weight, valued at the other year's mean); and that
the topic profile runs with and without citation data.
"""
import json

import numpy as np
import pandas as pd
import pytest

from analysis.flesch_decomposition import FRE_ASL, FRE_ASW, FRE_CONST, decompose as fdecomp
from analysis.topic_clusters import (build_features, cluster, clustering_text,
                                     load_conference_papers, stability)
from analysis.topic_decomposition import decompose, topic_gaps
from analysis.topic_profiles import fixed_mix, topic_profiles
from analysis.topic_trends import ols_clustered, topic_trends

COL = "topic_k15"


# ── clustering ───────────────────────────────────────────────────────────

def test_clustering_text_drops_links_and_markup():
    t = clustering_text("A $\\alpha$ title", "Code at https://github.com/x/y and www.a.org.")
    assert "github.com" not in t and "www" not in t and "$" not in t
    assert t.startswith("A ")


def test_load_keeps_venue_then_file_order_and_handles_absence(tmp_path):
    for venue, year, ids in [("neurips", 2020, ["n1", "n2"]), ("iclr", 2026, ["i1"])]:
        d = tmp_path / venue
        d.mkdir()
        (d / f"{venue}_{year}.json").write_text(json.dumps(
            [{"paper_id": i, "year": year, "title": None, "abstract": "x"} for i in ids]))
    df = load_conference_papers(str(tmp_path))
    assert df.paper_id.tolist() == ["n1", "n2", "i1"]     # ICLR 2026 kept
    assert df.title.tolist() == ["", "", ""]
    empty = load_conference_papers(str(tmp_path / "none"))
    assert empty.empty and "paper_id" in empty.columns


def _corpus(n_per=30):
    themes = ["graph neural network node message passing",
              "reinforcement learning policy reward agent",
              "image diffusion generative pixel denoising"]
    rng = np.random.default_rng(0)
    docs, truth = [], []
    for t, words in enumerate(themes):
        w = words.split()
        for _ in range(n_per):
            docs.append(" ".join(rng.choice(w, size=12)))
            truth.append(t)
    return pd.Series(docs), np.array(truth)


def test_clustering_is_deterministic_and_labels_every_paper():
    text, truth = _corpus()
    runs = []
    for _ in range(2):
        Z, lsa, terms = build_features(text, n_components=5, min_df=1)
        labels, term_df = cluster(Z, lsa, terms, k_values=[3])
        runs.append(labels[3])
    assert np.array_equal(runs[0], runs[1])
    assert len(runs[0]) == len(text)
    # three well separated themes come out as three clusters
    assert pd.crosstab(runs[0], truth).gt(0).sum(axis=1).eq(1).all()
    assert term_df.n.sum() == len(text) and len(term_df) == 3


def test_stability_of_perfectly_separated_clusters_is_one():
    text, _ = _corpus()
    Z, _, _ = build_features(text, n_components=5, min_df=1)
    (row,) = stability(Z, k_values=[3])
    assert row["ari"] == pytest.approx(1.0) and row["n_heldout"] == len(Z) - 2 * (len(Z) // 3)


# ── per-topic trends ─────────────────────────────────────────────────────

def test_ols_clustered_recovers_an_exact_line():
    x = np.repeat(np.arange(2015.0, 2020.0), 4)
    b, lo, hi = ols_clustered(3.0 - 0.5 * x, x, x.astype(int).astype(str))
    assert b == pytest.approx(-0.5) and lo == pytest.approx(hi)


def _trend_frame(topic, years, n, flesch_slope, venue="neurips"):
    rows = []
    for y in years:
        for i in range(n):
            rows.append({COL: topic, "venue": venue, "year": y,
                         "flesch_ease": 30 + flesch_slope * (y - 2015) + (i % 3 - 1),
                         "hype_total_per_100": 1 + 0.1 * (y - 2015) + 0.01 * (i % 2),
                         "abstract_acronym_density": 2.0 + 0.2 * (y - 2015) + 0.1 * (i % 2),
                         "title_acronym_density": 3.0 - 0.1 * (y - 2015) + 0.1 * (i % 2)})
    return pd.DataFrame(rows)


def test_topic_trends_signs_sorting_and_thin_topics():
    d = pd.concat([_trend_frame(0, range(2015, 2021), 30, -1.0),
                   _trend_frame(1, range(2015, 2021), 30, -2.0),
                   _trend_frame(2, range(2015, 2019), 30, -3.0),     # 4 years only
                   _trend_frame(1, [2021], 29, -2.0)])              # thin cell, ignored
    terms = pd.DataFrame({"k": [15] * 3, "cluster": [0, 1, 2], "top_terms": ["a", "b", "c"]})
    out = topic_trends(d, terms)
    assert out.topic.tolist()[:2] == [1, 0]                      # steepest decline first
    r1 = out.set_index("topic").loc[1]
    assert r1.flesch_slope == pytest.approx(-2.0)
    assert r1.flesch_last_year == 2020                           # 2021 has 29 papers
    assert r1.flesch_sig_same and r1.hype_sig_same
    assert not r1.acr_title_sig_same and r1.acr_title_sig        # significant, other way
    r2 = out.set_index("topic").loc[2]
    assert np.isnan(r2.flesch_slope) and np.isnan(r2.flesch_beta)


# ── Flesch decomposition ─────────────────────────────────────────────────

def _counts(year, words, sentences, syllables, n=3):
    return [{"venue": "neurips", "year": year, "word_count": words,
             "sentence_count": sentences, "syllable_count": syllables}] * n


def test_flesch_decomposition_closes_and_attributes_sentence_growth():
    d = pd.DataFrame(_counts(2015, 100, 5, 170) + _counts(2025, 100, 4, 170)
                     + _counts(2020, 1, 1, 9))                       # between years: unused
    r = fdecomp(d, "x", 2015, 2025)
    assert r["residual"] == pytest.approx(0, abs=1e-12)
    assert r["word_term"] == 0 and r["sentence_share"] == pytest.approx(100)
    assert r["fre_first"] == pytest.approx(FRE_CONST + FRE_ASL * 20 + FRE_ASW * 1.7)


def test_flesch_decomposition_skips_unscored_papers():
    d = pd.DataFrame(_counts(2015, 100, 5, 170) + _counts(2015, 0, 0, 0)
                     + _counts(2025, 100, 5, 200))
    r = fdecomp(d, "x", 2015, 2025)
    assert r["asl_first"] == 20 and r["sentence_term"] == 0


# ── topic profiles and fixed mix ─────────────────────────────────────────

def _profile_inputs():
    top = pd.DataFrame({"paper_id": list("abcde"), "year": [2015, 2015, 2025, 2025, 2025],
                        COL: [0, 1, 0, 1, 1]})
    terms = pd.DataFrame({"k": [15, 15, 10], "cluster": [0, 1, 0],
                          "top_terms": ["zero", "one", "other k"]})
    read = pd.DataFrame({"paper_id": list("abcd"), "flesch_ease": [30.0, 10.0, 20.0, 0.0],
                         "word_count": [100] * 4, "avg_sentence_length": [20.0] * 4})
    return top, terms, read


def test_profile_without_citations_has_no_citation_columns():
    top, terms, read = _profile_inputs()
    prof, d = topic_profiles(top, terms, read)
    assert list(prof.columns) == [COL, "n", "flesch", "abstract_words",
                                  "sentence_length", "top_terms"]
    assert prof[COL].tolist() == [1, 0]                       # least readable first
    one = prof.set_index(COL).loc[1]
    assert one.n == 3 and one.flesch == 5.0                   # e unscored: in n, not mean
    assert one.top_terms == "one"


def test_profile_with_citations_adds_columns_in_paper_order():
    top, terms, read = _profile_inputs()
    cit = pd.DataFrame({"paper_id": ["a", "c", "b"], "n_citations": [10, 30, 7]})
    prof, _ = topic_profiles(top, terms, read, citations=cit)
    assert list(prof.columns) == [COL, "n", "flesch", "abstract_words", "sentence_length",
                                  "median_citations", "n_with_citations", "top_terms"]
    zero = prof.set_index(COL).loc[0]
    assert zero.median_citations == 20 and zero.n_with_citations == 2


def test_fixed_mix_reweights_to_the_base_year():
    top, terms, read = _profile_inputs()
    _, d = topic_profiles(top, terms, read)
    fm = fixed_mix(d, min_year_n=1)
    assert fm.year.tolist() == [2015, 2025]
    assert fm.raw.tolist() == [20.0, 10.0]
    assert fm.fixed_mix.tolist() == [20.0, 10.0]              # 50/50 both years


def test_fixed_mix_gives_absent_base_topics_zero_weight_and_skips_thin_years():
    d = pd.DataFrame({COL: [0, 0, 0, 1], "year": [2015, 2016, 2016, 2016],
                      "flesch_ease": [20.0, 18.0, 18.0, 0.0]})
    fm = fixed_mix(d, min_year_n=1)
    assert fm.set_index("year").loc[2016, "fixed_mix"] == 18.0
    assert fixed_mix(d, min_year_n=10).empty


# ── within / between decomposition ───────────────────────────────────────

def test_topic_gaps_recover_additive_effects():
    rows = [{COL: t, "year": y, "flesch_ease": 10 + 5 * t - 2 * (y - 2015)}
            for t in range(3) for y in range(2015, 2019) for _ in range(2)]
    g = topic_gaps(pd.DataFrame(rows), COL)
    assert g.tolist() == pytest.approx([0.0, 5.0, 10.0])


def _decomp_inputs():
    # topic 0 declines 20 -> 10; topic 1 is constant at 0, share 1/4 -> 3/8;
    # topic 2 exists only in 2025. Means: 15 in 2015, 30/8 in 2025.
    def papers(year, topic, n, f):
        return [{"paper_id": f"{year}_{topic}_{i}", "year": year, COL: topic,
                 "flesch_ease": f} for i in range(n)]
    rows = (papers(2015, 0, 3, 20.0) + papers(2015, 1, 1, 0.0)
            + papers(2020, 0, 2, 15.0) + papers(2020, 1, 2, 0.0)
            + papers(2025, 0, 1, 10.0) + papers(2025, 1, 3, 0.0)
            + papers(2025, 2, 4, 5.0))
    d = pd.DataFrame(rows)
    return d[["paper_id", "year", COL]], d[["paper_id", "flesch_ease"]]


def test_symmetric_split_closes_and_absent_topic_enters_only_by_share():
    top, read = _decomp_inputs()
    t, summ = decompose(top, read, hard={1})
    s = summ.set_index("method")
    for m in s.index:
        assert s.loc[m, "within"] + s.loc[m, "between"] == pytest.approx(s.loc[m, "total"])
    assert s.loc["symmetric", "total"] == pytest.approx(30 / 8 - 15.0)
    assert t.loc[2, "f0"] == t.loc[2, "f1"] == 5.0 and t.loc[2, "within"] == 0
    assert t.loc[2, "w0"] == 0 and t.loc[2, "n0"] == 0
    assert summ.topics.iloc[0] == 3 and summ.topics_declining.iloc[0] == 1
    assert summ.hard_share0.iloc[0] == pytest.approx(25.0)
    assert summ.hard_share1.iloc[0] == pytest.approx(37.5)


def test_decompose_without_papers_in_an_endpoint_year_raises():
    top, read = _decomp_inputs()
    with pytest.raises(ValueError):
        decompose(top, read, hard=set(), last_year=2030)
