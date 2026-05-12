"""arXiv API client — parses Atom feed, no key required."""

import asyncio
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import Any

import httpx

from reviewtrace.retrieval.errors import RateLimitedError
from reviewtrace.retrieval.models import PaperMetadata
from reviewtrace.retrieval.normalizer import from_arxiv

BASE_URL = "https://export.arxiv.org/api/query"
_NS = {
    "atom": "https://www.w3.org/2005/Atom",
    "arxiv": "https://arxiv.org/schemas/atom",
}
_RETRY_DELAYS = [10, 30]  # seconds to wait on 1st and 2nd 429


async def search(
    query: str,
    max_results: int = 50,
    progress_cb: Callable[[str, str], None] | None = None,
) -> list[PaperMetadata]:
    """Search arXiv. Retries on 429 with 10s / 30s backoff, then skips."""
    results: list[PaperMetadata] = []
    batch_size = min(100, max_results)
    start = 0
    consecutive_429 = 0
    _rate_limited = False

    async with httpx.AsyncClient(timeout=30) as client:
        while len(results) < max_results:
            params: dict[str, Any] = {
                "search_query": f"all:{query}",
                "start": start,
                "max_results": min(batch_size, max_results - len(results)),
                "sortBy": "relevance",
                "sortOrder": "descending",
            }

            try:
                resp = await client.get(BASE_URL, params=params)
            except httpx.RequestError as e:
                print(f"[arxiv] Request error: {e}")
                break

            if resp.status_code == 429:
                if consecutive_429 < len(_RETRY_DELAYS):
                    delay = _RETRY_DELAYS[consecutive_429]
                    msg = (
                        f"Rate limited. Waiting {delay}s before retry..."
                        if consecutive_429 == 0
                        else f"Rate limited again. Waiting {delay}s before retry..."
                    )
                    print(f"[arxiv] {msg}")
                    if progress_cb:
                        progress_cb("arxiv", msg)
                    consecutive_429 += 1
                    await asyncio.sleep(delay)
                    continue
                else:
                    msg = "Skipped after repeated 429 errors. Continuing with other sources."
                    print(f"[arxiv] {msg}")
                    if progress_cb:
                        progress_cb("arxiv", msg)
                    _rate_limited = True
                    break

            if not resp.is_success:
                print(f"[arxiv] HTTP {resp.status_code} error")
                break

            consecutive_429 = 0
            entries = _parse_feed(resp.text)
            if not entries:
                break

            results.extend(from_arxiv(e) for e in entries if e.get("title"))
            start += len(entries)

            if len(entries) < batch_size:
                break

            await asyncio.sleep(3.0)  # arXiv requests ≥3s between calls

    if _rate_limited:
        raise RateLimitedError("arXiv: gave up after repeated 429 responses")
    return results[:max_results]


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------

def _parse_feed(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"[arxiv] XML parse error: {e}")
        return []

    entries = []
    for entry in root.findall("atom:entry", _NS):
        entries.append(_parse_entry(entry))
    return entries


def _parse_entry(entry: ET.Element) -> dict:
    # arXiv ID
    raw_id = _text(entry, "atom:id")
    arxiv_id = None
    if raw_id:
        m = re.search(r"arxiv\.org/abs/([^\s/v]+)", raw_id)
        if m:
            arxiv_id = m.group(1)

    # Published year
    published = _text(entry, "atom:published") or ""
    year = int(published[:4]) if len(published) >= 4 else None

    # Authors
    authors = [
        _text(a, "atom:name") or ""
        for a in entry.findall("atom:author", _NS)
    ]

    # DOI (may be absent on preprints)
    doi_el = entry.find("arxiv:doi", _NS)
    doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None

    return {
        "title": (_text(entry, "atom:title") or "").replace("\n", " ").strip(),
        "abstract": (_text(entry, "atom:summary") or "").replace("\n", " ").strip(),
        "authors": [a for a in authors if a],
        "year": year,
        "arxiv_id": arxiv_id,
        "doi": doi,
        "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else raw_id,
    }


def _text(el: ET.Element, tag: str) -> str | None:
    child = el.find(tag, _NS)
    return child.text.strip() if child is not None and child.text else None
