"""Taxonomy markdown export with full provenance.

Each taxonomy node lists:
  - Label + description
  - Number of papers in the cluster
  - Supporting evidence items (with paper citation)
"""

from pathlib import Path

from reviewtrace.db import connection as db


def export_taxonomy_md(output_path: Path) -> None:
    nodes = db.fetchall(
        "SELECT * FROM taxonomy_nodes ORDER BY cluster_id"
    )
    if not nodes:
        print("[exporter] No taxonomy nodes to export.")
        return

    lines = [
        "# ReviewTrace — Taxonomy with Provenance",
        "",
        f"*{len(nodes)} research directions identified*",
        "",
        "---",
        "",
    ]

    for node in nodes:
        node_id = node["id"]

        # Papers in this cluster
        cluster_papers = db.fetchall(
            """
            SELECT DISTINCT p.title, p.doi, p.year, p.authors
            FROM taxonomy_evidence te
            JOIN papers p ON te.paper_id = p.id
            WHERE te.taxonomy_node_id = ?
            """,
            (node_id,),
        )

        # Supporting evidence items
        evidence = db.fetchall(
            """
            SELECT te.relevance_score,
                   ei.evidence_type, ei.content,
                   p.title AS paper_title, p.year AS paper_year,
                   p.doi AS paper_doi
            FROM taxonomy_evidence te
            JOIN evidence_items ei ON te.evidence_item_id = ei.id
            JOIN papers p ON te.paper_id = p.id
            WHERE te.taxonomy_node_id = ?
            ORDER BY te.relevance_score DESC
            """,
            (node_id,),
        )

        lines.append(f"## {node['label']}")
        lines.append("")
        lines.append(node["description"] or "")
        lines.append("")

        if cluster_papers:
            lines.append(f"**Papers ({len(cluster_papers)})**:")
            for p in cluster_papers:
                doi_str = f" · DOI: {p['doi']}" if p["doi"] else ""
                lines.append(f"- {p['title']} ({p['year'] or 'n/a'}){doi_str}")
            lines.append("")

        if evidence:
            lines.append("**Supporting Evidence**:")
            for e in evidence:
                score = f"{e['relevance_score']:.2f}" if e["relevance_score"] is not None else "—"
                lines.append(
                    f"- `{e['evidence_type']}` · score={score}  "
                    f"**[{e['paper_title']}, {e['paper_year'] or 'n/a'}]**  "
                    f"_{e['content']}_"
                )
            lines.append("")
        else:
            lines.append("*No confirmed evidence links yet.*")
            lines.append("")

        lines.append("---")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"[exporter] Written {len(nodes)} taxonomy nodes to {output_path}")
