"""Tests for source policy, classifier, and screening engine."""

import csv
import json

import pytest

from reviewtrace.db.connection import fetchall, init_db, insert_paper
from reviewtrace.retrieval.models import PaperMetadata
from reviewtrace.screening.classifier import classify_source
from reviewtrace.screening.models import ScreeningCriteria
from reviewtrace.screening.policy import SourcePolicy, load_policy
from reviewtrace.screening.screener import export_csv, import_csv_overrides, run_screening


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    init_db(tmp_path / "test.db")
    yield


def _insert(doi=None, arxiv_id=None, title="Test", venue=None, year=2024) -> str:
    p = PaperMetadata(title=title, authors=["A B"], doi=doi, arxiv_id=arxiv_id, venue=venue, year=year)
    insert_paper(p.to_db_dict())
    return p.id


# ---------------------------------------------------------------------------
# Source Policy
# ---------------------------------------------------------------------------

def test_policy_defaults():
    policy = SourcePolicy()
    assert policy.verdict("peer_reviewed") == "allow"
    assert policy.verdict("preprint") == "allow"
    assert policy.verdict("workshop") == "flag"
    assert policy.verdict("unknown") == "flag"
    assert policy.verdict("blog") == "block"


def test_policy_is_blocked():
    policy = SourcePolicy(block=["blog", "grey_literature"])
    assert policy.is_blocked("blog")
    assert not policy.is_blocked("peer_reviewed")


def test_load_default_policy():
    policy = load_policy()
    assert "peer_reviewed" in policy.allow
    assert "blog" in policy.block


def test_load_custom_policy(tmp_path):
    custom = tmp_path / "policy.json"
    custom.write_text(json.dumps({"allow": ["peer_reviewed"], "flag": [], "block": ["preprint"]}))
    policy = load_policy(custom)
    assert policy.is_blocked("preprint")
    assert not policy.is_blocked("peer_reviewed")


# ---------------------------------------------------------------------------
# Source Type Classifier
# ---------------------------------------------------------------------------

def test_classify_arxiv_only():
    paper = {"arxiv_id": "2301.00001", "doi": None, "venue": None}
    assert classify_source(paper) == "preprint"


def test_classify_arxiv_with_doi():
    # arXiv + DOI → published, classify by venue/DOI
    paper = {"arxiv_id": "2301.00001", "doi": "10.1234/x", "venue": None}
    assert classify_source(paper) == "peer_reviewed"


def test_classify_known_venue():
    paper = {"arxiv_id": None, "doi": None, "venue": "NeurIPS 2023"}
    assert classify_source(paper) == "peer_reviewed"


def test_classify_icml():
    paper = {"arxiv_id": None, "doi": "10.x/y", "venue": "ICML"}
    assert classify_source(paper) == "peer_reviewed"


def test_classify_workshop():
    paper = {"arxiv_id": None, "doi": None, "venue": "ICML Workshop on Interpretability"}
    assert classify_source(paper) == "workshop"


def test_classify_doi_fallback():
    paper = {"arxiv_id": None, "doi": "10.9999/unknown", "venue": None}
    assert classify_source(paper) == "peer_reviewed"


def test_classify_unknown():
    paper = {"arxiv_id": None, "doi": None, "venue": None}
    assert classify_source(paper) == "unknown"


# ---------------------------------------------------------------------------
# Screening Engine (mocked LLM)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_include(monkeypatch):
    monkeypatch.setattr(
        "reviewtrace.screening.screener.complete",
        lambda prompt, max_tokens=256: json.dumps({
            "decision": "include",
            "reason": "Directly relevant to topic.",
            "confidence": 0.95,
        }),
    )


@pytest.fixture
def mock_llm_exclude(monkeypatch):
    monkeypatch.setattr(
        "reviewtrace.screening.screener.complete",
        lambda prompt, max_tokens=256: json.dumps({
            "decision": "exclude",
            "reason": "Not relevant to topic.",
            "confidence": 0.88,
        }),
    )


_CRITERIA = ScreeningCriteria(
    topic="Sparse autoencoders for mechanistic interpretability",
    inclusion=["Uses sparse autoencoders", "Studies neural network internals"],
    exclusion=["Not about neural networks", "Survey or meta-analysis only"],
)


def test_screening_include(mock_llm_include):
    _insert(doi="10.1/a", title="Sparse AE Paper", venue="NeurIPS")
    decisions = run_screening(_CRITERIA, delay_seconds=0)
    assert len(decisions) == 1
    assert decisions[0].decision == "include"
    assert decisions[0].confidence == 0.95
    assert decisions[0].screened_by == "llm"


def test_screening_exclude(mock_llm_exclude):
    _insert(doi="10.1/b", title="Unrelated Paper", venue="NeurIPS")
    decisions = run_screening(_CRITERIA, delay_seconds=0)
    assert decisions[0].decision == "exclude"


def test_screening_blocked_by_policy(mock_llm_include):
    _insert(doi=None, arxiv_id=None, title="Blog Post", venue="medium")
    policy = SourcePolicy(block=["blog"])
    decisions = run_screening(_CRITERIA, policy=policy, delay_seconds=0)
    assert decisions[0].decision == "exclude"
    assert decisions[0].screened_by == "policy"


def test_screening_skips_already_screened(mock_llm_include):
    _insert(doi="10.1/c", title="Paper C", venue="ICML")
    run_screening(_CRITERIA, delay_seconds=0)
    # Run again — should skip already-screened paper
    decisions = run_screening(_CRITERIA, delay_seconds=0)
    assert decisions == []


def test_screening_written_to_db(mock_llm_include):
    _insert(doi="10.1/d", title="Paper D")
    run_screening(_CRITERIA, delay_seconds=0)
    rows = fetchall("SELECT * FROM screening_decisions")
    assert len(rows) == 1
    assert rows[0]["decision"] == "include"


def test_screening_updates_paper_source_type(mock_llm_include):
    _insert(doi="10.1/e", title="Paper E", venue="NeurIPS")
    run_screening(_CRITERIA, delay_seconds=0)
    papers = fetchall("SELECT source_type FROM papers WHERE doi = '10.1/e'")
    assert papers[0]["source_type"] == "peer_reviewed"


# ---------------------------------------------------------------------------
# CSV export / import (human override)
# ---------------------------------------------------------------------------

def test_export_csv(mock_llm_include, tmp_path):
    _insert(doi="10.1/f", title="CSV Paper", venue="ICLR")
    run_screening(_CRITERIA, delay_seconds=0)

    out = tmp_path / "screening.csv"
    export_csv(out)
    assert out.exists()

    with out.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["decision"] == "include"


def test_import_csv_override(mock_llm_include, tmp_path):
    _insert(doi="10.1/g", title="Override Paper", venue="ICML")
    run_screening(_CRITERIA, delay_seconds=0)

    # Export, manually change decision, re-import
    out = tmp_path / "screening.csv"
    export_csv(out)

    with out.open() as f:
        rows = list(csv.DictReader(f))
    rows[0]["decision"] = "exclude"

    override = tmp_path / "overrides.csv"
    with override.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    count = import_csv_overrides(override)
    assert count == 1

    updated = fetchall("SELECT decision, screened_by FROM screening_decisions")
    assert updated[0]["decision"] == "exclude"
    assert updated[0]["screened_by"] == "human"
