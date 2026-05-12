"""LLM-based taxonomy label generation.

For each cluster, sends a sample of paper titles + abstracts to the LLM
and asks it to name the research direction and write a short description.
"""

import uuid

from reviewtrace.db import connection as db
from reviewtrace.llm import complete
from reviewtrace.llm_json import parse_llm_json
from reviewtrace.taxonomy.models import TaxonomyNode

_LABEL_PROMPT = """\
You are analyzing a cluster of research papers to identify a coherent research direction.

Papers in this cluster:
{papers_block}

Based on these papers, provide:
1. A concise label (3-8 words) that names this research direction
2. A description (2-3 sentences) explaining what these papers have in common and \
why they form a coherent research area

Return only one valid JSON object with fields "label" (3-8 words) and "description" (2-3 sentences).
Do not use Markdown. Do not wrap the JSON in code fences. Do not include text before or after the JSON.
Example: {{"label": "Sparse Feature Learning", "description": "Papers in this cluster..."}}
"""

_MAX_PAPERS_PER_LABEL = 8  # send at most this many papers to the LLM per cluster


def generate_labels(
    cluster_assignments: list[int],
    papers: list[dict],
) -> list[TaxonomyNode]:
    """Generate one TaxonomyNode per cluster. Papers and assignments are parallel lists."""
    # Group papers by cluster
    clusters: dict[int, list[dict]] = {}
    for paper, cid in zip(papers, cluster_assignments):
        clusters.setdefault(cid, []).append(paper)

    nodes: list[TaxonomyNode] = []
    for cluster_id, cluster_papers in sorted(clusters.items()):
        node = _label_cluster(cluster_id, cluster_papers)
        _save_node(node)
        nodes.append(node)

    return nodes


def _label_cluster(cluster_id: int, papers: list[dict]) -> TaxonomyNode:
    sample = papers[:_MAX_PAPERS_PER_LABEL]
    papers_block = "\n".join(
        f"- {p.get('title', 'Unknown')}: {(p.get('abstract') or '')[:200]}"
        for p in sample
    )

    prompt = _LABEL_PROMPT.format(papers_block=papers_block)

    try:
        raw = complete(prompt, max_tokens=256)
        parsed = parse_llm_json(raw)
        label = str(parsed.get("label", f"Cluster {cluster_id}")).strip()
        description = str(parsed.get("description", "")).strip()
    except Exception:
        print(f"[labeler] LLM output parse failed for cluster {cluster_id}; using fallback label.")
        label = f"Cluster {cluster_id}"
        description = f"Auto-labeled cluster containing {len(papers)} papers."

    return TaxonomyNode(
        id=str(uuid.uuid4()),
        label=label,
        description=description,
        cluster_id=cluster_id,
    )


def _save_node(node: TaxonomyNode) -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO taxonomy_nodes (id, label, description, cluster_id, parent_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (node.id, node.label, node.description, node.cluster_id, node.parent_id),
    )
