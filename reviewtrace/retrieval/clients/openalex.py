"""OpenAlex API client — free, no key required."""

import asyncio
from typing import Any

import httpx

from reviewtrace.config.settings import OPENALEX_EMAIL
from reviewtrace.retrieval.models import PaperMetadata
from reviewtrace.retrieval.normalizer import from_openalex

BASE_URL = "https://api.openalex.org"
_FIELDS = (
    "id,title,authorships,publication_year,doi,primary_location,"
    "best_oa_location,locations,abstract_inverted_index,"
    "cited_by_count,referenced_works_count"
)


async def search(query: str, max_results: int = 50) -> list[PaperMetadata]:
    """Search OpenAlex by keyword query."""
    params: dict[str, Any] = {
        "search": query,
        "per-page": min(max_results, 200),
        "select": _FIELDS,
        "filter": "type:article",
    }
    if OPENALEX_EMAIL:
        params["mailto"] = OPENALEX_EMAIL

    results: list[dict] = []
    cursor = "*"

    async with httpx.AsyncClient(timeout=30) as client:
        while len(results) < max_results:
            params["cursor"] = cursor
            try:
                resp = await client.get(f"{BASE_URL}/works", params=params)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                print(f"[openalex] HTTP error: {e}")
                break

            data = resp.json()
            batch = data.get("results") or []
            if not batch:
                break

            results.extend(batch)
            cursor = (data.get("meta") or {}).get("next_cursor")
            if not cursor:
                break

            await asyncio.sleep(0.1)  # be polite

    return [from_openalex(r) for r in results[:max_results] if r.get("title")]
