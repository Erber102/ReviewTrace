"""Taxonomy pipeline controller.

Orchestrates: embed → cluster → label → link → export
"""

from dataclasses import dataclass

from reviewtrace.db import connection as db
from reviewtrace.taxonomy.clusterer import cluster_papers
from reviewtrace.taxonomy.embedder import embed_texts
from reviewtrace.taxonomy.labeler import generate_labels
from reviewtrace.taxonomy.linker import link_all
from reviewtrace.taxonomy.models import TaxonomyNode


@dataclass
class TaxonomyResult:
    n_papers: int
    n_clusters: int
    n_nodes: int
    n_evidence_links: int


def run_taxonomy() -> TaxonomyResult:
    """Run the full taxonomy pipeline over all included papers."""
    papers = _get_included_papers()
    if not papers:
        print("[taxonomy] No included papers found. Run `screen` first.")
        return TaxonomyResult(0, 0, 0, 0)

    print(f"[taxonomy] Embedding {len(papers)} papers…")
    texts = [f"{p.get('title', '')} {p.get('abstract', '')}" for p in papers]
    embeddings = embed_texts(texts)

    print("[taxonomy] Clustering…")
    assignments = cluster_papers(embeddings, n_papers=len(papers))

    print("[taxonomy] Generating cluster labels…")
    nodes: list[TaxonomyNode] = generate_labels(assignments, papers)

    print(f"[taxonomy] Linking {len(nodes)} nodes to evidence…")
    links = link_all(nodes)
    total_links = sum(len(v) for v in links.values())

    print(f"[taxonomy] Done — {len(nodes)} nodes, {total_links} evidence links.")
    return TaxonomyResult(
        n_papers=len(papers),
        n_clusters=len(set(assignments)),
        n_nodes=len(nodes),
        n_evidence_links=total_links,
    )


def _get_included_papers() -> list[dict]:
    return db.fetchall(
        """
        SELECT p.*
        FROM papers p
        JOIN screening_decisions sd ON p.id = sd.paper_id
        WHERE sd.decision = 'include'
        ORDER BY p.year DESC
        """
    )
