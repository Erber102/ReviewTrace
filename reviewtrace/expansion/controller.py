"""Citation graph expansion controller.

Uses BFS (not DFS) to avoid following a single citation chain too deeply.
Each hop is bounded by max_papers_per_hop to prevent explosion.

Default hard-coded values (per plan): depth=2, max_per_hop=30.
"""

import asyncio
import uuid
from collections import deque
from dataclasses import dataclass

from reviewtrace.db import connection as db
from reviewtrace.expansion.backward import fetch_references
from reviewtrace.expansion.forward import fetch_citations
from reviewtrace.expansion.path_tracker import build_path, log_expanded_paper, seed_path
from reviewtrace.retrieval.models import PaperMetadata

_DEFAULT_DEPTH = 2
_DEFAULT_MAX_PER_HOP = 30


@dataclass
class ExpansionResult:
    seeds_count: int
    new_papers_count: int
    total_hops: int


async def expand(
    seed_paper_ids: list[str],
    max_depth: int = _DEFAULT_DEPTH,
    max_papers_per_hop: int = _DEFAULT_MAX_PER_HOP,
) -> ExpansionResult:
    """BFS citation expansion from seed papers.

    For each paper in the BFS frontier, fetches both backward (references)
    and forward (citing) papers, records them in DB with full citation paths.
    """
    # (paper_id, depth, parent_path)
    queue: deque[tuple[str, int, str]] = deque()
    visited: set[str] = set(seed_paper_ids)

    for sid in seed_paper_ids:
        queue.append((sid, 0, seed_path(sid)))

    new_papers: list[PaperMetadata] = []
    total_hops = 0

    while queue:
        paper_id, depth, parent_path = queue.popleft()

        if depth >= max_depth:
            continue

        run_id = str(uuid.uuid4())
        _log_expansion_run_start(run_id, paper_id, depth)

        refs, cites = await asyncio.gather(
            fetch_references(paper_id, limit=max_papers_per_hop),
            fetch_citations(paper_id, limit=max_papers_per_hop),
            return_exceptions=True,
        )

        refs = refs if isinstance(refs, list) else []
        cites = cites if isinstance(cites, list) else []
        total_hops += 1

        added = 0
        for direction, papers in [("backward_citation", refs), ("forward_citation", cites)]:
            for paper in papers:
                if paper.id in visited:
                    continue
                visited.add(paper.id)

                path = build_path(parent_path, direction, paper.id)
                db.insert_paper(paper.to_db_dict())
                log_expanded_paper(paper, run_id, direction, path)
                new_papers.append(paper)
                added += 1

                queue.append((paper.id, depth + 1, path))

        _log_expansion_run_done(run_id, added)

    return ExpansionResult(
        seeds_count=len(seed_paper_ids),
        new_papers_count=len(new_papers),
        total_hops=total_hops,
    )


# ---------------------------------------------------------------------------
# Internal audit helpers
# ---------------------------------------------------------------------------

def _log_expansion_run_start(run_id: str, paper_id: str, depth: int) -> None:
    db.execute(
        """
        INSERT INTO retrieval_runs (id, query, source, expansion_type, status)
        VALUES (?, ?, 'semantic_scholar', 'citation_expansion', 'pending')
        """,
        (run_id, f"expand:depth={depth}:paper={paper_id}"),
    )


def _log_expansion_run_done(run_id: str, count: int) -> None:
    db.execute(
        "UPDATE retrieval_runs SET result_count = ?, status = 'done' WHERE id = ?",
        (count, run_id),
    )
