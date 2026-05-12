"""Paper and text embedding via sentence-transformers.

Default model: allenai/specter2_base (paper embedding SOTA).
Falls back to all-MiniLM-L6-v2 if SPECTER2 fails to load.
Model is cached in memory across calls in the same process.
"""

import numpy as np

from reviewtrace.config.settings import EMBEDDING_MODEL

_MODEL_CACHE = None


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of strings. Returns (n, dim) float32 array."""
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    model = _get_model()
    return model.encode(
        texts,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,  # pre-normalize for fast cosine via dot product
    )


def cosine_similarity_matrix(query: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """
    query:  (dim,) — single query vector (assumed normalized)
    corpus: (n, dim) — corpus vectors (assumed normalized)
    returns (n,) cosine similarity scores
    """
    return corpus @ query


def top_k_indices(query: np.ndarray, corpus: np.ndarray, k: int) -> list[int]:
    """Return indices of top-k most similar corpus vectors to query."""
    if len(corpus) == 0:
        return []
    scores = cosine_similarity_matrix(query, corpus)
    k = min(k, len(scores))
    return np.argsort(scores)[::-1][:k].tolist()


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _get_model():
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    from sentence_transformers import SentenceTransformer

    try:
        _MODEL_CACHE = SentenceTransformer(EMBEDDING_MODEL)
        print(f"[embedder] Loaded model: {EMBEDDING_MODEL}")
    except Exception as e:
        fallback = "all-MiniLM-L6-v2"
        print(f"[embedder] Could not load {EMBEDDING_MODEL}: {e}. Falling back to {fallback}")
        _MODEL_CACHE = SentenceTransformer(fallback)

    return _MODEL_CACHE
