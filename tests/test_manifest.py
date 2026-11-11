"""reference/MANIFEST.md against the files it lists (reference/make_manifest.py)."""
import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "make_manifest", os.path.join(ROOT, "reference", "make_manifest.py"))
mm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mm)


def test_committed_manifest_matches_reference(capsys):
    assert mm.main([]) == 0, capsys.readouterr().out


def _tree(tmp_path, entries, files):
    for rel, body in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(body)
    lines = "\n".join(f"{h}  {p}" for h, p in entries)
    (tmp_path / "MANIFEST.md").write_text(
        f"# x\n\nprose\n\nsha256, first 16 hex:\n\n```\n{lines}\n```\n")
    return str(tmp_path / "MANIFEST.md")


def test_missing_unlisted_and_duplicate_paths_fail(tmp_path, capsys):
    a = tmp_path / "a.csv"
    m = _tree(tmp_path, [("0" * 16, "a.csv"), ("0" * 16, "gone.csv"), ("0" * 16, "a.csv")],
              {"a.csv": "1\n", "sub/new.csv": "2\n"})
    assert mm.main(["--manifest", m]) == 1
    out = capsys.readouterr().out
    assert "listed but missing: gone.csv" in out
    assert "not listed: sub/new.csv" in out
    assert "listed twice: a.csv" in out
    before = open(m).read()
    assert mm.main(["--manifest", m, "--write"]) == 1     # refuses to write
    assert open(m).read() == before
    assert a.exists()


def test_write_refreshes_stale_hashes_only(tmp_path):
    m = _tree(tmp_path, [("0" * 16, "a.csv")], {"a.csv": "1\n"})
    assert mm.main(["--manifest", m]) == 1
    assert mm.main(["--manifest", m, "--write"]) == 0
    assert mm.main(["--manifest", m]) == 0
    text = open(m).read()
    assert f"{mm.sha16(str(tmp_path / 'a.csv'))}  a.csv" in text and "prose" in text


def test_malformed_entry_is_an_error(tmp_path):
    m = _tree(tmp_path, [], {})
    with open(m, "a") as fh:
        fh.write("\nsha256, first 16 hex:\n\n```\nnot a hash line\n```\n")
    with pytest.raises(ValueError, match="not '<hash>  <path>'"):
        mm.main(["--manifest", m])
