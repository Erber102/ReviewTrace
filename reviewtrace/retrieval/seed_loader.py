"""Load seed papers from a text file and fetch their metadata.

File format (one entry per line, # = comment):
  2309.05144              # bare arXiv ID
  arXiv:2309.05144        # explicit arXiv prefix
  DOI:10.1234/xxx         # DOI
  10.1234/xxx             # bare DOI (must contain '/')

Attempts to fetch full metadata from Semantic Scholar. If a lookup fails
(no API key, rate limit, 404, network error), a minimal stub record is
inserted instead so the seed ID is still tracked and can anchor citation
expansion.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from pathlib import Path

import httpx

from reviewtrace.audit import logger as audit
from reviewtrace.db import connection as db
from reviewtrace.retrieval.models import PaperMetadata, SearchQuery
from reviewtrace.retrieval.normalizer import from_semantic_scholar

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_FIELDS = "title,authors,year,externalIds,venue,abstract,citationCount,referenceCount,url"

ProgressCb = Callable[[str], None]


def load_seeds(
    seeds_file: Path,
    progress_cb: ProgressCb | None = None,
) -> list[str]:
    """Load seed paper IDs from file. Returns list of internal paper IDs.

    For each identifier that cannot be resolved via Semantic Scholar, a
    minimal stub record is inserted so the seed is retained and can be
    used as a citation-expansion anchor.
    """
    def _log(msg: str) -> None:
        print(f"[seed_loader] {msg}")
        if progress_cb:
            progress_cb(msg)

    if not seeds_file.exists():
        _log(f"Seeds file not found: {seeds_file}")
        return []

    raw_ids: list[str] = []
    for line in seeds_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        raw_ids.append(line)

    if not raw_ids:
        _log("Seeds file is empty — skipping")
        return []

    _log(f"{len(raw_ids)} seed identifier(s) provided")

    from reviewtrace.config.settings import SEMANTIC_SCHOLAR_API_KEY
    if not SEMANTIC_SCHOLAR_API_KEY:
        _log(
            "No SEMANTIC_SCHOLAR_API_KEY configured — "
            "S2 metadata lookup may be rate-limited or unavailable"
        )

    resolved, failed = asyncio.run(_fetch_seeds(raw_ids))

    seed_ids: list[str] = []

    for paper in resolved:
        db.insert_paper(paper.to_db_dict())
        run_id = _record_seed_run(paper)
        _record_seed_retrieval(paper, run_id)
        seed_ids.append(paper.id)

    if resolved:
        _log(f"{len(resolved)} seed metadata record(s) resolved")

    if failed:
        _log(
            f"{len(resolved)} of {len(raw_ids)} metadata records resolved — "
            f"{len(failed)} unresolved"
        )
        stubs = [_make_stub(raw) for raw in failed]
        for stub in stubs:
            db.insert_paper(stub.to_db_dict())
            run_id = _record_seed_run(stub)
            _record_seed_retrieval(stub, run_id)
            seed_ids.append(stub.id)
        _log(f"{len(stubs)} unresolved seed stub(s) retained")
    elif not resolved:
        _log("0 seed metadata records resolved")
        _log("Continuing without resolved seed metadata")

    return seed_ids


async def _fetch_seeds(
    raw_ids: list[str],
) -> tuple[list[PaperMetadata], list[str]]:
    """Fetch metadata from S2. Returns (resolved, failed_raw_ids)."""
    headers: dict[str, str] = {}
    from reviewtrace.config.settings import SEMANTIC_SCHOLAR_API_KEY
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

    resolved: list[PaperMetadata] = []
    failed: list[str] = []

    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        for raw in raw_ids:
            s2_id = _to_s2_id(raw)
            try:
                resp = await client.get(
                    f"{_S2_BASE}/paper/{s2_id}",
                    params={"fields": _FIELDS},
                )
                if resp.status_code == 404:
                    print(f"[seed_loader] Not found on S2: {raw} — will insert stub")
                    failed.append(raw)
                    continue
                if resp.status_code == 429:
                    print(f"[seed_loader] Rate limited fetching {raw} — will insert stub")
                    failed.append(raw)
                    continue
                resp.raise_for_status()
                paper = from_semantic_scholar(resp.json())
                resolved.append(paper)
            except Exception as e:
                print(f"[seed_loader] Error fetching {raw}: {e} — will insert stub")
                failed.append(raw)

    return resolved, failed


def _make_stub(raw: str) -> PaperMetadata:
    """Create a minimal PaperMetadata stub for an unresolved seed identifier."""
    arxiv_id: str | None = None
    doi: str | None = None

    normalized = raw.strip()
    if normalized.lower().startswith("arxiv:"):
        arxiv_id = normalized[6:]
    elif normalized.lower().startswith("doi:"):
        doi = normalized[4:]
    elif normalized.startswith("10.") or "/" in normalized:
        doi = normalized
    else:
        # Bare arXiv ID: digits, dots, hyphens only
        if "/" not in normalized:
            arxiv_id = normalized

    return PaperMetadata(
        title=f"[Seed] {raw}",
        authors=[],
        arxiv_id=arxiv_id,
        doi=doi,
        source_type="unknown",
        url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
    )


def _to_s2_id(raw: str) -> str:
    """Convert user-supplied ID to S2 API format."""
    raw = raw.strip()
    if raw.lower().startswith("arxiv:"):
        return f"arXiv:{raw[6:]}"
    if raw.lower().startswith("doi:"):
        return f"DOI:{raw[4:]}"
    # bare arXiv ID: digits/dots with no slash
    if "/" not in raw and raw.replace(".", "").replace("-", "").isalnum():
        return f"arXiv:{raw}"
    # bare DOI
    if raw.startswith("10."):
        return f"DOI:{raw}"
    return raw


def _record_seed_run(paper: PaperMetadata) -> str:
    run_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO retrieval_runs (id, query, source, expansion_type, status, result_count)
        VALUES (?, ?, 'seed', 'seed', 'done', 1)
        """,
        (run_id, f"seed:{paper.id}"),
    )
    return run_id


def _record_seed_retrieval(paper: PaperMetadata, run_id: str) -> None:
    query = SearchQuery(
        query=f"seed:{paper.id}",
        source="seed",
        expansion_type="seed",
    )
    audit.log_paper_found(paper, run_id, query)
