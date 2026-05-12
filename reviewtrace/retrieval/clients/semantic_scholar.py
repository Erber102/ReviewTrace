"""Semantic Scholar API client.

Rate limits:
  - Without key: ~1 req/sec
  - With key:    100 req / 5 min  (~0.33 req/sec, use Semaphore in orchestrator)
"""

import asyncio
from typing import Any

import httpx

from reviewtrace.config.settings import SEMANTIC_SCHOLAR_API_KEY
from reviewtrace.retrieval.errors import RateLimitedError
from reviewtrace.retrieval.models import PaperMetadata
from reviewtrace.retrieval.normalizer import from_semantic_scholar

BASE_URL = "https://api.semanticscholar.org/graph/v1"
_FIELDS = "title,authors,year,externalIds,venue,abstract,citationCount,referenceCount,url"

_HEADERS: dict[str, str] = {}
if SEMANTIC_SCHOLAR_API_KEY:
    _HEADERS["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY


async def search(query: str, max_results: int = 50) -> list[PaperMetadata]:
    """Search Semantic Scholar by keyword query."""
    results: list[dict] = []
    offset = 0
    batch_size = min(100, max_results)
    consecutive_429 = 0
    _MAX_429 = 3

    async with httpx.AsyncClient(timeout=30, headers=_HEADERS) as client:
        while len(results) < max_results:
            params: dict[str, Any] = {
                "query": query,
                "limit": batch_size,
                "offset": offset,
                "fields": _FIELDS,
            }
            try:
                resp = await client.get(f"{BASE_URL}/paper/search", params=params)
                if resp.status_code == 429:
                    consecutive_429 += 1
                    if consecutive_429 >= _MAX_429:
                        raise RateLimitedError(
                            f"Semantic Scholar: gave up after {consecutive_429} consecutive 429 responses"
                        )
                    print(f"[semantic_scholar] Rate limited (attempt {consecutive_429}), waiting 10s")
                    await asyncio.sleep(10)
                    continue
                consecutive_429 = 0
                resp.raise_for_status()
            except RateLimitedError:
                raise
            except httpx.HTTPError as e:
                print(f"[semantic_scholar] HTTP error: {e}")
                break

            data = resp.json()
            batch = data.get("data") or []
            if not batch:
                break

            results.extend(batch)
            offset += len(batch)

            total = data.get("total", 0)
            if offset >= total:
                break

            # Respect rate limits
            delay = 1.0 if not SEMANTIC_SCHOLAR_API_KEY else 1.5
            await asyncio.sleep(delay)

    return [from_semantic_scholar(r) for r in results[:max_results] if r.get("title")]


async def get_references(paper_id: str, limit: int = 100) -> list[PaperMetadata]:
    """Fetch papers referenced by the given S2 paper ID."""
    return await _get_citation_edge(paper_id, "references", limit)


async def get_citations(paper_id: str, limit: int = 100) -> list[PaperMetadata]:
    """Fetch papers that cite the given S2 paper ID."""
    return await _get_citation_edge(paper_id, "citations", limit)


async def _get_citation_edge(paper_id: str, edge: str, limit: int) -> list[PaperMetadata]:
    results: list[dict] = []
    offset = 0

    async with httpx.AsyncClient(timeout=30, headers=_HEADERS) as client:
        while len(results) < limit:
            params: dict[str, Any] = {
                "limit": min(500, limit - len(results)),
                "offset": offset,
                "fields": _FIELDS,
            }
            try:
                resp = await client.get(
                    f"{BASE_URL}/paper/{paper_id}/{edge}", params=params
                )
                if resp.status_code == 404:
                    break
                if resp.status_code == 429:
                    await asyncio.sleep(10)
                    continue
                resp.raise_for_status()
            except httpx.HTTPError as e:
                print(f"[semantic_scholar] {edge} error for {paper_id}: {e}")
                break

            data = resp.json()
            # edge results are wrapped: {"data": [{"citedPaper": {...}}, ...]}
            key = "citedPaper" if edge == "references" else "citingPaper"
            batch = [item[key] for item in (data.get("data") or []) if item.get(key)]
            if not batch:
                break

            results.extend(batch)
            offset += len(batch)

            total = data.get("total", 0)
            if offset >= total:
                break

            await asyncio.sleep(1.0 if not SEMANTIC_SCHOLAR_API_KEY else 1.5)

    return [from_semantic_scholar(r) for r in results if r.get("title")]
