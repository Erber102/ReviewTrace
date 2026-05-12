"""Search query planner.

Generates a diverse set of SearchQuery objects from a topic string and
optional seed abstracts. Uses Claude for keyword synonym expansion.
"""

import json

from reviewtrace.config.settings import LLM_PROVIDER
from reviewtrace.retrieval.models import SearchQuery

# OpenAlex and arXiv are primary: all expanded keywords are sent to both.
# Semantic Scholar is secondary: only the base topic is queried here.
# S2 is better leveraged via citation expansion (backward/forward references).
_PRIMARY_SOURCES = ["openalex", "arxiv"]
_SECONDARY_SOURCES = ["semantic_scholar"]


def plan_queries(
    topic: str,
    seed_abstracts: list[str] | None = None,
    max_results_per_query: int = 50,
) -> list[SearchQuery]:
    """
    Generate search queries across all sources.

    Primary (OpenAlex, arXiv): topic + all LLM-expanded keywords.
    Secondary (Semantic Scholar): topic only — S2's main role is citation expansion.
    """
    keywords = _expand_keywords(topic, seed_abstracts or [])
    queries: list[SearchQuery] = []

    for kw in keywords:
        for source in _PRIMARY_SOURCES:
            queries.append(
                SearchQuery(
                    query=kw,
                    source=source,
                    expansion_type="keyword",
                    max_results=max_results_per_query,
                )
            )

    # S2: base topic only
    queries.append(
        SearchQuery(
            query=topic,
            source="semantic_scholar",
            expansion_type="keyword",
            max_results=max_results_per_query,
        )
    )

    return queries


def _expand_keywords(topic: str, seed_abstracts: list[str]) -> list[str]:
    """Ask the configured LLM to generate 8 related search terms. Falls back to topic-only."""
    if not LLM_PROVIDER:
        return [topic]

    abstract_block = ""
    if seed_abstracts:
        samples = seed_abstracts[:3]
        abstract_block = "\n\nSeed paper abstracts for context:\n" + "\n---\n".join(samples)

    prompt = (
        f"You are helping build a systematic literature review search strategy.\n"
        f"Topic: {topic}{abstract_block}\n\n"
        f"Generate exactly 8 search terms or short phrases that would find papers "
        f"relevant to this topic. Include synonyms, related concepts, and narrower "
        f"sub-topics. Return a JSON array of strings, nothing else.\n"
        f'Example: ["term1", "term2", ...]'
    )

    try:
        from reviewtrace.llm import complete

        raw = complete(prompt, max_tokens=512).strip()
        expanded: list[str] = json.loads(raw)
        if isinstance(expanded, list):
            return [topic] + [str(k) for k in expanded if k]
    except Exception as e:
        print(f"[planner] LLM expansion failed: {e}")

    return [topic]
