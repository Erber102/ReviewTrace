# Audit Model

ReviewTrace is designed around provenance-first literature review.

The system records how each paper, decision, evidence item, and taxonomy node was produced. Every stage of the pipeline writes to an append-only audit trail in the local SQLite database.

## 1. Retrieval provenance

For each retrieval run, ReviewTrace records:

- Topic and query string
- Query parameters (max results, source)
- Source (OpenAlex, arXiv, Semantic Scholar)
- Timestamp
- Normalized paper identity (deterministic ID from DOI or arXiv ID)
- Number of results returned
- Run status (done / error)

## 2. Citation expansion provenance

For citation graph expansion, ReviewTrace records:

- Seed paper identity
- Expansion direction: forward (citations) or backward (references)
- BFS depth level
- Parent paper that triggered the expansion
- Discovered paper identity
- Source used for citation metadata (Semantic Scholar)
- Citation path string: `seed:X → direction → Y → direction → Z`

## 3. Deduplication provenance

For deduplication, ReviewTrace records:

- Canonical paper ID (the paper kept)
- Duplicate candidate ID (the paper removed)
- Match type: DOI exact match or title fuzzy match
- Title similarity score (for fuzzy matches)
- Deduplication decision timestamp

Note: DOI deduplication is also enforced at the database layer via a UNIQUE constraint on paper IDs derived from DOIs.

## 4. Screening provenance

For LLM-assisted screening, ReviewTrace records:

- Research topic and screening criteria
- LLM provider and model name
- Source type classification (peer_reviewed, preprint, workshop, blog, etc.)
- Policy gate decision (allowed, flagged, blocked)
- Structured LLM output: decision (include / exclude / uncertain), rationale, confidence score
- Timestamp
- Whether the decision was made by the LLM or a human override

## 5. Evidence provenance

For evidence extraction, ReviewTrace records:

- Source paper identity
- Evidence type (method_proposal, empirical_finding, theoretical_claim, limitation, comparison, dataset_contribution)
- Extracted evidence text
- Linked taxonomy node (when available)
- Relevance score to the linked node

## 6. Human overrides

Planned support:

- User-edited screening decisions
- Override reason and timestamp
- Previous LLM decision
- Updated human decision

This enables a full audit trail distinguishing LLM-generated decisions from human-reviewed decisions.

## Design principle

ReviewTrace should not ask users to blindly trust an AI-generated literature review.

Instead, it should allow users to inspect how each output was produced, trace any claim back to its source paper and extraction method, and correct or override any decision with a recorded reason.
