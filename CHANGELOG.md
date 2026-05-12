# Changelog

## v0.1.0 — Initial public prototype

### Added

- Web UI with FastAPI + React (`reviewtrace web`)
- CLI pipeline runner (`reviewtrace run`)
- OpenAlex and arXiv retrieval (primary sources)
- Optional Semantic Scholar integration for citation metadata and expansion
- Citation graph expansion (BFS, configurable depth and per-hop limit)
- DOI and fuzzy-title deduplication (Levenshtein threshold 0.9)
- LLM-assisted screening with source-type policy gate
- Evidence extraction (method proposals, empirical findings, theoretical claims, limitations, comparisons, dataset contributions)
- Taxonomy generation (embedding-based clustering → LLM labelling → evidence linking)
- Audit export (JSON and Markdown)
- CSV, JSON, Markdown, and GraphML exports
- Demo mode (`--demo`) for lightweight first runs
- Multi-provider LLM support: Anthropic, OpenAI, Google Gemini, DeepSeek
- arXiv 429 rate-limit handling with retry backoff
- Real-time Web UI progress streaming via SSE
