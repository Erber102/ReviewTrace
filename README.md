# ReviewTrace

ReviewTrace is an open-source infrastructure project for auditable literature review.

It helps researchers trace claims in a literature review back to supporting evidence, flag weak or overbroad citations, and generate reproducible review logs.

Instead of asking “Can AI write my related work?”, ReviewTrace asks:

“Can every claim in this review be traced, checked, and audited?”

## Features

- **Web UI** — one-command start (`reviewtrace web`), built with FastAPI + React
- **Multi-source retrieval** — OpenAlex and arXiv as primary sources; Semantic Scholar for citation expansion
- **Citation graph expansion** — BFS forward/backward citation traversal with configurable depth
- **Deduplication** — DOI-level dedup at the DB layer + fuzzy title matching (Levenshtein ≥ 0.9)
- **LLM screening** — include/exclude decisions with source-type policy gate
- **Evidence extraction** — structured evidence items (method proposals, empirical findings, etc.)
- **Taxonomy** — embedding-based clustering → LLM-labelled nodes → evidence linking
- **Full audit trail** — append-only provenance for every retrieval run and paper
- **Export** — `papers.csv`, `citation_graph.graphml`, `evidence_matrix.csv`, `taxonomy.md`, audit JSON/Markdown

## Quickstart

### 1. Install

```bash
conda create -n reviewtrace python=3.11 -y
conda activate reviewtrace
pip install -e ".[all-llm]"
```

### 2. Configure

Copy `.env.template` to `.env` and fill in your API keys:

```bash
cp .env.template .env
# Edit .env — set at minimum ANTHROPIC_API_KEY (or another provider key)
```

Key variables:

| Variable | Description | Default |
|---|---|---|
| `REVIEWTRACE_LLM_PROVIDER` | `anthropic` / `openai` / `google` / `deepseek` | `anthropic` |
| `REVIEWTRACE_LLM_MODEL` | Model name (provider-specific) | `claude-opus-4-6` |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `GOOGLE_API_KEY` | Google Gemini API key | — |
| `DEEPSEEK_API_KEY` | DeepSeek API key | — |
| `SEMANTIC_SCHOLAR_API_KEY` | S2 key for higher rate limits | — |

### 3a. Web UI (recommended)

```bash
reviewtrace web
```

Opens at **http://localhost:8000** — builds the React frontend automatically on first run.

```bash
reviewtrace web --skip-build   # subsequent launches (reuse existing build)
reviewtrace web --port 8080    # custom port
```

### 3b. Command line

```bash
reviewtrace run \
  --topic "Sparse Autoencoders for Mechanistic Interpretability" \
  --seeds data/seeds.txt \
  --criteria data/example_criteria.json \
  --output-dir outputs/
```

Outputs written to `outputs/`:
- `papers.csv` — all papers with screening decisions and duplicate flags
- `retrieval_audit.json` / `retrieval_audit.md` — full provenance audit
- `citation_graph.graphml` — citation network (import into Gephi/Cytoscape)
- `evidence_matrix.csv` — paper × evidence type count matrix
- `evidence_items.json` — full extracted evidence grouped by paper
- `taxonomy.md` — thematic clusters with labelled nodes and evidence links

---

## Web UI

| Page | What it shows |
|---|---|
| **Run** | Configure topic / seeds / criteria, run pipeline, live progress log |
| **Papers** | Filterable table with decision badges, expandable abstract + audit trail |
| **Taxonomy** | Thematic node cards with linked evidence |
| **Audit** | Retrieval run timeline by source |
| **Export** | Stats overview + one-click downloads for all output files |

The API is also available at `/docs` (Swagger UI) when the server is running.

---

## CLI Reference

Each pipeline stage can be run individually:

```bash
# Keyword retrieval only
reviewtrace retrieve --topic "my topic" --max-results 50

# Citation graph expansion
reviewtrace expand --depth 2 --max-per-hop 30

# Deduplication
reviewtrace dedup

# Screening (with optional criteria file)
reviewtrace screen --topic "my topic" --criteria criteria.json

# Evidence extraction
reviewtrace extract --output-dir outputs/

# Taxonomy + clustering
reviewtrace taxonomize --output-dir outputs/

# Export all outputs
reviewtrace export --output-dir outputs/
```

### `run` options

| Flag | Default | Description |
|---|---|---|
| `--topic` / `-t` | required | Research topic |
| `--seeds` / `-s` | none | Seeds file (one arXiv/DOI per line) |
| `--criteria` / `-c` | none | Screening criteria JSON |
| `--db` | `reviewtrace.db` | SQLite database path |
| `--output-dir` / `-o` | `outputs/` | Output directory |
| `--max-results` / `-n` | 50 | Max results per keyword query |
| `--depth` | 2 | Citation BFS depth |
| `--max-per-hop` | 30 | Max papers per expansion hop |
| `--llm-delay` | 0.5 | Seconds between LLM calls |
| `--skip-expand` | false | Skip citation graph expansion |

---

## Seeds file format

```
# Comments start with #
arXiv:2309.05144        # explicit arXiv prefix
2309.08600              # bare arXiv ID
10.1234/example         # bare DOI
DOI:10.1234/example     # explicit DOI prefix
```

## Criteria file format

```json
{
  "topic": "Sparse Autoencoders for Mechanistic Interpretability",
  "inclusion": [
    "Proposes or evaluates sparse autoencoders for neural network analysis"
  ],
  "exclusion": [
    "Does not involve neural network interpretability"
  ]
}
```

---

## Architecture

```
reviewtrace/
├── config/          # Settings + .env loading
├── db/              # SQLite schema, migrations, connection helpers
├── llm.py           # Unified LLM interface (Anthropic/OpenAI/Google/DeepSeek)
├── retrieval/       # Keyword search clients + orchestrator + seed loader
├── audit/           # Provenance logger, dedup, audit export
├── expansion/       # BFS citation expansion (forward + backward)
├── screening/       # Source classifier, policy gate, LLM screener
├── evidence/        # Evidence extractor + matrix export
├── taxonomy/        # Embedder, clusterer, labeler, linker, exporter
└── export/          # papers.csv + citation_graph.graphml
```

### Paper identity

Each paper gets a deterministic ID: `sha256("doi:<DOI>")[:16]` or `sha256("arxiv:<ID>")[:16]` or `sha256("title:<title>")[:16]`. This means the same paper retrieved from multiple sources always maps to the same DB row.

### Audit trail

Every retrieval run and paper-run association is recorded with a deterministic ID (`sha256("<paper_id>:<run_id>")[:16]`), making the audit log idempotent — re-running a query won't create duplicate records.

---

## Development

```bash
# Run tests
pytest

# Lint
ruff check reviewtrace tests

# Type check
mypy reviewtrace
```

### Database schema

10 tables defined in `reviewtrace/db/schema.sql`:
`papers`, `retrieval_runs`, `paper_retrievals`, `dedup_decisions`, `screening_decisions`, `evidence_items`, `taxonomy_nodes`, `taxonomy_evidence`, `generated_claims`, `claim_verifications`

Migrations in `reviewtrace/db/migrations/` are applied automatically by `init_db()`.

---

## LLM providers

| Provider | Install | Env var |
|---|---|---|
| Anthropic (default) | included | `ANTHROPIC_API_KEY` |
| OpenAI | `pip install -e ".[openai]"` | `OPENAI_API_KEY` |
| Google Gemini | `pip install -e ".[google]"` | `GOOGLE_API_KEY` |
| DeepSeek | `pip install -e ".[openai]"` | `DEEPSEEK_API_KEY` |

Set `REVIEWTRACE_LLM_PROVIDER=deepseek` and `REVIEWTRACE_LLM_MODEL=deepseek-chat` to use DeepSeek (uses the OpenAI-compatible API).
