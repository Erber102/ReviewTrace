"""Evidence matrix export.

Generates:
  - evidence_matrix.csv  — paper × evidence_type count matrix
  - evidence_items.json  — all items with full content
"""

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from reviewtrace.db import connection as db
from reviewtrace.evidence.models import EVIDENCE_TYPES


def export_matrix_csv(output_path: Path) -> None:
    """Write paper × evidence_type count matrix to CSV."""
    items = db.fetchall(
        """
        SELECT ei.paper_id, ei.evidence_type, p.title, p.doi, p.year
        FROM evidence_items ei
        JOIN papers p ON ei.paper_id = p.id
        ORDER BY p.title
        """
    )

    # Build count matrix: {paper_id: {etype: count}}
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    meta: dict[str, dict] = {}
    for row in items:
        pid = row["paper_id"]
        counts[pid][row["evidence_type"]] += 1
        meta[pid] = {"title": row["title"], "doi": row["doi"], "year": row["year"]}

    if not meta:
        print("[matrix] No evidence items to export.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["paper_id", "title", "doi", "year"] + list(EVIDENCE_TYPES) + ["total"]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pid, m in meta.items():
            row = {
                "paper_id": pid,
                "title": m["title"],
                "doi": m["doi"],
                "year": m["year"],
            }
            total = 0
            for etype in EVIDENCE_TYPES:
                n = counts[pid].get(etype, 0)
                row[etype] = n
                total += n
            row["total"] = total
            writer.writerow(row)

    print(f"[matrix] Written {len(meta)} rows to {output_path}")


def export_items_json(output_path: Path) -> None:
    """Write all evidence items with full content to JSON."""
    items = db.fetchall(
        """
        SELECT
            ei.id, ei.paper_id, ei.evidence_type, ei.content, ei.location,
            p.title, p.doi, p.year, p.venue
        FROM evidence_items ei
        JOIN papers p ON ei.paper_id = p.id
        ORDER BY p.title, ei.evidence_type
        """
    )

    # Group by paper
    by_paper: dict[str, dict] = {}
    for row in items:
        pid = row["paper_id"]
        if pid not in by_paper:
            by_paper[pid] = {
                "paper_id": pid,
                "title": row["title"],
                "doi": row["doi"],
                "year": row["year"],
                "venue": row["venue"],
                "evidence": [],
            }
        by_paper[pid]["evidence"].append({
            "id": row["id"],
            "evidence_type": row["evidence_type"],
            "content": row["content"],
            "location": row["location"],
        })

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_items": len(items),
        "total_papers": len(by_paper),
        "papers": list(by_paper.values()),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"[matrix] Written {len(items)} items across {len(by_paper)} papers to {output_path}")
