"""Tests for the acronym reuse, robustness and concentration analyses.

All three are counting over the `|`-joined acronym lists that acronyms.py
writes. What is tested is where counting can go wrong without a full run
noticing: the bin edges, empty cells and empty entries, the case rule of the
exclusion list, the year window, the order of ties, and the histogram route
by which a corpus with no per-paper file joins the reuse table.
"""
import math
from collections import Counter

import pandas as pd
import pytest

import analysis.acronym_reuse as reuse
from analysis.acronym_concentration import acronym_concentration
from analysis.acronym_concentration import load as load_conc
from analysis.acronym_robustness import COMMON, density, reuse_share, robustness


# ── reuse: counting and bins ─────────────────────────────────────────────

def test_extract_counts_skips_empty_cells_and_entries_and_strips():
    df = pd.DataFrame({"abstract_acronyms": ["GAN|VAE", None, "", " GAN |", "|"]})
    assert reuse.extract_acronym_counts(df) == Counter({"GAN": 2, "VAE": 1})


@pytest.mark.parametrize("count,label", [(1, "1"), (2, "2--9"), (9, "2--9"),
                                         (10, "10--99"), (99, "10--99"),
                                         (100, "100--999"), (999, "100--999"),
                                         (1000, "1000+"), (10**6, "1000+")])
def test_bin_edges(count, label):
    d = reuse.freq_distribution({count: 1})
    assert d[label] == 100.0 and sum(d.values()) == 100.0


def test_zero_count_is_rejected():
    with pytest.raises(ValueError):
        reuse.freq_distribution({0: 3})


def test_empty_corpus_is_all_zero():
    assert reuse.freq_distribution({}) == {lbl: 0.0 for lbl in reuse.LABELS}
    assert reuse.reuse_row("X", {})["n_unique"] == 0


def test_shares_are_of_types_not_tokens():
    """One acronym used 1000 times and three used once: 75 percent single use."""
    d = reuse.freq_distribution(reuse.histogram({"A": 1000, "B": 1, "C": 1, "D": 1}))
    assert d["1"] == 75.0 and d["1000+"] == 25.0


def test_histogram_route_equals_counter_route(tmp_path):
    c = Counter({"GAN": 3, "VAE": 1, "MLP": 1, "SGD": 12})
    path = tmp_path / "h.csv"
    reuse.write_histogram(c, str(path))
    assert reuse.read_histogram(str(path)) == {1: 2, 3: 1, 12: 1}
    assert reuse.reuse_row("X", reuse.read_histogram(str(path))) == \
        reuse.reuse_row("X", reuse.histogram(c))


def test_read_histogram_sums_repeated_counts(tmp_path):
    path = tmp_path / "h.csv"
    pd.DataFrame({"count": [1, 1, 5], "n_types": [2, 3, 1]}).to_csv(path, index=False)
    assert reuse.read_histogram(str(path)) == {1: 5, 5: 1}


@pytest.mark.parametrize("frame", [{"count": [1], "types": [2]},
                                   {"count": [0], "n_types": [2]}])
def test_read_histogram_rejects_malformed_files(tmp_path, frame):
    path = tmp_path / "h.csv"
    pd.DataFrame(frame).to_csv(path, index=False)
    with pytest.raises(ValueError):
        reuse.read_histogram(str(path))


def test_table_ends_with_the_literature_row_and_writes_like_the_paper(tmp_path):
    out = reuse.build_table([reuse.reuse_row("NeurIPS", {1: 1, 2: 2})])
    assert out.venue.tolist() == ["NeurIPS", reuse.BD_LABEL]
    path = tmp_path / "t.csv"
    out.to_csv(path, index=False, float_format="%.1f")
    lines = path.read_text().splitlines()
    assert lines[0] == "venue,n_unique,1,2--9,10--99,100--999,1000+"
    assert lines[1] == "NeurIPS,3,33.3,66.7,0.0,0.0,0.0"
    assert lines[2] == "B\\&D (2020),1112345,30.0,49.0,,,"


def test_conference_rows_skip_a_missing_venue(tmp_path):
    pd.DataFrame({"abstract_acronyms": ["GAN|GAN"]}).to_csv(tmp_path / "iclr.csv",
                                                           index=False)
    rows = reuse.conference_rows(str(tmp_path))
    assert [r["venue"] for r in rows] == ["ICLR"]
    assert rows[0]["n_unique"] == 1 and rows[0]["2--9"] == 100.0


# ── robustness ───────────────────────────────────────────────────────────

def _row(year, abstract="", words=10, title="", twords=5):
    return {"year": str(year), "abstract_acronyms": abstract,
            "abstract_word_count": str(words), "title_acronyms": title,
            "title_word_count": str(twords)}


def test_list_has_thirty_terms_all_upper_case():
    assert len(COMMON) == 30 and all(t == t.upper() for t in COMMON)


def test_empty_paper_counts_as_zero_density_and_stays_in_the_mean():
    rows = [_row(2025, "GAN|XYZ", 10), _row(2025, "", 0)]
    assert density(rows, "abstract", set()) == pytest.approx(10.0)


def test_exclusion_matches_the_upper_cased_acronym():
    """'Adam' in an abstract is ADAM on the list."""
    rows = [_row(2025, "Adam|XYZ", 10)]
    assert density(rows, "abstract", COMMON) == pytest.approx(10.0)


def test_no_rows_and_no_acronyms_give_nan():
    assert math.isnan(density([], "abstract", set()))
    assert math.isnan(reuse_share([_row(2025)], set()))


def test_reuse_threshold_is_strict():
    rows = [_row(2025, "|".join(["A"] * 9 + ["B"] * 10))]
    assert reuse_share(rows, set()) == 50.0          # A (9) rare, B (10) not


def test_density_uses_one_year_reuse_uses_all_years():
    rows = [_row(2024, "OLD"), _row(2025, "GAN|NEW", 10, "NEW", 5)]
    r = robustness(rows)
    assert r["n_papers"] == 1
    assert r["n_unique_abstract_acronyms"] == 3
    assert r["abstract_density_all"] == 20.0 and r["abstract_density_excl"] == 10.0
    assert r["title_density_all"] == 20.0


# ── concentration ────────────────────────────────────────────────────────

def test_window_is_2015_to_2025(tmp_path):
    d = tmp_path / "acronyms"
    d.mkdir()
    pd.DataFrame({"paper_id": list("abcd"), "year": [2014, 2015, 2025, 2026],
                  "abstract_acronyms": ["X"] * 4}).to_csv(d / "neurips.csv", index=False)
    out = load_conc(str(tmp_path), ["neurips"])
    assert out.year.tolist() == [2015, 2025]


def test_concentration_shares_and_singletons():
    d = pd.DataFrame({"abstract_acronyms": ["GAN|GAN|GAN|VAE", "MLP", None]})
    conc, top = acronym_concentration(d, top_n=[1, 5], n_top_terms=2)
    r1 = conc.iloc[0]
    assert r1.n_types == 3 and r1.n_tokens == 5
    assert r1.token_share == pytest.approx(60.0)
    assert r1.singleton_type_share == pytest.approx(200 / 3)
    assert r1.singleton_token_share == pytest.approx(40.0)
    # top_n beyond the number of types: all tokens, type share over 100
    assert conc.iloc[1].token_share == pytest.approx(100.0)
    assert conc.iloc[1].type_share > 100
    assert top.acronym.tolist() == ["GAN", "VAE"]


def test_ties_keep_first_appearance_order():
    d = pd.DataFrame({"abstract_acronyms": ["ZZ|AA", "MM"]})
    _, top = acronym_concentration(d, top_n=[1], n_top_terms=3)
    assert top.acronym.tolist() == ["ZZ", "AA", "MM"]


def test_concentration_without_acronyms_raises():
    with pytest.raises(ValueError):
        acronym_concentration(pd.DataFrame({"abstract_acronyms": [None, None]}))
