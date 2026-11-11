"""Tests for the dependency handling of main.py and its report in verify.py.

A command whose inputs are absent is not run; it is recorded in
$AA_DATA/incomplete.json, the stage carries on, and verify.py lists it before
the missing outputs it causes. The full --from aggregate route is exercised
by hand on the distributed metrics (README, Execution); these tests isolate
the mechanism.
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import main  # noqa: E402
import verify  # noqa: E402


def test_unmet_needs_skip_the_command_and_are_recorded(tmp_path, monkeypatch, capsys):
    need = str(tmp_path / "processed" / "*" / "*.json")
    monkeypatch.setattr(main, "NEEDS", {"-c": [need]})
    inc = {}
    main.run("analysis", [["-c", "raise SystemExit(3)"]], inc)    # would fail if run
    assert inc == {"-c raise SystemExit(3)": {"stage": "analysis", "script": "-c",
                                               "absent": [need]}}
    assert "not run: -c needs" in capsys.readouterr().out
    # once the input exists the command runs and its record is cleared
    (tmp_path / "processed" / "neurips").mkdir(parents=True)
    (tmp_path / "processed" / "neurips" / "neurips_1987.json").write_text("[]")
    inc2 = {"-c pass": {"stage": "analysis"}}
    main.run("analysis", [["-c", "pass"]], inc2)
    assert inc2 == {}


def test_a_failing_command_with_its_inputs_still_stops_the_pipeline(monkeypatch):
    monkeypatch.setattr(main, "NEEDS", {})
    with pytest.raises(SystemExit, match="failed"):
        main.run("analysis", [["-c", "raise SystemExit(3)"]], {})


def test_processed_dependent_commands_declare_their_input():
    """The scripts that read the processed abstracts are exactly the ones the
    --from aggregate route cannot run."""
    for script in ("src/aggregate/aggregate_papers_per_year.py",
                   "src/analysis/latex_robustness.py", "src/analysis/topic_clusters.py"):
        assert main.NEEDS[script] == [main.PROCESSED]
    for script in ("src/analysis/topic_trends.py", "src/analysis/topic_profiles.py",
                   "src/analysis/topic_decomposition.py"):
        assert main.NEEDS[script] == [main.TOPIC_ASSIGN]
    # A NEEDS key is a script or a whole command line, and either is staged.
    staged = ({cmd[0] for _, cmds in main.STAGES for cmd in cmds}
              | {" ".join(cmd) for _, cmds in main.STAGES for cmd in cmds})
    assert set(main.NEEDS) <= staged


def test_self_audit_is_skipped_without_the_manuscript(monkeypatch, capsys):
    """The self-audit reads the paper's own abstract, which is not
    distributed: without AA_PAPER the stage is skipped, not recorded as
    incomplete, and nothing runs."""
    monkeypatch.setattr(main, "PAPER", None)
    inc = {}
    main.run("self_audit", [["-c", "raise SystemExit(3)"]], inc)    # would fail if run
    assert inc == {} and "AA_PAPER is not set; skipped" in capsys.readouterr().out
    cmd = dict(main.STAGES)["self_audit"][0]
    assert cmd[0] == "src/metrics/audit_self.py" and "--from-tex" in cmd


def test_incomplete_json_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INCOMPLETE", str(tmp_path / "incomplete.json"))
    main.save_incomplete({"b": {"stage": "s"}, "a": {"stage": "s"}})
    assert list(main.load_incomplete()) == ["a", "b"]


def test_verify_lists_incomplete_analyses(tmp_path, monkeypatch, capsys):
    (tmp_path / "tmlr").mkdir()
    (tmp_path / "incomplete.json").write_text(json.dumps({
        "x": {"stage": "analysis", "script": "src/analysis/topic_clusters.py",
              "absent": ["data/processed/*/*.json"]}}))
    (tmp_path / "tmlr" / "skipped.json").write_text(json.dumps({
        "incomplete": [{"section": "topics", "input": "aggregate/topic_profiles.csv"}]}))
    monkeypatch.setattr(verify, "DATA", str(tmp_path))
    verify.incomplete_section()
    out = capsys.readouterr().out
    assert "incomplete analyses" in out
    assert "analysis: src/analysis/topic_clusters.py, absent data/processed/*/*.json" in out
    assert "section topics, absent aggregate/topic_profiles.csv" in out


def test_verify_says_nothing_when_complete(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(verify, "DATA", str(tmp_path))
    verify.incomplete_section()
    assert capsys.readouterr().out == ""
