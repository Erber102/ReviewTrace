"""Retrieval audit logger — append-only.

All retrieval events are written here. Records are never modified or deleted
after creation (except the run status transition pending → done/error,
which is part of the run lifecycle, not a history change).
"""


from reviewtrace.db import connection as db
from reviewtrace.retrieval.models import PaperMetadata, SearchQuery


def log_run_start(run_id: str, query: SearchQuery) -> None:
    """Record the start of a retrieval run."""
    db.execute(
        """
        INSERT INTO retrieval_runs (id, query, source, expansion_type, status)
        VALUES (?, ?, ?, ?, 'pending')
        """,
        (run_id, query.query, query.source, query.expansion_type),
    )


def log_run_done(run_id: str, result_count: int, status: str) -> None:
    """Update run status once it completes (pending → done | error)."""
    db.execute(
        "UPDATE retrieval_runs SET result_count = ?, status = ? WHERE id = ?",
        (result_count, status, run_id),
    )


def log_paper_found(
    paper: PaperMetadata,
    run_id: str,
    query: SearchQuery,
) -> None:
    """Record that a paper was found in a retrieval run (append-only).

    Uses a deterministic ID = sha256(paper_id + run_id)[:16] so that
    INSERT OR IGNORE silently skips duplicate (paper, run) pairs.
    """
    import hashlib

    record_id = hashlib.sha256(f"{paper.id}:{run_id}".encode()).hexdigest()[:16]
    seed_id = query.metadata.get("seed_paper_id")
    citation_path = (
        f"seed:{seed_id} → {query.expansion_type} → {paper.id}"
        if seed_id
        else None
    )
    db.execute(
        """
        INSERT OR IGNORE INTO paper_retrievals
            (id, paper_id, retrieval_run_id, retrieval_reason, citation_path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            record_id,
            paper.id,
            run_id,
            query.expansion_type,
            citation_path,
        ),
    )


def get_paper_audit(paper_id: str) -> list[dict]:
    """Return the full retrieval audit trail for a single paper."""
    return db.fetchall(
        """
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
        """,
        (paper_id,),
    )


def get_all_runs() -> list[dict]:
    """Return all retrieval runs ordered by timestamp."""
    return db.fetchall(
        "SELECT * FROM retrieval_runs ORDER BY timestamp"
    )
