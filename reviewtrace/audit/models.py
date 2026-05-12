"""Dataclasses for audit trail records."""

from dataclasses import dataclass


@dataclass
class RetrievalRun:
    id: str
    query: str
    source: str
    expansion_type: str
    timestamp: str
    result_count: int
    status: str  # pending / done / error


@dataclass
class PaperRetrieval:
    id: str
    paper_id: str
    retrieval_run_id: str
    retrieval_reason: str  # keyword_match / backward_citation / forward_citation / author_expansion
    citation_path: str | None
    created_at: str


@dataclass
class DedupDecision:
    id: str
    paper_id_kept: str
    paper_id_removed: str
    match_type: str          # doi_match / title_fuzzy / manual
    similarity_score: float | None
