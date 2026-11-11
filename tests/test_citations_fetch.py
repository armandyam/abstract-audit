"""Tests for the citation fetchers: Semantic Scholar, OpenAlex and the fallback.

The responses in tests/fixtures/citations/ are written by hand in the shape of
the Semantic Scholar /paper/search and OpenAlex /works responses, with the
fields the fetchers request; ids and counts are invented. Every test runs
offline: urlopen is replaced by a function that fails the test if called,
except where a test installs its own stand-in to exercise the retry logic.
"""
import csv
import datetime as dt
import io
import json
import os
import urllib.error

import pytest

import citations.fallback as fb
import citations.fetch_openalex as oa
import citations.fetch_s2 as s2
from citations._common import (
    normalise_title, provenance_path, update_provenance, write_provenance,
)

URL = "https://example.invalid/x"   # never fetched; urlopen is replaced
FIX = os.path.join(os.path.dirname(__file__), "fixtures", "citations")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("a test tried to reach the network")
    monkeypatch.setattr("urllib.request.urlopen", no_network)
    monkeypatch.setattr("time.sleep", lambda s: None)


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ── title normalisation ──────────────────────────────────────────────────

@pytest.mark.parametrize("raw, norm", [
    ("Attention Is All You Need", "attention is all you need"),
    ("ATTENTION -- is all you need!", "attention is all you need"),
    ("  Résumé:\tdeep   nets ", "r sum deep nets"),     # non-ASCII is not kept
    ("", ""),
    (None, ""),
])
def test_normalise_title(raw, norm):
    assert normalise_title(raw) == norm


# ── Semantic Scholar ─────────────────────────────────────────────────────

def test_s2_exact_match_takes_first_equal_normalised_title():
    r = s2.match_exact(fixture("s2_paper_search.json"), "Attention Is All You Need")
    assert r["paperId"].endswith("2")          # not the survey, not the third
    assert r["citationCount"] == 98765


def test_s2_exact_match_none_on_near_miss_and_empty():
    data = fixture("s2_paper_search.json")
    assert s2.match_exact(data, "Attention Is All You Need Too") is None
    assert s2.match_exact({}, "Attention Is All You Need") is None
    assert s2.match_exact({"data": None}, "a b c") is None


def test_s2_lookup_short_title_is_not_queried():
    def get(url, key):
        raise AssertionError("queried")
    assert s2.lookup("Two words", None, get=get) is None


def test_s2_lookup_distinguishes_error_from_non_match():
    assert s2.lookup("Attention Is All You Need", None, get=lambda u, k: None) is s2._ERROR
    assert s2.lookup("Attention Is All You Need", None, get=lambda u, k: {}) is None


def test_s2_search_url_quotes_title_and_requests_fields():
    url = s2.search_url("A/B testing & more")
    assert "query=A/B%20testing%20%26%20more" in url
    assert "fields=paperId,title,citationCount,referenceCount,year" in url
    assert url.endswith("limit=5")


def test_s2_make_row_three_outcomes():
    p = {"paper_id": "x", "venue": "iclr", "year": 2020}
    m = s2.make_row(p, {"citationCount": 5, "referenceCount": 9, "paperId": "abc"})
    assert m["match_type"] == "title" and m["n_citations"] == 5 and m["s2_paper_id"] == "abc"
    assert s2.make_row(p, None)["match_type"] == "unmatched"
    e = s2.make_row(p, s2._ERROR)
    assert e["match_type"] == "error" and e["n_citations"] == ""
    assert s2.make_row({"paper_id": "y", "year": 1999}, None)["venue"] == "neurips"


def test_s2_fetch_resumes_and_retries_error_rows(tmp_path):
    out = tmp_path / "iclr_s2.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=s2.FIELDNAMES)
        w.writeheader()
        w.writerow({"paper_id": "done", "venue": "iclr", "year": 2020, "n_citations": 1,
                    "n_references": 1, "s2_paper_id": "s", "match_type": "title"})
        w.writerow({"paper_id": "err", "venue": "iclr", "year": 2020, "n_citations": "",
                    "n_references": "", "s2_paper_id": "", "match_type": "error"})
    papers = [
        {"paper_id": "done", "venue": "iclr", "year": 2020, "title": "Should not be queried"},
        {"paper_id": "err", "venue": "iclr", "year": 2020, "title": "Attention Is All You Need"},
        {"paper_id": "new", "venue": "iclr", "year": 2021, "title": "No such paper here"},
    ]
    queried = []

    def get(url, key):
        queried.append(url)
        return fixture("s2_paper_search.json")

    t = s2.fetch(papers, str(out), None, get=get, sleep=0)
    assert len(queried) == 2 and t == {"matched": 1, "unmatched": 1}
    rows = read_rows(out)
    # the retry replaced the error row in place: one row per paper
    assert [r["paper_id"] for r in rows] == ["done", "err", "new"]
    assert rows[1]["match_type"] == "title" and rows[1]["n_citations"] == "98765"
    assert rows[2]["match_type"] == "unmatched"
    assert s2.already_fetched_ids(str(out)) == {"done", "err", "new"}


def test_s2_retry_after_error_gives_full_coverage(tmp_path):
    """One failed request then a success: coverage is 100 percent, not 50."""
    import citations.coverage as cov
    out = tmp_path / "neurips_s2.csv"
    papers = [{"paper_id": "p", "venue": "neurips", "year": 2020,
               "title": "Attention Is All You Need"}]
    s2.fetch(papers, str(out), None, get=lambda u, k: None, sleep=0)
    assert [r["match_type"] for r in read_rows(out)] == ["error"]
    s2.fetch(papers, str(out), None, get=lambda u, k: fixture("s2_paper_search.json"),
             sleep=0)
    assert [r["match_type"] for r in read_rows(out)] == ["title"]
    row = cov.coverage(["neurips"], cit_dir=str(tmp_path)).iloc[0]
    assert row["n_papers"] == 1 and row["coverage_pct"] == 100.0 and row["n_error"] == 0


def test_s2_compacts_a_file_left_with_repeated_rows(tmp_path):
    out = tmp_path / "x_s2.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=s2.FIELDNAMES)
        w.writeheader()
        for mt, c in [("error", ""), ("title", 5), ("error", "")]:
            w.writerow({"paper_id": "a", "year": 2020, "n_citations": c, "match_type": mt})
        w.writerow({"paper_id": "b", "year": 2020, "match_type": "error"})
        w.writerow({"paper_id": "b", "year": 2020, "match_type": "error"})
    assert s2.compact(str(out)) == 3
    rows = read_rows(out)
    assert [(r["paper_id"], r["match_type"], r["n_citations"]) for r in rows] == [
        ("a", "title", "5"), ("b", "error", "")]
    assert s2.compact(str(out)) == 0


def test_analyses_refuse_repeated_paper_ids(tmp_path):
    import pandas as pd
    import citations.coverage as cov
    import citations.enrich as en
    import citations.references as ref
    from citations._common import read_citations
    p = tmp_path / "neurips_s2.csv"
    p.write_text("paper_id,venue,year,n_citations,n_references,s2_paper_id,match_type\n"
                 "a,neurips,2020,,,,error\na,neurips,2020,3,4,s,title\n")
    with pytest.raises(SystemExit, match="repeated paper_id"):
        read_citations(str(p))
    with pytest.raises(SystemExit, match="repeated paper_id"):
        cov.coverage(["neurips"], cit_dir=str(tmp_path))
    with pytest.raises(SystemExit, match="repeated paper_id"):
        en.enrich(pd.read_csv(p))
    with pytest.raises(SystemExit, match="repeated paper_id"):
        ref.load(str(p))
    with pytest.raises(SystemExit, match="repeated paper_id"):
        fb.load_csv(str(p))


def test_s2_fetch_years_subset(tmp_path):
    out = tmp_path / "x.csv"
    papers = [{"paper_id": str(y), "year": y, "title": "Attention Is All You Need"}
              for y in (2019, 2020)]
    s2.fetch(papers, str(out), None, years=[2020], get=lambda u, k: {}, sleep=0)
    assert [r["paper_id"] for r in read_rows(out)] == ["2020"]


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, headers=None):
    return urllib.error.HTTPError("u", code, "x", headers or {}, None)


def test_s2_get_404_is_empty_and_exhaustion_is_none(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout: (_ for _ in ()).throw(_http_error(404)))
    assert s2._get(URL, None) == {}
    calls = []

    def boom(req, timeout):
        calls.append(1)
        raise _http_error(500)
    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert s2._get(URL, None) is None and len(calls) == s2.MAX_RETRIES


def test_s2_get_429_does_not_consume_retries_and_sends_headers(monkeypatch):
    seen = []
    seq = [_http_error(429, {"Retry-After": "0"})] * 7

    def urlopen(req, timeout):
        seen.append(dict(req.header_items()))
        if seq:
            raise seq.pop()
        return _Resp(b'{"data": []}')
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    assert s2._get(URL, "KEY") == {"data": []}
    assert len(seen) == 8
    h = {k.lower(): v for k, v in seen[0].items()}
    assert h["x-api-key"] == "KEY" and "abstract-audit" in h["user-agent"]


def test_s2_get_429_budget_exhausted_is_none(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout: (_ for _ in ()).throw(_http_error(429)))
    assert s2._get(URL, None) is None


# ── OpenAlex ─────────────────────────────────────────────────────────────

def test_openalex_query_removes_commas_and_mailto_is_optional():
    q = oa.query_params("Deep, residual, learning")
    assert q["filter"] == "title.search:Deep  residual  learning"
    assert "mailto" not in oa.works_url(q)
    assert "mailto=x%40y.z" in oa.works_url(q, "x@y.z")


def test_openalex_exact_match():
    r = oa.match_exact(fixture("openalex_works_filter.json"),
                       "Deep Residual Learning for Image Recognition")
    assert r["id"].endswith("W1000000002") and r["cited_by_count"] == 200000
    assert oa.match_exact({}, "Deep Residual Learning") is None


def test_openalex_fetch_writes_merged_and_yearly_and_resumes(tmp_path):
    merged, yearly = tmp_path / "icml_openalex.csv", tmp_path / "openalex"
    papers = [{"paper_id": "a", "venue": "icml", "year": 2016,
               "title": "Deep Residual Learning for Image Recognition"},
              {"paper_id": "b", "venue": "icml", "year": 2017, "title": "Short"}]
    get = lambda url: fixture("openalex_works_filter.json")  # noqa: E731
    t = oa.fetch(papers, "icml", str(merged), str(yearly), get=get, sleep=0)
    assert t == {"matched": 1, "unmatched": 1, "error": 0}
    rows = read_rows(merged)
    assert rows[0]["openalex_id"].endswith("W1000000002") and rows[0]["n_references"] == "22"
    assert rows[1]["match_type"] == "unmatched"
    assert [r["paper_id"] for r in read_rows(yearly / "icml_2016.csv")] == ["a"]
    os.remove(merged)          # the yearly files alone are enough to resume
    t2 = oa.fetch(papers, "icml", str(merged), str(yearly),
                  get=lambda u: pytest.fail("refetched"), sleep=0)
    assert t2 == {"matched": 0, "unmatched": 0, "error": 0}


@pytest.mark.parametrize("code", [400, 404])
def test_openalex_get_bad_request_is_a_definitive_empty_result(monkeypatch, code):
    calls = []

    def urlopen(req, timeout):
        calls.append(1)
        raise _http_error(code)
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    assert oa._get(URL) == {} and len(calls) == 1


@pytest.mark.parametrize("exc", [_http_error(500), _http_error(503), _http_error(429),
                                 urllib.error.URLError("down"), TimeoutError()])
def test_openalex_get_transient_failures_retry_then_report_error(monkeypatch, exc):
    calls = []

    def urlopen(req, timeout):
        calls.append(1)
        raise exc
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    assert oa._get(URL) is None and len(calls) == oa.MAX_RETRIES


def test_openalex_get_recovers_after_a_server_error(monkeypatch):
    seq = [_http_error(500), _http_error(502)]

    def urlopen(req, timeout):
        if seq:
            raise seq.pop(0)
        return _Resp(b'{"results": []}')
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    assert oa._get(URL) == {"results": []}


def test_openalex_lookup_error_is_not_a_non_match():
    title = "Deep Residual Learning for Image Recognition"
    assert oa.lookup(title, get=lambda u: None) is oa._ERROR
    assert oa.lookup(title, get=lambda u: {}) is None
    assert oa.make_row({"paper_id": "a", "year": 2016}, oa._ERROR)["match_type"] == "error"


def test_openalex_error_rows_are_retried_and_replaced(tmp_path):
    merged, yearly = tmp_path / "icml_openalex.csv", tmp_path / "openalex"
    papers = [{"paper_id": "a", "venue": "icml", "year": 2016,
               "title": "Deep Residual Learning for Image Recognition"}]
    t = oa.fetch(papers, "icml", str(merged), str(yearly), get=lambda u: None, sleep=0)
    assert t == {"matched": 0, "unmatched": 0, "error": 1}
    assert [r["match_type"] for r in read_rows(merged)] == ["error"]
    assert oa.already_fetched_ids(str(merged), str(yearly), "icml") == set()
    t = oa.fetch(papers, "icml", str(merged), str(yearly),
                 get=lambda u: fixture("openalex_works_filter.json"), sleep=0)
    assert t == {"matched": 1, "unmatched": 0, "error": 0}
    for path in (merged, yearly / "icml_2016.csv"):
        assert [(r["paper_id"], r["match_type"]) for r in read_rows(path)] == [("a", "title")]


# ── fallback: fuzzy title and OpenAlex ───────────────────────────────────

def test_ratio_on_normalised_titles():
    assert fb.ratio("A B C", "a-b-c") == 1.0
    assert fb.ratio("", "") == 1.0
    assert 0.88 < fb.ratio("partially labelled data", "partially labeled data") < 1.0


def test_best_fuzzy_takes_highest_ratio_not_first():
    res = fixture("s2_paper_search_fuzzy.json")["data"]
    best = fb.best_fuzzy(res, "Learning to Rank with Partially Labeled Data")
    assert best["paperId"].endswith("2")


def test_fuzzy_threshold_boundary():
    res = [{"title": "abcdefghij"}]
    r = fb.ratio("abcdefghij", "abcdefghix")      # 0.9
    assert fb.best_fuzzy(res, "abcdefghix", threshold=r) is not None
    assert fb.best_fuzzy(res, "abcdefghix", threshold=r + 1e-9) is None
    assert fb.best_fuzzy([], "anything") is None
    assert fb.first_fuzzy(res, "abcdefghix", threshold=r + 1e-9) is None


def test_first_fuzzy_keeps_openalex_order():
    res = fixture("openalex_works_search.json")["results"]
    r = fb.first_fuzzy(res, "Learning to rank with partially labeled data")
    assert r["id"].endswith("W2000000002")


def _router(s2_name, oa_name):
    def get(url, headers=None):
        if "semanticscholar" in url:
            return fixture(s2_name) if s2_name else {}
        assert "mailto" not in url
        return fixture(oa_name) if oa_name else {}
    return get


ROW = {"paper_id": "p1", "venue": "neurips", "year": "2008", "n_citations": "",
       "n_references": "", "s2_paper_id": "", "match_type": "unmatched",
       "citation_percentile": "", "mncs": ""}
TITLE = "Learning to Rank with Partially Labeled Data"


def test_recover_prefers_s2_fuzzy():
    new = fb.recover(ROW, TITLE, None, get=_router("s2_paper_search_fuzzy.json",
                                                   "openalex_works_search.json"), sleep=False)
    assert new["match_type"] == "s2_fuzzy" and new["n_citations"] == 151
    assert new["paper_id"] == "p1" and new["year"] == "2008"


def test_recover_falls_back_to_openalex_id_in_s2_column():
    new = fb.recover(ROW, TITLE, None, get=_router(None, "openalex_works_search.json"),
                     sleep=False)
    assert new["match_type"] == "openalex"
    assert new["s2_paper_id"] == "https://openalex.org/W2000000002"
    assert new["n_citations"] == 140 and new["n_references"] == 28


def test_recover_none_when_both_fail():
    assert fb.recover(ROW, TITLE, None, get=_router(None, None), sleep=False) is None


def test_fallback_short_title_skips_s2_only():
    calls = []

    def get(url, headers=None):
        calls.append(url)
        return {}
    fb.recover(ROW, "Two words", None, get=get, sleep=False)
    assert len(calls) == 1 and "openalex" in calls[0]


def test_fallback_run_touches_only_unmatched_and_clears_enrichment():
    rows = [dict(ROW, paper_id="p1", citation_percentile="55.0"),
            dict(ROW, paper_id="p2"),
            dict(ROW, paper_id="p3", match_type="title", n_citations="4.0")]
    titles = {"p1": TITLE}                 # p2 has no title
    out, counts = fb.run(rows, titles, None,
                         get=_router("s2_paper_search_fuzzy.json", None), sleep=False)
    assert counts == {"unmatched_before": 2, "s2_fuzzy": 1, "openalex": 0, "no_title": 1}
    assert out[0]["match_type"] == "s2_fuzzy" and out[0]["citation_percentile"] == ""
    assert out[1] is rows[1] and out[2] is rows[2]


def test_fallback_save_keeps_input_columns(tmp_path):
    p = tmp_path / "neurips_s2.csv"
    fields = list(ROW)
    fb.save_csv(str(p), fields, [{k: v for k, v in ROW.items() if k != "mncs"}])
    f2, rows = fb.load_csv(str(p))
    assert f2 == fields and rows[0]["mncs"] == ""


# ── provenance sidecar ───────────────────────────────────────────────────

def test_provenance_records_rows_match_types_and_date(tmp_path):
    p = tmp_path / "icml_s2.csv"
    p.write_text("paper_id,match_type\na,title\nb,unmatched\nc,title\n")
    out = write_provenance(str(p), "Semantic Scholar", "https://x", "fetch_s2.py",
                           today=dt.date(2026, 6, 11))
    assert out == str(tmp_path / "icml_s2.provenance.json") == provenance_path(str(p))
    rec = json.load(open(out))
    assert rec["retrieved"] == "2026-06-11" and rec["n_rows"] == 3
    assert rec["match_type"] == {"title": 2, "unmatched": 1}


def test_provenance_of_missing_or_empty_csv(tmp_path):
    rec = json.load(open(write_provenance(str(tmp_path / "none.csv"), "s", "e", "f")))
    assert rec["n_rows"] == 0 and rec["match_type"] == {}


def test_update_provenance_keeps_original_retrieval(tmp_path):
    p = tmp_path / "neurips_s2.csv"
    p.write_text("paper_id,match_type\na,unmatched\n")
    write_provenance(str(p), "S2", "e", "f", today=dt.date(2026, 5, 1))
    p.write_text("paper_id,match_type\na,s2_fuzzy\n")
    update_provenance(str(p), "fallback", {"s2_fuzzy": 1}, today=dt.date(2026, 5, 11))
    rec = json.load(open(provenance_path(str(p))))
    assert rec["retrieved"] == "2026-05-01"
    assert rec["fallback"] == {"retrieved": "2026-05-11", "s2_fuzzy": 1}
    assert rec["match_type"] == {"s2_fuzzy": 1}


def test_update_provenance_without_sidecar(tmp_path):
    p = tmp_path / "iclr_s2.csv"
    p.write_text("paper_id,match_type\n")
    update_provenance(str(p), "fallback", {}, today=dt.date(2026, 1, 1))
    rec = json.load(open(provenance_path(str(p))))
    assert rec["file"] == "iclr_s2.csv" and rec["n_rows"] == 0


def test_openalex_resume_restores_a_row_written_only_to_the_yearly_file(tmp_path):
    """An interruption between the yearly and the merged write leaves the row
    in the yearly file only; the next run must not drop it from the merged file."""
    import csv
    merged = tmp_path / "neurips_openalex.csv"
    yearly = tmp_path / "openalex"
    yearly.mkdir()
    row = {"paper_id": "p1", "venue": "neurips", "year": "2020", "n_citations": "5",
           "n_references": "10", "openalex_id": "W1", "match_type": "exact"}
    with open(yearly / "neurips_2020.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=oa.FIELDNAMES)
        w.writeheader()
        w.writerow(row)
    with open(merged, "w", newline="") as fh:
        csv.DictWriter(fh, fieldnames=oa.FIELDNAMES).writeheader()
    calls = []
    oa.fetch([{"paper_id": "p1", "year": 2020, "title": "T"}], "neurips",
             str(merged), str(yearly), get=lambda *a, **k: calls.append(1), sleep=0)
    assert calls == []                                  # not fetched again
    with open(merged, newline="") as fh:
        assert [r["paper_id"] for r in csv.DictReader(fh)] == ["p1"]
