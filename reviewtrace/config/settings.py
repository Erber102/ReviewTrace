"""Runtime configuration loaded from environment variables.

A .env file in the project root is loaded automatically if present.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)

# ── Paper API keys ─────────────────────────────────────────────────────────────

# Semantic Scholar API key — free at https://www.semanticscholar.org/product/api
# Without a key the API still works but rate limits are tighter (1 req/sec).
SEMANTIC_SCHOLAR_API_KEY: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

# OpenAlex polite pool: include your email for higher rate limits (optional)
OPENALEX_EMAIL: str = os.getenv("OPENALEX_EMAIL", "")

# ── LLM provider selection ────────────────────────────────────────────────────

# Which LLM provider to use: anthropic | openai | google | deepseek
LLM_PROVIDER: str = os.getenv("REVIEWTRACE_LLM_PROVIDER", "anthropic")

# Model name passed to the chosen provider
_PROVIDER_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "google": "gemini-2.0-flash",
    "deepseek": "deepseek-v4-pro",
}
LLM_MODEL: str = os.getenv("REVIEWTRACE_LLM_MODEL") or _PROVIDER_DEFAULT_MODELS.get(
    LLM_PROVIDER, "claude-sonnet-4-20250514"
)

# ── LLM API keys ──────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

# ── Embedding model ───────────────────────────────────────────────────────────
# SPECTER2 is the paper-embedding SOTA; falls back to all-MiniLM-L6-v2 if unavailable.
EMBEDDING_MODEL: str = os.getenv("REVIEWTRACE_EMBEDDING_MODEL", "allenai/specter2_base")
