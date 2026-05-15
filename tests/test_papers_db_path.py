"""Tests for db_path query-param support on paper endpoints."""

from __future__ import annotations

import uuid

import pytest

from reviewtrace.db.connection import execute, init_db, insert_paper
from reviewtrace.retrieval.models import PaperMetadata


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    init_db(tmp_path / "test.db")
    yield


def _insert(doi: str, title: str) -> str:
    p = PaperMetadata(title=title, authors=["A B"], doi=doi, venue="ICLR", year=2024)
    insert_paper(p.to_db_dict())
    return p.id


def _screen(paper_id: str, decision: str = "include") -> None:
    execute(
        "INSERT INTO screening_decisions (id, paper_id, decision, reason, confidence, screened_by) VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4()), paper_id, decision, "ok", 0.9, "llm"),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path, monkeypatch):
    """Create an isolated DB in tmp_path/run_a/ with one paper and return the path."""

    run_dir = tmp_path / "run_a"
    run_dir.mkdir()
    db_file = run_dir / "reviewtrace.db"
    init_db(db_file)
    pid = _insert("10.1/x", "Run A Paper")
    _screen(pid)
    # Return both the path and the paper id
    return db_file, pid


# ---------------------------------------------------------------------------
# GET /api/papers?db_path=...
# ---------------------------------------------------------------------------

def test_papers_default_db(tmp_path, monkeypatch):
    """Without db_path, /api/papers reads from the configured global DB."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))
    _insert("10.1/a", "Default DB Paper")

    with TestClient(app) as client:
        resp = client.get("/api/papers")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.json()]
    assert "Default DB Paper" in titles


def test_papers_valid_db_path(tmp_path, monkeypatch):
    """?db_path=<valid path inside cwd> reads from that DB."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))
    # Switch cwd so run_a/ is inside it
    monkeypatch.chdir(tmp_path)

    run_dir = tmp_path / "run_a"
    run_dir.mkdir()
    db_file = run_dir / "reviewtrace.db"
    init_db(db_file)
    _insert("10.1/b", "Run A Paper")

    with TestClient(app) as client:
        resp = client.get(f"/api/papers?db_path={db_file}")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.json()]
    assert "Run A Paper" in titles


def test_papers_db_path_outside_cwd_returns_403(tmp_path, monkeypatch):
    """?db_path pointing outside cwd returns 403."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    inner = tmp_path / "inner"
    inner.mkdir()
    monkeypatch.chdir(inner)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(inner / "test.db"))

    outside_db = tmp_path / "secret.db"
    outside_db.write_bytes(b"")

    with TestClient(app) as client:
        resp = client.get(f"/api/papers?db_path={outside_db}")
    assert resp.status_code == 403


def test_papers_db_path_nonexistent_returns_404(tmp_path, monkeypatch):
    """?db_path pointing to a nonexistent file returns 404."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        resp = client.get(f"/api/papers?db_path={tmp_path / 'missing.db'}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/papers/{paper_id}/audit?db_path=...
# ---------------------------------------------------------------------------

def test_paper_audit_valid_db_path(tmp_path, monkeypatch):
    """Audit endpoint reads from the specified DB."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    run_dir = tmp_path / "run_b"
    run_dir.mkdir()
    db_file = run_dir / "reviewtrace.db"
    init_db(db_file)
    pid = _insert("10.1/c", "Audit Paper")

    with TestClient(app) as client:
        resp = client.get(f"/api/papers/{pid}/audit?db_path={db_file}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_paper_audit_db_path_outside_cwd_returns_403(tmp_path, monkeypatch):
    """Audit endpoint rejects db_path outside cwd."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    inner = tmp_path / "inner"
    inner.mkdir()
    monkeypatch.chdir(inner)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(inner / "test.db"))

    outside_db = tmp_path / "secret.db"
    outside_db.write_bytes(b"")

    with TestClient(app) as client:
        resp = client.get(f"/api/papers/fake-id/audit?db_path={outside_db}")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/evidence?db_path=...
# ---------------------------------------------------------------------------

def test_evidence_db_path_outside_cwd_returns_403(tmp_path, monkeypatch):
    """Evidence endpoint rejects db_path outside cwd."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    inner = tmp_path / "inner"
    inner.mkdir()
    monkeypatch.chdir(inner)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(inner / "test.db"))

    outside_db = tmp_path / "secret.db"
    outside_db.write_bytes(b"")

    with TestClient(app) as client:
        resp = client.get(f"/api/evidence?db_path={outside_db}")
    assert resp.status_code == 403


def test_evidence_valid_db_path(tmp_path, monkeypatch):
    """Evidence endpoint reads from the specified DB."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    run_dir = tmp_path / "run_c"
    run_dir.mkdir()
    db_file = run_dir / "reviewtrace.db"
    init_db(db_file)

    with TestClient(app) as client:
        resp = client.get(f"/api/evidence?db_path={db_file}")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/taxonomy?db_path=...
# ---------------------------------------------------------------------------

def test_taxonomy_valid_db_path(tmp_path, monkeypatch):
    """Taxonomy endpoint reads from the specified DB."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    run_dir = tmp_path / "run_tax"
    run_dir.mkdir()
    db_file = run_dir / "reviewtrace.db"
    init_db(db_file)

    with TestClient(app) as client:
        resp = client.get(f"/api/taxonomy?db_path={db_file}")
    assert resp.status_code == 200
    assert resp.json() == []


def test_taxonomy_db_path_outside_cwd_returns_403(tmp_path, monkeypatch):
    """Taxonomy endpoint rejects db_path outside cwd."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    inner = tmp_path / "inner"
    inner.mkdir()
    monkeypatch.chdir(inner)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(inner / "test.db"))

    outside_db = tmp_path / "secret.db"
    outside_db.write_bytes(b"")

    with TestClient(app) as client:
        resp = client.get(f"/api/taxonomy?db_path={outside_db}")
    assert resp.status_code == 403


def test_taxonomy_db_path_nonexistent_returns_404(tmp_path, monkeypatch):
    """Taxonomy endpoint returns 404 for a nonexistent db_path."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        resp = client.get(f"/api/taxonomy?db_path={tmp_path / 'missing.db'}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/runs?db_path=...
# ---------------------------------------------------------------------------

def test_runs_valid_db_path(tmp_path, monkeypatch):
    """Runs endpoint reads from the specified DB."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    run_dir = tmp_path / "run_audit"
    run_dir.mkdir()
    db_file = run_dir / "reviewtrace.db"
    init_db(db_file)

    with TestClient(app) as client:
        resp = client.get(f"/api/runs?db_path={db_file}")
    assert resp.status_code == 200
    assert resp.json() == []


def test_runs_db_path_outside_cwd_returns_403(tmp_path, monkeypatch):
    """Runs endpoint rejects db_path outside cwd."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    inner = tmp_path / "inner"
    inner.mkdir()
    monkeypatch.chdir(inner)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(inner / "test.db"))

    outside_db = tmp_path / "secret.db"
    outside_db.write_bytes(b"")

    with TestClient(app) as client:
        resp = client.get(f"/api/runs?db_path={outside_db}")
    assert resp.status_code == 403


def test_runs_db_path_nonexistent_returns_404(tmp_path, monkeypatch):
    """Runs endpoint returns 404 for a nonexistent db_path."""
    from fastapi.testclient import TestClient

    from reviewtrace.api.app import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        resp = client.get(f"/api/runs?db_path={tmp_path / 'missing.db'}")
    assert resp.status_code == 404
