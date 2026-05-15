"""Tests for taxonomy: embedding, clustering, labeling, linking, export."""

import json
import uuid

import numpy as np
import pytest

from reviewtrace.db.connection import execute, fetchall, init_db, insert_paper
from reviewtrace.retrieval.models import PaperMetadata
from reviewtrace.taxonomy.clusterer import _choose_k, cluster_papers
from reviewtrace.taxonomy.controller import run_taxonomy
from reviewtrace.taxonomy.embedder import cosine_similarity_matrix, top_k_indices
from reviewtrace.taxonomy.exporter import export_taxonomy_md
from reviewtrace.taxonomy.labeler import generate_labels
from reviewtrace.taxonomy.linker import link_all
from reviewtrace.taxonomy.models import TaxonomyNode


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
        "INSERT INTO screening_decisions (id, paper_id, decision, reason, confidence, screened_by) VALUES (?, ?, 'include', 'r', 0.9, 'llm')",
        (str(uuid.uuid4()), paper_id),
    )


def _insert_evidence(paper_id: str, etype: str = "method_proposal", content: str = "We propose X.") -> str:
    eid = str(uuid.uuid4())
    execute(
        "INSERT INTO evidence_items (id, paper_id, evidence_type, content, location) VALUES (?, ?, ?, ?, 'abstract')",
        (eid, paper_id, etype, content),
    )
    return eid


def _fake_embed(monkeypatch, dim: int = 16):
    """Replace embed_texts with a deterministic stub that returns random unit vectors."""
    rng = np.random.default_rng(42)

    def _stub(texts):
        vecs = rng.standard_normal((len(texts), dim)).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / norms

    monkeypatch.setattr("reviewtrace.taxonomy.embedder._get_model", lambda: None)
    monkeypatch.setattr("reviewtrace.taxonomy.embedder.embed_texts", _stub)
    monkeypatch.setattr("reviewtrace.taxonomy.linker.embed_texts", _stub)
    monkeypatch.setattr("reviewtrace.taxonomy.controller.embed_texts", _stub)


def _fake_llm_label(monkeypatch):
    monkeypatch.setattr(
        "reviewtrace.taxonomy.labeler.complete",
        lambda p, max_tokens=256: json.dumps({
            "label": "Sparse Autoencoders",
            "description": "Research on SAEs for mechanistic interpretability.",
        }),
    )


def _fake_llm_confirm_yes(monkeypatch):
    monkeypatch.setattr(
        "reviewtrace.taxonomy.linker.complete",
        lambda p, max_tokens=128: json.dumps({"relevant": True, "reason": "Directly related."}),
    )


def _fake_llm_confirm_no(monkeypatch):
    monkeypatch.setattr(
        "reviewtrace.taxonomy.linker.complete",
        lambda p, max_tokens=128: json.dumps({"relevant": False, "reason": "Not related."}),
    )


# ---------------------------------------------------------------------------
# Embedder utilities
# ---------------------------------------------------------------------------

def test_cosine_similarity_normalized():
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]], dtype=np.float32)
    sims = cosine_similarity_matrix(a, b)
    assert abs(sims[0] - 1.0) < 1e-5
    assert abs(sims[1] - 0.0) < 1e-5
    assert abs(sims[2] - (-1.0)) < 1e-5


def test_top_k_indices_order():
    query = np.array([1.0, 0.0], dtype=np.float32)
    corpus = np.array([
        [0.9, 0.1],   # most similar
        [0.0, 1.0],   # least similar
        [0.8, 0.2],   # second
    ], dtype=np.float32)
    # Normalize
    corpus = corpus / np.linalg.norm(corpus, axis=1, keepdims=True)
    idxs = top_k_indices(query, corpus, k=2)
    assert idxs[0] == 0   # most similar first
    assert idxs[1] == 2


def test_top_k_empty_corpus():
    q = np.array([1.0, 0.0], dtype=np.float32)
    assert top_k_indices(q, np.empty((0, 2), dtype=np.float32), k=5) == []


# ---------------------------------------------------------------------------
# Clusterer
# ---------------------------------------------------------------------------

def test_choose_k():
    assert _choose_k(10) == 5   # max(5, 10//8) = max(5,1) = 5
    assert _choose_k(40) == 5   # max(5, 40//8) = max(5,5) = 5
    assert _choose_k(80) == 10  # max(5, 80//8) = max(5,10) = 10
    assert _choose_k(4) == 5


def test_cluster_papers_returns_assignments():
    embs = np.random.default_rng(0).standard_normal((12, 16)).astype(np.float32)
    assignments = cluster_papers(embs, n_papers=12)
    assert len(assignments) == 12
    assert all(isinstance(a, int) for a in assignments)


def test_cluster_papers_k_capped_by_n():
    # Only 3 papers, k would be 5 → capped to 3
    embs = np.random.default_rng(0).standard_normal((3, 16)).astype(np.float32)
    assignments = cluster_papers(embs, n_papers=3)
    assert len(assignments) == 3
    assert max(assignments) <= 2  # cluster IDs 0, 1, 2


def test_cluster_papers_empty():
    assert cluster_papers(np.empty((0, 16), dtype=np.float32)) == []


# ---------------------------------------------------------------------------
# Labeler
# ---------------------------------------------------------------------------

def test_generate_labels_creates_nodes(monkeypatch):
    _fake_llm_label(monkeypatch)
    _insert_paper("10.1/a", "SAE Paper")
    papers = fetchall("SELECT * FROM papers")
    assignments = [0] * len(papers)

    nodes = generate_labels(assignments, papers)
    assert len(nodes) == 1
    assert nodes[0].label == "Sparse Autoencoders"
    assert nodes[0].cluster_id == 0


def test_generate_labels_saved_to_db(monkeypatch):
    _fake_llm_label(monkeypatch)
    _insert_paper("10.1/b", "Paper B")
    papers = fetchall("SELECT * FROM papers")
    generate_labels([0] * len(papers), papers)

    rows = fetchall("SELECT * FROM taxonomy_nodes")
    assert len(rows) == 1
    assert rows[0]["label"] == "Sparse Autoencoders"


def test_generate_labels_multiple_clusters(monkeypatch):
    _fake_llm_label(monkeypatch)
    for i in range(4):
        _insert_paper(f"10.1/{i}", f"Paper {i}")
    papers = fetchall("SELECT * FROM papers")
    assignments = [0, 0, 1, 1]

    nodes = generate_labels(assignments, papers)
    assert len(nodes) == 2
    cluster_ids = {n.cluster_id for n in nodes}
    assert cluster_ids == {0, 1}


def _fake_llm_label_with_relabel(monkeypatch):
    """Returns the same generic label on the first call, a specific label on the relabel call."""
    def _stub(prompt, max_tokens=256):
        if "already been assigned" in prompt:
            return json.dumps({
                "label": "Specific SAE Feature Decomposition",
                "description": "More specific cluster about feature decomposition.",
            })
        return json.dumps({
            "label": "Sparse Autoencoders",
            "description": "Research on SAEs for mechanistic interpretability.",
        })
    monkeypatch.setattr("reviewtrace.taxonomy.labeler.complete", _stub)


def test_generate_labels_deduplicates_duplicate_labels(monkeypatch):
    """When LLM returns the same label for two clusters, the later node is relabeled."""
    _fake_llm_label_with_relabel(monkeypatch)
    for i in range(4):
        _insert_paper(f"10.1/dup{i}", f"Paper {i}", abstract=f"Abstract {i}.")
    papers = fetchall("SELECT * FROM papers")
    assignments = [0, 0, 1, 1]  # two clusters, LLM returns same label for both

    nodes = generate_labels(assignments, papers)
    assert len(nodes) == 2

    labels = [n.label for n in nodes]
    assert labels[0] != labels[1], "Duplicate labels must be resolved"

    # DB rows should also have distinct labels
    rows = fetchall("SELECT label FROM taxonomy_nodes ORDER BY cluster_id")
    assert rows[0]["label"] != rows[1]["label"]


def test_generate_labels_no_dedup_when_labels_differ(monkeypatch):
    """When LLM returns distinct labels, no relabeling should occur."""
    call_count = {"n": 0}
    def _stub(prompt, max_tokens=256):
        call_count["n"] += 1
        label = "Cluster Alpha" if call_count["n"] == 1 else "Cluster Beta"
        return json.dumps({"label": label, "description": "Description."})
    monkeypatch.setattr("reviewtrace.taxonomy.labeler.complete", _stub)

    for i in range(4):
        _insert_paper(f"10.1/nd{i}", f"Paper {i}", abstract=f"Abstract {i}.")
    papers = fetchall("SELECT * FROM papers")
    assignments = [0, 0, 1, 1]

    nodes = generate_labels(assignments, papers)
    assert nodes[0].label == "Cluster Alpha"
    assert nodes[1].label == "Cluster Beta"
    # LLM called exactly twice (one per cluster, no relabeling)
    assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# Linker
# ---------------------------------------------------------------------------

def test_link_all_saves_confirmed(monkeypatch):
    _fake_embed(monkeypatch)
    _fake_llm_confirm_yes(monkeypatch)

    pid = _insert_paper("10.1/c", "Paper C")
    _insert_evidence(pid, "method_proposal", "We propose SAEs.")
    node = TaxonomyNode(id=str(uuid.uuid4()), label="SAE Methods",
                        description="Sparse autoencoder methods.", cluster_id=0)
    execute(
        "INSERT INTO taxonomy_nodes (id, label, description, cluster_id) VALUES (?, ?, ?, ?)",
        (node.id, node.label, node.description, node.cluster_id),
    )

    links = link_all([node], top_k=3)
    assert node.id in links
    assert len(links[node.id]) >= 1
    rows = fetchall("SELECT * FROM taxonomy_evidence WHERE taxonomy_node_id = ?", (node.id,))
    assert len(rows) >= 1


def test_link_all_skips_unconfirmed(monkeypatch):
    _fake_embed(monkeypatch)
    _fake_llm_confirm_no(monkeypatch)

    pid = _insert_paper("10.1/d", "Paper D")
    _insert_evidence(pid, "limitation", "Limited scope.")
    node = TaxonomyNode(id=str(uuid.uuid4()), label="SAE Methods",
                        description="Sparse autoencoder methods.", cluster_id=0)
    execute(
        "INSERT INTO taxonomy_nodes (id, label, description, cluster_id) VALUES (?, ?, ?, ?)",
        (node.id, node.label, node.description, node.cluster_id),
    )

    links = link_all([node], top_k=3)
    assert links[node.id] == []
    rows = fetchall("SELECT * FROM taxonomy_evidence")
    assert len(rows) == 0


def test_link_all_empty_evidence(monkeypatch):
    _fake_embed(monkeypatch)
    node = TaxonomyNode(id=str(uuid.uuid4()), label="L", description="D.", cluster_id=0)
    links = link_all([node])
    assert links == {}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def test_export_taxonomy_md(monkeypatch, tmp_path):
    _fake_embed(monkeypatch)
    _fake_llm_confirm_yes(monkeypatch)

    pid = _insert_paper("10.1/e", "Export Paper", abstract="We propose SAEs.")
    eid = _insert_evidence(pid, "method_proposal", "We propose SAEs for interpretability.")
    node_id = str(uuid.uuid4())
    execute(
        "INSERT INTO taxonomy_nodes (id, label, description, cluster_id) VALUES (?, ?, ?, ?)",
        (node_id, "SAE Methods", "Methods using sparse autoencoders.", 0),
    )
    execute(
        "INSERT INTO taxonomy_evidence (id, taxonomy_node_id, evidence_item_id, paper_id, relevance_score) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), node_id, eid, pid, 0.95),
    )

    out = tmp_path / "taxonomy.md"
    export_taxonomy_md(out)

    content = out.read_text()
    assert "SAE Methods" in content
    assert "Export Paper" in content
    assert "We propose SAEs" in content
    assert "method_proposal" in content


def test_export_taxonomy_md_no_nodes(tmp_path):
    out = tmp_path / "taxonomy.md"
    export_taxonomy_md(out)
    assert not out.exists()


# ---------------------------------------------------------------------------
# Full pipeline (controller)
# ---------------------------------------------------------------------------

def test_run_taxonomy_full(monkeypatch):
    _fake_embed(monkeypatch)
    _fake_llm_label(monkeypatch)
    _fake_llm_confirm_yes(monkeypatch)

    for i in range(6):
        pid = _insert_paper(f"10.1/{i}", f"Paper {i}", abstract=f"Abstract {i}.")
        _mark_included(pid)
        _insert_evidence(pid, "method_proposal", f"Method {i}.")

    result = run_taxonomy()
    assert result.n_papers == 6
    assert result.n_nodes >= 1
    assert result.n_evidence_links >= 0


def test_run_taxonomy_no_papers(monkeypatch):
    _fake_embed(monkeypatch)
    result = run_taxonomy()
    assert result.n_papers == 0
    assert result.n_nodes == 0
