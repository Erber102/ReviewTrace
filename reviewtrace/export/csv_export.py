"""CSV export helpers."""

import csv
import json
from pathlib import Path

from reviewtrace.db import connection as db


def export_papers_csv(output_path: Path) -> None:
    """Export all canonical (non-duplicate) papers with screening status."""
    removed = {
        r["paper_id_removed"]
        for r in db.fetchall("SELECT paper_id_removed FROM dedup_decisions")
    }
    screening = {
        r["paper_id"]: r
        for r in db.fetchall("SELECT * FROM screening_decisions")
    }
    papers = db.fetchall("SELECT * FROM papers ORDER BY year DESC, title")

    if not papers:
        print("[csv_export] No papers to export.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id", "title", "authors", "year", "doi", "arxiv_id", "venue",
        "source_type", "citation_count",
        "screening_decision", "screening_confidence", "screening_reason",
        "is_duplicate",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for p in papers:
            sd = screening.get(p["id"], {})
            authors = p.get("authors") or "[]"
            try:
                authors_list = json.loads(authors)
                authors_str = "; ".join(authors_list)
            except Exception:
                authors_str = authors

            writer.writerow({
                "id": p["id"],
                "title": p["title"],
                "authors": authors_str,
                "year": p["year"],
                "doi": p["doi"],
                "arxiv_id": p["arxiv_id"],
                "venue": p["venue"],
                "source_type": p["source_type"],
                "citation_count": p["citation_count"],
                "screening_decision": sd.get("decision", ""),
                "screening_confidence": sd.get("confidence", ""),
                "screening_reason": sd.get("reason", ""),
                "is_duplicate": "yes" if p["id"] in removed else "no",
            })

    print(f"[csv_export] Written {len(papers)} papers to {output_path}")


def export_screening_csv(output_path: Path) -> None:
    """Export screening decisions (alias for screener.export_csv for consistency)."""
    from reviewtrace.screening.screener import export_csv
    export_csv(output_path)
