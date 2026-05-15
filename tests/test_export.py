"""Tests for CSV and GraphML export."""

import csv
import uuid
import xml.etree.ElementTree as ET

import pytest

from reviewtrace.db.connection import execute, init_db, insert_paper
from reviewtrace.export.csv_export import export_papers_csv
from reviewtrace.export.graphml_export import _extract_source, export_graphml
from reviewtrace.retrieval.models import PaperMetadata


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    init_db(tmp_path / "test.db")
    yield


def _insert(doi: str, title: str, venue: str = "NeurIPS", year: int = 2024) -> str:
    p = PaperMetadata(title=title, authors=["A B"], doi=doi, venue=venue, year=year)
    insert_paper(p.to_db_dict())
    return p.id


def _screen(paper_id: str, decision: str = "include") -> None:
    execute(
        "INSERT INTO screening_decisions (id, paper_id, decision, reason, confidence, screened_by) VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4()), paper_id, decision, "ok", 0.9, "llm"),
    )


def _add_citation_edge(source_id: str, target_id: str, direction: str = "backward_citation") -> None:
    run_id = str(uuid.uuid4())
    execute(
        "INSERT INTO retrieval_runs (id, query, source, expansion_type, status) VALUES (?,?,?,?,?)",
        (run_id, f"expand:depth=0:paper={source_id}", "semantic_scholar", "citation_expansion", "done"),
    )
    path = f"seed:{source_id} → {direction} → {target_id}"
    execute(
        "INSERT INTO paper_retrievals (id, paper_id, retrieval_run_id, retrieval_reason, citation_path) VALUES (?,?,?,?,?)",
        (str(uuid.uuid4()), target_id, run_id, direction, path),
    )


# ---------------------------------------------------------------------------
# papers.csv
# ---------------------------------------------------------------------------

def test_export_papers_csv_basic(tmp_path):
    pid = _insert("10.1/a", "Paper A")
    _screen(pid, "include")
    out = tmp_path / "papers.csv"
    export_papers_csv(out)

    assert out.exists()
    with out.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["title"] == "Paper A"
    assert rows[0]["doi"] == "10.1/a"
    assert rows[0]["screening_decision"] == "include"
    assert rows[0]["is_duplicate"] == "no"


def test_export_papers_csv_marks_duplicate(tmp_path):
    pid_kept = _insert("10.1/b", "Paper B")
    pid_dup = _insert("10.1/c", "Paper B duplicate")
    # manually record dedup decision
    execute(
        "INSERT INTO dedup_decisions (id, paper_id_kept, paper_id_removed, match_type) VALUES (?,?,?,?)",
        (str(uuid.uuid4()), pid_kept, pid_dup, "title_fuzzy"),
    )
    out = tmp_path / "papers.csv"
    export_papers_csv(out)

    with out.open() as f:
        rows = {r["id"]: r for r in csv.DictReader(f)}
    assert rows[pid_dup]["is_duplicate"] == "yes"
    assert rows[pid_kept]["is_duplicate"] == "no"


def test_export_papers_csv_empty(tmp_path):
    out = tmp_path / "papers.csv"
    export_papers_csv(out)
    assert not out.exists()


def test_export_papers_csv_no_screening(tmp_path):
    _insert("10.1/d", "Unscreened Paper")
    out = tmp_path / "papers.csv"
    export_papers_csv(out)

    with out.open() as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["screening_decision"] == ""


# ---------------------------------------------------------------------------
# citation_graph.graphml
# ---------------------------------------------------------------------------

def test_export_graphml_nodes(tmp_path):
    _insert("10.1/e", "Paper E")
    _insert("10.1/f", "Paper F")
    out = tmp_path / "graph.graphml"
    export_graphml(out)

    assert out.exists()
    tree = ET.parse(out)
    root = tree.getroot()
    ns = {"g": "http://graphml.graphdrawing.org/graphml"}
    nodes = root.findall(".//g:node", ns)
    assert len(nodes) == 2


def test_export_graphml_edges(tmp_path):
    pid1 = _insert("10.1/g", "Seed Paper")
    pid2 = _insert("10.1/h", "Cited Paper")
    _add_citation_edge(pid1, pid2, "backward_citation")

    out = tmp_path / "graph.graphml"
    export_graphml(out)

    tree = ET.parse(out)
    root = tree.getroot()
    ns = {"g": "http://graphml.graphdrawing.org/graphml"}
    edges = root.findall(".//g:edge", ns)
    assert len(edges) == 1
    assert edges[0].get("source") == pid1
    assert edges[0].get("target") == pid2


def test_export_graphml_empty(tmp_path):
    out = tmp_path / "graph.graphml"
    export_graphml(out)
    assert not out.exists()


# ---------------------------------------------------------------------------
# _extract_source helper
# ---------------------------------------------------------------------------

def test_extract_source_simple():
    path = "seed:P001 → backward_citation → P031"
    assert _extract_source(path, "backward_citation") == "P001"


def test_extract_source_two_hops():
    path = "seed:P001 → backward_citation → P031 → forward_citation → P042"
    assert _extract_source(path, "forward_citation") == "P031"


def test_extract_source_invalid():
    assert _extract_source("only_one_part", "backward_citation") is None


# ---------------------------------------------------------------------------
# GET /api/export endpoint – output_dir validation
# ---------------------------------------------------------------------------

def test_export_list_default(tmp_path, monkeypatch):
    """GET /api/export with no output_dir uses the configured default."""
    from fastapi.testclient import TestClient
    from reviewtrace.api.app import app

    monkeypatch.setenv("REVIEWTRACE_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.get("/api/export")
    assert response.status_code == 200
    kinds = {item["kind"] for item in response.json()}
    assert "papers" in kinds


def test_export_list_valid_subdir(tmp_path, monkeypatch):
    """GET /api/export?output_dir=<subdir> works for a path inside the root."""
    from fastapi.testclient import TestClient
    from reviewtrace.api.app import app

    monkeypatch.setenv("REVIEWTRACE_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    subdir = tmp_path / "my_run"
    subdir.mkdir()
    (subdir / "papers.csv").write_text("id,title\n")

    with TestClient(app) as client:
        response = client.get(f"/api/export?output_dir={subdir}")
    assert response.status_code == 200
    papers = next(item for item in response.json() if item["kind"] == "papers")
    assert papers["available"] is True


def test_export_list_rejects_path_outside_root(tmp_path, monkeypatch):
    """GET /api/export?output_dir=<outside root> returns 403."""
    from fastapi.testclient import TestClient
    from reviewtrace.api.app import app

    root = tmp_path / "outputs"
    root.mkdir()
    monkeypatch.setenv("REVIEWTRACE_OUTPUT_DIR", str(root))
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    outside = tmp_path / "secret"
    outside.mkdir()

    with TestClient(app) as client:
        response = client.get(f"/api/export?output_dir={outside}")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/export/manifest endpoint
# ---------------------------------------------------------------------------

def test_export_manifest_returns_manifest(tmp_path, monkeypatch):
    """GET /api/export/manifest returns the run_manifest.json content."""
    import json
    from fastapi.testclient import TestClient
    from reviewtrace.api.app import app

    root = tmp_path / "outputs"
    root.mkdir()
    monkeypatch.setenv("REVIEWTRACE_OUTPUT_DIR", str(root))
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    data = {"run_id": "abc", "topic": "T", "status": "completed", "stats": {"included": 5}}
    (root / "run_manifest.json").write_text(json.dumps(data))

    with TestClient(app) as client:
        response = client.get("/api/export/manifest")
    assert response.status_code == 200
    assert response.json()["run_id"] == "abc"


def test_export_manifest_subdir(tmp_path, monkeypatch):
    """GET /api/export/manifest?output_dir=<subdir> reads from the subdir."""
    import json
    from fastapi.testclient import TestClient
    from reviewtrace.api.app import app

    root = tmp_path / "outputs"
    root.mkdir()
    subdir = root / "run_a"
    subdir.mkdir()
    monkeypatch.setenv("REVIEWTRACE_OUTPUT_DIR", str(root))
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    data = {"run_id": "run_a", "topic": "SAE", "status": "completed", "stats": {}}
    (subdir / "run_manifest.json").write_text(json.dumps(data))

    with TestClient(app) as client:
        response = client.get(f"/api/export/manifest?output_dir={subdir}")
    assert response.status_code == 200
    assert response.json()["run_id"] == "run_a"


def test_export_manifest_missing_returns_404(tmp_path, monkeypatch):
    """GET /api/export/manifest returns 404 when run_manifest.json does not exist."""
    from fastapi.testclient import TestClient
    from reviewtrace.api.app import app

    root = tmp_path / "outputs"
    root.mkdir()
    monkeypatch.setenv("REVIEWTRACE_OUTPUT_DIR", str(root))
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.get("/api/export/manifest")
    assert response.status_code == 404


def test_export_manifest_rejects_path_outside_root(tmp_path, monkeypatch):
    """GET /api/export/manifest?output_dir=<outside root> returns 403."""
    from fastapi.testclient import TestClient
    from reviewtrace.api.app import app

    root = tmp_path / "outputs"
    root.mkdir()
    outside = tmp_path / "secret"
    outside.mkdir()
    monkeypatch.setenv("REVIEWTRACE_OUTPUT_DIR", str(root))
    monkeypatch.setenv("REVIEWTRACE_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.get(f"/api/export/manifest?output_dir={outside}")
    assert response.status_code == 403
