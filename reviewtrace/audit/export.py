"""Export retrieval audit trail to JSON and Markdown."""

import json
from datetime import datetime, timezone
from pathlib import Path

from reviewtrace.audit.logger import get_all_runs, get_paper_audit
from reviewtrace.db import connection as db


def export_json(output_path: Path) -> None:
    """Write retrieval_audit.json — answers 'how was this paper found?'"""
    papers = db.fetchall("SELECT id, title, doi, arxiv_id, year, authors FROM papers ORDER BY title")
    runs = get_all_runs()

    paper_records = []
    for p in papers:
        trail = get_paper_audit(p["id"])
        paper_records.append({
            "id": p["id"],
            "title": p["title"],
            "doi": p["doi"],
            "arxiv_id": p["arxiv_id"],
            "year": p["year"],
            "retrieval_paths": trail,
        })

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_papers": len(papers),
        "total_runs": len(runs),
        "papers": paper_records,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))


def export_markdown(output_path: Path) -> None:
    """Write audit_report.md — human-readable retrieval provenance."""
    papers = db.fetchall(
        "SELECT id, title, doi, arxiv_id, year FROM papers ORDER BY title"
    )
    runs = get_all_runs()
    dedup_decisions = db.fetchall("SELECT * FROM dedup_decisions")

    lines: list[str] = [
        "# ReviewTrace — Retrieval Audit Report",
        f"\nGenerated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"\n**Total papers retrieved**: {len(papers)}",
        f"**Total retrieval runs**: {len(runs)}",
        f"**Duplicates removed**: {len(dedup_decisions)}",
        "\n---\n",
        "## Retrieval Runs\n",
        "| Source | Query | Type | Results | Status |",
        "|--------|-------|------|---------|--------|",
    ]

    for r in runs:
        query_short = (r["query"] or "")[:50]
        lines.append(
            f"| {r['source']} | {query_short} | {r['expansion_type']} "
            f"| {r['result_count']} | {r['status']} |"
        )

    lines += ["\n---\n", "## Paper Provenance\n"]

    for p in papers:
        trail = get_paper_audit(p["id"])
        doi_str = f"DOI: {p['doi']}" if p["doi"] else (f"arXiv: {p['arxiv_id']}" if p["arxiv_id"] else "no ID")
        lines.append(f"### {p['title']}")
        lines.append(f"_{doi_str} · {p['year'] or 'n/a'}_\n")

        if trail:
            for t in trail:
                path_str = f" · path: `{t['citation_path']}`" if t["citation_path"] else ""
                lines.append(
                    f"- **{t['source']}** via `{t['retrieval_reason']}`"
                    f" · query: _{t['query']}_"
                    f"{path_str}"
                )
        else:
            lines.append("- _(no retrieval record)_")
        lines.append("")

    if dedup_decisions:
        lines += ["---\n", "## Deduplication Decisions\n",
                  "| Kept | Removed | Match Type | Similarity |",
                  "|------|---------|------------|------------|"]
        for d in dedup_decisions:
            score = f"{d['similarity_score']:.3f}" if d["similarity_score"] is not None else "—"
            lines.append(
                f"| `{d['paper_id_kept'][:8]}` | `{d['paper_id_removed'][:8]}` "
                f"| {d['match_type']} | {score} |"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
