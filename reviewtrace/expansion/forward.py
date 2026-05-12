"""Forward citation fetcher — retrieves papers that cite a given paper."""

from reviewtrace.db import connection as db
from reviewtrace.expansion.backward import _s2_identifier
from reviewtrace.retrieval.models import PaperMetadata


async def fetch_citations(paper_id: str, limit: int = 30) -> list[PaperMetadata]:
    """Fetch papers that cite paper_id (forward citations).

    paper_id is our internal hash ID. Resolution follows the same
    DOI / arXiv ID / s2_paper_id priority as backward citations.
    Returns empty list if the paper cannot be resolved.
    """
    from reviewtrace.retrieval.clients.semantic_scholar import get_citations

    record = db.get_paper_by_id(paper_id)
    if record is None:
        return []

    s2_id = _s2_identifier(record)
    if s2_id is None:
        return []

    return await get_citations(s2_id, limit=limit)
