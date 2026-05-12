"""Tests for metadata normalizer and author name normalization."""

from reviewtrace.retrieval.normalizer import (
    _reconstruct_openalex_abstract,
    from_arxiv,
    from_openalex,
    from_semantic_scholar,
    normalize_author,
    normalize_authors,
)

# ---------------------------------------------------------------------------
# Author normalization
# ---------------------------------------------------------------------------

def test_normalize_first_last():
    assert normalize_author("Alice Smith") == "Smith A"


def test_normalize_last_first():
    assert normalize_author("Smith, Alice") == "Smith A"


def test_normalize_initial_last():
    assert normalize_author("A. Smith") == "Smith A"


def test_normalize_last_initial():
    assert normalize_author("Smith, A.") == "Smith A"


def test_normalize_middle_name():
    assert normalize_author("Alice B. Smith") == "Smith A"


def test_normalize_single_name():
    assert normalize_author("Aristotle") == "Aristotle"


def test_normalize_empty():
    assert normalize_author("") == ""


def test_normalize_authors_mixed():
    result = normalize_authors([
        {"name": "Alice Smith"},
        {"name": "Bob, Charlie"},
        "Dave Evans",
    ])
    assert result == ["Smith A", "Bob C", "Evans D"]


# ---------------------------------------------------------------------------
# OpenAlex abstract reconstruction
# ---------------------------------------------------------------------------

def test_reconstruct_abstract():
    inverted = {"Hello": [0], "world": [1], "foo": [2]}
    assert _reconstruct_openalex_abstract(inverted) == "Hello world foo"


def test_reconstruct_abstract_empty():
    assert _reconstruct_openalex_abstract({}) == ""


def test_reconstruct_abstract_gaps():
    inverted = {"A": [0], "C": [2]}  # position 1 is empty
    result = _reconstruct_openalex_abstract(inverted)
    assert "A" in result and "C" in result


# ---------------------------------------------------------------------------
# from_openalex
# ---------------------------------------------------------------------------

_OA_RAW = {
    "id": "https://openalex.org/W1234",
    "title": "Sparse Autoencoders",
    "authorships": [
        {"author": {"display_name": "Alice Smith"}},
        {"author": {"display_name": "Bob Jones"}},
    ],
    "publication_year": 2024,
    "doi": "https://doi.org/10.1234/test",
    "primary_location": {"source": {"display_name": "NeurIPS"}},
    "abstract_inverted_index": {"A": [0], "method": [1]},
    "cited_by_count": 42,
    "referenced_works_count": 30,
    "best_oa_location": {"pdf_url": "https://example.com/paper.pdf"},
    "locations": [],
}


def test_from_openalex_basic():
    paper = from_openalex(_OA_RAW)
    assert paper.title == "Sparse Autoencoders"
    assert paper.doi == "10.1234/test"
    assert paper.year == 2024
    assert paper.venue == "NeurIPS"
    assert paper.citation_count == 42
    assert paper.authors == ["Smith A", "Jones B"]
    assert paper.abstract == "A method"
    assert paper.raw_source == "openalex"


def test_from_openalex_id_stable():
    p1 = from_openalex(_OA_RAW)
    p2 = from_openalex({**_OA_RAW, "id": "different_oa_id"})
    assert p1.id == p2.id  # ID is based on DOI, not OA id


# ---------------------------------------------------------------------------
# from_semantic_scholar
# ---------------------------------------------------------------------------

_S2_RAW = {
    "paperId": "abc123",
    "title": "Mechanistic Interpretability",
    "authors": [{"name": "Charlie Brown"}, {"name": "Dana White"}],
    "year": 2023,
    "externalIds": {"DOI": "10.5678/mech", "ArXiv": "2301.00001"},
    "venue": "ICML",
    "abstract": "We study circuits.",
    "citationCount": 100,
    "referenceCount": 50,
    "url": "https://semanticscholar.org/paper/abc123",
}


def test_from_s2_basic():
    paper = from_semantic_scholar(_S2_RAW)
    assert paper.title == "Mechanistic Interpretability"
    assert paper.doi == "10.5678/mech"
    assert paper.arxiv_id == "2301.00001"
    assert paper.authors == ["Brown C", "White D"]
    assert paper.citation_count == 100
    assert paper.raw_source == "semantic_scholar"
    assert paper.raw_id == "abc123"


# ---------------------------------------------------------------------------
# from_arxiv
# ---------------------------------------------------------------------------

_ARXIV_RAW = {
    "title": "Feature Visualization",
    "abstract": "We visualize features in neural networks.",
    "authors": ["Eve Adams", "Frank Lee"],
    "year": 2022,
    "arxiv_id": "2204.12345",
    "doi": None,
    "url": "https://arxiv.org/abs/2204.12345",
}


def test_from_arxiv_basic():
    paper = from_arxiv(_ARXIV_RAW)
    assert paper.title == "Feature Visualization"
    assert paper.arxiv_id == "2204.12345"
    assert paper.authors == ["Adams E", "Lee F"]
    assert paper.raw_source == "arxiv"
    assert paper.source_type is None  # set by screener later


def test_paper_id_prefers_doi():
    paper = from_semantic_scholar(_S2_RAW)
    # same DOI → same ID regardless of source
    oa_paper = from_openalex({**_OA_RAW, "doi": "https://doi.org/10.5678/mech"})
    assert paper.id == oa_paper.id
