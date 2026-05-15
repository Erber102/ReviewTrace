"""LLM-based taxonomy label generation.

For each cluster, sends a sample of paper titles + abstracts to the LLM
and asks it to name the research direction and write a short description.
After all labels are generated a post-processing pass detects duplicate or
near-duplicate labels and relabels the later node to be more specific.
"""

import difflib
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

_RELABEL_PROMPT = """\
You are disambiguating taxonomy nodes in a literature review.

The label "{existing_label}" has already been assigned to a different cluster.
You must generate a MORE SPECIFIC and DISTINCT label for this cluster.

Papers in this cluster:
{papers_block}

Generate a label (3-8 words) that:
- Is clearly different from "{existing_label}"
- Captures what is UNIQUE about these papers compared to the general topic
- Is specific enough to distinguish this cluster from the other one

Return only one valid JSON object with fields "label" (3-8 words) and "description" (2-3 sentences).
Do not use Markdown. Do not wrap the JSON in code fences. Do not include text before or after the JSON.
"""

_MAX_PAPERS_PER_LABEL = 8  # send at most this many papers to the LLM per cluster
_DUPLICATE_THRESHOLD = 0.85  # SequenceMatcher ratio above which labels are considered duplicates


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

    _deduplicate_labels(nodes, clusters)
    return nodes


def _deduplicate_labels(nodes: list[TaxonomyNode], clusters: dict[int, list[dict]]) -> None:
    """Post-processing: detect duplicate/near-duplicate labels and relabel later nodes."""
    # seen: list of (normalised_label, node) for nodes already confirmed distinct
    seen: list[tuple[str, TaxonomyNode]] = []

    for node in nodes:
        normalised = node.label.strip().lower()
        conflict_label: str | None = None
        for seen_norm, _ in seen:
            ratio = difflib.SequenceMatcher(None, normalised, seen_norm).ratio()
            if ratio >= _DUPLICATE_THRESHOLD:
                conflict_label = node.label
                break

        if conflict_label is not None:
            papers = clusters.get(node.cluster_id, [])
            new_label, new_description = _relabel_specific(conflict_label, papers)
            print(
                f"[labeler] Duplicate label '{conflict_label}' for cluster {node.cluster_id}; "
                f"relabeled to '{new_label}'"
            )
            node.label = new_label
            node.description = new_description
            _save_node(node)
            normalised = new_label.strip().lower()

        seen.append((normalised, node))


def _relabel_specific(existing_label: str, papers: list[dict]) -> tuple[str, str]:
    """Ask the LLM for a more specific label given that existing_label is already taken."""
    sample = papers[:_MAX_PAPERS_PER_LABEL]
    papers_block = "\n".join(
        f"- {p.get('title', 'Unknown')}: {(p.get('abstract') or '')[:200]}"
        for p in sample
    )
    prompt = _RELABEL_PROMPT.format(existing_label=existing_label, papers_block=papers_block)
    try:
        raw = complete(prompt, max_tokens=256)
        parsed = parse_llm_json(raw)
        label = str(parsed.get("label", existing_label)).strip()
        description = str(parsed.get("description", "")).strip()
    except Exception:
        label = f"{existing_label} (Variant)"
        description = ""
    return label, description


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
