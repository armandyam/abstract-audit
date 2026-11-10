"""Tests for the arXiv and PubMed acquisition and processing scripts.

The snapshot and the baseline are gigabytes and cannot be refetched in the
form the paper used, so a full run never passes through these parsers again.
What is tested is the record-level logic: how a year is read, which records
are dropped, how a structured abstract is joined and then cleaned, and how a
baseline release is picked out of the NLM index.
"""
import gzip
import hashlib
import json

import pandas as pd
import pytest

import processing.clean_pubmed as clean
import processing.fetch_pubmed as fetch
import processing.process_arxiv as arxiv
import scraping.download_arxiv as download
from arxiv_categories import ARXIV_ML_CATEGORIES, is_ml

ABS = "We study a problem and report what we found in detail."


# ── ML categories ────────────────────────────────────────────────────────────

def test_eleven_ml_categories():
    assert len(ARXIV_ML_CATEGORIES) == 11
    assert {"cs.LG", "stat.ML", "cs.CY"} <= ARXIV_ML_CATEGORIES


def test_missing_category_is_non_ml():
    mask = is_ml(pd.Series(["cs.LG", "hep-th", None, float("nan")]))
    assert mask.tolist() == [True, False, False, False]


# ── arXiv processing ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("aid,year", [
    ("0704.0001", 2007), ("2509.04450", 2025), ("2509.04450v3", 2025),
    ("cs/9812021", 1998), ("math.GT/0309136", 2003), ("hep-th/9108001", 1991),
    ("3001.00001", 2030), ("3101.00001", 1931),
])
def test_year_from_identifier(aid, year):
    assert arxiv._year_from_arxiv_id(aid) == year


def test_update_date_is_only_a_fallback():
    assert arxiv.get_year({"id": "1501.00001", "update_date": "2009-01-01"}) == 2015
    assert arxiv.get_year({"id": "odd-id", "update_date": "2012-05-01"}) == 2012
    assert arxiv.get_year({"id": "odd-id", "update_date": "n/a"}) is None
    assert arxiv.get_year({"id": ""}) is None


def test_to_paper_keeps_primary_category_and_parsed_authors():
    p = arxiv.to_paper({"id": "2101.00001", "title": " A  title ", "abstract": ABS,
                        "categories": "cs.LG stat.ML",
                        "authors_parsed": [["Doe", "Jane", ""], ["Roe", "", ""]]})
    assert p["year"] == 2021 and p["title"] == "A title"
    assert p["arxiv_primary_category"] == "cs.LG"
    assert p["arxiv_categories"] == ["cs.LG", "stat.ML"]
    assert p["authors"] == ["Jane Doe", "Roe"]


@pytest.mark.parametrize("record", [
    {"id": "2101.00001", "title": "", "abstract": ABS},                # no title
    {"id": "", "title": "T", "abstract": ABS},                         # no id
    {"id": "2101.00001", "title": "T", "abstract": "four words only here"},
    {"id": "weird", "title": "T", "abstract": ABS},                    # no year
])
def test_to_paper_filters(record):
    assert arxiv.to_paper(record) is None


def test_no_categories_means_no_arxiv_fields():
    p = arxiv.to_paper({"id": "2101.00001", "title": "T", "abstract": ABS,
                        "authors": "A. One, B. Two"})
    assert "arxiv_primary_category" not in p
    assert p["authors"] == ["A. One", "B. Two"]


def test_download_sha256_and_missing_snapshot(tmp_path):
    f = tmp_path / download.SNAPSHOT_NAME
    f.write_bytes(b"{}\n")
    assert download.sha256(str(f)) == hashlib.sha256(b"{}\n").hexdigest()
    assert download.check(str(tmp_path)) == str(f)
    with pytest.raises(SystemExit):
        download.check(str(tmp_path / "empty"))


# ── PubMed fetch ─────────────────────────────────────────────────────────────

def test_baseline_files_pick_one_release_without_checksums():
    html = ('<a href="pubmed26n0002.xml.gz">pubmed26n0002.xml.gz</a> '
            '<a href="pubmed26n0001.xml.gz.md5">x</a> '
            '<a href="pubmed26n0001.xml.gz">pubmed26n0001.xml.gz</a> '
            '<a href="pubmed25n1274.xml.gz">old</a> README.txt')
    assert fetch.baseline_files(html) == ["pubmed26n0001.xml.gz", "pubmed26n0002.xml.gz"]
    assert fetch.baseline_files(html, "pubmed25n") == ["pubmed25n1274.xml.gz"]
    assert fetch.baseline_files("no files here") == []


def test_parse_md5_line():
    assert fetch.parse_md5("MD5(pubmed26n0001.xml.gz)= FB7C05737F47F7E07245F0C064C6E00A\n") \
        == "fb7c05737f47f7e07245f0c064c6e00a"
    with pytest.raises(ValueError):
        fetch.parse_md5("<html>not found</html>")


def _article(pmid, year=None, title="A title.", abstract=None, lang="eng",
             medline_date=None, structured=False):
    date = (f"<Year>{year}</Year>" if year else "") + \
           (f"<MedlineDate>{medline_date}</MedlineDate>" if medline_date else "")
    if structured:
        abst = ('<AbstractText Label="BACKGROUND">Cells repair <i>DNA</i> damage.</AbstractText>'
                '<AbstractText Label="METHODS">We used PCR on many samples here.</AbstractText>')
    else:
        abst = f"<AbstractText>{abstract or ABS}</AbstractText>"
    lang_el = f"<Language>{lang}</Language>" if lang else ""
    return (f"<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article>"
            f"<Journal><JournalIssue><PubDate>{date}</PubDate></JournalIssue></Journal>"
            f"<ArticleTitle>{title}</ArticleTitle><Abstract>{abst}</Abstract>"
            f"<AuthorList><Author><LastName>Doe</LastName><ForeName>Jane</ForeName></Author>"
            f"<Author><CollectiveName>The Group</CollectiveName></Author></AuthorList>"
            f"{lang_el}</Article></MedlineCitation></PubmedArticle>")


def _gz(tmp_path, articles):
    path = tmp_path / "pubmed26n0001.xml.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write("<PubmedArticleSet>" + "".join(articles) + "</PubmedArticleSet>")
    return str(path)


def test_parse_file_filters_and_dates(tmp_path):
    path = _gz(tmp_path, [
        _article(1, 2020),                                   # kept
        _article(2, 2020, lang="fre"),                       # not English
        _article(3, 2020, lang=None),                        # no language: kept
        _article(4, 1985),                                   # before start year
        _article(5, 2020, abstract="too short to keep"),     # under six words
        _article(6, 2020, title="Published erratum for a paper."),
        _article(7, medline_date="2019 Jan-Feb"),            # MedlineDate year
        _article(8, 2027),                                   # ahead of print: kept
        _article(9),                                         # no year at all
        _article(10, 2020, title=""),                        # no title
    ])
    buckets = fetch.parse_file(path, None, 1990)
    ids = {y: [p["paper_id"] for p in ps] for y, ps in buckets.items()}
    assert ids == {2020: ["pmid_1", "pmid_3"], 2019: ["pmid_7"], 2027: ["pmid_8"]}
    assert buckets[2020][0]["authors"] == ["Jane Doe", "The Group"]
    assert buckets[2020][0]["venue"] == "pubmed"
    assert fetch.parse_file(path, {2019}, 1990).keys() == {2019}


def test_structured_abstract_keeps_labels_for_the_cleaner(tmp_path):
    path = _gz(tmp_path, [_article(1, 2020, structured=True)])
    abstract = fetch.parse_file(path, None, 1990)[2020][0]["abstract"]
    assert abstract == ("BACKGROUND: Cells repair DNA damage. "
                        "METHODS: We used PCR on many samples here.")
    assert clean.clean_abstract(abstract) == (
        "Cells repair DNA damage. We used PCR on many samples here.")


# ── PubMed cleaning ──────────────────────────────────────────────────────────

def test_clean_abstract_rules():
    assert clean.clean_abstract("MATERIALS AND METHODS: Rats & mice were used.") \
        == "Rats and mice were used."
    assert clean.clean_abstract("Naïve  T‐cells\nrespond.") == "Nave Tcells respond."
    assert clean.clean_abstract("BACKGROUND/AIMS: x") == "x"
    assert clean.clean_abstract("") == ""


def test_clean_papers_drops_short_and_leaves_input_untouched():
    papers = [{"paper_id": "a", "abstract": "RESULTS: one two three four five"},
              {"paper_id": "b", "abstract": "one two three four five six"},
              {"paper_id": "c"}]
    out = clean.clean_papers(papers)
    assert [p["paper_id"] for p in out] == ["b"]
    assert papers[0]["abstract"].startswith("RESULTS")


def test_clean_writes_processed_pubmed(tmp_path, monkeypatch):
    src, dst = tmp_path / "pubmed_parsed", tmp_path / "pubmed"
    src.mkdir()
    (src / "pubmed_2020.json").write_text(json.dumps(
        [{"paper_id": "pmid_1", "abstract": "OBJECTIVE: " + ABS}]))
    assert clean.process_file(str(src / "pubmed_2020.json"),
                              str(dst / "pubmed_2020.json")) == (1, 1)
    assert json.loads((dst / "pubmed_2020.json").read_text())[0]["abstract"] == ABS


def test_clean_refuses_to_clean_in_place(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["clean_pubmed.py", "--in-dir", str(tmp_path),
                                     "--out-dir", str(tmp_path)])
    with pytest.raises(SystemExit, match="must differ"):
        clean.main()


# ── PubMed resume: shards, interruption, settings ────────────────────────────

def _baseline(tmp_path, monkeypatch, files):
    """A fake baseline: each name maps to a list of (pmid, year) records,
    written into the cache so no download happens."""
    cache = tmp_path / "cache"
    cache.mkdir(exist_ok=True)
    for name, recs in files.items():
        with gzip.open(cache / name, "wt", encoding="utf-8") as fh:
            fh.write("<PubmedArticleSet>" + "".join(_article(p, y) for p, y in recs)
                     + "</PubmedArticleSet>")
    monkeypatch.setattr(fetch, "list_baseline_files", lambda prefix: sorted(files))
    monkeypatch.setattr(fetch, "_download",
                        lambda url, dest: pytest.fail("unexpected download"))
    out = tmp_path / "out"
    return ["--out-base", str(out), "--cache-dir", str(cache), "--no-md5",
            "--keep-cache"], out


def _ids(out):
    got = {}
    for f in sorted(out.glob("pubmed_*.json")):
        got[f.name] = [p["paper_id"] for p in json.loads(f.read_text())]
    return got


FILES = {"pubmed26n0001.xml.gz": [(1, 2020), (2, 2021)],
         "pubmed26n0002.xml.gz": [(3, 2020)],
         "pubmed26n0003.xml.gz": [(4, 2021), (5, 2019)]}


def test_pubmed_interrupted_run_resumes_without_loss_or_duplicates(tmp_path, monkeypatch):
    argv, out = _baseline(tmp_path, monkeypatch, FILES)
    real_parse = fetch.parse_file

    def crash_on_third(path, *a):
        if path.endswith("0003.xml.gz"):
            raise KeyboardInterrupt
        return real_parse(path, *a)
    monkeypatch.setattr(fetch, "parse_file", crash_on_third)
    with pytest.raises(KeyboardInterrupt):
        fetch.main(argv)

    # The two finished files are on disk before the state lists them
    state = json.loads((out / fetch.STATE_NAME).read_text())
    assert state["done"] == ["pubmed26n0001.xml.gz", "pubmed26n0002.xml.gz"]
    assert sorted(p.name for p in (out / fetch.SHARD_DIR).iterdir()) == [
        "pubmed26n0001.jsonl.gz", "pubmed26n0002.jsonl.gz"]

    monkeypatch.setattr(fetch, "parse_file", real_parse)
    fetch.main(argv)
    expected = {"pubmed_2019.json": ["pmid_5"],
                "pubmed_2020.json": ["pmid_1", "pmid_3"],
                "pubmed_2021.json": ["pmid_2", "pmid_4"]}
    assert _ids(out) == expected
    fetch.main(argv)            # nothing left to parse: same output, no duplicates
    assert _ids(out) == expected


def test_pubmed_crash_after_shard_before_state_reparses_that_file(tmp_path, monkeypatch):
    argv, out = _baseline(tmp_path, monkeypatch, FILES)
    real_save = fetch.save_state
    calls = {"n": 0}

    def crash_on_second_save(*a):
        calls["n"] += 1
        if calls["n"] == 3:     # initial save, file 1, then file 2's record
            raise KeyboardInterrupt
        return real_save(*a)
    monkeypatch.setattr(fetch, "save_state", crash_on_second_save)
    with pytest.raises(KeyboardInterrupt):
        fetch.main(argv)
    monkeypatch.setattr(fetch, "save_state", real_save)
    fetch.main(argv)
    assert _ids(out)["pubmed_2020.json"] == ["pmid_1", "pmid_3"]


@pytest.mark.parametrize("extra", [["--start-year", "2021"], ["--years", "2020"],
                                   ["--baseline-prefix", "pubmed25n"]])
def test_pubmed_resume_with_other_settings_is_refused(tmp_path, monkeypatch, extra):
    argv, out = _baseline(tmp_path, monkeypatch, FILES)
    fetch.main(argv + ["--max-files", "1"])
    with pytest.raises(SystemExit, match="settings"):
        fetch.main(argv + extra)


def test_pubmed_years_subset_is_fingerprinted(tmp_path, monkeypatch):
    argv, out = _baseline(tmp_path, monkeypatch, FILES)
    fetch.main(argv + ["--years", "2021", "2020"])
    assert set(_ids(out)) == {"pubmed_2020.json", "pubmed_2021.json"}
    fetch.main(argv + ["--years", "2020", "2021"])     # same set, other order: fine
    with pytest.raises(SystemExit, match="settings"):
        fetch.main(argv + ["--years", "2019"])


def test_pubmed_legacy_state_and_unexplained_year_files_are_refused(tmp_path, monkeypatch):
    argv, out = _baseline(tmp_path, monkeypatch, FILES)
    out.mkdir()
    (out / fetch.STATE_NAME).write_text(json.dumps(["pubmed26n0001.xml.gz"]))
    with pytest.raises(SystemExit, match="earlier version"):
        fetch.main(argv)
    (out / fetch.STATE_NAME).unlink()
    (out / "pubmed_2020.json").write_text("[]")
    with pytest.raises(SystemExit, match="no state file"):
        fetch.main(argv)
