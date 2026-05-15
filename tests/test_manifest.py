"""Tests for run_manifest.json generation and manifest scanning."""

import json
from pathlib import Path

import pytest

from reviewtrace.db.connection import init_db
from reviewtrace.manifest import collect_stats, scan_manifests, write_manifest


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    init_db(tmp_path / "test.db")
    yield


def test_write_manifest_completed(tmp_path):
    dest = write_manifest(
        tmp_path / "out",
        topic="Sparse Autoencoders",
        demo=True,
        fresh=True,
        db_path=Path("reviewtrace.db"),
        status="completed",
        run_id="abc123",
    )
    assert dest.exists()
    data = json.loads(dest.read_text())
    assert data["run_id"] == "abc123"
    assert data["topic"] == "Sparse Autoencoders"
    assert data["status"] == "completed"
    assert data["demo"] is True
    assert data["fresh"] is True
    assert "created_at" in data
    assert "stats" in data
    assert "error" not in data


def test_write_manifest_error(tmp_path):
    dest = write_manifest(
        tmp_path / "out",
        topic="Test Topic",
        demo=False,
        fresh=False,
        db_path=Path("reviewtrace.db"),
        status="error",
        error="Something went wrong",
    )
    data = json.loads(dest.read_text())
    assert data["status"] == "error"
    assert data["error"] == "Something went wrong"


def test_write_manifest_generates_run_id(tmp_path):
    dest = write_manifest(
        tmp_path / "out",
        topic="T",
        demo=False,
        fresh=False,
        db_path=Path("reviewtrace.db"),
        status="completed",
    )
    data = json.loads(dest.read_text())
    assert len(data["run_id"]) == 12  # hex[:12]


def test_write_manifest_creates_output_dir(tmp_path):
    out = tmp_path / "nested" / "dir"
    assert not out.exists()
    write_manifest(
        out,
        topic="T",
        demo=False,
        fresh=False,
        db_path=Path("reviewtrace.db"),
        status="completed",
    )
    assert out.exists()
    assert (out / "run_manifest.json").exists()


def test_collect_stats_empty_db(tmp_path):
    stats = collect_stats()
    assert stats["total_papers"] == 0
    assert stats["included"] == 0
    assert stats["excluded"] == 0
    assert stats["evidence_items"] == 0
    assert stats["taxonomy_nodes"] == 0
    assert stats["retrieval_runs"] == 0


def test_manifest_stats_keys(tmp_path):
    dest = write_manifest(
        tmp_path / "out",
        topic="T",
        demo=False,
        fresh=False,
        db_path=Path("reviewtrace.db"),
        status="completed",
    )
    stats = json.loads(dest.read_text())["stats"]
    expected_keys = {
        "total_papers", "canonical_papers", "duplicates",
        "included", "excluded", "uncertain", "unscreened",
        "evidence_items", "taxonomy_nodes", "retrieval_runs",
    }
    assert expected_keys == set(stats.keys())


# ---------------------------------------------------------------------------
# scan_manifests
# ---------------------------------------------------------------------------

def _write_raw_manifest(directory: Path, data: dict) -> Path:
    """Write a raw manifest dict to directory/run_manifest.json."""
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / "run_manifest.json"
    dest.write_text(json.dumps(data))
    return dest


def _minimal_manifest(run_id: str, topic: str, created_at: str, status: str = "completed") -> dict:
    return {
        "run_id": run_id,
        "topic": topic,
        "created_at": created_at,
        "status": status,
        "demo": False,
        "fresh": False,
        "db_path": "reviewtrace.db",
        "output_dir": "outputs",
        "stats": {},
    }


def test_scan_manifests_empty_dir(tmp_path):
    assert scan_manifests(tmp_path) == []


def test_scan_manifests_nonexistent_dir(tmp_path):
    assert scan_manifests(tmp_path / "does_not_exist") == []


def test_scan_manifests_finds_manifests(tmp_path):
    _write_raw_manifest(tmp_path / "run_a", _minimal_manifest("aaa", "Topic A", "2024-01-02T00:00:00+00:00"))
    _write_raw_manifest(tmp_path / "run_b", _minimal_manifest("bbb", "Topic B", "2024-01-01T00:00:00+00:00"))

    results = scan_manifests(tmp_path)
    assert len(results) == 2
    # sorted by created_at descending — newer first
    assert results[0]["run_id"] == "aaa"
    assert results[1]["run_id"] == "bbb"


def test_scan_manifests_nested(tmp_path):
    """Manifests in sub-subdirectories are discovered."""
    _write_raw_manifest(tmp_path / "a" / "b", _minimal_manifest("nested", "Nested", "2024-03-01T00:00:00+00:00"))
    results = scan_manifests(tmp_path)
    assert len(results) == 1
    assert results[0]["run_id"] == "nested"


def test_scan_manifests_skips_invalid_json(tmp_path):
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "run_manifest.json").write_text("not json{{{")
    _write_raw_manifest(tmp_path / "good", _minimal_manifest("ok", "T", "2024-01-01T00:00:00+00:00"))
    results = scan_manifests(tmp_path)
    assert len(results) == 1
    assert results[0]["run_id"] == "ok"


def test_scan_manifests_skips_missing_required_fields(tmp_path):
    (tmp_path / "incomplete").mkdir()
    (tmp_path / "incomplete" / "run_manifest.json").write_text(json.dumps({"status": "completed"}))
    results = scan_manifests(tmp_path)
    assert results == []


def test_scan_manifests_includes_error_status(tmp_path):
    data = _minimal_manifest("err1", "T", "2024-01-01T00:00:00+00:00", status="error")
    data["error"] = "Something failed"
    _write_raw_manifest(tmp_path / "errrun", data)
    results = scan_manifests(tmp_path)
    assert results[0]["status"] == "error"
    assert results[0]["error"] == "Something failed"


# ---------------------------------------------------------------------------
# GET /api/review-runs endpoint
# ---------------------------------------------------------------------------

def test_review_runs_endpoint(tmp_path, monkeypatch):
    """GET /api/review-runs returns manifests sorted by created_at descending."""

    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    monkeypatch.setenv("REVIEWTRACE_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    _write_raw_manifest(tmp_path / "r1", _minimal_manifest("r1", "Topic 1", "2024-06-01T00:00:00+00:00"))
    _write_raw_manifest(tmp_path / "r2", _minimal_manifest("r2", "Topic 2", "2024-05-01T00:00:00+00:00"))

    with TestClient(app) as client:
        response = client.get("/api/review-runs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["run_id"] == "r1"   # newer first
    assert data[1]["run_id"] == "r2"
    assert data[0]["topic"] == "Topic 1"


def test_review_runs_endpoint_empty(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    monkeypatch.setenv("REVIEWTRACE_OUTPUT_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.get("/api/review-runs")

    assert response.status_code == 200
    assert response.json() == []
