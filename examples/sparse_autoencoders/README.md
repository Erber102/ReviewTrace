# Example: Sparse Autoencoders for Mechanistic Interpretability

This example demonstrates a small auditable literature review run on sparse autoencoders for mechanistic interpretability.

## Quick demo

This is the recommended first run. It uses a small number of queries, skips citation expansion, and finishes in a few minutes.

```bash
reviewtrace run \
  --topic "Sparse Autoencoders for Mechanistic Interpretability" \
  --seeds examples/sparse_autoencoders/seeds.txt \
  --criteria examples/sparse_autoencoders/criteria.json \
  --output-dir outputs/sparse_autoencoders_demo/ \
  --demo
```

Or with explicit options:

```bash
reviewtrace run \
  --topic "Sparse Autoencoders for Mechanistic Interpretability" \
  --seeds examples/sparse_autoencoders/seeds.txt \
  --criteria examples/sparse_autoencoders/criteria.json \
  --output-dir outputs/sparse_autoencoders_demo/ \
  --max-results 10 \
  --skip-expand
```

## Full run

```bash
reviewtrace run \
  --topic "Sparse Autoencoders for Mechanistic Interpretability" \
  --seeds examples/sparse_autoencoders/seeds.txt \
  --criteria examples/sparse_autoencoders/criteria.json \
  --output-dir outputs/sparse_autoencoders_full/ \
  --max-results 50 \
  --depth 2 \
  --max-per-hop 30
```

## Expected outputs

The run produces:

- `papers.csv` — retrieved papers with metadata, dedup flags, and screening decisions
- `retrieval_audit.md` — human-readable provenance report
- `citation_graph.graphml` — citation network (import into Gephi or Cytoscape)
- `evidence_items.json` — structured evidence extracted from included papers
- `evidence_matrix.csv` — paper × evidence type count matrix
- `taxonomy.md` — thematic clusters with labelled nodes and linked evidence

Sample outputs are provided in `expected_outputs/`.

## What to inspect

1. Open `retrieval_audit.md` to see where each paper came from — which query, which source, which citation path.
2. Open `papers.csv` to inspect deduplication decisions and screening outcomes.
3. Open `evidence_items.json` to see extracted evidence linked to source papers.
4. Open `taxonomy.md` to inspect generated thematic clusters and their supporting evidence.
