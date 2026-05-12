"""Retrieval orchestrator.

Runs all SearchQueries concurrently (with per-source rate limiting),
normalizes results, and writes papers + audit records to the DB via
the audit logger.
"""

import asyncio
import uuid
from collections.abc import Callable

from reviewtrace.audit import logger as audit
from reviewtrace.db import connection as db
from reviewtrace.retrieval.errors import RateLimitedError, SkippedError
from reviewtrace.retrieval.models import PaperMetadata, SearchQuery

# Per-source concurrency limits
_SEMAPHORES: dict[str, asyncio.Semaphore] = {}

ProgressCb = Callable[[str, str], None]


def _get_semaphore(source: str) -> asyncio.Semaphore:
    if source not in _SEMAPHORES:
        limit = 1 if source == "semantic_scholar" else 3
        _SEMAPHORES[source] = asyncio.Semaphore(limit)
    return _SEMAPHORES[source]


async def run_queries(
    queries: list[SearchQuery],
    progress_cb: ProgressCb | None = None,
) -> list[PaperMetadata]:
    """Execute all queries, write results to DB, return unique paper list."""
    tasks = [_run_one(q, progress_cb) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen_ids: set[str] = set()
    all_papers: list[PaperMetadata] = []
    for r in results:
        if isinstance(r, BaseException):
            print(f"[orchestrator] Query failed: {r}")
            continue
        for paper in r:
            if paper.id not in seen_ids:
                seen_ids.add(paper.id)
                all_papers.append(paper)

    return all_papers


async def _run_one(
    query: SearchQuery,
    progress_cb: ProgressCb | None = None,
) -> list[PaperMetadata]:
    sem = _get_semaphore(query.source)
    async with sem:
        run_id = str(uuid.uuid4())
        audit.log_run_start(run_id, query)

        try:
            papers = await _dispatch(query, progress_cb)
        except RateLimitedError as e:
            print(f"[orchestrator] {query.source} / '{query.query}' rate limited: {e}")
            audit.log_run_done(run_id, 0, "rate_limited")
            return []
        except SkippedError as e:
            print(f"[orchestrator] {query.source} / '{query.query}' skipped: {e}")
            audit.log_run_done(run_id, 0, "skipped")
            return []
        except Exception as e:
            print(f"[orchestrator] {query.source} / '{query.query}' error: {e}")
            audit.log_run_done(run_id, 0, "error")
            return []

        status = "zero_results" if len(papers) == 0 else "done"
        audit.log_run_done(run_id, len(papers), status)

        for paper in papers:
            db.insert_paper(paper.to_db_dict())
            audit.log_paper_found(paper, run_id, query)

        if progress_cb and papers:
            progress_cb(query.source, f"Found {len(papers)} papers for '{query.query[:60]}'")

        return papers


async def _dispatch(
    query: SearchQuery,
    progress_cb: ProgressCb | None = None,
) -> list[PaperMetadata]:
    from reviewtrace.retrieval.clients import arxiv, openalex, semantic_scholar

    if query.source == "openalex":
        if progress_cb:
            progress_cb("openalex", f"Searching: {query.query[:70]}")
        return await openalex.search(query.query, query.max_results)
    elif query.source == "semantic_scholar":
        if progress_cb:
            progress_cb("semantic_scholar", f"Searching: {query.query[:70]}")
        return await semantic_scholar.search(query.query, query.max_results)
    elif query.source == "arxiv":
        if progress_cb:
            progress_cb("arxiv", f"Searching: {query.query[:70]}")
        return await arxiv.search(query.query, query.max_results, progress_cb=progress_cb)
    else:
        raise ValueError(f"Unknown source: {query.source}")
