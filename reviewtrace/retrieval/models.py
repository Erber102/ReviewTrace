"""Core data models for the retrieval layer."""

import hashlib
import json
from dataclasses import dataclass, field


@dataclass
class PaperMetadata:
    title: str
    authors: list[str]
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    venue: str | None = None
    abstract: str | None = None
    source_type: str | None = None
    url: str | None = None
    citation_count: int | None = None
    reference_count: int | None = None
    raw_source: str = ""
    raw_id: str | None = None

    @property
    def id(self) -> str:
        """Stable ID: prefer DOI, then arXiv ID, then title hash."""
        if self.doi:
            key = f"doi:{self.doi.lower().strip()}"
        elif self.arxiv_id:
            key = f"arxiv:{self.arxiv_id.lower().strip()}"
        else:
            key = f"title:{self.title.lower().strip()}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def to_db_dict(self) -> dict:
        return {
            "id": self.id,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "s2_paper_id": self.raw_id if self.raw_source == "semantic_scholar" else None,
            "title": self.title,
            "authors": json.dumps(self.authors),
            "year": self.year,
            "venue": self.venue,
            "abstract": self.abstract,
            "source_type": self.source_type,
            "url": self.url,
            "citation_count": self.citation_count,
            "reference_count": self.reference_count,
        }


@dataclass
class SearchQuery:
    query: str
    source: str               # openalex / semantic_scholar / arxiv / all
    expansion_type: str       # keyword / backward_citation / forward_citation / author
    max_results: int = 50
    metadata: dict = field(default_factory=dict)  # extra context (e.g. seed_paper_id)
