"""Tests for ICLR and ICML record processing.

Both venues read a different raw source in different years. The early
sources pass their text through unchanged, because the published values were
computed on exactly that text; the export years filter and sanitise. These
pin which source each year reads and what each path keeps.
"""
import json

import pytest

import processing.process_iclr as iclr
import processing.process_icml as icml

ABS = "We propose a method and show that it works well in practice."


# ── year to source ───────────────────────────────────────────────────────

def test_iclr_sources_cover_2013_to_2026_once():
    assert sorted(iclr.SOURCES) == list(range(2013, 2027))
    assert iclr.SOURCES[2013] == "openreview"
    assert {iclr.SOURCES[y] for y in (2014, 2015, 2016)} == {"arxiv"}
    assert {iclr.SOURCES[y] for y in range(2017, 2027)} == {"data"}


def test_icml_sources_cover_2008_to_2025_once():
    assert sorted(icml.SOURCES) == list(range(2008, 2026))
    assert {icml.SOURCES[y] for y in range(2008, 2013)} == {"legacy"}
    assert {icml.SOURCES[y] for y in range(2013, 2017)} == {"pmlr"}
    assert {icml.SOURCES[y] for y in range(2017, 2026)} == {"data"}


def test_iclr_2014_reads_the_arxiv_file_not_openreview(tmp_path):
    """2014 OpenReview notes carry no decisions, so that file must be ignored."""
    raw = tmp_path / "raw"
    raw.mkdir()
    rec = {"paper_id": "2014_arxiv_1", "venue": "iclr", "year": 2014, "title": "T",
           "abstract": ABS, "authors": ["A"], "arxiv_id": "1"}
    (raw / "iclr_2014_arxiv.json").write_text(json.dumps([rec]))
    (raw / "iclr_2014_openreview.json").write_text(json.dumps([{**rec, "paper_id": "wrong"}]))
    n, _ = iclr.process_year(2014, str(raw), str(tmp_path / "out"))
    out = json.loads((tmp_path / "out" / "iclr_2014.json").read_text())
    assert n == 1 and out[0]["paper_id"] == "2014_arxiv_1"


def test_year_without_a_source_is_skipped(tmp_path):
    assert iclr.process_year(2012, str(tmp_path), str(tmp_path)) == (0, 0)
    assert icml.process_year(2007, str(tmp_path), str(tmp_path)) == (0, 0)


# ── ICLR ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("record,accepted", [
    ({"decision": "Accept (Oral)"}, True),
    ({"decision": "accept"}, True),
    ({"decision": "Reject"}, False),
    ({"decision": "", "labels": "ICLR 2026 Poster"}, True),
    ({"decision": "", "labels": "ICLR 2026 Spotlight"}, True),
    ({"decision": "", "labels": "ICLR 2026 Conference Withdrawn Submission"}, False),
    ({}, False),
])
def test_is_accepted(record, accepted):
    assert iclr.is_accepted(record) is accepted


def test_from_early_drops_only_the_source_key_and_keeps_text_and_order():
    raw = [{"paper_id": "b", "venue": "iclr", "year": 2013, "title": "  T  ",
            "abstract": "x  y", "authors": ["A"], "decision": "d"},
           {"paper_id": "a", "venue": "iclr", "year": 2013, "title": "T2",
            "abstract": ABS, "authors": ["B"], "decision": "d"}]
    out = iclr.from_early(raw, "openreview")
    assert [r["paper_id"] for r in out] == ["b", "a"]
    assert out[0]["title"] == "  T  " and out[0]["abstract"] == "x  y"
    assert "decision" not in out[0]


def test_from_openreview_export_filters_and_sanitises():
    raw = [{"id": "1", "year": 2020, "title": " T\n", "abstract": f"  {ABS}\n",
            "authors": "A, B", "decision": "Accept (Poster)"},
           {"id": "2", "year": 2020, "title": "T", "abstract": ABS, "authors": "A",
            "decision": "Reject"},
           {"id": "", "year": 2020, "title": "T", "abstract": ABS, "authors": "A",
            "decision": "Accept"},
           {"id": "4", "year": 2020, "title": "T", "abstract": "four words only here",
            "authors": "A", "decision": "Accept"}]
    papers, skipped = iclr.from_openreview_export(raw, 2020)
    assert skipped == 3
    assert papers == [{"paper_id": "1", "venue": "iclr", "year": 2020, "title": "T",
                       "abstract": ABS, "authors": ["A", "B"]}]


# ── ICML ─────────────────────────────────────────────────────────────────

def test_from_archive_rebuilds_canonical_record_in_key_order():
    legacy = {"paper_id": "2008_icmlcc_1", "year": 2008, "title": "T",
              "authors": ["A"], "abstract": ABS}
    pmlr = {"paper_id": "2013_pmlr_x", "year": 2013, "title": "T", "authors": ["A"],
            "abs_url": "u", "abstract": ABS}
    for rec in (legacy, pmlr):
        (out,) = icml.from_archive([rec])
        assert list(out) == ["paper_id", "venue", "year", "title", "abstract", "authors"]
        assert out["venue"] == "icml" and out["abstract"] == ABS


def test_strip_html():
    assert icml.strip_html("a<br/>b &#x27;c&#x27; <sup>2</sup>") == "a b 'c' 2"


def test_make_paper_id_prefers_url_then_title_hash():
    assert icml.make_paper_id({"virtualsite_url": "https://icml.cc/virtual/2023/poster/123/"}, 2023) == "123"
    a = icml.make_paper_id({"name": "T"}, 2023)
    assert len(a) == 12 and a == icml.make_paper_id({"name": "T"}, 2023)
    assert a != icml.make_paper_id({"name": "T"}, 2024)


def test_from_export_keeps_posters_with_title_abstract_and_authors():
    base = {"name": "T", "abstract": ABS, "speakers/authors": "A &amp; Co, B",
            "virtualsite_url": "u/1"}
    raw = [{**base, "type": "Poster"},
           {**base, "type": "Workshop"},
           {**base, "type": "Poster", "abstract": "too short"},
           {**base, "type": "Poster", "speakers/authors": ""},
           {**base, "type": "Poster", "name": "<b></b>"},
           {k: v for k, v in base.items()}]            # no type: legacy export, a paper
    papers, skipped = icml.from_export(raw, 2019)
    assert skipped == 4 and len(papers) == 2
    assert papers[0]["authors"] == ["A & Co", "B"]
