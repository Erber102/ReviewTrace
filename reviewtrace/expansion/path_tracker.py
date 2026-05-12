"""Citation path construction and logging.

Path format: "seed:{seed_id} → backward_citation → {p1} → forward_citation → {p2}"
Each hop records the direction (backward_citation = references, forward_citation = citing papers).
"""

import hashlib

from reviewtrace.db import connection as db
from reviewtrace.retrieval.models import PaperMetadata


def build_path(parent_path: str, direction: str, paper_id: str) -> str:
    """Extend an existing citation path by one hop."""
    return f"{parent_path} → {direction} → {paper_id}"


def seed_path(seed_id: str) -> str:
    return f"seed:{seed_id}"


def log_expanded_paper(
    paper: PaperMetadata,
    run_id: str,
    direction: str,    # backward_citation | forward_citation
    citation_path: str,
) -> None:
    """Write an expansion retrieval record with a pre-built citation path."""
    record_id = hashlib.sha256(f"{paper.id}:{run_id}".encode()).hexdigest()[:16]
    db.execute(
        """
        INSERT OR IGNORE INTO paper_retrievals
            (id, paper_id, retrieval_run_id, retrieval_reason, citation_path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (record_id, paper.id, run_id, direction, citation_path),
    )
