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


def test_demo_help_shows_fresh():
    result = runner.invoke(app, ["demo", "--help"])
    output = _strip_ansi(result.output)
    assert result.exit_code == 0
    assert "--fresh" in output


def test_run_help_shows_fresh():
    result = runner.invoke(app, ["run", "--help"])
    output = _strip_ansi(result.output)
    assert result.exit_code == 0
    assert "--fresh" in output


def test_fresh_deletes_db_and_output(tmp_path, monkeypatch):
    """--fresh removes the DB file and output dir before the pipeline runs."""
    db_file = tmp_path / "test.db"
    db_file.write_text("stale")          # simulate pre-existing DB
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "old_file.txt").write_text("stale output")

    captured = {}

    def fake_pipeline(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("reviewtrace.cli._execute_pipeline", fake_pipeline)

    seeds_file = tmp_path / "seeds.txt"
    seeds_file.write_text("")
    criteria_file = tmp_path / "criteria.json"
    criteria_file.write_text(json.dumps({"topic": "T", "inclusion": [], "exclusion": []}))

    result = runner.invoke(app, [
        "run",
        "--topic", "Test",
        "--seeds", str(seeds_file),
        "--criteria", str(criteria_file),
        "--db", str(db_file),
        "--output-dir", str(out_dir),
        "--fresh",
    ])
    assert result.exit_code == 0
    assert captured.get("fresh") is True


def test_execute_pipeline_fresh_removes_db(tmp_path):
    """_execute_pipeline with fresh=True removes the DB file and clears output dir.

    The fresh reset happens before any pipeline I/O, so we verify the filesystem
    state after the reset even if the pipeline itself fails due to missing infra.
    """
    from reviewtrace.cli import _execute_pipeline

    db_file = tmp_path / "test.db"
    db_file.write_text("old data")
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()
    stale_file = out_dir / "old.txt"
    stale_file.write_text("stale")

    # The pipeline will fail once it tries real network/LLM calls, but the
    # fresh filesystem reset runs first — we just catch whatever comes after.
    try:
        _execute_pipeline(
            topic="T",
            seeds=None,
            criteria=None,
            db_path=db_file,
            output_dir=out_dir,
            max_results=5,
            depth=0,
            max_per_hop=5,
            llm_delay=0.0,
            skip_expand=True,
            demo=True,
            max_queries=1,
            fresh=True,
        )
    except Exception:
        pass  # pipeline may fail after the fresh reset — that's expected here

    # DB file deleted before init_db recreated it — it now exists again as a fresh
    # SQLite file, not the stale text content we wrote.
    assert db_file.read_bytes()[:6] != b"old da", "DB was not reset when fresh=True"
    # Stale output file was cleared
    assert not stale_file.exists(), "Output dir was not cleared when fresh=True"


def test_demo_constants_are_consistent():
    """The demo defaults reference files in the sparse_autoencoders example directory."""
    assert _DEMO_SEEDS == _DEMO_CRITERIA.parent / "seeds.txt"
    assert _DEMO_CRITERIA == _DEMO_SEEDS.parent / "criteria.json"
    assert "sparse_autoencoders" in str(_DEMO_SEEDS)
    assert "sparse_autoencoders" in str(_DEMO_OUTPUT_DIR)
    from reviewtrace.cli import _DEMO_TOPIC  # noqa: PLC0415
    assert "Sparse Autoencoders" in _DEMO_TOPIC
