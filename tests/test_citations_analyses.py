"""Tests for the citation analyses and the snapshot check.

verify.py compares the citation numbers the paper prints with the
recomputed outputs when the published snapshot is present (no citation output
is distributed). These tests cover what that run cannot: the
percentile rule under ties, the exclusion rules (immature years, missing
counts, zero-length bibliographies, authorless records), the decile cut-offs
at their boundaries, inputs that are missing or empty, and the three
snapshot modes.
"""
import json
import os

import numpy as np
import pandas as pd
import pytest

import citations.coverage as cov
import citations.judge_deciles as jd
import citations.readability_deciles as rdd
import citations.references as refs
import citations.regression as reg
import citations.regression_topics as rt
import citations.snapshot as snap
import citations.topic_citations as tc
from citations.enrich import enrich


# ── enrich: within-year percentile and MNCS ──────────────────────────────

def test_percentile_ties_share_the_mean_rank():
    df = pd.DataFrame({"year": [2020] * 4, "n_citations": [0, 0, 5, 10]})
    out = enrich(df)
    # kind="rank": a tie spans ranks 1 and 2, so both get 1.5 / 4
    assert out.citation_percentile.tolist() == [37.5, 37.5, 75.0, 100.0]
    assert out.mncs.tolist() == pytest.approx([0, 0, 5 / 3.75, 10 / 3.75])


def test_percentile_within_year_and_missing_counts():
    df = pd.DataFrame({"year": [2020, 2020, 2021, 2021, 2022],
                       "n_citations": [1, "", 100, None, None]})
    out = enrich(df)
    assert out.citation_percentile.iloc[0] == 100.0      # alone among valid 2020
    assert np.isnan(out.citation_percentile.iloc[1])
    assert out.citation_percentile.iloc[2] == 100.0      # 2021 not mixed with 2020
    assert np.isnan(out.citation_percentile.iloc[4])     # year with no valid count


def test_mncs_undefined_when_year_mean_is_zero():
    out = enrich(pd.DataFrame({"year": [2025, 2025], "n_citations": [0, 0]}))
    assert out.citation_percentile.tolist() == [75.0, 75.0]   # ranks 1, 2 -> 1.5 / 2
    assert out.mncs.isna().all()


def test_enrich_overwrites_stale_columns_and_keeps_input():
    df = pd.DataFrame({"year": [1], "n_citations": ["3"], "citation_percentile": [9.0],
                       "mncs": [9.0]})
    out = enrich(df)
    assert out.citation_percentile.iloc[0] == 100.0 and out.mncs.iloc[0] == 1.0
    assert df.citation_percentile.iloc[0] == 9.0


def test_enrich_empty():
    out = enrich(pd.DataFrame({"year": [], "n_citations": []}))
    assert list(out.columns) == ["year", "n_citations", "citation_percentile", "mncs"]


# ── snapshot: strict, fresh, absent ──────────────────────────────────────

def _write_snapshot(tmp_path, contents):
    for name, text in contents.items():
        (tmp_path / name).write_text(text)
    return {name: snap.sha256(str(tmp_path / name)) for name in contents}


def test_snapshot_modes(tmp_path):
    files = {"neurips_s2.csv": "a\n", "iclr_s2.csv": "b\n", "icml_s2.csv": "c\n"}
    want = _write_snapshot(tmp_path, files)
    assert snap.mode(str(tmp_path), want) == snap.STRICT
    (tmp_path / "icml_s2.csv").write_text("c changed\n")
    assert snap.mode(str(tmp_path), want) == snap.FRESH
    assert snap.status(str(tmp_path), want)["icml_s2.csv"] == "differs"
    os.remove(tmp_path / "iclr_s2.csv")
    assert snap.mode(str(tmp_path), want) == snap.ABSENT
    assert snap.status(str(tmp_path), want)["iclr_s2.csv"] == "missing"


def test_snapshot_absent_for_empty_dir(tmp_path):
    assert snap.mode(str(tmp_path)) == snap.ABSENT
    assert snap.mode(str(tmp_path / "does_not_exist")) == snap.ABSENT


def test_snapshot_sha256_matches_hashlib(tmp_path):
    import hashlib
    p = tmp_path / "f"
    p.write_bytes(os.urandom(3 * (1 << 20) + 7))
    assert snap.sha256(str(p)) == hashlib.sha256(p.read_bytes()).hexdigest()


def test_snapshot_table_covers_the_three_venues_with_hashes_and_dates():
    assert set(snap.SNAPSHOT) == {f"{v}_s2.csv" for v in ("neurips", "iclr", "icml")}
    assert set(snap.RETRIEVED) == set(snap.SNAPSHOT)
    for name, h in snap.SNAPSHOT.items():
        assert len(h) == 64 and int(h, 16) >= 0
        assert snap.RETRIEVED[name][:4] == "2026"


# ── coverage ─────────────────────────────────────────────────────────────

def test_coverage_counts_and_cutoff():
    df = pd.DataFrame({
        "year": [2023, 2024, 2024, 2025, 2025],
        "n_citations": [1.0, None, 3.0, None, 0.0],
        "match_type": ["title", "unmatched", "openalex", "unmatched", "s2_fuzzy"]})
    r = cov.venue_row(df, "neurips", 2024)
    assert r["n_papers_to_max_year"] == 3 and r["n_with_citations_to_max_year"] == 2
    assert r["coverage_pct"] == pytest.approx(200 / 3)
    assert r["n_papers"] == 5 and r["n_error"] == 0
    assert r["supplemented_pct"] == pytest.approx(40.0)   # over all years


def test_coverage_empty_venue_is_nan_not_error():
    r = cov.venue_row(pd.DataFrame({"year": [], "n_citations": [], "match_type": []}), "icml")
    assert np.isnan(r["coverage_pct"]) and np.isnan(r["supplemented_pct"])


def test_coverage_missing_venue_file_exits(tmp_path):
    with pytest.raises(SystemExit, match="iclr_s2.csv"):
        cov.coverage(["iclr"], cit_dir=str(tmp_path))


# ── references ───────────────────────────────────────────────────────────

def _s2(path, rows):
    pd.DataFrame(rows, columns=["paper_id", "year", "n_citations", "n_references",
                                "match_type"]).to_csv(path, index=False)


def test_references_exclude_zero_and_blank_and_thin_years(tmp_path):
    rows = [(f"a{i}", 2020, 1, 10.0, "title") for i in range(3)]
    rows += [("z", 2020, 1, 0.0, "title"), ("b", 2020, None, None, "unmatched")]
    rows += [("c", 2021, 1, 50.0, "title")]
    _s2(tmp_path / "neurips_s2.csv", rows)
    kept, seen = refs.load(str(tmp_path / "neurips_s2.csv"))
    assert kept[2020] == [10.0] * 3 and seen[2020] == 5
    long_p, wide_p = refs.write({"neurips": kept}, {"neurips": seen}, ["neurips"],
                                str(tmp_path / "out"), min_papers=2)
    long = pd.read_csv(long_p)
    assert long.to_dict("records") == [{"venue": "neurips", "year": 2020,
                                        "references_mean": 10.0, "n_papers": 3,
                                        "n_total": 5, "coverage": 0.6}]
    wide = open(wide_p).read().splitlines()
    assert wide == ["year,neurips", "2020,10.0", "2021,nan"]


def test_references_year_union_across_venues(tmp_path):
    long_p, wide_p = refs.write({"neurips": {2020: [1.0]}, "iclr": {2021: [2.0]}},
                                {"neurips": {2020: 1}, "iclr": {2021: 1}},
                                ["neurips", "iclr"], str(tmp_path), min_papers=1)
    assert open(wide_p).read().splitlines() == ["year,neurips,iclr", "2020,1.0,nan",
                                                "2021,nan,2.0"]


def test_references_missing_file_exits(tmp_path):
    with pytest.raises(SystemExit, match="icml_s2.csv"):
        refs.load(str(tmp_path / "icml_s2.csv"))


# ── regression ───────────────────────────────────────────────────────────

def _venue_files(tmp_path, venue, n=60, seed=0, year0=2023):
    """A small venue: readability, citations and processed records."""
    rng = np.random.default_rng(seed)
    ids = [f"{venue}{i}" for i in range(n)]
    years = [year0 + (i % 3) for i in range(n)]               # 2023, 2024, 2025
    flesch = rng.normal(20, 10, n)
    words = rng.integers(80, 300, n)
    cites = np.round(np.exp(1 + 0.05 * flesch + rng.normal(0, 0.5, n)))
    for sub in ("readability", "citations", f"processed/{venue}"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"paper_id": ids, "year": years, "flesch_ease": flesch,
                  "avg_sentence_length": rng.normal(22, 4, n), "word_count": words}
                 ).to_csv(tmp_path / "readability" / f"{venue}.csv", index=False)
    pd.DataFrame({"paper_id": ids, "year": years, "n_citations": cites}
                 ).to_csv(tmp_path / "citations" / f"{venue}_s2.csv", index=False)
    recs = [{"paper_id": p, "authors": ["a"] * (1 + i % 4)} for i, p in enumerate(ids)]
    recs[0]["authors"] = []                    # authorless record, dropped
    del recs[1]["authors"]                     # missing field, dropped
    json.dump(recs, open(tmp_path / f"processed/{venue}/{venue}_x.json", "w"))
    return tmp_path


def _load(tmp_path, venue, **kw):
    return reg.load(venue, read_dir=str(tmp_path / "readability"),
                    cit_dir=str(tmp_path / "citations"),
                    processed_dir=str(tmp_path / "processed"), **kw)


def test_regression_sample_rules(tmp_path):
    _venue_files(tmp_path, "iclr")
    d = _load(tmp_path, "iclr")
    assert d.year.max() == 2024 and (d.n_authors > 0).all()
    assert {"iclr0", "iclr1"}.isdisjoint(d.paper_id)
    assert (d.venue == "iclr").all()
    assert len(_load(tmp_path, "iclr", max_year=2025)) > len(d)


def test_regression_missing_citations_dropped(tmp_path):
    _venue_files(tmp_path, "icml")
    c = pd.read_csv(tmp_path / "citations" / "icml_s2.csv")
    c.loc[5, "n_citations"] = np.nan
    c.to_csv(tmp_path / "citations" / "icml_s2.csv", index=False)
    assert "icml5" not in set(_load(tmp_path, "icml").paper_id)


def test_regression_missing_venue_exits(tmp_path):
    with pytest.raises(SystemExit, match="neurips.csv"):
        _load(tmp_path, "neurips")


def test_ols_recovers_planted_slope():
    rng = np.random.default_rng(1)
    n = 4000
    d = pd.DataFrame({"venue": "v", "year": rng.integers(2000, 2010, n),
                      "flesch_ease": rng.normal(0, 1, n),
                      "word_count": rng.integers(50, 300, n),
                      "n_authors": rng.integers(1, 8, n)})
    d["n_citations"] = np.expm1(0.5 * d.flesch_ease + rng.normal(0, 1, n)).clip(0)
    a = reg.ols_fe_cluster(d)
    assert a["n"] == n and a["n_clusters"] == 10 and a["beta_flesch"] > 0.2
    assert a["ci_lo"] < a["beta_flesch"] < a["ci_hi"]


def test_ols_year_confound_is_absorbed_by_fixed_effects():
    """Readability and citations both trend by year, unrelated within a year:
    the pooled correlation is strong, the fixed effects coefficient is not."""
    rng = np.random.default_rng(2)
    n = 6000
    year = rng.integers(2000, 2012, n)
    d = pd.DataFrame({"venue": "v", "year": year,
                      "flesch_ease": 3.0 * (year - 2000) + rng.normal(0, 1, n),
                      "word_count": rng.integers(50, 300, n),
                      "n_authors": rng.integers(1, 8, n)})
    d["n_citations"] = np.expm1(0.4 * (year - 2000) + rng.normal(0, 1, n)).clip(0)
    assert np.corrcoef(d.flesch_ease, np.log1p(d.n_citations))[0, 1] > 0.5
    r = reg.ols_fe_cluster(d)
    assert r["ci_lo"] < 0 < r["ci_hi"]


def test_cohens_d_known_value_small_groups_and_ties():
    # one venue-year of 20: pct = rank / 20; top >= 0.9 is ranks 18-20, bottom <= 0.1 is 1-2
    x = [0, 2] + [9] * 15 + [2, 4, 6]
    d = pd.DataFrame({"venue": "v", "year": 2020, "n_citations": range(20), "x": x})
    top, bot = reg.decile_groups(d)
    assert list(top.x) == [2, 4, 6] and list(bot.x) == [0, 2]
    # pooled variance (2 * 4 + 1 * 2) / 3
    assert reg.cohens_d(d, "x") == pytest.approx(3 / np.sqrt(10 / 3))
    # a group of one has no variance: d is NaN, as upstream
    ten = pd.DataFrame({"venue": "v", "year": 2020, "n_citations": range(10), "x": range(10)})
    assert np.isnan(reg.cohens_d(ten, "x"))
    tied = pd.DataFrame({"venue": "v", "year": 2020, "n_citations": [0] * 10, "x": range(10)})
    t2, b2 = reg.decile_groups(tied)
    assert t2.empty and b2.empty                 # all tied at pct 0.55


def test_regression_run_shapes(tmp_path):
    for i, v in enumerate(("neurips", "iclr")):
        _venue_files(tmp_path, v, n=120, seed=i)
    frames = {v: _load(tmp_path, v) for v in ("neurips", "iclr")}
    r, d = reg.run(frames)
    assert r.model.tolist() == ["pooled", "neurips", "iclr"]
    assert list(r.columns) == reg.COLUMNS
    assert r.loc[0, "n"] == r.loc[1, "n"] + r.loc[2, "n"]
    assert d.metric.tolist() == reg.D_METRICS and (d["sample"] == "pooled").all()


# ── topic controls ───────────────────────────────────────────────────────

def _topic_frame(n=1500, seed=3):
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({"paper_id": [f"p{i}" for i in range(n)], "venue": "v",
                      "year": rng.integers(2015, 2020, n),
                      "flesch_ease": rng.normal(15, 8, n),
                      "word_count": rng.integers(80, 300, n),
                      "n_authors": rng.integers(1, 9, n)})
    d["topic_k10"] = rng.integers(0, 4, n)
    d["n_citations"] = np.round(np.exp(2 + 0.02 * d.flesch_ease + 0.8 * d.topic_k10
                                       + rng.normal(0, 0.7, n)))
    return d


def test_topic_fit_without_topics_equals_published_model():
    d = _topic_frame()
    a, b = rt.fit(d, None), reg.ols_fe_cluster(d)
    for k in ("beta_flesch", "se_flesch", "ci_lo", "ci_hi"):
        assert a[k] == pytest.approx(b[k], rel=1e-9, abs=1e-12)
    assert a["n_topic_dummies"] == 0 and "wald_topics" not in a


def test_topic_fit_dummies_and_wald():
    r = rt.fit(_topic_frame(), "topic_k10")
    assert r["n_topic_dummies"] == 3 and r["wald_df"] == 3 and r["wald_topics"] > 100
    assert r["r2_within"] > rt.fit(_topic_frame(), None)["r2_within"]


def test_topic_run_skips_absent_k_and_unassigned_papers(capsys):
    d = _topic_frame()
    topics = d[["paper_id", "venue", "year", "topic_k10"]].iloc[:-100]
    out = rt.run(d.drop(columns=["topic_k10"]), topics, k_values=[10, 15])
    assert out.model.tolist() == ["no topic control (published)", "+ topic FE (k=10)"]
    assert out.n.tolist() == [len(d), len(d) - 100]
    assert "topic_k15" in capsys.readouterr().out


# ── topic citation columns ───────────────────────────────────────────────

def test_citation_columns_topic_without_citations():
    assign = pd.DataFrame({"paper_id": list("abcde"), "topic_k15": [0, 0, 0, 1, 1]})
    cit = pd.DataFrame({"paper_id": ["a", "b", "c"], "n_citations": [1.0, 3.0, 10.0]})
    c = tc.citation_columns(assign, cit)
    assert c.median_citations.tolist()[0] == 3.0 and np.isnan(c.median_citations[1])
    assert c.n_with_citations.tolist() == [3, 0]


def test_add_to_profile_inserts_before_top_terms_keeps_order():
    prof = pd.DataFrame({"topic_k15": [2, 0], "n": [5, 7], "flesch": [1.0, 2.0],
                         "top_terms": ["x", "y"]})
    cols = pd.DataFrame({"topic_k15": [0, 2], "median_citations": [4.0, 9.0],
                         "n_with_citations": [3, 1]})
    out = tc.add_to_profile(prof, cols)
    assert list(out.columns) == ["topic_k15", "n", "flesch", "median_citations",
                                 "n_with_citations", "top_terms"]
    assert out.topic_k15.tolist() == [2, 0] and out.median_citations.tolist() == [9.0, 4.0]
    again = tc.add_to_profile(out, cols)          # idempotent on a full profile
    assert again.equals(out)


def test_add_to_profile_without_top_terms_appends():
    prof = pd.DataFrame({"topic_k15": [0], "flesch": [1.0]})
    cols = pd.DataFrame({"topic_k15": [0], "median_citations": [1.0], "n_with_citations": [1]})
    assert list(tc.add_to_profile(prof, cols).columns)[-2:] == ["median_citations",
                                                               "n_with_citations"]


def test_topic_citation_corr():
    p = pd.DataFrame({"flesch": [1.0, 2.0, 3.0, 4.0], "median_citations": [8, 6, 4, 2]})
    c = tc.topic_citation_corr(p)
    assert c["pearson"] == pytest.approx(-1) and c["spearman"] == pytest.approx(-1)
    two = tc.topic_citation_corr(p.iloc[:2])
    assert np.isnan(two["pearson"]) and two["n_topics"] == 2
    gap = p.assign(median_citations=[8, np.nan, 4, 2])
    assert tc.topic_citation_corr(gap)["n_topics"] == 3


def test_base_profile():
    assign = pd.DataFrame({"paper_id": list("abc"), "topic_k15": [0, 0, 1]})
    read = pd.DataFrame({"paper_id": ["a", "b"], "flesch_ease": [10.0, 20.0]})
    b = tc.base_profile(assign, read)
    assert b.n.tolist() == [2, 1] and b.flesch.tolist()[0] == 15.0 and np.isnan(b.flesch[1])


# ── readability deciles ──────────────────────────────────────────────────

def _decile_inputs(tmp_path, venue, pcts, years, flesch):
    (tmp_path / "r").mkdir(exist_ok=True)
    (tmp_path / "c").mkdir(exist_ok=True)
    ids = [f"{venue}{i}" for i in range(len(pcts))]
    pd.DataFrame({"paper_id": ids, "year": years, "flesch_ease": flesch}
                 ).to_csv(tmp_path / "r" / f"{venue}.csv", index=False)
    pd.DataFrame({"paper_id": ids, "year": years, "citation_percentile": pcts}
                 ).to_csv(tmp_path / "c" / f"{venue}_s2.csv", index=False)


def test_decile_boundaries_inclusive_and_max_year(tmp_path):
    _decile_inputs(tmp_path, "neurips", [90, 89.9, 10, 10.1, None, 95],
                   [2024] * 5 + [2025], [30.0, 0, 10.0, 0, 0, 99.0])
    df = rdd.load(["neurips"], 2024, str(tmp_path / "r"), str(tmp_path / "c"))
    out = rdd.top_bottom(df).set_index("metric")
    assert list(out.index) == ["flesch_ease"]            # absent metrics skipped
    assert out.loc["flesch_ease", "top_n"] == 1 and out.loc["flesch_ease", "top_mean"] == 30
    assert out.loc["flesch_ease", "bottom_n"] == 1 and out.loc["flesch_ease", "delta"] == 20
    assert np.isnan(out.loc["flesch_ease", "top_ci"])    # one value, no spread


def test_decile_pools_venues_and_names_output(tmp_path):
    _decile_inputs(tmp_path, "iclr", [95, 5], [2020, 2020], [2.0, 1.0])
    _decile_inputs(tmp_path, "icml", [95, 5], [2020, 2020], [4.0, 1.0])
    df = rdd.load(["iclr", "icml"], None, str(tmp_path / "r"), str(tmp_path / "c"))
    out = rdd.top_bottom(df).set_index("metric")
    assert out.loc["flesch_ease", "top_mean"] == 3.0
    assert out.loc["flesch_ease", "top_ci"] == pytest.approx(1.96 * np.sqrt(2) / np.sqrt(2))
    assert rdd.suffix(["iclr", "icml"]) == "_combined"
    assert rdd.suffix(["neurips"]) == "" and rdd.suffix(["icml"]) == "_icml"


def test_decile_empty_groups_give_empty_rows():
    df = pd.DataFrame({"citation_percentile": [50.0], "flesch_ease": [1.0]})
    out = rdd.top_bottom(df)
    assert out.top_n.tolist() == [0] and np.isnan(out.delta.iloc[0])


def test_decile_missing_venue_exits(tmp_path):
    with pytest.raises(SystemExit):
        rdd.load(["neurips"], 2024, str(tmp_path), str(tmp_path))


# ── judge deciles ────────────────────────────────────────────────────────

def _judge_inputs(tmp_path, venue="iclr", models=("M1", "M2")):
    jdir = tmp_path / "judge" / venue
    jdir.mkdir(parents=True)
    ids, pcts = ["t", "b", "m", "late"], [95.0, 5.0, 50.0, 99.0]
    years = [2024, 2024, 2024, 2025]
    for k, m in enumerate(models):
        rows = []
        for pid, y in zip(ids, years):
            for prompt in jd.PROMPTS:
                base = {"t": 4.0, "b": 2.0, "m": 3.0, "late": 1.0}[pid] + k
                for run, off in enumerate((-1.0, 0.0, 1.0)):     # mean over runs = base
                    rows.append((pid, y, prompt, run, base + off))
        pd.DataFrame(rows, columns=["paper_id", "year", "prompt_name", "run", "score"]
                     ).to_csv(jdir / f"{m}.csv", index=False)
    (tmp_path / "cit").mkdir()
    pd.DataFrame({"paper_id": ids, "year": years, "citation_percentile": pcts}
                 ).to_csv(tmp_path / "cit" / f"{venue}_s2.csv", index=False)


def test_judge_deciles_model_average_and_ci(tmp_path):
    _judge_inputs(tmp_path)
    out = jd.build(["iclr"], 2024, str(tmp_path / "judge"), str(tmp_path / "cit"),
                   models=["M1", "M2"])
    assert out.prompt.tolist() == jd.PROMPTS and list(out.columns) == jd.COLUMNS
    r = out.iloc[0]
    assert r.top_mean == 4.5 and r.bottom_mean == 2.5 and r.delta == 2.0 and r.n_models == 2
    assert r.top_ci == pytest.approx(1.96 * np.std([4, 5], ddof=1) / np.sqrt(2))


def test_judge_deciles_max_year_none_includes_immature_year(tmp_path):
    _judge_inputs(tmp_path)
    out = jd.build(["iclr"], None, str(tmp_path / "judge"), str(tmp_path / "cit"),
                   models=["M1", "M2"])
    assert out.top_mean.iloc[0] == pytest.approx((4 + 1) / 2 + 0.5)


def test_judge_deciles_missing_model_file_exits(tmp_path):
    _judge_inputs(tmp_path)
    with pytest.raises(SystemExit, match="M3.csv"):
        jd.build(["iclr"], 2024, str(tmp_path / "judge"), str(tmp_path / "cit"),
                 models=["M1", "M3"])
