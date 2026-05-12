"""Load seed papers from a text file and fetch their metadata.

File format (one entry per line, # = comment):
  2309.05144              # bare arXiv ID
  arXiv:2309.05144        # explicit arXiv prefix
  DOI:10.1234/xxx         # DOI
  10.1234/xxx             # bare DOI (must contain '/')

Fetches metadata from Semantic Scholar and inserts papers into DB,
tagged with retrieval_reason = 'seed'.
"""

import asyncio
import uuid
from pathlib import Path

import httpx

from reviewtrace.audit import logger as audit
from reviewtrace.db import connection as db
from reviewtrace.retrieval.models import PaperMetadata, SearchQuery
from reviewtrace.retrieval.normalizer import from_semantic_scholar

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_FIELDS = "title,authors,year,externalIds,venue,abstract,citationCount,referenceCount,url"


def load_seeds(seeds_file: Path) -> list[str]:
    """Load seed paper IDs from file. Returns list of internal paper IDs."""
    if not seeds_file.exists():
        print(f"[seed_loader] Seeds file not found: {seeds_file}")
        return []

    ids = []
    for line in seeds_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ids.append(line)

    if not ids:
        return []

    print(f"[seed_loader] Loading {len(ids)} seed papers…")
    papers = asyncio.run(_fetch_seeds(ids))

    seed_ids = []
    for paper in papers:
        db.insert_paper(paper.to_db_dict())
        run_id = _record_seed_run(paper)
        _record_seed_retrieval(paper, run_id)
        seed_ids.append(paper.id)

    print(f"[seed_loader] {len(seed_ids)} seed papers loaded.")
    return seed_ids


async def _fetch_seeds(raw_ids: list[str]) -> list[PaperMetadata]:
    headers = {}
    from reviewtrace.config.settings import SEMANTIC_SCHOLAR_API_KEY
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

    papers = []
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        for raw in raw_ids:
            s2_id = _to_s2_id(raw)
            try:
                resp = await client.get(
                    f"{_S2_BASE}/paper/{s2_id}",
                    params={"fields": _FIELDS},
                )
                if resp.status_code == 404:
                    print(f"[seed_loader] Not found: {raw}")
                    continue
                resp.raise_for_status()
                paper = from_semantic_scholar(resp.json())
                papers.append(paper)
            except Exception as e:
                print(f"[seed_loader] Error fetching {raw}: {e}")
    return papers


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
