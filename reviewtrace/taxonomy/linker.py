"""Taxonomy–evidence linker (the core of Phase 6).

For each taxonomy node, retrieves the top-k most similar evidence items via
embedding cosine similarity, then confirms relevance with the LLM.

This is the provenance layer: the link record answers
"why does this taxonomy node exist?" with specific evidence.
"""

import uuid

from reviewtrace.db import connection as db
from reviewtrace.llm import complete
from reviewtrace.llm_json import parse_llm_json
from reviewtrace.taxonomy.embedder import embed_texts, top_k_indices
from reviewtrace.taxonomy.models import TaxonomyNode

_TOP_K = 5          # candidates per node before LLM confirmation
_MIN_LINKS = 2      # warn if a node has fewer confirmed links

_CONFIRM_PROMPT = """\
You are checking whether a piece of evidence supports a taxonomy node in a \
literature review.

Taxonomy node:
  Label:       {label}
  Description: {description}

Evidence item:
  Type:    {evidence_type}
  Content: {content}
  Paper:   {paper_title} ({paper_year})

Does this evidence directly support, illustrate, or exemplify the taxonomy \
node described above?

Return only one valid JSON object with fields "relevant" (true or false) and "reason" (one sentence).
Do not use Markdown. Do not wrap the JSON in code fences. Do not include text before or after the JSON.
Example: {{"relevant": true, "reason": "The evidence directly describes the method proposed by this node."}}
"""


def link_all(
    nodes: list[TaxonomyNode],
    top_k: int = _TOP_K,
) -> dict[str, list[dict]]:
    """Link taxonomy nodes to evidence items.

    Returns {node_id: [{"evidence_item_id": ..., "paper_id": ..., "relevance_score": ...}]}
    """
    evidence_rows = db.fetchall(
        """
        SELECT ei.id, ei.paper_id, ei.evidence_type, ei.content,
               p.title AS paper_title, p.year AS paper_year
        FROM evidence_items ei
        JOIN papers p ON ei.paper_id = p.id
        """
    )
    if not evidence_rows or not nodes:
        return {}

    # Embed all evidence content once
    evidence_texts = [r["content"] for r in evidence_rows]
    evidence_embs = embed_texts(evidence_texts)  # (n_evidence, dim)

    links: dict[str, list[dict]] = {}

    for node in nodes:
        node_text = f"{node.label}. {node.description}"
        node_emb = embed_texts([node_text])[0]   # (dim,)

        candidate_indices = top_k_indices(node_emb, evidence_embs, k=top_k)
        confirmed = []

        for idx in candidate_indices:
            row = evidence_rows[idx]
            score = float(evidence_embs[idx] @ node_emb)

            if _llm_confirm(node, row):
                _save_link(node.id, row["id"], row["paper_id"], score)
                confirmed.append({
                    "evidence_item_id": row["id"],
                    "paper_id": row["paper_id"],
                    "relevance_score": score,
                })

        if len(confirmed) < _MIN_LINKS:
            print(f"[linker] Warning: node '{node.label}' has only {len(confirmed)} confirmed links")

        links[node.id] = confirmed

    return links


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _llm_confirm(node: TaxonomyNode, evidence_row: dict) -> bool:
    prompt = _CONFIRM_PROMPT.format(
        label=node.label,
        description=node.description,
        evidence_type=evidence_row["evidence_type"],
        content=evidence_row["content"],
        paper_title=evidence_row.get("paper_title") or "Unknown",
        paper_year=evidence_row.get("paper_year") or "n/a",
    )
    try:
        raw = complete(prompt, max_tokens=128)
        parsed = parse_llm_json(raw)
        return bool(parsed.get("relevant", False))
    except Exception:
        print("[linker] LLM output parse failed; skipped link.")
        return False


def _save_link(node_id: str, evidence_id: str, paper_id: str, score: float) -> None:
    db.execute(
        """
        INSERT OR IGNORE INTO taxonomy_evidence
            (id, taxonomy_node_id, evidence_item_id, paper_id, relevance_score)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), node_id, evidence_id, paper_id, score),
    )
