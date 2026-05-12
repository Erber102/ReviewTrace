"""Tests for the `reviewtrace demo` CLI command."""

import json
import re

from typer.testing import CliRunner

from reviewtrace.cli import _DEMO_CRITERIA, _DEMO_OUTPUT_DIR, _DEMO_SEEDS, app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_demo_help():
    result = runner.invoke(app, ["demo", "--help"])
    output = _strip_ansi(result.output)
    assert result.exit_code == 0
    assert "demo" in output.lower()
    assert "--output-dir" in output
    assert "--max-results" in output
    assert "--max-queries" in output


def test_demo_missing_seeds_shows_error(tmp_path):
    """demo should fail with a clear message when seeds file is missing."""
    missing = tmp_path / "no_seeds.txt"
    result = runner.invoke(app, [
        "demo",
        "--seeds", str(missing),
        "--criteria", str(missing),
    ])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_demo_missing_criteria_shows_error(tmp_path):
    """demo should fail with a clear message when criteria file is missing."""
    seeds_file = tmp_path / "seeds.txt"
    seeds_file.write_text("")
    missing_criteria = tmp_path / "no_criteria.json"
    result = runner.invoke(app, [
        "demo",
        "--seeds", str(seeds_file),
        "--criteria", str(missing_criteria),
    ])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_demo_startup_message(tmp_path, monkeypatch):
    """demo prints the startup message before running the pipeline."""
    seeds_file = tmp_path / "seeds.txt"
    seeds_file.write_text("2309.08600\n")
    criteria_file = tmp_path / "criteria.json"
    criteria_file.write_text(json.dumps({
        "topic": "Test topic",
        "inclusion": ["relevant"],
        "exclusion": ["irrelevant"],
    }))
    output_dir = tmp_path / "outputs"

    # Patch _execute_pipeline so no real network calls are made
    monkeypatch.setattr("reviewtrace.cli._execute_pipeline", lambda **_: None)

    result = runner.invoke(app, [
        "demo",
        "--topic", "Test topic",
        "--seeds", str(seeds_file),
        "--criteria", str(criteria_file),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0
    assert "Running ReviewTrace demo" in result.output
    assert "Test topic" in result.output


def test_demo_constants_are_consistent():
    """The demo defaults reference files in the sparse_autoencoders example directory."""
    assert _DEMO_SEEDS == _DEMO_CRITERIA.parent / "seeds.txt"
    assert _DEMO_CRITERIA == _DEMO_SEEDS.parent / "criteria.json"
    assert "sparse_autoencoders" in str(_DEMO_SEEDS)
    assert "sparse_autoencoders" in str(_DEMO_OUTPUT_DIR)
    from reviewtrace.cli import _DEMO_TOPIC  # noqa: PLC0415
    assert "Sparse Autoencoders" in _DEMO_TOPIC
