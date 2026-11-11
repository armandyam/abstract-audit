"""Tests for the ICML scrapers' parsing and the PMLR resume logic.

ICML comes from three sources: the icml.cc archive pages (2008-2012, one
layout per year), PMLR (2013-2016), and the icml.cc export (2017 onward).
The archive fixtures are reduced to the structure each year's parser keys on.
"""
import json

import pytest

from scraping.download_icml import normalise
from scraping.scrape_icml_legacy import (
    _authors,
    _strip_trailing_junk,
    build_records,
    parse_2008,
    parse_2009,
    parse_2010,
    parse_2011,
    parse_2012,
)
from scraping.scrape_icml_pmlr import (
    load_raw,
    merge,
    paper_id,
    parse_abstract,
    parse_index,
)

ABS = "We propose a method and show that it works well in practice."


# ── icml.cc archive layouts, 2008-2012 ───────────────────────────────────

def test_parse_2008():
    h = (f'<p>paper ID: 12</p><h3>First</h3><p><i>Ann Lee, Bob Ray</i></p><p>{ABS}</p>'
         f'<p>paper ID: 13</p><h3>Second</h3><p><i>Cy Dee</i></p><p>Other text.</p></div>')
    out = parse_2008(h)
    assert [(p, t) for p, t, _, _ in out] == [("12", "First"), ("13", "Second")]
    assert out[0][2] == ["Ann Lee", "Bob Ray"] and out[0][3] == ABS


def test_parse_2009_ignores_sidebar_before_proceedings():
    h = ('<h3><a name="10"></a>Sidebar</h3><p><i>nav</i></p><p>paper ID: 0</p>'
         'ICML 2009 Proceedings'
         f'<h3><a name="7"></a>Real paper</h3>\n<p><i>Ann Lee</i></p>\n<p>paper ID: 7</p>{ABS}<hr>')
    assert parse_2009(h) == [("7", "Real paper", ["Ann Lee"], ABS)]


def test_parse_2010_drops_parenthesised_affiliations():
    h = ('<a name="5"></a><p>Paper ID: 5</p><h3>T</h3>'
         f'<p><em>Ann Lee (MIT) and Bob Ray (CMU)</em></p><p class="abstracts">{ABS}</p>')
    assert parse_2010(h) == [("5", "T", ["Ann Lee", "Bob Ray"], ABS)]


def test_parse_2011():
    h = ("<a name='9'><h3 class='t'>Title</h3><span class='name'>Ann Lee, Bob Ray</span>"
         f"<p class='a'><span class='b'>Abstract:</span>{ABS}</p>")
    assert parse_2011(h) == [("9", "Title", ["Ann Lee", "Bob Ray"], ABS)]


def test_parse_2012_unclosed_abstract_paragraph():
    h = ('<div class="paper" id="paper-3"><h2>T</h2><p class="authors">Ann Lee</p>'
         f'<p class="abstract"><strong>Abstract:</strong>{ABS}</div>'
         '<div class="paper" id="paper-4"><h2>No abstract</h2></div>')
    out = parse_2012(h)
    assert out[0] == ("3", "T", ["Ann Lee"], ABS)
    assert out[1] == ("4", "No abstract", [], "")


@pytest.mark.parametrize("tail", ["[Full paper] [Discussion]", "[ Corrected paper ]",
                                  "discussion+video", "ICML version (pdf) x"])
def test_strip_trailing_navigation_junk(tail):
    assert _strip_trailing_junk(f"{ABS} {tail}") == ABS


def test_authors_drops_bare_affiliations():
    """2011 lists affiliations without parentheses."""
    assert _authors("Ann Lee, University of Somewhere; Bob Ray") == ["Ann Lee", "Bob Ray"]


def test_legacy_build_records_drops_short_or_untitled():
    parsed = [("1", "T", ["A"], ABS), ("2", "", ["A"], ABS), ("3", "T", ["A"], "short")]
    recs, dropped = build_records(2010, parsed)
    assert [r["paper_id"] for r in recs] == ["2010_icmlcc_1"] and dropped == 2
    assert list(recs[0]) == ["paper_id", "year", "title", "authors", "abstract"]


# ── icml.cc export, 2017 onward ──────────────────────────────────────────

def test_normalise_accepts_both_export_field_names():
    new = normalise({"type": "Poster", "title": "T", "url": "u", "authors": "A, B",
                     "abstract": "x"})
    old = normalise({"type": "Poster", "name": "T", "virtualsite_url": "u",
                     "speakers/authors": "A, B", "abstract": "x"})
    assert new == old == {"type": "Poster", "name": "T", "virtualsite_url": "u",
                          "speakers/authors": "A, B", "abstract": "x"}


# ── PMLR, 2013-2016 ──────────────────────────────────────────────────────

INDEX = """
<div class="paper"><p class="title">First &amp; best</p>
  <span class="authors">Ann Lee,&nbsp;Bob Ray</span>
  <a href="https://proceedings.mlr.press/v28/lee13.html">abs</a></div>
<div class="paper"><p class="title">Second</p>
  <span class="authors">Cy Dee</span>
  <a href="/v28/dee13.html">abs</a></div>
<div class="paper"><p class="title">No abs link</p></div>
"""


def test_parse_index():
    out = parse_index(INDEX)
    assert [p["title"] for p in out] == ["First & best", "Second"]
    assert out[0]["authors"] == ["Ann Lee", "Bob Ray"]
    assert out[1]["abs_url"] == "https://proceedings.mlr.press/v28/dee13.html"


def test_parse_abstract():
    assert parse_abstract(f'<div id="x" class="abstract"> <p>{ABS}</p> </div>') == ABS
    assert parse_abstract("<div>no abstract here</div>") == ""


def test_paper_id_from_abs_url():
    assert paper_id(2013, "https://proceedings.mlr.press/v28/lee13.html") == "2013_pmlr_lee13"


def _fetcher(calls):
    def fetch(url):
        calls.append(url)
        return f"abstract of {url.rsplit('/', 1)[-1]}"
    return fetch


def test_merge_fresh_run_fetches_everything_in_index_order():
    calls = []
    recs, n = merge(2013, parse_index(INDEX), {}, _fetcher(calls))
    assert n == 2 and len(calls) == 2
    assert [r["paper_id"] for r in recs] == ["2013_pmlr_lee13", "2013_pmlr_dee13"]
    assert list(recs[0]) == ["paper_id", "year", "title", "authors", "abs_url", "abstract"]


def _site(monkeypatch, pmlr, fail_on=None):
    """Serve INDEX and abstract pages; raise on the URL in `fail_on`."""
    calls = []

    def get(url, retries=4):
        if url.endswith("/v28/"):
            return INDEX
        calls.append(url)
        if url == fail_on:
            raise KeyboardInterrupt
        return f'<div class="abstract">abstract of {url.rsplit("/", 1)[-1]}</div>'
    monkeypatch.setattr(pmlr, "_get", get)
    return calls


def test_interrupted_scrape_keeps_progress_and_restart_fetches_only_missing(tmp_path, monkeypatch):
    import scraping.scrape_icml_pmlr as pmlr
    monkeypatch.setattr(pmlr, "CHECKPOINT", 1)
    second = "https://proceedings.mlr.press/v28/dee13.html"
    _site(monkeypatch, pmlr, fail_on=second)
    with pytest.raises(KeyboardInterrupt):
        pmlr.scrape_year(2013, str(tmp_path), delay=0, limit=None)
    saved = json.loads((tmp_path / "icml_2013_pmlr.json").read_text())
    assert [r["paper_id"] for r in saved] == ["2013_pmlr_lee13"]

    calls = _site(monkeypatch, pmlr)
    pmlr.scrape_year(2013, str(tmp_path), delay=0, limit=None)
    assert calls == [second]
    final = json.loads((tmp_path / "icml_2013_pmlr.json").read_text())
    assert [r["paper_id"] for r in final] == ["2013_pmlr_lee13", "2013_pmlr_dee13"]
    assert final[0] == saved[0]


def test_failed_index_fetch_leaves_the_raw_file_untouched(tmp_path, monkeypatch):
    import scraping.scrape_icml_pmlr as pmlr
    path = tmp_path / "icml_2013_pmlr.json"
    path.write_text('[{"paper_id": "2013_pmlr_x", "abstract": "kept"}]')
    monkeypatch.setattr(pmlr, "_get", lambda url, retries=4: "")
    with pytest.raises(SystemExit):
        pmlr.scrape_year(2013, str(tmp_path), delay=0, limit=None)
    assert path.read_text() == '[{"paper_id": "2013_pmlr_x", "abstract": "kept"}]'


def test_completed_rerun_leaves_records_unchanged(tmp_path):
    full, _ = merge(2013, parse_index(INDEX), {}, _fetcher([]))
    path = tmp_path / "icml_2013_pmlr.json"
    path.write_text(json.dumps(full))
    calls = []
    again, n = merge(2013, parse_index(INDEX), load_raw(str(path)), _fetcher(calls))
    assert n == 0 and calls == [] and again == full


def test_load_raw_refetches_records_with_empty_abstract(tmp_path):
    """A failed fetch leaves an empty abstract; the next run must retry it."""
    path = tmp_path / "raw.json"
    path.write_text(json.dumps([{"paper_id": "a", "abstract": ""},
                                {"paper_id": "b", "abstract": "text"}]))
    assert list(load_raw(str(path))) == ["b"]
    assert load_raw(str(tmp_path / "missing.json")) == {}


def test_legacy_page_without_papers_keeps_raw_file(tmp_path, monkeypatch):
    import scraping.scrape_icml_legacy as legacy
    p = tmp_path / "icml_2010_legacy.json"
    p.write_text('[{"paper_id": "kept"}]')
    monkeypatch.setattr(legacy, "_get", lambda url: "<html>page moved</html>")
    with pytest.raises(SystemExit):
        legacy.scrape_year(2010, str(tmp_path))
    assert p.read_text() == '[{"paper_id": "kept"}]'


@pytest.mark.parametrize("payload", [[], {}])
def test_empty_icml_export_keeps_raw_file(tmp_path, monkeypatch, payload):
    import scraping.download_icml as dl
    p = tmp_path / "icml_2024_data.json"
    p.write_text('[{"name": "kept"}]')

    class Resp:
        status_code = 200
        def json(self):
            return payload

    class Session:
        headers = {}
        def post(self, *a, **k):
            return Resp()
    monkeypatch.setattr(dl, "get_csrf_and_action", lambda s, y: ("t", "https://icml.cc/x"))
    monkeypatch.setattr(dl.requests, "Session", Session)
    assert dl.download_year(2024, str(tmp_path), 0) == 0
    assert p.read_text() == '[{"name": "kept"}]'
