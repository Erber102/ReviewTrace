-- ReviewTrace Database Schema
-- Version: 001_initial

CREATE TABLE IF NOT EXISTS papers (
    id          TEXT PRIMARY KEY,   -- sha256(doi or arxiv_id or title+authors)
    doi         TEXT UNIQUE,
    arxiv_id    TEXT,
    title       TEXT NOT NULL,
    authors     TEXT,               -- JSON array of strings
    year        INTEGER,
    venue       TEXT,
    abstract    TEXT,
    source_type TEXT,               -- peer_reviewed / preprint / workshop / blog / unknown
    url         TEXT,
    citation_count   INTEGER,
    reference_count  INTEGER,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS retrieval_runs (
    id              TEXT PRIMARY KEY,
    query           TEXT NOT NULL,
    source          TEXT NOT NULL,  -- openalex / semantic_scholar / arxiv
    expansion_type  TEXT,           -- keyword / backward_citation / forward_citation / author
    timestamp       TEXT DEFAULT (datetime('now')),
    result_count    INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending'  -- pending / done / error
);

-- Links each paper to the retrieval run that found it (append-only)
CREATE TABLE IF NOT EXISTS paper_retrievals (
    id                  TEXT PRIMARY KEY,
    paper_id            TEXT NOT NULL REFERENCES papers(id),
    retrieval_run_id    TEXT NOT NULL REFERENCES retrieval_runs(id),
    retrieval_reason    TEXT NOT NULL,  -- keyword_match / backward_citation / forward_citation / author_expansion
    citation_path       TEXT,           -- e.g. "seed:P001 → backward → P031 → forward → P042"
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dedup_decisions (
    id                  TEXT PRIMARY KEY,
    paper_id_kept       TEXT NOT NULL REFERENCES papers(id),
    paper_id_removed    TEXT NOT NULL,
    match_type          TEXT NOT NULL,  -- doi_match / title_fuzzy / manual
    similarity_score    REAL,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS screening_decisions (
    id                  TEXT PRIMARY KEY,
    paper_id            TEXT NOT NULL REFERENCES papers(id),
    decision            TEXT NOT NULL,  -- include / exclude / uncertain
    reason              TEXT,
    confidence          REAL,
    source_type_label   TEXT,           -- label assigned by source classifier
    screened_by         TEXT,           -- llm / human
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evidence_items (
    id              TEXT PRIMARY KEY,
    paper_id        TEXT NOT NULL REFERENCES papers(id),
    evidence_type   TEXT NOT NULL,  -- method_proposal / empirical_finding / theoretical_claim / limitation / comparison / dataset_contribution
    content         TEXT NOT NULL,
    location        TEXT,           -- abstract / section name / page ref
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS taxonomy_nodes (
    id          TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    description TEXT,
    cluster_id  INTEGER,
    parent_id   TEXT REFERENCES taxonomy_nodes(id),
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Provenance: which evidence items support which taxonomy node
CREATE TABLE IF NOT EXISTS taxonomy_evidence (
    id                  TEXT PRIMARY KEY,
    taxonomy_node_id    TEXT NOT NULL REFERENCES taxonomy_nodes(id),
    evidence_item_id    TEXT NOT NULL REFERENCES evidence_items(id),
    paper_id            TEXT NOT NULL REFERENCES papers(id),
    relevance_score     REAL,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS generated_claims (
    id                  TEXT PRIMARY KEY,
    source_text         TEXT NOT NULL,
    claim               TEXT NOT NULL,
    taxonomy_node_id    TEXT REFERENCES taxonomy_nodes(id),
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS claim_verifications (
    id                          TEXT PRIMARY KEY,
    claim_id                    TEXT NOT NULL REFERENCES generated_claims(id),
    verdict                     TEXT NOT NULL,  -- supported / partially_supported / unsupported
    supporting_evidence_ids     TEXT,           -- JSON array of evidence_item ids
    issue                       TEXT,
    confidence                  REAL,
    created_at                  TEXT DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_papers_doi         ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id    ON papers(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_paper_retrievals_paper ON paper_retrievals(paper_id);
CREATE INDEX IF NOT EXISTS idx_evidence_paper     ON evidence_items(paper_id);
CREATE INDEX IF NOT EXISTS idx_taxonomy_evidence_node ON taxonomy_evidence(taxonomy_node_id);
