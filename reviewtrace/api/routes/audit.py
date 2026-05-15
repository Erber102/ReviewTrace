"""Audit, stats, taxonomy, evidence endpoints."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Query

from reviewtrace.api.schemas import (
    EvidenceLinkOut,
    ReviewRunOut,
    RunOut,
    StatsOut,
    TaxonomyNodeOut,
)
from reviewtrace.api import db_per_request
from reviewtrace.audit.logger import get_all_runs
from reviewtrace.db import connection as db
from reviewtrace.manifest import scan_manifests

router = APIRouter()


def _count(sql: str) -> int:
    row = db.fetchone(sql)
    return int(row["n"]) if row else 0


@router.get("/stats", response_model=StatsOut)
async def get_stats() -> StatsOut:
    total = _count("SELECT COUNT(*) AS n FROM papers")
    dup_count = _count("SELECT COUNT(*) AS n FROM dedup_decisions")

    counts = {
        r["decision"]: r["n"]
        for r in db.fetchall(
            "SELECT decision, COUNT(*) AS n FROM screening_decisions GROUP BY decision"
        )
    }
    screened_ids = {
        r["paper_id"] for r in db.fetchall("SELECT paper_id FROM screening_decisions")
    }
    duplicate_ids = {
        r["paper_id_removed"] for r in db.fetchall("SELECT paper_id_removed FROM dedup_decisions")
    }
    all_ids = {r["id"] for r in db.fetchall("SELECT id FROM papers")}
    canonical_ids = all_ids - duplicate_ids
    unscreened = len(canonical_ids - screened_ids)

    return StatsOut(
        total_papers=total,
        canonical_papers=len(canonical_ids),
        duplicates=dup_count,
        included=counts.get("include", 0),
        excluded=counts.get("exclude", 0),
        uncertain=counts.get("uncertain", 0),
        unscreened=unscreened,
        total_runs=_count("SELECT COUNT(*) AS n FROM retrieval_runs"),
        total_evidence=_count("SELECT COUNT(*) AS n FROM evidence_items"),
        taxonomy_nodes=_count("SELECT COUNT(*) AS n FROM taxonomy_nodes"),
    )


@router.get("/runs", response_model=list[RunOut])
async def list_runs(
    db_path: str | None = Query(default=None),
) -> list[RunOut]:
    resolved_db = db_per_request.validate_db_path(db_path)
    rows = db_per_request.fetchall(
        resolved_db,
        "SELECT * FROM retrieval_runs ORDER BY timestamp",
    )
    return [RunOut(**r) for r in rows]


@router.get("/review-runs", response_model=list[ReviewRunOut])
async def list_review_runs() -> list[ReviewRunOut]:
    """List completed and errored pipeline runs discovered from run_manifest.json files."""
    output_root = Path(os.getenv("REVIEWTRACE_OUTPUT_DIR", "outputs"))
    manifests = scan_manifests(output_root)
    return [ReviewRunOut(**m) for m in manifests]


@router.get("/taxonomy", response_model=list[TaxonomyNodeOut])
async def list_taxonomy(
    db_path: str | None = Query(default=None),
) -> list[TaxonomyNodeOut]:
    resolved_db = db_per_request.validate_db_path(db_path)
    nodes = db_per_request.fetchall(resolved_db, "SELECT * FROM taxonomy_nodes ORDER BY label")
    out = []
    for node in nodes:
        paper_ids = [
            r["paper_id"]
            for r in db_per_request.fetchall(
                resolved_db,
                "SELECT DISTINCT paper_id FROM taxonomy_evidence WHERE taxonomy_node_id = ?",
                (node["id"],),
            )
        ]
        ev_rows = db_per_request.fetchall(
            resolved_db,
            """
            SELECT te.evidence_item_id AS evidence_id,
                   te.paper_id,
                   te.relevance_score,
                   ei.content,
                   ei.evidence_type
            FROM taxonomy_evidence te
            LEFT JOIN evidence_items ei ON ei.id = te.evidence_item_id
            WHERE te.taxonomy_node_id = ?
            ORDER BY te.relevance_score DESC
            LIMIT 20
            """,
            (node["id"],),
        )
        out.append(
            TaxonomyNodeOut(
                id=node["id"],
                label=node.get("label"),
                description=node.get("description"),
                cluster_id=node.get("cluster_id"),
                paper_ids=paper_ids,
                evidence_links=[EvidenceLinkOut(**e) for e in ev_rows],
            )
        )
    return out


@router.get("/evidence")
async def list_evidence(
    paper_id: str | None = None,
    db_path: str | None = Query(default=None),
) -> list[dict]:
    resolved_db = db_per_request.validate_db_path(db_path)
    if paper_id:
        return db_per_request.fetchall(
            resolved_db,
            "SELECT * FROM evidence_items WHERE paper_id = ? ORDER BY evidence_type",
            (paper_id,),
        )
    return db_per_request.fetchall(
        resolved_db,
        "SELECT * FROM evidence_items ORDER BY paper_id, evidence_type",
    )
