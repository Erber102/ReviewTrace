"""Typed exceptions for the retrieval layer."""


class RateLimitedError(Exception):
    """Raised when a source returns persistent 429 responses and gives up."""


class SkippedError(Exception):
    """Raised when a source query is intentionally skipped (e.g. no API key)."""
