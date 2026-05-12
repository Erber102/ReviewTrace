"""Tests for DB schema and connection helpers."""

import hashlib
import json

import pytest

from reviewtrace.db.connection import (
    execute,
    fetchall,
    get_paper_by_doi,
    get_paper_by_id,
    get_retrieval_path,
    init_db,
    insert_paper,
)


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    """Each test gets its own fresh SQLite file."""
    init_db(tmp_path / "test.db")
    yield


def _paper_id(doi: str) -> str:
    return hashlib.sha256(doi.encode()).hexdigest()[:16]


def _make_paper(doi: str = "10.1234/test", title: str = "Test Paper") -> dict:
    return {
        "id": _paper_id(doi),
        "doi": doi,
        "arxiv_id": None,
        "title": title,
        "authors": json.dumps(["Alice", "Bob"]),
        "year": 2024,
        "venue": "NeurIPS",
        "abstract": "This is a test abstract.",
        "source_type": "peer_reviewed",
        "url": None,
        "citation_count": 10,
        "reference_count": 30,
    }


def test_schema_tables_exist():
    tables = {r["name"] for r in fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {
        "papers", "retrieval_runs", "paper_retrievals", "dedup_decisions",
        "screening_decisions", "evidence_items", "taxonomy_nodes",
        "taxonomy_evidence", "generated_claims", "claim_verifications",
    }
    assert expected.issubset(tables)


def test_insert_and_get_paper():
    paper = _make_paper()
    insert_paper(paper)
    result = get_paper_by_id(paper["id"])
    assert result is not None
    assert result["title"] == "Test Paper"
    assert result["doi"] == "10.1234/test"


def test_get_paper_by_doi():
    paper = _make_paper(doi="10.9999/unique")
    insert_paper(paper)
    result = get_paper_by_doi("10.9999/unique")
    assert result is not None
    assert result["id"] == paper["id"]


def test_insert_paper_ignore_duplicate():
    paper = _make_paper()
    insert_paper(paper)
    insert_paper(paper)  # should not raise
    rows = fetchall("SELECT * FROM papers WHERE doi = ?", (paper["doi"],))
    assert len(rows) == 1


def test_get_retrieval_path_empty():
    paper = _make_paper()
    insert_paper(paper)
    path = get_retrieval_path(paper["id"])
    assert path == []


def test_retrieval_path_recorded():
    import uuid
    paper = _make_paper()
    insert_paper(paper)

    run_id = str(uuid.uuid4())
    execute(
        "INSERT INTO retrieval_runs (id, query, source, expansion_type, status) VALUES (?, ?, ?, ?, ?)",
        (run_id, "sparse autoencoder", "semantic_scholar", "keyword", "done"),
    )

    pr_id = str(uuid.uuid4())
    execute(
        "INSERT INTO paper_retrievals (id, paper_id, retrieval_run_id, retrieval_reason, citation_path) VALUES (?, ?, ?, ?, ?)",
        (pr_id, paper["id"], run_id, "keyword_match", None),
    )

    path = get_retrieval_path(paper["id"])
    assert len(path) == 1
    assert path[0]["retrieval_reason"] == "keyword_match"
    assert path[0]["source"] == "semantic_scholar"


def test_migrations_table_exists():
    tables = {r["name"] for r in fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "_migrations" in tables
