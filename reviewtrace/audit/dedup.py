"""Deduplication of the paper pool.

Strategy (in order):
  1. DOI exact match        → auto-merge, record as doi_match
  2. Title fuzzy match      → auto-merge if Levenshtein ratio > 0.9, record as title_fuzzy
  3. Everything else        → kept as-is (no flag in MVP)

Records are written to dedup_decisions. Papers are never deleted from DB —
downstream queries filter via get_canonical_paper_ids().
"""

import uuid
from dataclasses import dataclass

from Levenshtein import ratio as lev_ratio

from reviewtrace.db import connection as db

_FUZZY_THRESHOLD = 0.9


@dataclass
class DedupResult:
    total_before: int
    total_after: int
    doi_merges: int
    fuzzy_merges: int


def run_dedup() -> DedupResult:
    """Deduplicate all papers currently in the DB. Idempotent."""
    papers = db.fetchall("SELECT id, doi, title FROM papers ORDER BY created_at")
    if not papers:
        return DedupResult(0, 0, 0, 0)

    already_removed = {
        r["paper_id_removed"]
        for r in db.fetchall("SELECT paper_id_removed FROM dedup_decisions")
    }
    active = [p for p in papers if p["id"] not in already_removed]

    # DOI-exact dedup is already handled at insert time:
    # PaperMetadata.id is derived from DOI, so same-DOI papers share the same
    # primary key and are silently ignored by INSERT OR IGNORE.
    # We only need to run title-based fuzzy dedup here.
    fuzzy_merges = _dedup_by_title(active)

    return DedupResult(
        total_before=len(papers),
        total_after=len(papers) - fuzzy_merges,
        doi_merges=0,
        fuzzy_merges=fuzzy_merges,
    )


def get_canonical_paper_ids() -> set[str]:
    """Return IDs of papers not removed by deduplication."""
    all_ids = {r["id"] for r in db.fetchall("SELECT id FROM papers")}
    removed_ids = {
        r["paper_id_removed"]
        for r in db.fetchall("SELECT paper_id_removed FROM dedup_decisions")
    }
    return all_ids - removed_ids


def get_canonical_papers() -> list[dict]:
    """Return full paper records for canonical (non-duplicate) papers."""
    canonical_ids = get_canonical_paper_ids()
    if not canonical_ids:
        return []
    placeholders = ",".join("?" * len(canonical_ids))
    return db.fetchall(
        f"SELECT * FROM papers WHERE id IN ({placeholders})",
        tuple(canonical_ids),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dedup_by_title(papers: list[dict]) -> int:
    """O(n²) pairwise title fuzzy match among papers without DOI duplicates."""
    merges = 0
    removed: set[str] = set()

    for i, p1 in enumerate(papers):
        if p1["id"] in removed:
            continue
        t1 = (p1["title"] or "").lower().strip()

        for p2 in papers[i + 1:]:
            if p2["id"] in removed:
                continue
            t2 = (p2["title"] or "").lower().strip()
            if not t1 or not t2:
                continue

            score = lev_ratio(t1, t2)
            if score >= _FUZZY_THRESHOLD:
                _record_decision(p1["id"], p2["id"], "title_fuzzy", similarity_score=score)
                removed.add(p2["id"])
                merges += 1

    return merges


def _record_decision(
    kept_id: str,
    removed_id: str,
    match_type: str,
    similarity_score: float | None,
) -> None:
    db.execute(
        """
        INSERT OR IGNORE INTO dedup_decisions
            (id, paper_id_kept, paper_id_removed, match_type, similarity_score)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), kept_id, removed_id, match_type, similarity_score),
    )
