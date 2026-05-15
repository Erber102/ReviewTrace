"""Papers endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from reviewtrace.api import db_per_request
from reviewtrace.api.schemas import AuditEntry, PaperOut

router = APIRouter()


def _build_paper_out(row: dict, duplicate_ids: set[str]) -> PaperOut:
    return PaperOut(
        id=row["id"],
        title=row.get("title"),
        authors=row.get("authors"),
        year=row.get("year"),
        venue=row.get("venue"),
        doi=row.get("doi"),
        arxiv_id=row.get("arxiv_id"),
        url=row.get("url"),
        abstract=row.get("abstract"),
        source_type=row.get("source_type"),
        citation_count=row.get("citation_count"),
        decision=row.get("decision"),
        confidence=row.get("confidence"),
        reason=row.get("reason"),
        is_duplicate=row["id"] in duplicate_ids,
    )


@router.get("/papers", response_model=list[PaperOut])
async def list_papers(
    decision: str = "all",
    include_duplicates: bool = False,
    db_path: str | None = Query(default=None),
) -> list[PaperOut]:
    """List papers with optional decision filter."""
    resolved_db = db_per_request.validate_db_path(db_path)

    duplicate_ids: set[str] = {
        r["paper_id_removed"]
        for r in db_per_request.fetchall(resolved_db, "SELECT paper_id_removed FROM dedup_decisions")
    }

    rows = db_per_request.fetchall(
        resolved_db,
        """
        SELECT p.*,
               sd.decision,
               sd.confidence,
               sd.reason
        FROM papers p
        LEFT JOIN screening_decisions sd ON sd.paper_id = p.id
        ORDER BY p.year DESC, p.title
        """,
    )

    out = []
    for row in rows:
        is_dup = row["id"] in duplicate_ids
        if not include_duplicates and is_dup:
            continue
        if decision != "all":
            if decision == "unscreened":
                if row.get("decision") is not None:
                    continue
            elif row.get("decision") != decision:
                continue
        out.append(_build_paper_out(row, duplicate_ids))

    return out


@router.get("/papers/{paper_id}", response_model=PaperOut)
async def get_paper(
    paper_id: str,
    db_path: str | None = Query(default=None),
) -> PaperOut:
    resolved_db = db_per_request.validate_db_path(db_path)
    duplicate_ids: set[str] = {
        r["paper_id_removed"]
        for r in db_per_request.fetchall(resolved_db, "SELECT paper_id_removed FROM dedup_decisions")
    }
    row = db_per_request.fetchone(
        resolved_db,
        """
        SELECT p.*,
               sd.decision,
               sd.confidence,
               sd.reason
        FROM papers p
        LEFT JOIN screening_decisions sd ON sd.paper_id = p.id
        WHERE p.id = ?
        """,
        (paper_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")
    return _build_paper_out(row, duplicate_ids)


_AUDIT_SQL = """
    SELECT
        pr.retrieval_reason,
        pr.citation_path,
        pr.created_at,
        rr.query,
        rr.source,
        rr.expansion_type,
        rr.timestamp AS run_timestamp
    FROM paper_retrievals pr
    JOIN retrieval_runs rr ON pr.retrieval_run_id = rr.id
    WHERE pr.paper_id = ?
    ORDER BY pr.created_at
"""


@router.get("/papers/{paper_id}/audit", response_model=list[AuditEntry])
async def get_paper_audit_trail(
    paper_id: str,
    db_path: str | None = Query(default=None),
) -> list[AuditEntry]:
    resolved_db = db_per_request.validate_db_path(db_path)
    entries = db_per_request.fetchall(resolved_db, _AUDIT_SQL, (paper_id,))
    return [AuditEntry(**e) for e in entries]
