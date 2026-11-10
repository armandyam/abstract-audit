"""Tests for the ICLR scrapers' parsing.

Three sources feed ICLR: the OpenReview export (2017 onward, two API shapes),
the 2013 OpenReview submission notes, and the archived iclr.cc accepted lists
resolved through the arXiv API (2014-2016). Each is third-party markup, so
these pin the fields each parser keys on. Network calls are not exercised.
"""
from scraping.scrape_iclr import note_to_record
from scraping.scrape_iclr_arxiv import (
    EXCLUDE,
    arxiv_ids,
    build_records,
    parse_arxiv_feed,
)
from scraping.scrape_iclr_openreview_early import notes_to_records


# ── OpenReview export, 2017 onward ───────────────────────────────────────

def test_note_to_record_api_v1_plain_fields():
    note = {"id": "abc", "content": {
        "title": "A title", "abstract": "An abstract.",
        "authors": ["Ann Lee", "Bob Ray"], "authorids": ["~Ann1", "~Bob1"],
        "decision": "Accept (Poster)", "rating": ["6", "-1", "x"],
        "keywords": ["vision"], "venue": "ICLR 2019"}}
    r = note_to_record(note, 2019)
    assert r["id"] == "abc" and r["year"] == 2019
    assert r["title"] == "A title" and r["abstract"] == "An abstract."
    assert r["authors"] == "Ann Lee, Bob Ray"
    assert r["author_ids"] == "~Ann1, ~Bob1"
    assert r["decision"] == "Accept (Poster)"
    assert r["scores"] == [6, -1]          # non-numeric ratings dropped
    assert r["keywords"] == ["vision"]
    assert r["labels"] == "ICLR 2019"


def test_note_to_record_api_v2_wrapped_values():
    """API v2 wraps every content field in {"value": ...}."""
    note = {"id": "v2id", "content": {
        "title": {"value": "Wrapped"}, "abstract": {"value": "Text."},
        "authors": {"value": ["Ann Lee"]}, "authorids": {"value": ["~Ann1"]},
        "decision": {"value": ""}, "venue": {"value": "ICLR 2026 Poster"}}}
    r = note_to_record(note, 2026)
    assert r["title"] == "Wrapped" and r["authors"] == "Ann Lee"
    assert r["decision"] == "" and r["labels"] == "ICLR 2026 Poster"
    assert r["scores"] == [] and r["keywords"] == []


def test_note_to_record_scalar_rating():
    r = note_to_record({"id": "x", "content": {"title": "t", "rating": 7}}, 2018)
    assert r["scores"] == [7]


# ── 2013 OpenReview submissions ──────────────────────────────────────────

ABSTRACT = "We study a problem and report a careful answer to it."


def _note(nid, decision, abstract=ABSTRACT, title="Title"):
    return {"id": nid, "content": {"title": title, "abstract": abstract,
                                   "authors": "Ann Lee, Bob Ray", "decision": decision}}


def test_early_keeps_conference_track_accepts_only():
    notes = [_note("a", "conferenceOral-iclr2013-conference"),
             _note("b", "conferencePoster-iclr2013-workshop"),
             _note("c", "reject"),
             _note("d", "")]
    recs, dropped = notes_to_records(notes, 2013)
    assert [r["paper_id"] for r in recs] == ["2013_openreview_a"]
    assert dropped == 3


def test_early_drops_missing_title_or_short_abstract():
    acc = "conferencePoster-iclr2013-conference"
    recs, dropped = notes_to_records([_note("a", acc, title=""),
                                      _note("b", acc, abstract="too short"),
                                      _note("c", acc)], 2013)
    assert [r["paper_id"] for r in recs] == ["2013_openreview_c"]
    assert dropped == 2


def test_early_record_shape():
    (r,), _ = notes_to_records([_note("a", "conferenceOral-iclr2013-conference")], 2013)
    assert list(r) == ["paper_id", "venue", "year", "title", "abstract", "authors", "decision"]
    assert r["venue"] == "iclr" and r["authors"] == ["Ann Lee", "Bob Ray"]


# ── 2014-2016 archived accepted lists via arXiv ──────────────────────────

def test_arxiv_ids_dedupes_keeps_order_and_strips_versions():
    page = ('<a href="https://arxiv.org/abs/1412.6980v9">Adam</a>'
            '<a href="http://arxiv.org/pdf/1409.1556">VGG</a>'
            '<a href="https://arxiv.org/abs/1412.6980">Adam again (orals list)</a>'
            '<a href="https://example.org/1412.0000">not arXiv</a>')
    assert arxiv_ids(page) == ["1412.6980", "1409.1556"]


def test_2015_excludes_the_paper_accepted_in_2016():
    assert "1411.7676" in EXCLUDE[2015]


FEED = """<feed>
<entry><id>http://arxiv.org/abs/1412.6980v9</id>
<title>A Method for
  Stochastic Optimization</title>
<summary>  We introduce a method &amp; more.  </summary>
<author><name>Author One</name></author><author><name>Author Two</name></author>
</entry>
<entry><id>http://arxiv.org/abs/1409.1556v6</id>
<title>No abstract</title><summary>   </summary></entry>
</feed>"""


def test_parse_arxiv_feed_cleans_text_and_skips_empty_summaries():
    out = parse_arxiv_feed(FEED)
    assert list(out) == ["1412.6980"]
    assert out["1412.6980"] == {"title": "A Method for Stochastic Optimization",
                                "abstract": "We introduce a method & more.",
                                "authors": ["Author One", "Author Two"]}


def test_build_records_page_order_skips_unresolved():
    meta = {"1": {"title": "T1", "abstract": "A1", "authors": ["x"]},
            "3": {"title": "T3", "abstract": "A3", "authors": ["y"]}}
    recs = build_records(2015, ["3", "2", "1"], meta)
    assert [r["arxiv_id"] for r in recs] == ["3", "1"]
    assert recs[0]["paper_id"] == "2015_arxiv_3"
    assert list(recs[0]) == ["paper_id", "venue", "year", "title", "abstract",
                             "authors", "arxiv_id"]


# ── ICLR dataset, 2017-2025 ──────────────────────────────────────────────

def test_dataset_row_to_raw_record_shape():
    import numpy as np
    from scraping.fetch_iclr_dataset import to_record
    row = {"year": np.int64(2017), "id": "B1", "title": "T", "abstract": "A",
           "authors": "Ann Lee, Bob Ray", "author_ids": "", "decision": "Reject",
           "scores": np.array([6, 4]), "keywords": np.array(["rl"], dtype=object),
           "labels": "rl"}
    r = to_record(row)
    assert list(r) == ["year", "id", "title", "abstract", "authors", "decision",
                       "scores", "keywords", "labels", "author_ids"]
    assert r["year"] == 2017 and type(r["year"]) is int
    assert r["scores"] == [6, 4] and r["keywords"] == ["rl"]


def test_dataset_download_rejects_a_file_with_the_wrong_hash(tmp_path):
    import pytest
    from scraping.fetch_iclr_dataset import download
    bad = tmp_path / "iclr25v2.parquet"
    bad.write_bytes(b"not the dataset")
    with pytest.raises(SystemExit):
        download(str(bad))


# ── OpenReview login ─────────────────────────────────────────────────────

def test_no_credentials_means_no_login(monkeypatch):
    import scraping.scrape_iclr as v2
    import scraping.scrape_iclr_openreview_early as v1
    monkeypatch.delenv("OPENREVIEW_USERNAME", raising=False)
    monkeypatch.delenv("OPENREVIEW_PASSWORD", raising=False)
    for mod in (v2, v1):
        h = mod.auth_headers()
        assert "Authorization" not in h
        assert "@" not in h["User-Agent"]          # nothing personal in the header


# ── failures never overwrite raw data ────────────────────────────────────

def _raw(tmp_path):
    p = tmp_path / "iclr_2015_arxiv.json"
    p.write_text('[{"paper_id": "kept"}]')
    return p


def test_arxiv_index_failure_leaves_raw_file(tmp_path, monkeypatch):
    import pytest
    import scraping.scrape_iclr_arxiv as ax
    p = _raw(tmp_path)
    def get(url, retries=4):
        raise RuntimeError("down")
    monkeypatch.setattr(ax, "_get", get)
    with pytest.raises(RuntimeError):
        ax.scrape_year(2015, str(tmp_path))
    assert p.read_text() == '[{"paper_id": "kept"}]'


def test_arxiv_empty_index_leaves_raw_file(tmp_path, monkeypatch):
    import pytest
    import scraping.scrape_iclr_arxiv as ax
    p = _raw(tmp_path)
    monkeypatch.setattr(ax, "_get", lambda url, retries=4: "<html>moved</html>")
    with pytest.raises(SystemExit):
        ax.scrape_year(2015, str(tmp_path))
    assert p.read_text() == '[{"paper_id": "kept"}]'


def test_arxiv_failed_feed_batch_leaves_raw_file(tmp_path, monkeypatch):
    import pytest
    import scraping.scrape_iclr_arxiv as ax
    p = _raw(tmp_path)
    page = '<a href="https://arxiv.org/abs/1412.6980">x</a>'
    def get(url, retries=4):
        if "export.arxiv.org" in url:
            raise RuntimeError("api down")
        return page
    monkeypatch.setattr(ax, "_get", get)
    with pytest.raises(RuntimeError):
        ax.scrape_year(2015, str(tmp_path))
    assert p.read_text() == '[{"paper_id": "kept"}]'


def test_get_raises_after_retries(monkeypatch):
    import pytest
    import scraping.scrape_iclr_arxiv as ax
    def boom(*a, **k):
        raise OSError("no network")
    monkeypatch.setattr(ax.urllib.request, "urlopen", boom)
    monkeypatch.setattr(ax.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        ax._get("https://example.invalid", retries=2)


def test_openreview_scrapers_keep_raw_file_on_empty_result(tmp_path, monkeypatch):
    import pytest
    import scraping.scrape_iclr as v2
    import scraping.scrape_iclr_openreview_early as v1
    keep = '[{"id": "kept"}]'
    (tmp_path / "iclr_2013_openreview.json").write_text(keep)
    (tmp_path / "iclr_2026_data.json").write_text(keep)
    monkeypatch.setattr(v1, "fetch_notes", lambda year: [])
    with pytest.raises(SystemExit):
        v1.scrape_year(2013, str(tmp_path))
    monkeypatch.setattr(v2, "fetch_all_notes", lambda venue_id, headers: [])
    monkeypatch.setattr(v2, "auth_headers", lambda: {})
    assert v2.download_year(2026, str(tmp_path)) == 0
    assert (tmp_path / "iclr_2013_openreview.json").read_text() == keep
    assert (tmp_path / "iclr_2026_data.json").read_text() == keep


def test_arxiv_feed_resolving_nothing_leaves_raw_file(tmp_path, monkeypatch):
    import pytest
    import scraping.scrape_iclr_arxiv as ax
    p = _raw(tmp_path)
    page = '<a href="https://arxiv.org/abs/1412.6980">x</a>'
    monkeypatch.setattr(ax, "_get", lambda url, retries=4:
                        "<feed></feed>" if "export.arxiv.org" in url else page)
    monkeypatch.setattr(ax.time, "sleep", lambda s: None)
    with pytest.raises(SystemExit):
        ax.scrape_year(2015, str(tmp_path))
    assert p.read_text() == '[{"paper_id": "kept"}]'
