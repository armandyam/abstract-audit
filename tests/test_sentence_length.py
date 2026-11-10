"""Tests for the Hohmann sentence length metric.

The full run reproduces the per-paper files byte for byte, so what is tested
here is what NeurIPS abstracts never exercise: text without a terminating
period, an empty abstract, periods that do not end a sentence, and the
resume path over a partially written output. The metric's place in the TMLR
export and the self-audit is checked as well, since both name it by string.
"""
import json

import pandas as pd
import pytest

import plotting.export_pgfplots_data as export
from metrics.sentence_length import process_venue, words_per_sentence


# ── the ratio ────────────────────────────────────────────────────────────

def test_two_sentences():
    assert words_per_sentence("We do one thing. We do another thing.") == (8, 2, 4.0)


def test_no_terminating_period_is_one_sentence():
    """A run-on abstract still has a defined ratio: all words, one sentence."""
    assert words_per_sentence("No terminator here at all") == (5, 1, 5.0)


def test_empty_abstract_scores_zero_not_an_error():
    assert words_per_sentence("") == (0, 1, 0.0)


def test_decimal_point_is_not_a_sentence_end():
    """Only a period followed by whitespace, or a final one, ends a sentence."""
    _, ns, _ = words_per_sentence("Accuracy rose to 93.5 on the test set.")
    assert ns == 1


def test_abbreviation_followed_by_space_counts_as_a_break():
    """The narrator rule is a full stop followed by whitespace; it does not
    know abbreviations. Recorded here so a change to that is deliberate."""
    _, ns, _ = words_per_sentence("We use e.g. dropout here.")
    assert ns == 2


def test_ratio_is_rounded_to_four_decimals():
    _, _, wps = words_per_sentence("One two three. Four five six. Seven.")
    assert wps == round(7 / 3, 4)


# ── the per-venue runner ─────────────────────────────────────────────────

def _processed(tmp_path, papers_by_year):
    d = tmp_path / "processed" / "neurips"
    d.mkdir(parents=True)
    for year, papers in papers_by_year.items():
        (d / f"neurips_{year}.json").write_text(json.dumps(papers))
    return str(tmp_path / "processed")


def _paper(pid, year, abstract="A sentence here. Another one."):
    return {"paper_id": pid, "venue": "neurips", "year": year,
            "title": "T", "abstract": abstract, "authors": []}


def test_missing_venue_writes_nothing(tmp_path):
    assert process_venue("icml", str(tmp_path), str(tmp_path / "out")) == 0
    assert not (tmp_path / "out").exists()


def test_columns_and_values(tmp_path):
    proc = _processed(tmp_path, {2020: [_paper("a", 2020)]})
    out = tmp_path / "out"
    assert process_venue("neurips", proc, str(out)) == 1
    df = pd.read_csv(out / "neurips.csv")
    assert list(df.columns) == ["paper_id", "venue", "year", "n_words",
                                "n_sentences", "words_per_sentence"]
    assert df.iloc[0].tolist() == ["a", "neurips", 2020, 5, 2, 2.5]


def test_resume_tops_up_a_partial_year_without_duplicates(tmp_path):
    proc = _processed(tmp_path, {2020: [_paper("a", 2020), _paper("b", 2020)]})
    out = tmp_path / "out"
    out.mkdir()
    pd.DataFrame([{"paper_id": "a", "venue": "neurips", "year": 2020, "n_words": 5,
                   "n_sentences": 2, "words_per_sentence": 2.5}]).to_csv(
        out / "neurips.csv", index=False)
    assert process_venue("neurips", proc, str(out)) == 1
    df = pd.read_csv(out / "neurips.csv")
    assert sorted(df.paper_id) == ["a", "b"]
    assert process_venue("neurips", proc, str(out)) == 0      # now complete


# ── wiring ───────────────────────────────────────────────────────────────

def test_tmlr_export_names_the_series_as_the_paper_does():
    assert ("sentence_length", "words_per_sentence", "sentence_length") in export.STYLE


def test_tmlr_export_writes_sentence_length(tmp_path, monkeypatch):
    agg = tmp_path / "aggregate"
    agg.mkdir()
    pd.DataFrame({"year": [2013, 2014], "neurips_words_per_sentence_mean": [24.0, 25.0],
                  "iclr_words_per_sentence_mean": [None, 22.0]}).to_csv(
        agg / "sentence_length.csv", index=False)
    monkeypatch.setattr(export, "AGG", str(agg))
    export.export_metric("sentence_length", "words_per_sentence", "sentence_length",
                         out=str(tmp_path / "tmlr"))
    df = pd.read_csv(tmp_path / "tmlr" / "sentence_length.csv")
    assert list(df.columns) == ["year", "neurips", "iclr"]
    assert df.iclr.isna().tolist() == [True, False]


@pytest.mark.parametrize("abstract", ["", "no period", "Two. Sentences."])
def test_runner_never_divides_by_zero(tmp_path, abstract):
    proc = _processed(tmp_path, {2020: [_paper("a", 2020, abstract)]})
    process_venue("neurips", proc, str(tmp_path / "out"))
    df = pd.read_csv(tmp_path / "out" / "neurips.csv")
    assert (df.n_sentences >= 1).all()
