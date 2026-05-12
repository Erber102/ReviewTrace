"""Retrieval orchestrator.

Runs all SearchQueries concurrently (with per-source rate limiting),
normalizes results, and writes papers + audit records to the DB via
the audit logger.
"""

import asyncio
import uuid

from reviewtrace.audit import logger as audit
from reviewtrace.db import connection as db
from reviewtrace.retrieval.models import PaperMetadata, SearchQuery

# Per-source concurrency limits
_SEMAPHORES: dict[str, asyncio.Semaphore] = {}


def _get_semaphore(source: str) -> asyncio.Semaphore:
    if source not in _SEMAPHORES:
        limit = 1 if source == "semantic_scholar" else 3
        _SEMAPHORES[source] = asyncio.Semaphore(limit)
    return _SEMAPHORES[source]


async def run_queries(queries: list[SearchQuery]) -> list[PaperMetadata]:
    """Execute all queries, write results to DB, return unique paper list."""
    tasks = [_run_one(q) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen_ids: set[str] = set()
    all_papers: list[PaperMetadata] = []
    for r in results:
        if isinstance(r, Exception):
            print(f"[orchestrator] Query failed: {r}")
            continue
        for paper in r:
            if paper.id not in seen_ids:
                seen_ids.add(paper.id)
                all_papers.append(paper)

    return all_papers


async def _run_one(query: SearchQuery) -> list[PaperMetadata]:
    sem = _get_semaphore(query.source)
    async with sem:
        run_id = str(uuid.uuid4())
        audit.log_run_start(run_id, query)

        try:
            papers = await _dispatch(query)
        except Exception as e:
            print(f"[orchestrator] {query.source} / '{query.query}' error: {e}")
            audit.log_run_done(run_id, 0, "error")
            return []

        audit.log_run_done(run_id, len(papers), "done")

        for paper in papers:
            db.insert_paper(paper.to_db_dict())
            audit.log_paper_found(paper, run_id, query)

        return papers


async def _dispatch(query: SearchQuery) -> list[PaperMetadata]:
    from reviewtrace.retrieval.clients import arxiv, openalex, semantic_scholar

    if query.source == "openalex":
        return await openalex.search(query.query, query.max_results)
    elif query.source == "semantic_scholar":
        return await semantic_scholar.search(query.query, query.max_results)
    elif query.source == "arxiv":
        return await arxiv.search(query.query, query.max_results)
    else:
        raise ValueError(f"Unknown source: {query.source}")
