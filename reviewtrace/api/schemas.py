"""Pydantic request/response schemas for the ReviewTrace API."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    topic: str = Field(..., description="Research topic")
    seeds: str = Field("", description="Seed papers, one arXiv ID or DOI per line")
    criteria_topic: str = Field("", description="Criteria topic (defaults to topic)")
    inclusion: list[str] = Field(default_factory=list, description="Inclusion criteria")
    exclusion: list[str] = Field(default_factory=list, description="Exclusion criteria")
    max_results: int = Field(50, ge=1, le=500)
    depth: int = Field(2, ge=0, le=4)
    max_per_hop: int = Field(30, ge=1, le=100)
    llm_delay: float = Field(0.5, ge=0.0, le=10.0)
    skip_expand: bool = False
    demo: bool = False
    max_queries: int | None = Field(None, ge=1, le=20)


class JobStarted(BaseModel):
    job_id: str


class JobStatus(BaseModel):
    job_id: str
    status: str  # running | done | error
    event_count: int


# ---------------------------------------------------------------------------
# Papers
# ---------------------------------------------------------------------------


class PaperOut(BaseModel):
    id: str
    title: str | None
    authors: str | None  # JSON string from DB
    year: int | None
    venue: str | None
    doi: str | None
    arxiv_id: str | None
    url: str | None
    abstract: str | None
    source_type: str | None
    citation_count: int | None
    decision: str | None       # include | exclude | uncertain | None
    confidence: float | None
    reason: str | None
    is_duplicate: bool


class AuditEntry(BaseModel):
    retrieval_reason: str | None
    citation_path: str | None
    query: str | None
    source: str | None
    run_timestamp: str | None


# ---------------------------------------------------------------------------
# Audit / Runs
# ---------------------------------------------------------------------------


class RunOut(BaseModel):
    id: str
    query: str | None
    source: str | None
    expansion_type: str | None
    status: str | None
    result_count: int | None
    timestamp: str | None


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


class EvidenceLinkOut(BaseModel):
    evidence_id: str
    paper_id: str
    content: str | None
    evidence_type: str | None
    relevance_score: float | None


class TaxonomyNodeOut(BaseModel):
    id: str
    label: str | None
    description: str | None
    cluster_id: int | None
    paper_ids: list[str]
    evidence_links: list[EvidenceLinkOut]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class StatsOut(BaseModel):
    total_papers: int
    canonical_papers: int
    duplicates: int
    included: int
    excluded: int
    uncertain: int
    unscreened: int
    total_runs: int
    total_evidence: int
    taxonomy_nodes: int
