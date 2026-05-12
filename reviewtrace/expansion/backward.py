"""Backward citation fetcher — retrieves the references of a paper."""

from reviewtrace.db import connection as db
from reviewtrace.retrieval.models import PaperMetadata


def _s2_identifier(paper: dict) -> str | None:
    """Return the best S2-compatible identifier for a DB paper record."""
    if paper.get("s2_paper_id"):
        return paper["s2_paper_id"]
    if paper.get("doi"):
        return f"DOI:{paper['doi']}"
    if paper.get("arxiv_id"):
        return f"arXiv:{paper['arxiv_id']}"
    return None


async def fetch_references(paper_id: str, limit: int = 30) -> list[PaperMetadata]:
    """Fetch papers referenced by paper_id (backward citations).

    paper_id is our internal hash ID. We resolve it to an S2 identifier
    via DOI, arXiv ID, or stored s2_paper_id.
    Returns empty list if the paper cannot be resolved or S2 has no data.
    """
    from reviewtrace.retrieval.clients.semantic_scholar import get_references

    record = db.get_paper_by_id(paper_id)
    if record is None:
        return []

    s2_id = _s2_identifier(record)
    if s2_id is None:
        return []

    return await get_references(s2_id, limit=limit)
