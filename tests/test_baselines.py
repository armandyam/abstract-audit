"""Tests for the arXiv and PubMed baselines: opt-in aggregation, the shipped
baselines/ files, and the six-column TMLR export.

The full run is checked against the upstream files (see reference/MANIFEST.md).
What is tested here is the contract around it: the baselines stay out of the
default aggregation, the columns and year index they add, the category map,
the column-at-a-time PubMed path, the count-weighted ML split when a group is
empty, the PubMed cap, and the acronym histogram's reduction to the reuse
table's shares.
"""
import ast
import filecmp
import json
import os
from collections import Counter

import numpy as np
import pandas as pd
import pytest

import aggregate._utils as U
import baselines.make_baselines as mb
import plotting.export_pgfplots_data as export
from aggregate._utils import aggregate, baselines_from_env

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def write(root, metric, venue, rows):
    d = root / "per_paper" / metric
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(d / f"{venue}.csv", index=False)
    return str(root / "per_paper")


def corpus(tmp_path):
    write(tmp_path, "hedging", "neurips", [
        {"paper_id": "n1", "year": 2020, "hedging_per_100": 1.0},
        {"paper_id": "n2", "year": 2021, "hedging_per_100": 2.0}])
    write(tmp_path, "hedging", "pubmed", [
        {"paper_id": "p1", "year": 2020, "hedging_per_100": 3.0},
        {"paper_id": "p2", "year": 2020, "hedging_per_100": 5.0},
        {"paper_id": "p3", "year": 2027, "hedging_per_100": 7.0}])
    return write(tmp_path, "hedging", "arxiv", [
        {"paper_id": "a1", "year": 2019, "hedging_per_100": 1.0},
        {"paper_id": "a2", "year": 2020, "hedging_per_100": 3.0},
        {"paper_id": "a3", "year": 2020, "hedging_per_100": 9.0},
        {"paper_id": "a4", "year": 2020, "hedging_per_100": 4.0}])


def processed(tmp_path, mapping):
    d = tmp_path / "processed" / "arxiv"
    d.mkdir(parents=True)
    recs = [{"paper_id": k, "arxiv_primary_category": v} for k, v in mapping.items()]
    recs.append({"paper_id": "no-category"})
    (d / "arxiv_2020.json").write_text(json.dumps(recs))
    return str(tmp_path / "processed")


# ── opt-in ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("", []), ("  ", []), ("arxiv", ["arxiv"]), ("arxiv,pubmed", ["pubmed", "arxiv"]),
    ("PubMed  arxiv", ["pubmed", "arxiv"]),
])
def test_baselines_from_env(value, expected):
    assert baselines_from_env(value) == expected


def test_unknown_baseline_is_an_error():
    with pytest.raises(ValueError, match="unknown"):
        baselines_from_env("pubmed,arxive")


def test_default_ignores_baseline_files(tmp_path, monkeypatch):
    """The baselines' files sit beside the conferences' and must not leak in."""
    monkeypatch.delenv("AA_BASELINES", raising=False)
    pp = corpus(tmp_path)
    a = aggregate("hedging", ["hedging_per_100"], venues=["neurips"],
                  per_paper_dir=pp, out_dir=str(tmp_path / "a"))
    b = aggregate("hedging", ["hedging_per_100"], venues=["neurips"], baselines=[],
                  per_paper_dir=pp, out_dir=str(tmp_path / "b"))
    assert filecmp.cmp(a, b, shallow=False)
    assert os.listdir(tmp_path / "a") == ["hedging.csv"]
    assert list(pd.read_csv(a).columns)[1:] == [
        "neurips_hedging_per_100_mean", "neurips_hedging_per_100_std",
        "neurips_hedging_per_100_count"]


def test_env_enables_baselines(tmp_path, monkeypatch):
    pp = corpus(tmp_path)
    monkeypatch.setenv("AA_BASELINES", "pubmed")
    out = aggregate("hedging", ["hedging_per_100"], venues=["neurips"],
                    per_paper_dir=pp, out_dir=str(tmp_path / "a"))
    assert "pubmed_hedging_per_100_mean" in pd.read_csv(out).columns
    assert not (tmp_path / "a" / "hedging_arxiv_by_category.csv").exists()


def test_baseline_columns_order_and_year_union(tmp_path):
    pp = corpus(tmp_path)
    write(tmp_path, "hedging", "arxiv", [
        {"paper_id": "a1", "year": 2019, "hedging_per_100": 1.0,
         "arxiv_primary_category": "cs.LG"}])
    out = aggregate("hedging", ["hedging_per_100"], venues=["neurips"],
                    baselines=["arxiv", "pubmed"], per_paper_dir=pp,
                    out_dir=str(tmp_path / "a"))
    df = pd.read_csv(out)
    prefixes = [c.split("_")[0] for c in df.columns[1:]]
    assert prefixes == ["neurips"] * 3 + ["pubmed"] * 3 + ["arxiv"] * 3
    assert df["year"].tolist() == [2019, 2020, 2021, 2027]
    pm = df.set_index("year")
    assert pm.loc[2020, "pubmed_hedging_per_100_mean"] == 4.0
    assert pm.loc[2027, "pubmed_hedging_per_100_count"] == 1


def test_category_map_from_processed_and_uncategorised_rows_dropped(tmp_path):
    pp = corpus(tmp_path)
    proc = processed(tmp_path, {"a1": "cs.LG", "a2": "cs.LG", "a3": "hep-th"})
    aggregate("hedging", ["hedging_per_100"], venues=[], baselines=["arxiv"],
              per_paper_dir=pp, out_dir=str(tmp_path / "a"), processed_dir=proc)
    cat = pd.read_csv(tmp_path / "a" / "hedging_arxiv_by_category.csv")
    assert list(cat.columns) == ["year", "arxiv_primary_category", "hedging_per_100_mean",
                                 "hedging_per_100_std", "hedging_per_100_count"]
    assert cat[["year", "arxiv_primary_category"]].values.tolist() == [
        [2019, "cs.LG"], [2020, "cs.LG"], [2020, "hep-th"]]       # a4 has no category
    wide = pd.read_csv(tmp_path / "a" / "hedging.csv").set_index("year")
    assert wide.loc[2020, "arxiv_hedging_per_100_count"] == 3    # the year row keeps a4


def test_pubmed_columnwise_equals_whole_frame(tmp_path):
    rng = np.random.default_rng(0)
    n = 500
    rows = pd.DataFrame({"paper_id": [f"p{i}" for i in range(n)],
                         "year": rng.integers(1990, 1996, n),
                         "x": rng.normal(size=n), "y": rng.normal(size=n)})
    rows.loc[::7, "y"] = np.nan
    write(tmp_path, "m", "pubmed", rows.to_dict("records"))
    out = aggregate("m", ["x", "y", "absent"], venues=[], baselines=["pubmed"],
                    per_paper_dir=str(tmp_path / "per_paper"), out_dir=str(tmp_path / "a"))
    got = pd.read_csv(out)
    whole = pd.read_csv(tmp_path / "per_paper" / "m" / "pubmed.csv")
    want = whole.groupby("year")[["x", "y"]].agg(["mean", "std", "count"]).reset_index()
    want.columns = ["year"] + [f"pubmed_{c}_{s}" for c, s in want.columns[1:]]
    path = tmp_path / "want.csv"
    want.to_csv(path, index=False)
    assert filecmp.cmp(out, path, shallow=False)
    assert "pubmed_absent_mean" not in got.columns


def test_pubmed_without_any_metric_column_is_skipped(tmp_path):
    """A PubMed file holding none of the columns adds nothing."""
    pp = write(tmp_path, "m", "pubmed", [{"paper_id": "p", "year": 2027, "other": 1.0}])
    write(tmp_path, "m", "neurips", [{"paper_id": "n", "year": 2020, "x": 1.0}])
    out = aggregate("m", ["x"], venues=["neurips"], baselines=["pubmed"],
                    per_paper_dir=pp, out_dir=str(tmp_path / "a"))
    df = pd.read_csv(out)
    assert df["year"].tolist() == [2020] and not any(c.startswith("pubmed") for c in df)


def test_missing_baseline_file_is_skipped(tmp_path):
    pp = write(tmp_path, "ttr", "neurips", [{"paper_id": "a", "year": 2020, "ttr": 0.5}])
    out = aggregate("ttr", ["ttr"], venues=["neurips"], baselines=["pubmed", "arxiv"],
                    per_paper_dir=pp, out_dir=str(tmp_path / "a"))
    assert [c.split("_")[0] for c in pd.read_csv(out).columns[1:]] == ["neurips"] * 3


# ── export ───────────────────────────────────────────────────────────────────

def cat_frame():
    return pd.DataFrame({
        "year": [2020, 2020, 2020, 2021],
        "arxiv_primary_category": ["cs.LG", "cs.CV", "hep-th", "math.AG"],
        "m_mean": [1.0, 4.0, 2.0, 3.0],
        "m_count": [1, 3, 5, 0],
    })


def test_weighted_mean_is_count_weighted():
    s = export.arxiv_split(cat_frame(), "m").set_index("year")
    assert s.loc[2020, "arxiv_ml"] == (1.0 * 1 + 4.0 * 3) / 4
    assert s.loc[2020, "arxiv_nonml"] == 2.0
    assert np.isnan(s.loc[2021, "arxiv_nonml"])      # counts sum to zero
    assert np.isnan(s.loc[2021, "arxiv_ml"])         # no ML category that year


def test_weighted_mean_empty_group_and_missing_column():
    df = cat_frame()
    none = export.weighted_mean_by_year(df, "m", pd.Series(False, index=df.index))
    assert none.empty and list(none.columns) == ["year", "wmean"]
    absent = export.arxiv_split(df, "other")
    assert absent.empty and list(absent.columns) == ["year", "arxiv_ml", "arxiv_nonml"]


def baselines_dir(tmp_path):
    b = tmp_path / "baselines" / "aggregate"
    b.mkdir(parents=True)
    pd.DataFrame({"year": [2020, 2025, 2026, 2027],
                  "pubmed_m_mean": [5.0, 6.0, 7.0, 8.0]}).to_csv(b / "fam.csv", index=False)
    cat_frame().to_csv(b / "fam_arxiv_by_category.csv", index=False)
    pd.DataFrame({"year": [1991, 2020, 2021, 2027],
                  "arxiv_ml": [None, 4, None, None], "arxiv_nonml": [2, 5, 1, None],
                  "pubmed_scored": [None, 10, 11, 3], "pubmed_records": [None, 12, 11, 3]}
                 ).astype("Int64").to_csv(tmp_path / "baselines" / "papers_per_year.csv",
                                          index=False)
    return str(tmp_path / "baselines")


def test_full_metric_has_six_columns_and_caps_pubmed(tmp_path, monkeypatch):
    agg = tmp_path / "agg"
    agg.mkdir()
    pd.DataFrame({"year": [2019, 2020], "neurips_m_mean": [1.0, 2.0],
                  "iclr_m_mean": [np.nan, 3.0], "icml_m_mean": [4.0, np.nan]}
                 ).to_csv(agg / "fam.csv", index=False)
    monkeypatch.setattr(export, "AGG", str(agg))
    export.export_metric_full("fam", "m", "fam", baselines_dir(tmp_path), str(tmp_path / "o"))
    df = pd.read_csv(tmp_path / "o" / "fam.csv")
    assert list(df.columns) == ["year", "neurips", "iclr", "icml",
                                "arxiv_ml", "arxiv_nonml", "pubmed"]
    assert df["year"].tolist() == [2019, 2020, 2025, 2026, 2027]   # nothing dropped
    p = df.set_index("year")["pubmed"]
    assert p[2025] == 6.0 and p[2026:].isna().all()


def test_full_metric_without_pubmed_keeps_an_empty_column(tmp_path, monkeypatch):
    agg = tmp_path / "agg"
    agg.mkdir()
    pd.DataFrame({"year": [2020], "neurips_q_mean": [1.0]}).to_csv(agg / "fam.csv", index=False)
    monkeypatch.setattr(export, "AGG", str(agg))
    export.export_metric_full("fam", "q", "q", str(tmp_path / "nothing"), str(tmp_path / "o"))
    df = pd.read_csv(tmp_path / "o" / "q.csv")
    assert list(df.columns) == ["year", "neurips", "pubmed"] and df["pubmed"].isna().all()


def test_full_papers_per_year(tmp_path, monkeypatch):
    agg = tmp_path / "agg"
    agg.mkdir()
    pd.DataFrame({"year": [2020, 2021, 2026], "neurips": [10, 12, 0],
                  "iclr": [0, 3, 5], "icml": [4, 0, 0]}).to_csv(agg / "papers_per_year.csv",
                                                                 index=False)
    monkeypatch.setattr(export, "AGG", str(agg))
    export.export_papers_per_year_full(baselines_dir(tmp_path), str(tmp_path / "o"))
    df = pd.read_csv(tmp_path / "o" / "papers_per_year.csv").set_index("year")
    assert df.index.tolist() == [1991, 2020, 2021, 2026]   # arXiv years added, 2027 not
    assert np.isnan(df.loc[1991, "neurips"]) and np.isnan(df.loc[2026, "neurips"])
    assert df.loc[1991, "arxiv_nonml"] == 2 and np.isnan(df.loc[1991, "arxiv_ml"])
    assert df.loc[2021, "pubmed"] == 11 and np.isnan(df.loc[2026, "pubmed"])


def test_tmlr_without_baselines_is_unchanged(tmp_path, monkeypatch):
    """The conference-only TMLR set must not gain baseline columns."""
    agg = tmp_path / "agg"
    agg.mkdir()
    pd.DataFrame({"year": [2020], "neurips_hedging_per_100_mean": [1.0]}
                 ).to_csv(agg / "hedging.csv", index=False)
    monkeypatch.setattr(export, "AGG", str(agg))
    monkeypatch.setattr(export, "OUT", str(tmp_path / "pg"))
    export.export_tmlr()
    assert list(pd.read_csv(tmp_path / "pg" / "tmlr" / "hedging.csv").columns) == \
        ["year", "neurips"]
    assert not (tmp_path / "pg" / "tmlr" / "sentence_length.csv").exists()


# ── make_baselines ───────────────────────────────────────────────────────────

def upstream_freq_distribution(counter: Counter) -> dict:
    """The upstream table's bucketing, applied to the full counter."""
    labels = ["1", "2--9", "10--99", "100--999", "1000+"]
    total = len(counter)
    if total == 0:
        return {lbl: 0.0 for lbl in labels}
    b = {lbl: 0 for lbl in labels}
    for c in counter.values():
        b["1" if c == 1 else "2--9" if c < 10 else "10--99" if c < 100
          else "100--999" if c < 1000 else "1000+"] += 1
    return {lbl: 100.0 * n / total for lbl, n in b.items()}


def test_histogram_reproduces_upstream_buckets():
    rng = np.random.default_rng(1)
    counter = Counter({f"A{i}": int(k) for i, k in enumerate(rng.zipf(1.6, 3000))})
    row = mb.reuse_row(mb.histogram(counter))
    assert row["n_unique"] == len(counter)
    want = upstream_freq_distribution(counter)
    assert {k: row[k] for k in want} == want                      # exact, not approx


@pytest.mark.parametrize("count,bucket", [(1, "1"), (2, "2--9"), (9, "2--9"),
                                          (10, "10--99"), (999, "100--999"),
                                          (1000, "1000+"), (10**6, "1000+")])
def test_bucket_edges(count, bucket):
    row = mb.reuse_row({count: 4})
    assert row[bucket] == 100.0 and sum(row[k] for k, *_ in mb.BUCKETS) == 100.0


def test_empty_histogram():
    assert mb.reuse_row({}) == {"n_unique": 0, "1": 0.0, "2--9": 0.0, "10--99": 0.0,
                                "100--999": 0.0, "1000+": 0.0}


def test_count_acronyms_skips_missing_and_blank():
    c = mb.count_acronyms(["DNA|PCR|DNA", np.nan, " RNA | ", "", None])
    assert c == Counter({"DNA": 2, "PCR": 1, "RNA": 1})


def test_acronym_histograms_split_and_pubmed_cap(tmp_path):
    write(tmp_path, "acronyms", "arxiv", [
        {"year": 2020, "abstract_acronyms": "GAN|GAN|CNN", "arxiv_primary_category": "cs.LG"},
        {"year": 2020, "abstract_acronyms": "CNN", "arxiv_primary_category": "cs.CV"},
        {"year": 2020, "abstract_acronyms": "QCD", "arxiv_primary_category": "hep-ph"},
        {"year": 2020, "abstract_acronyms": "QED", "arxiv_primary_category": None}])
    pp = write(tmp_path, "acronyms", "pubmed", [
        {"year": 2025, "abstract_acronyms": "DNA|DNA"},
        {"year": 2026, "abstract_acronyms": "DNA|RNA"}])
    h = mb.acronym_histograms(pp, max_year=2025)
    got = {g: dict(zip(d["occurrences"], d["acronym_types"])) for g, d in h.groupby("group")}
    assert got == {"arxiv_ml": {2: 2}, "arxiv_nonml": {1: 2}, "pubmed": {2: 1}}


def test_papers_per_year_two_pubmed_denominators(tmp_path):
    agg = tmp_path / "aggregate"
    agg.mkdir()
    cat_frame().rename(columns={"m_mean": "title_acronym_density_mean",
                                "m_count": "title_acronym_density_count"}
                       ).to_csv(agg / "acronyms_arxiv_by_category.csv", index=False)
    pd.DataFrame({"year": [2020, 2027], "pubmed_flesch_ease_count": [9, 1]}
                 ).to_csv(agg / "readability.csv", index=False)
    pd.DataFrame({"year": [2020, 2027], "pubmed_words_per_sentence_count": [10, 1]}
                 ).to_csv(agg / "sentence_length.csv", index=False)
    df = mb.papers_per_year(str(agg)).set_index("year")
    assert list(df.columns) == ["arxiv_ml", "arxiv_nonml", "pubmed_scored", "pubmed_records"]
    assert df.loc[2020].tolist() == [4, 5, 9, 10]
    assert df.loc[2021, "arxiv_nonml"] == 0 and pd.isna(df.loc[2021, "pubmed_scored"])


def test_families_match_the_aggregation_scripts():
    """FAMILIES must aggregate what src/aggregate/aggregate_<family>.py does."""
    checked = 0
    for family, cols in mb.FAMILIES.items():
        path = os.path.join(SRC, "aggregate", f"aggregate_{family}.py")
        if not os.path.exists(path):
            continue
        tree = ast.parse(open(path).read())
        consts = {t.id: ast.literal_eval(n.value) for n in ast.walk(tree)
                  if isinstance(n, ast.Assign) for t in n.targets
                  if isinstance(t, ast.Name) and t.id == "COLS"}
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and getattr(n.func, "id", "") == "aggregate")
        arg = call.args[1]
        script_cols = consts["COLS"] if isinstance(arg, ast.Name) else ast.literal_eval(arg)
        assert script_cols == cols, family
        checked += 1
    assert checked >= 15
