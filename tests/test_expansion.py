"""Tests for citation graph expansion — path tracking and BFS controller."""

import asyncio
import uuid

import pytest

from reviewtrace.db.connection import fetchall, init_db, insert_paper
from reviewtrace.expansion.controller import expand
from reviewtrace.expansion.path_tracker import build_path, log_expanded_paper, seed_path
from reviewtrace.retrieval.models import PaperMetadata


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    init_db(tmp_path / "test.db")
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_paper(doi: str, title: str = "Test", s2_id: str | None = None) -> PaperMetadata:
    p = PaperMetadata(title=title, authors=["Smith A"], doi=doi, raw_source="semantic_scholar", raw_id=s2_id)
    d = p.to_db_dict()
    if s2_id:
        d["s2_paper_id"] = s2_id
    insert_paper(d)
    return p


# ---------------------------------------------------------------------------
# Path tracker
# ---------------------------------------------------------------------------

def test_seed_path():
    assert seed_path("abc123") == "seed:abc123"


def test_build_path_one_hop():
    path = build_path("seed:P001", "backward_citation", "P031")
    assert path == "seed:P001 → backward_citation → P031"


def test_build_path_two_hops():
    path = build_path("seed:P001 → backward_citation → P031", "forward_citation", "P042")
    assert path == "seed:P001 → backward_citation → P031 → forward_citation → P042"


def test_log_expanded_paper_written():
    paper = _make_paper(doi="10.1234/exp", title="Expanded Paper")
    run_id = str(uuid.uuid4())
    path = build_path(seed_path("seed_abc"), "backward_citation", paper.id)

    # Insert a dummy retrieval run so the FK holds
    from reviewtrace.db.connection import execute
    execute(
        "INSERT INTO retrieval_runs (id, query, source, expansion_type, status) VALUES (?, ?, ?, ?, ?)",
        (run_id, "expand:depth=0:paper=seed_abc", "semantic_scholar", "citation_expansion", "pending"),
    )

    log_expanded_paper(paper, run_id, "backward_citation", path)

    rows = fetchall("SELECT * FROM paper_retrievals WHERE paper_id = ?", (paper.id,))
    assert len(rows) == 1
    assert rows[0]["citation_path"] == path
    assert rows[0]["retrieval_reason"] == "backward_citation"


def test_log_expanded_paper_idempotent():
    paper = _make_paper(doi="10.1234/idem", title="Idempotent Paper")
    run_id = str(uuid.uuid4())
    path = build_path(seed_path("s1"), "forward_citation", paper.id)

    from reviewtrace.db.connection import execute
    execute(
        "INSERT INTO retrieval_runs (id, query, source, expansion_type, status) VALUES (?, ?, ?, ?, ?)",
        (run_id, "expand:depth=0:paper=s1", "semantic_scholar", "citation_expansion", "pending"),
    )

    log_expanded_paper(paper, run_id, "forward_citation", path)
    log_expanded_paper(paper, run_id, "forward_citation", path)

    rows = fetchall("SELECT * FROM paper_retrievals WHERE paper_id = ?", (paper.id,))
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# BFS controller (mocked S2 API calls)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_s2(monkeypatch):
    """Stub out S2 reference/citation API calls to avoid network."""

    async def fake_references(paper_id, limit=30):
        if "seed" in paper_id or "DOI:10.0000" in paper_id:
            return [
                PaperMetadata(title="Ref Paper 1", authors=["A B"], doi="10.1111/ref1",
                              raw_source="semantic_scholar", raw_id="s2ref1"),
                PaperMetadata(title="Ref Paper 2", authors=["C D"], doi="10.1111/ref2",
                              raw_source="semantic_scholar", raw_id="s2ref2"),
            ]
        return []

    async def fake_citations(paper_id, limit=30):
        if "seed" in paper_id or "DOI:10.0000" in paper_id:
            return [
                PaperMetadata(title="Citing Paper 1", authors=["E F"], doi="10.2222/cit1",
                              raw_source="semantic_scholar", raw_id="s2cit1"),
            ]
        return []

    monkeypatch.setattr(
        "reviewtrace.retrieval.clients.semantic_scholar.get_references", fake_references
    )
    monkeypatch.setattr(
        "reviewtrace.retrieval.clients.semantic_scholar.get_citations", fake_citations
    )


def test_expand_depth1(mock_s2):
    seed = _make_paper(doi="10.0000/seed", title="Seed Paper", s2_id="s2seed")

    result = asyncio.run(expand([seed.id], max_depth=1, max_papers_per_hop=10))

    assert result.seeds_count == 1
    assert result.new_papers_count == 3  # 2 refs + 1 citation
    assert result.total_hops == 1

    # All new papers in DB
    all_papers = fetchall("SELECT * FROM papers")
    assert len(all_papers) == 4  # seed + 3 new


def test_expand_citation_paths_recorded(mock_s2):
    seed = _make_paper(doi="10.0000/seed", title="Seed Paper", s2_id="s2seed")

    asyncio.run(expand([seed.id], max_depth=1, max_papers_per_hop=10))

    # Each new paper has a citation path containing the seed ID
    new_retrievals = fetchall(
        "SELECT * FROM paper_retrievals WHERE citation_path IS NOT NULL"
    )
    assert len(new_retrievals) == 3
    for r in new_retrievals:
        assert seed.id in r["citation_path"]
        assert "→" in r["citation_path"]


def test_expand_no_revisit(mock_s2):
    """BFS should not expand the same paper twice."""
    seed = _make_paper(doi="10.0000/seed", title="Seed Paper", s2_id="s2seed")

    result = asyncio.run(expand([seed.id], max_depth=2, max_papers_per_hop=10))

    # depth=2: seed expanded → finds 3 papers; those are expanded but fake_* returns
    # nothing for non-seed IDs, so total stays 3 new papers
    assert result.new_papers_count == 3
    all_papers = fetchall("SELECT * FROM papers")
    assert len(all_papers) == 4


def test_expand_empty_seeds():
    result = asyncio.run(expand([], max_depth=2))
    assert result.new_papers_count == 0
    assert result.total_hops == 0
