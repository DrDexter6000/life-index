"""Semantic baseline computation for adaptive similarity threshold.

During index rebuild, compute P25 of the "random-doc-vs-all-docs" cosine
distribution. This baseline reflects how similar randomly chosen documents
are to each other in the embedding space.
"""

from typing import Any

import numpy as np


def compute_semantic_baseline(
    vectors: dict[str, dict[str, Any]], sample_size: int = 50, seed: int = 42
) -> float:
    """Compute P25 of max-cosine distribution from doc embeddings.

    Algorithm:
    1. Randomly sample `sample_size` doc embeddings as pseudo-queries
    2. For each pseudo-query, compute cosine similarity vs ALL other docs, take max
    3. Return P25 percentile of this max-cosine distribution

    Args:
        vectors: dict from SimpleVectorIndex.vectors {path: {"embedding": [...], "date": ..., ...}}
        sample_size: number of pseudo-queries to sample
        seed: random seed for reproducibility

    Returns:
        P25 percentile value (float). Returns 0.0 if insufficient data.
    """
    if len(vectors) < 5 or sample_size <= 0:
        return 0.0

    normalized_embeddings: list[np.ndarray] = []
    for data in vectors.values():
        embedding = data.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            continue

        vector = np.asarray(embedding, dtype=np.float32)
        if vector.ndim != 1 or vector.size == 0:
            continue

        norm = float(np.linalg.norm(vector))
        if norm <= 1e-8:
            continue

        normalized_embeddings.append(vector / norm)

    total_docs = len(normalized_embeddings)
    if total_docs < 5:
        return 0.0

    embedding_matrix = np.vstack(normalized_embeddings)
    rng = np.random.default_rng(seed)
    sample_indices = rng.choice(
        total_docs, size=min(sample_size, total_docs), replace=False
    )

    max_scores: list[float] = []
    for index in sample_indices:
        similarities = embedding_matrix @ embedding_matrix[index]
        similarities[index] = -1.0  # exclude self-match
        max_scores.append(float(np.max(similarities)))

    if not max_scores:
        return 0.0

    return float(np.percentile(np.asarray(max_scores, dtype=np.float32), 25))
