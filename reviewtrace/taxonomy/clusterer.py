"""Paper clustering via KMeans.

k = max(5, n_papers // 8)  — hard-coded per plan.
Returns cluster assignments as a list of ints (one per paper).
"""

import numpy as np
from sklearn.cluster import KMeans


def cluster_papers(embeddings: np.ndarray, n_papers: int | None = None) -> list[int]:
    """
    Cluster paper embeddings. k is derived from paper count.

    embeddings: (n, dim) float32 array
    returns:    list of cluster IDs, length n
    """
    n = len(embeddings)
    if n == 0:
        return []

    k = _choose_k(n_papers if n_papers is not None else n)
    k = min(k, n)  # can't have more clusters than papers

    km = KMeans(n_clusters=k, random_state=42, n_init="auto")
    labels = km.fit_predict(embeddings)
    return labels.tolist()


def _choose_k(n: int) -> int:
    return max(5, n // 8)
