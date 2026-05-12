"""Tests for evidence extraction and matrix export."""

import csv
import json
import uuid

import pytest

from reviewtrace.db.connection import execute, fetchall, init_db, insert_paper
from reviewtrace.evidence.extractor import extract_paper, run_extraction
from reviewtrace.evidence.matrix import export_items_json, export_matrix_csv
from reviewtrace.evidence.models import EVIDENCE_TYPES
from reviewtrace.retrieval.models import PaperMetadata


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    init_db(tmp_path / "test.db")
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_paper(doi: str, title: str, abstract: str = "Some abstract.", venue: str = "NeurIPS") -> str:
    p = PaperMetadata(title=title, authors=["A B"], doi=doi, venue=venue,
                      abstract=abstract, year=2024)
    insert_paper(p.to_db_dict())
    return p.id


def _mark_included(paper_id: str) -> None:
    execute(
        """
        INSERT INTO screening_decisions (id, paper_id, decision, reason, confidence, screened_by)
        VALUES (?, ?, 'include', 'relevant', 0.9, 'llm')
        """,
        (str(uuid.uuid4()), paper_id),
    )


def _fake_llm(items: list[dict]):
    """Return a monkeypatch-compatible complete() stub."""
    def _complete(prompt, max_tokens=1024):
        return json.dumps(items)
    return _complete


# ---------------------------------------------------------------------------
# extract_paper
# ---------------------------------------------------------------------------

def test_extract_paper_returns_items(monkeypatch):
    monkeypatch.setattr(
        "reviewtrace.evidence.extractor.complete",
        _fake_llm([
            {"evidence_type": "method_proposal", "content": "We propose SAEs."},
            {"evidence_type": "empirical_finding", "content": "Achieves 95% accuracy."},
        ]),
    )
    paper = {"id": "p1", "title": "SAE Paper", "venue": "NeurIPS",
             "year": 2024, "abstract": "We propose SAEs. Achieves 95% accuracy."}
    items = extract_paper(paper)
    assert len(items) == 2
    assert items[0].evidence_type == "method_proposal"
    assert items[1].evidence_type == "empirical_finding"
    assert all(i.location == "abstract" for i in items)
    assert all(i.paper_id == "p1" for i in items)


def test_extract_paper_skips_invalid_types(monkeypatch):
    monkeypatch.setattr(
        "reviewtrace.evidence.extractor.complete",
        _fake_llm([
            {"evidence_type": "made_up_type", "content": "Something."},
            {"evidence_type": "limitation", "content": "Limited to English."},
        ]),
    )
    paper = {"id": "p2", "title": "T", "venue": "V", "year": 2024, "abstract": "Text."}
    items = extract_paper(paper)
    assert len(items) == 1
    assert items[0].evidence_type == "limitation"


def test_extract_paper_empty_abstract():
    paper = {"id": "p3", "title": "T", "venue": "V", "year": 2024, "abstract": ""}
    items = extract_paper(paper)
    assert items == []


def test_extract_paper_llm_returns_empty(monkeypatch):
    monkeypatch.setattr("reviewtrace.evidence.extractor.complete", _fake_llm([]))
    paper = {"id": "p4", "title": "T", "venue": "V", "year": 2024, "abstract": "Abstract text."}
    items = extract_paper(paper)
    assert items == []


def test_extract_paper_handles_llm_error(monkeypatch):
    def _broken(prompt, max_tokens=1024):
        raise RuntimeError("API error")
    monkeypatch.setattr("reviewtrace.evidence.extractor.complete", _broken)
    paper = {"id": "p5", "title": "T", "venue": "V", "year": 2024, "abstract": "Text."}
    items = extract_paper(paper)
    assert items == []


def test_extract_paper_strips_markdown_fence(monkeypatch):
    monkeypatch.setattr(
        "reviewtrace.evidence.extractor.complete",
        lambda p, max_tokens=1024: '```json\n[{"evidence_type": "limitation", "content": "Limited scope."}]\n```',
    )
    paper = {"id": "p6", "title": "T", "venue": "V", "year": 2024, "abstract": "Text."}
    items = extract_paper(paper)
    assert len(items) == 1
    assert items[0].evidence_type == "limitation"


# ---------------------------------------------------------------------------
# run_extraction
# ---------------------------------------------------------------------------

def test_run_extraction_only_included(monkeypatch):
    monkeypatch.setattr(
        "reviewtrace.evidence.extractor.complete",
        _fake_llm([{"evidence_type": "method_proposal", "content": "A method."}]),
    )
    pid_inc = _insert_paper("10.1/inc", "Included Paper")
    _insert_paper("10.1/exc", "Excluded Paper")
    _mark_included(pid_inc)
    # pid_exc has no screening decision → not included

    all_items = run_extraction(delay_seconds=0)
    assert len(all_items) == 1
    assert all_items[0].paper_id == pid_inc


def test_run_extraction_saved_to_db(monkeypatch):
    monkeypatch.setattr(
        "reviewtrace.evidence.extractor.complete",
        _fake_llm([
            {"evidence_type": "comparison", "content": "Outperforms baseline by 5%."},
            {"evidence_type": "limitation", "content": "Only tested on English text."},
        ]),
    )
    pid = _insert_paper("10.1/save", "Saved Paper")
    _mark_included(pid)

    run_extraction(delay_seconds=0)

    rows = fetchall("SELECT * FROM evidence_items WHERE paper_id = ?", (pid,))
    assert len(rows) == 2
    types = {r["evidence_type"] for r in rows}
    assert types == {"comparison", "limitation"}


def test_run_extraction_skips_already_extracted(monkeypatch):
    call_count = {"n": 0}

    def _counting_llm(prompt, max_tokens=1024):
        call_count["n"] += 1
        return json.dumps([{"evidence_type": "method_proposal", "content": "A."}])

    monkeypatch.setattr("reviewtrace.evidence.extractor.complete", _counting_llm)
    pid = _insert_paper("10.1/skip", "Skip Paper")
    _mark_included(pid)

    run_extraction(delay_seconds=0)
    run_extraction(delay_seconds=0)  # second run should skip

    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# Matrix export
# ---------------------------------------------------------------------------

def _setup_evidence(tmp_path) -> str:
    """Insert paper + evidence items, return paper id."""
    pid = _insert_paper("10.1/mat", "Matrix Paper", abstract="We propose X. X outperforms Y.")
    _mark_included(pid)
    for etype in ["method_proposal", "empirical_finding", "comparison"]:
        execute(
            "INSERT INTO evidence_items (id, paper_id, evidence_type, content, location) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), pid, etype, f"Content for {etype}.", "abstract"),
        )
    return pid


def test_export_matrix_csv(tmp_path):
    _setup_evidence(tmp_path)
    out = tmp_path / "matrix.csv"
    export_matrix_csv(out)

    assert out.exists()
    with out.open() as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["method_proposal"] == "1"
    assert rows[0]["empirical_finding"] == "1"
    assert rows[0]["comparison"] == "1"
    assert rows[0]["limitation"] == "0"
    assert rows[0]["total"] == "3"


def test_export_matrix_csv_empty(tmp_path):
    out = tmp_path / "matrix.csv"
    export_matrix_csv(out)
    assert not out.exists()


def test_export_items_json(tmp_path):
    _setup_evidence(tmp_path)
    out = tmp_path / "items.json"
    export_items_json(out)

    data = json.loads(out.read_text())
    assert data["total_items"] == 3
    assert data["total_papers"] == 1
    assert data["papers"][0]["title"] == "Matrix Paper"
    assert len(data["papers"][0]["evidence"]) == 3


def test_all_evidence_types_covered():
    """Smoke test: EVIDENCE_TYPES tuple is complete and matches expected set."""
    expected = {
        "method_proposal", "empirical_finding", "theoretical_claim",
        "limitation", "comparison", "dataset_contribution",
    }
    assert set(EVIDENCE_TYPES) == expected
