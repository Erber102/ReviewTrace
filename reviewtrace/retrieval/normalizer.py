"""Normalize raw API responses into PaperMetadata.

Each source has its own _from_* function. Author names are canonicalized
to "LastName F" format (last name + first initial).
"""

import re
from typing import Any

from reviewtrace.retrieval.models import PaperMetadata

# ---------------------------------------------------------------------------
# Author name normalization
# ---------------------------------------------------------------------------

def normalize_author(name: str) -> str:
    """
    Convert various author name formats to 'LastName F'.

    Handles:
      - "Alice Smith"         → "Smith A"
      - "Smith, Alice"        → "Smith A"
      - "A. Smith"            → "Smith A"
      - "Smith, A."           → "Smith A"
      - "Alice B. Smith"      → "Smith A"
      - Single-word names stay as-is.
    """
    name = name.strip()
    if not name:
        return name

    # "Last, First" format
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        last = parts[0]
        first = parts[1] if len(parts) > 1 else ""
    else:
        tokens = name.split()
        if len(tokens) == 1:
            return tokens[0]
        last = tokens[-1]
        first = tokens[0]

    # Extract first initial (skip initials-only tokens like "A.")
    first_initial = ""
    for token in re.split(r"[\s.]+", first):
        token = token.strip(".")
        if token:
            first_initial = token[0].upper()
            break

    if first_initial:
        return f"{last} {first_initial}"
    return last


def normalize_authors(raw_authors: list[Any]) -> list[str]:
    """Normalize a list of author name strings or dicts."""
    result = []
    for a in raw_authors:
        if isinstance(a, str):
            result.append(normalize_author(a))
        elif isinstance(a, dict):
            # OpenAlex: {"author": {"display_name": "..."}}
            # S2:       {"name": "..."}
            name = (
                a.get("display_name")
                or (a.get("author") or {}).get("display_name")
                or a.get("name")
                or ""
            )
            if name:
                result.append(normalize_author(name))
    return result


# ---------------------------------------------------------------------------
# Per-source normalizers
# ---------------------------------------------------------------------------

def from_openalex(raw: dict) -> PaperMetadata:
    doi = raw.get("doi")
    if doi:
        doi = doi.replace("https://doi.org/", "").strip()

    abstract = _reconstruct_openalex_abstract(raw.get("abstract_inverted_index") or {})

    primary_loc = raw.get("primary_location") or {}
    source = primary_loc.get("source") or {}
    venue = source.get("display_name")

    best_oa = raw.get("best_oa_location") or {}
    url = best_oa.get("pdf_url") or best_oa.get("landing_page_url") or raw.get("id")

    return PaperMetadata(
        title=(raw.get("title") or "").strip(),
        authors=normalize_authors(raw.get("authorships") or []),
        year=raw.get("publication_year"),
        doi=doi or None,
        arxiv_id=_extract_arxiv_id_from_openalex(raw),
        venue=venue,
        abstract=abstract or None,
        url=url,
        citation_count=raw.get("cited_by_count"),
        reference_count=raw.get("referenced_works_count"),
        raw_source="openalex",
        raw_id=raw.get("id"),
    )


def from_semantic_scholar(raw: dict) -> PaperMetadata:
    external = raw.get("externalIds") or {}
    doi = external.get("DOI")
    arxiv_id = external.get("ArXiv")

    authors = [a.get("name", "") for a in (raw.get("authors") or [])]

    return PaperMetadata(
        title=(raw.get("title") or "").strip(),
        authors=normalize_authors([{"name": a} for a in authors]),
        year=raw.get("year"),
        doi=doi,
        arxiv_id=arxiv_id,
        venue=raw.get("venue"),
        abstract=raw.get("abstract"),
        url=raw.get("url"),
        citation_count=raw.get("citationCount"),
        reference_count=raw.get("referenceCount"),
        raw_source="semantic_scholar",
        raw_id=raw.get("paperId"),
    )


def from_arxiv(raw: dict) -> PaperMetadata:
    """raw is the parsed dict from _parse_arxiv_entry."""
    return PaperMetadata(
        title=(raw.get("title") or "").strip(),
        authors=normalize_authors([{"name": a} for a in (raw.get("authors") or [])]),
        year=raw.get("year"),
        doi=raw.get("doi"),
        arxiv_id=raw.get("arxiv_id"),
        venue=None,
        abstract=(raw.get("abstract") or "").strip() or None,
        url=raw.get("url"),
        citation_count=None,
        reference_count=None,
        raw_source="arxiv",
        raw_id=raw.get("arxiv_id"),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reconstruct_openalex_abstract(inverted_index: dict[str, list[int]]) -> str:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    max_pos = max(pos for positions in inverted_index.values() for pos in positions)
    words: list[str] = [""] * (max_pos + 1)
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(w for w in words if w)


def _extract_arxiv_id_from_openalex(raw: dict) -> str | None:
    for loc in raw.get("locations") or []:
        src = (loc.get("source") or {})
        if "arxiv" in (src.get("host_organization_lineage_names") or []):
            url = loc.get("landing_page_url") or ""
            m = re.search(r"arxiv\.org/abs/([^\s/]+)", url)
            if m:
                return m.group(1)
    return None
