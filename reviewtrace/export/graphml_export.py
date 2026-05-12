"""Citation graph export to GraphML format.

Nodes = papers, edges = citation relationships recorded in paper_retrievals.
Viewable in Gephi, NetworkX, yEd, etc.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from reviewtrace.db import connection as db

_NS = "http://graphml.graphdrawing.org/graphml"
_EDGE_TYPES = {"backward_citation", "forward_citation"}


def export_graphml(output_path: Path) -> None:
    papers = {r["id"]: r for r in db.fetchall("SELECT id, title, year, doi FROM papers")}
    edges = db.fetchall(
        """
        SELECT DISTINCT pr.paper_id AS target, rr.query, pr.retrieval_reason, pr.citation_path
        FROM paper_retrievals pr
        JOIN retrieval_runs rr ON pr.retrieval_run_id = rr.id
        WHERE pr.retrieval_reason IN ('backward_citation', 'forward_citation')
          AND pr.citation_path IS NOT NULL
        """
    )

    if not papers:
        print("[graphml] No papers to export.")
        return

    # Build edges list: (source_id, target_id, relation)
    edge_list: list[tuple[str, str, str]] = []
    for e in edges:
        path = e["citation_path"] or ""
        source = _extract_source(path, e["retrieval_reason"])
        target = e["target"]
        if source and source in papers and target in papers:
            edge_list.append((source, target, e["retrieval_reason"]))

    root = ET.Element("graphml", xmlns=_NS)

    # Key declarations
    for kid, fname, ftype, ffor in [
        ("title", "title", "string", "node"),
        ("year", "year", "int", "node"),
        ("doi", "doi", "string", "node"),
        ("relation", "relation", "string", "edge"),
    ]:
        k = ET.SubElement(root, "key")
        k.set("id", kid)
        k.set("for", ffor)
        k.set("attr.name", fname)
        k.set("attr.type", ftype)

    graph = ET.SubElement(root, "graph", id="citation_graph", edgedefault="directed")

    for pid, p in papers.items():
        node = ET.SubElement(graph, "node", id=pid)
        _data(node, "title", p.get("title") or "")
        _data(node, "year", str(p.get("year") or ""))
        _data(node, "doi", p.get("doi") or "")

    for i, (src, tgt, rel) in enumerate(edge_list):
        edge = ET.SubElement(graph, "edge", id=f"e{i}", source=src, target=tgt)
        _data(edge, "relation", rel)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(output_path), encoding="utf-8", xml_declaration=True)
    print(f"[graphml] Written {len(papers)} nodes, {len(edge_list)} edges to {output_path}")


def _data(parent: ET.Element, key: str, value: str) -> None:
    d = ET.SubElement(parent, "data")
    d.set("key", key)
    d.text = value


def _extract_source(citation_path: str, relation: str) -> str | None:
    """Extract the source node ID from a citation path string.

    Path format: "seed:P001 → backward_citation → P031 → forward_citation → P042"
    For the last hop, the source is the second-to-last token.
    """
    parts = [p.strip() for p in citation_path.split("→")]
    # parts[-1] is the target paper id, parts[-2] is the relation, parts[-3] is the source
    if len(parts) < 3:
        # "seed:X → relation → target" - source is the seed
        if parts and parts[0].startswith("seed:"):
            return parts[0].replace("seed:", "")
        return None
    source = parts[-3]
    if source.startswith("seed:"):
        source = source.replace("seed:", "")
    return source
