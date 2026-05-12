"""Papers endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from reviewtrace.api.schemas import AuditEntry, PaperOut
from reviewtrace.audit.logger import get_paper_audit
from reviewtrace.db import connection as db

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
) -> list[PaperOut]:
    """List papers with optional decision filter."""
    duplicate_ids: set[str] = {
        r["paper_id_removed"]
        for r in db.fetchall("SELECT paper_id_removed FROM dedup_decisions")
    }

    rows = db.fetchall(
        """
        SELECT p.*,
               sd.decision,
               sd.confidence,
               sd.reason
        FROM papers p
        LEFT JOIN screening_decisions sd ON sd.paper_id = p.id
        ORDER BY p.year DESC, p.title
        """
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
async def get_paper(paper_id: str) -> PaperOut:
    duplicate_ids: set[str] = {
        r["paper_id_removed"]
        for r in db.fetchall("SELECT paper_id_removed FROM dedup_decisions")
    }
    row = db.fetchone(
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


@router.get("/papers/{paper_id}/audit", response_model=list[AuditEntry])
async def get_paper_audit_trail(paper_id: str) -> list[AuditEntry]:
    entries = get_paper_audit(paper_id)
    return [AuditEntry(**e) for e in entries]
