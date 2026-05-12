"""Tests for audit logger, deduplication, and export."""

import json
import uuid

import pytest

from reviewtrace.audit import logger as audit
from reviewtrace.audit.dedup import get_canonical_paper_ids, run_dedup
from reviewtrace.audit.export import export_json, export_markdown
from reviewtrace.db.connection import fetchall, init_db
from reviewtrace.retrieval.models import PaperMetadata, SearchQuery


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    init_db(tmp_path / "test.db")
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_paper(doi=None, arxiv_id=None, title="Test Paper", year=2024) -> PaperMetadata:
    from reviewtrace.db.connection import insert_paper

    paper = PaperMetadata(
        title=title,
        authors=["Smith A"],
        year=year,
        doi=doi,
        arxiv_id=arxiv_id,
    )
    insert_paper(paper.to_db_dict())
    return paper


def _make_query(source="openalex", expansion_type="keyword") -> SearchQuery:
    return SearchQuery(query="sparse autoencoder", source=source, expansion_type=expansion_type)


# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------

def test_log_run_start_and_done():
    run_id = str(uuid.uuid4())
    q = _make_query()
    audit.log_run_start(run_id, q)

    runs = fetchall("SELECT * FROM retrieval_runs WHERE id = ?", (run_id,))
    assert len(runs) == 1
    assert runs[0]["status"] == "pending"
    assert runs[0]["query"] == "sparse autoencoder"

    audit.log_run_done(run_id, 42, "done")
    runs = fetchall("SELECT * FROM retrieval_runs WHERE id = ?", (run_id,))
    assert runs[0]["status"] == "done"
    assert runs[0]["result_count"] == 42


def test_log_paper_found():
    paper = _insert_paper(doi="10.1234/test")
    run_id = str(uuid.uuid4())
    q = _make_query()
    audit.log_run_start(run_id, q)
    audit.log_paper_found(paper, run_id, q)

    trail = audit.get_paper_audit(paper.id)
    assert len(trail) == 1
    assert trail[0]["retrieval_reason"] == "keyword"
    assert trail[0]["source"] == "openalex"


def test_log_paper_found_with_citation_path():
    seed = _insert_paper(doi="10.0000/seed", title="Seed Paper")
    paper = _insert_paper(doi="10.1234/cited", title="Cited Paper")

    run_id = str(uuid.uuid4())
    q = SearchQuery(
        query="sparse autoencoder",
        source="semantic_scholar",
        expansion_type="backward_citation",
        metadata={"seed_paper_id": seed.id},
    )
    audit.log_run_start(run_id, q)
    audit.log_paper_found(paper, run_id, q)

    trail = audit.get_paper_audit(paper.id)
    assert trail[0]["citation_path"] is not None
    assert seed.id in trail[0]["citation_path"]
    assert paper.id in trail[0]["citation_path"]


def test_log_paper_found_idempotent():
    paper = _insert_paper(doi="10.1234/test")
    run_id = str(uuid.uuid4())
    q = _make_query()
    audit.log_run_start(run_id, q)
    audit.log_paper_found(paper, run_id, q)
    audit.log_paper_found(paper, run_id, q)  # duplicate insert ignored

    rows = fetchall("SELECT * FROM paper_retrievals WHERE paper_id = ?", (paper.id,))
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_dedup_doi_same_paper_prevented_at_insert():
    # Same DOI → same PaperMetadata.id → INSERT OR IGNORE keeps only one.
    # dedup.py doesn't need to handle this; it's covered by the schema.
    _insert_paper(doi="10.1111/same", title="Paper A")
    _insert_paper(doi="10.1111/same", title="Paper A duplicate")

    from reviewtrace.db.connection import fetchall as db_fetchall
    rows = db_fetchall("SELECT * FROM papers")
    assert len(rows) == 1  # second insert was silently ignored


def test_dedup_title_fuzzy_match():
    _insert_paper(title="Sparse Autoencoders for Mechanistic Interpretability")
    _insert_paper(title="Sparse Autoencoders for Mechanistic Interpretabillity")  # typo

    result = run_dedup()
    assert result.fuzzy_merges == 1
    canonical = get_canonical_paper_ids()
    assert len(canonical) == 1


def test_dedup_no_match():
    _insert_paper(title="Sparse Autoencoders")
    _insert_paper(title="Transformer Circuits")

    result = run_dedup()
    assert result.doi_merges == 0
    assert result.fuzzy_merges == 0
    assert result.total_after == 2


def test_dedup_idempotent():
    _insert_paper(title="Sparse Autoencoders for Mechanistic Interpretability")
    _insert_paper(title="Sparse Autoencoders for Mechanistic Interpretabillity")  # typo

    run_dedup()
    run_dedup()  # second run should not create extra records

    decisions = fetchall("SELECT * FROM dedup_decisions")
    assert len(decisions) == 1


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def test_export_json(tmp_path):
    paper = _insert_paper(doi="10.1234/test", title="Export Test Paper")
    run_id = str(uuid.uuid4())
    q = _make_query()
    audit.log_run_start(run_id, q)
    audit.log_paper_found(paper, run_id, q)
    audit.log_run_done(run_id, 1, "done")

    out = tmp_path / "audit.json"
    export_json(out)

    data = json.loads(out.read_text())
    assert data["total_papers"] == 1
    assert data["total_runs"] == 1
    assert data["papers"][0]["title"] == "Export Test Paper"
    assert len(data["papers"][0]["retrieval_paths"]) == 1


def test_export_markdown(tmp_path):
    paper = _insert_paper(doi="10.1234/test", title="Markdown Test Paper")
    run_id = str(uuid.uuid4())
    q = _make_query()
    audit.log_run_start(run_id, q)
    audit.log_paper_found(paper, run_id, q)
    audit.log_run_done(run_id, 1, "done")

    out = tmp_path / "audit.md"
    export_markdown(out)

    content = out.read_text()
    assert "Markdown Test Paper" in content
    assert "openalex" in content
    assert "keyword" in content
