"""Tests for the AI-Native Academia generators and checkers
(paper/ai_native_academia/, src/analysis/judge_agreement.py and the
--venues option of src/analysis/topic_clusters.py).

verify.py compares the built macros, tables and analysis CSVs with the
references on the full corpus. Tested here: the generators run on the
committed reference inputs reproduce every citation-free macro the paper
prints; the citation items are skipped without citation outputs and written
with them; the checker's modes; the topic labels and the table row format
kept from upstream; and the judge statistics on small inputs.
"""
import csv
import importlib.util
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "paper", "ai_native_academia")
REF = os.path.join(HERE, "reference")
SHARED = os.path.join(ROOT, "shared", "reference")


def _load(name: str):
    key = f"ai_native_academia_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, os.path.join(HERE, f"{name}.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return sys.modules[key]


T = _load("topics")
MM = _load("make_macros")
MT = _load("make_tables")
CM = _load("check_macros")
CT = _load("check_tables")

from analysis import judge_agreement as ja  # noqa: E402
from analysis import topic_clusters as tc  # noqa: E402


@pytest.fixture(scope="module")
def ref_data(tmp_path_factory):
    """A data root holding only committed reference files."""
    d = tmp_path_factory.mktemp("aina")
    agg = d / "aggregate"
    agg.mkdir()
    shutil.copy(os.path.join(ROOT, "shared", "reference", "analysis",
                             "latex_robustness.csv"), agg)
    shutil.copy(os.path.join(ROOT, "shared", "reference", "analysis",
                             "acronym_reuse_freq.csv"), agg)
    for f in os.listdir(os.path.join(REF, "analysis")):
        shutil.copy(os.path.join(REF, "analysis", f), agg)
    for fam in ("readability", "acronyms"):
        (d / "per_paper" / fam).mkdir(parents=True)
        for v in ("neurips", "iclr", "icml"):
            shutil.copy(os.path.join(SHARED, "per_paper", fam, f"{v}.csv"),
                        d / "per_paper" / fam)
    return d


@pytest.fixture(scope="module")
def built(ref_data):
    out = ref_data / "ai_native_academia"
    rec = MM.build(str(ref_data), str(out))
    return out, rec


# ── macros on the reference inputs ───────────────────────────────────────

def test_reference_inputs_reproduce_every_citation_free_macro(built):
    out, rec = built
    assert rec["incomplete"] == []
    res = CM.check(str(out), "absent")
    assert res.ok == 42 and res.bad == 0 and res.missing == 0
    assert res.skipped == len(MM.CITATION_MACROS) == 10


def test_absent_citations_skip_exactly_the_citation_items(built):
    out, rec = built
    assert set(rec["macros"][MM.MACRO_FILE]) == MM.CITATION_MACROS
    assert rec["tables"] == ["topic_profile.tex"]
    assert not os.path.exists(out / "tables" / "topic_profile.tex")


def test_reference_holds_no_citation_macro():
    with open(os.path.join(REF, "macros.csv"), newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 42
    assert not {r["name"] for r in rows} & MM.CITATION_MACROS
    assert CM.load_reference()                       # raises on a citation macro


def test_reference_profile_has_no_citation_column():
    cols = pd.read_csv(os.path.join(REF, "analysis", "topic_profiles_neurips.csv")).columns
    assert not {"median_citations", "n_with_citations"} & set(cols)


def test_checker_reports_a_changed_value(built, tmp_path):
    out, _ = built
    shutil.copytree(out, tmp_path / "b")
    path = tmp_path / "b" / MM.MACRO_FILE
    text = path.read_text().replace("\\newcommand{\\TopicK}{15}", "\\newcommand{\\TopicK}{16}")
    path.write_text(text)
    res = CM.check(str(tmp_path / "b"), "absent")
    assert res.bad == 1 and any("TopicK" in line for line in res.lines)


def test_checker_flags_a_skipped_non_citation_item(built, tmp_path):
    out, _ = built
    shutil.copytree(out, tmp_path / "b")
    sk = json.loads((tmp_path / "b" / "skipped.json").read_text())
    sk["macros"][MM.MACRO_FILE].append("TopicK")
    (tmp_path / "b" / "skipped.json").write_text(json.dumps(sk))
    res = CM.check(str(tmp_path / "b"), "absent")
    assert any("skipped non-citation items ['TopicK']" in line for line in res.lines)


def test_missing_input_marks_its_section_incomplete(tmp_path):
    rec = MM.build(str(tmp_path), str(tmp_path / "out"))
    sections = {i["section"] for i in rec["incomplete"]}
    assert {"normalisation", "topics", "fixed_mix", "acronyms_per_title"} <= sections
    res = CM.check(str(tmp_path / "out"), "absent")
    assert res.missing == 42
    assert any(line.startswith("  INCOMPLETE") for line in res.lines)


def test_citation_outputs_add_their_macros_and_the_table(ref_data, tmp_path):
    """Synthetic citation outputs (no real citation value is used)."""
    d = tmp_path / "d"
    shutil.copytree(ref_data, d, ignore=shutil.ignore_patterns("ai_native_academia"))
    cit = d / "aggregate" / "citations" / "ai_native_academia"
    cit.mkdir(parents=True)
    pd.DataFrame({"model": ["none", "k10", "k15"], "n": [1000.0] * 3, "n_clusters": [20] * 3,
                  "beta_flesch": [0.05, 0.03, 0.04], "se_flesch": [0.01] * 3,
                  "ci_lo": [0.03, 0.01, 0.02], "ci_hi": [0.07, 0.05, 0.06],
                  "r2_within": [0.1, 0.2, 0.3], "n_topic_dummies": [0, 9, 14]}
                 ).to_csv(cit / "citation_regression_topics.csv", index=False)
    prof = pd.read_csv(d / "aggregate" / T.PROFILES)
    pd.DataFrame({"topic_k15": prof.topic_k15, "median_citations": np.arange(len(prof)) + 10.0}
                 ).to_csv(cit / "topic_citations.csv", index=False)
    rec = MM.build(str(d), str(d / "ai_native_academia"))
    assert rec["macros"][MM.MACRO_FILE] == [] and rec["tables"] == []
    assert rec["written"][MM.MACRO_FILE] == 52
    body = (d / "ai_native_academia" / "tables" / "topic_profile.tex").read_text()
    assert body.count("\\\\\n") == len(prof) + 1          # header and one row per topic


# ── upstream formats kept ────────────────────────────────────────────────

def test_topic_labels_name_every_reference_cluster():
    terms = pd.read_csv(os.path.join(REF, "analysis", "topic_terms_neurips.csv"))
    labels = [T.topic_label(t) for t in terms[terms.k == T.K].top_terms]
    assert len(set(labels)) == T.K


def test_topic_label_without_a_rule_raises():
    with pytest.raises(ValueError):
        T.topic_label("alpha, beta, gamma")


def test_profile_row_braces_only_the_first_comma():
    big = pd.Series({"label": "X", "top_terms": "a, b, c", "n": 1234, "flesch": 9.04,
                     "median_citations": 34.0})
    small = big.copy()
    small["n"] = 808
    assert MM.profile_row(big) == "X & a{,} b & 1,234 & 9.0 & 34 \\\\\n"
    assert MM.profile_row(small) == "X & a, b & 808 & 9.0 & 34 \\\\\n"


def test_topic_clusters_suffix_keeps_the_pooled_names():
    assert tc.suffix(tc.VENUES) == ""
    assert tc.suffix(["neurips"]) == "_neurips"


# ── tables ───────────────────────────────────────────────────────────────

def test_tables_on_reference_inputs(ref_data, tmp_path):
    out = tmp_path / "tables"
    rec = MT.build(str(ref_data), str(out))
    assert sorted(rec["written"]) == ["acronym_reuse_freq.tex", "judge_agreement.tex",
                                      "judge_raw_stability.tex"]
    assert rec["skipped"] == {"citation_readability_top_bottom.tex":
                              MT.REASONS["citation"]}
    n = pd.read_csv(ref_data / "aggregate" / "judge_scored_papers_neurips.csv")
    s = n[n.prompt_name == "simple"]
    cap = rec["caption_values"]["judge_raw_stability.tex"]
    assert cap["first_year_papers_min"] == str(s.n_1987.min())
    assert cap["first_year_papers_max"] == str(s.n_1987.max())
    # The PubMed row is what shared/baselines/acronym_histograms.csv gives,
    # which differs from the row the paper prints.
    reuse = pd.read_csv(ref_data / "aggregate" / "acronym_reuse_freq.csv").set_index("venue")
    tex = (out / "acronym_reuse_freq.tex").read_text()
    assert f"PubMed & {int(reuse.loc['PubMed', 'n_unique']):,} &" in tex
    assert "ICLR" not in tex and "\\caption" not in tex


def test_check_tables_without_manuscript_skips_all(tmp_path):
    res = CT.check(str(tmp_path), "absent", None)
    assert res.bad == res.missing == 0 and len(res.records) == 5


# ── judge statistics ─────────────────────────────────────────────────────

def _frame():
    rows = []
    for m_i, m in enumerate(["A", "B", "C"]):
        for p in range(6):
            for run in range(3):
                score = 1 + (p + m_i * (p % 2)) % 5 + (1 if (m == "C" and run == 2) else 0)
                rows.append({"paper_id": f"p{p}", "year": 2000 + p % 2, "prompt_name": "simple",
                             "run": run, "score": float(score), "model": m})
    return pd.DataFrame(rows)


def test_run_stability_identical_share():
    st = ja.run_stability(_frame()).set_index("model")
    assert st.loc["A", "pct_all_three_identical"] == 100.0
    assert st.loc["C", "pct_all_three_identical"] == 0.0
    assert st.loc["A", "mean_run_sd"] == 0.0


def test_agreement_alpha_matches_definition():
    med = ja.per_paper_median(_frame())
    pairs, alpha = ja.agreement(med, ["A", "B", "C"], ["simple"])
    wide = med.pivot(index="paper_id", columns="model", values="score")
    k = 3
    want = k / (k - 1) * (1 - wide.var(ddof=1).sum() / wide.sum(axis=1).var(ddof=1))
    assert alpha.cronbach_alpha.iloc[0] == pytest.approx(want)
    assert len(pairs) == 3 and (pairs.n_papers == 6).all()


def test_raw_levels_and_scored_papers_use_the_given_years():
    med = ja.per_paper_median(_frame())
    raw = ja.raw_levels(med, 2000, 2001)
    assert {"raw_2000", "raw_2001", "raw_delta"} <= set(raw.columns)
    n = ja.scored_papers(med, 2000, 2001)
    assert list(n.columns) == ["prompt_name", "model", "n_2000", "n_2001"]
    assert (n.n_2000 == 3).all() and (n.n_2001 == 3).all()
