# Evaluation Plan

This document describes how ReviewTrace will be evaluated as research infrastructure for auditable literature review.

## Retrieval coverage

| Metric | Description |
|---|---|
| Key-paper recall | Fraction of manually identified key papers retrieved |
| Duplicate rate | Fraction of retrieved papers that are duplicates before dedup |
| Source diversity | Distribution of papers across OpenAlex, arXiv, Semantic Scholar |
| Citation expansion yield | Additional papers found via citation expansion vs. keyword search alone |

## Screening quality

| Metric | Description |
|---|---|
| Precision | Fraction of included papers that are actually relevant |
| Recall | Fraction of relevant papers that are included |
| False include rate | Fraction of included papers that should have been excluded |
| False exclude rate | Fraction of excluded papers that should have been included |
| LLM-human agreement | Agreement rate between LLM screening decisions and human labels |

## Evidence grounding

| Metric | Description |
|---|---|
| Evidence correctness | Fraction of extracted evidence items that are factually accurate relative to source |
| Evidence type accuracy | Fraction of evidence items correctly classified by type |
| Unsupported extraction rate | Fraction of evidence items not traceable to source text |

## Taxonomy quality

| Metric | Description |
|---|---|
| Node purity | Average topical coherence within a taxonomy node |
| Evidence-node alignment | Fraction of evidence links that human reviewers judge as correct |
| Human usefulness rating | Subjective 1–5 rating of taxonomy usefulness for literature review |

## Audit usefulness

| Metric | Description |
|---|---|
| Time to locate source evidence | Time for a reviewer to trace a claim to its source paper |
| Number of corrected decisions | Count of screening decisions corrected after audit inspection |
| Weak citations identified | Count of citations flagged as weakly supported by extracted evidence |
| User trust rating | Subjective 1–5 rating of trust in the review after audit inspection |

## Baselines

| Baseline | Description |
|---|---|
| Manual keyword search | Human-performed keyword search without automated retrieval or screening |
| Vanilla LLM review | LLM-generated literature summary with no retrieval provenance |
| No citation expansion | Retrieval without citation graph expansion |
| No audit trail | Retrieval and screening without provenance logging |
| No screening provenance | Retrieval with citation expansion but without screening rationale recording |

## Initial case studies

### 1. Sparse Autoencoders for Mechanistic Interpretability

An active research area with a small number of highly-cited seed papers, a clear inclusion criterion (SAE for neural network analysis), and diverse adjacent topics (compression, representation learning, superposition). Useful for testing retrieval precision and false include rate.

Example files: `examples/sparse_autoencoders/`

### 2. Manifold-based Retrieval-Augmented Generation

A cross-disciplinary topic spanning information retrieval, manifold learning, and language model generation. Useful for testing retrieval coverage across sources and deduplication of conference vs. arXiv preprint versions.

### 3. Coding Rate Regularization for Representation Learning

A more specialized topic with a smaller literature. Useful for testing citation expansion yield and taxonomy quality when the paper pool is small.
