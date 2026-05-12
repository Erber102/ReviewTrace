"""Rule-based source type classifier.

Returns one of: peer_reviewed | preprint | workshop | blog | grey_literature | unknown

No ML — purely based on venue name, DOI presence, and arXiv ID.
"""

# Major peer-reviewed venues (lowercase). Extend as needed.
_KNOWN_PEER_REVIEWED: set[str] = {
    # ML conferences
    "neurips", "nips", "advances in neural information processing systems",
    "icml", "international conference on machine learning",
    "iclr", "international conference on learning representations",
    "cvpr", "conference on computer vision and pattern recognition",
    "iccv", "eccv",
    "aaai", "ijcai",
    "acl", "emnlp", "naacl", "coling",
    "sigkdd", "kdd", "www", "wsdm", "cikm", "sigir",
    "uai", "aistats",
    # Science journals
    "nature", "science", "cell",
    "nature machine intelligence", "nature communications",
    "pnas", "proceedings of the national academy of sciences",
    "plos one", "plos computational biology",
    "journal of machine learning research", "jmlr",
    "transactions on machine learning research", "tmlr",
    "ieee transactions on neural networks and learning systems",
    "ieee transactions on pattern analysis and machine intelligence",
    "artificial intelligence",
    "machine learning",
}

_WORKSHOP_KEYWORDS: set[str] = {
    "workshop", "ws-", "w-", "findings of", "findings",
}

_BLOG_KEYWORDS: set[str] = {
    "blog", "medium", "substack", "towards data science", "distill",
}


def classify_source(paper: dict) -> str:
    """
    Classify the source type of a paper DB record.

    Priority order:
      1. arXiv only (no DOI) → preprint
      2. Venue matches known peer-reviewed list → peer_reviewed
      3. Venue contains workshop keywords → workshop
      4. Venue contains blog keywords → blog
      5. Has DOI → peer_reviewed (most DOIs are published papers)
      6. Fallback → unknown
    """
    venue = (paper.get("venue") or "").strip()
    venue_lower = venue.lower()
    doi = paper.get("doi")
    arxiv_id = paper.get("arxiv_id")

    # arXiv preprint (no DOI means it hasn't been published elsewhere)
    if arxiv_id and not doi:
        return "preprint"

    # Workshop check first — "ICML Workshop" should not be peer_reviewed
    if venue_lower and any(kw in venue_lower for kw in _WORKSHOP_KEYWORDS):
        return "workshop"

    # Blog / grey literature
    if venue_lower and any(kw in venue_lower for kw in _BLOG_KEYWORDS):
        return "blog"

    # Known peer-reviewed venue
    if venue_lower and _matches_known(venue_lower, _KNOWN_PEER_REVIEWED):
        return "peer_reviewed"

    # DOI is a strong signal for publication
    if doi:
        return "peer_reviewed"

    return "unknown"


def _matches_known(venue_lower: str, known: set[str]) -> bool:
    """True if venue_lower exactly matches or contains a known venue name."""
    if venue_lower in known:
        return True
    return any(k in venue_lower for k in known)
