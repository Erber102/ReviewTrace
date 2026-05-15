"""Run manifest writer.

Writes output_dir/run_manifest.json after each pipeline run, capturing
run identity and summary stats so the artifact is self-describing.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from reviewtrace.db import connection as db


def collect_stats() -> dict:
    """Query the current DB state and return a stats dict."""
    total = db.fetchone("SELECT COUNT(*) AS n FROM papers")["n"]
    dup_ids = {r["paper_id_removed"] for r in db.fetchall("SELECT paper_id_removed FROM dedup_decisions")}
    all_ids = {r["id"] for r in db.fetchall("SELECT id FROM papers")}
    canonical_ids = all_ids - dup_ids
    screened_ids = {r["paper_id"] for r in db.fetchall("SELECT paper_id FROM screening_decisions")}

    counts: dict[str, int] = {}
    for r in db.fetchall("SELECT decision, COUNT(*) AS n FROM screening_decisions GROUP BY decision"):
        counts[r["decision"]] = r["n"]

    return {
        "total_papers": total,
        "canonical_papers": len(canonical_ids),
        "duplicates": len(dup_ids),
        "included": counts.get("include", 0),
        "excluded": counts.get("exclude", 0),
        "uncertain": counts.get("uncertain", 0),
        "unscreened": len(canonical_ids - screened_ids),
        "evidence_items": db.fetchone("SELECT COUNT(*) AS n FROM evidence_items")["n"],
        "taxonomy_nodes": db.fetchone("SELECT COUNT(*) AS n FROM taxonomy_nodes")["n"],
        "retrieval_runs": db.fetchone("SELECT COUNT(*) AS n FROM retrieval_runs")["n"],
    }


def scan_manifests(output_root: Path) -> list[dict]:
    """Recursively find all run_manifest.json files under output_root.

    Returns a list of manifest dicts sorted by created_at descending.
    Silently skips files that cannot be read or parsed.
    """
    output_root = Path(output_root)
    results: list[dict] = []
    if not output_root.exists():
        return results

    for manifest_file in output_root.rglob("run_manifest.json"):
        try:
            data = json.loads(manifest_file.read_text())
            # Ensure required fields are present before including
            if "run_id" in data and "topic" in data and "created_at" in data:
                results.append(data)
        except Exception:
            pass

    results.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return results


def write_manifest(
    output_dir: Path,
    *,
    topic: str,
    demo: bool,
    fresh: bool,
    db_path: Path,
    status: str,
    run_id: str | None = None,
    error: str | None = None,
) -> Path:
    """Write run_manifest.json to output_dir and return the path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stats: dict = {}
    try:
        stats = collect_stats()
    except Exception:
        pass  # DB may be unavailable on error paths

    manifest = {
        "run_id": run_id or uuid.uuid4().hex[:12],
        "topic": topic,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "demo": demo,
        "fresh": fresh,
        "db_path": str(db_path),
        "output_dir": str(output_dir),
        "stats": stats,
    }
    if error is not None:
        manifest["error"] = error

    dest = output_dir / "run_manifest.json"
    dest.write_text(json.dumps(manifest, indent=2))
    return dest
