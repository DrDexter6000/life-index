#!/usr/bin/env python3
"""
Life Index - Vector Normalization Guards
向量归一化断言守卫：防止非归一化向量静默降低余弦相似度质量。

设计决策:
- 仅采样 3 条向量（首条、末条、随机中间）而非全量校验，避免性能退化
- 发现非归一化向量时 ERROR 级别日志 + 抛异常，不静默修复
- atol=1e-6 与 embedding_backends.py 中 normalize_embeddings=True 的精度一致
"""

from __future__ import annotations

import logging
import random
from typing import Dict, Sequence

import numpy as np

logger = logging.getLogger(__name__)


class VectorNotNormalizedError(Exception):
    """Raised when stored vectors fail the unit-norm assertion.

    Attributes:
        details: Per-sample diagnostic dict with index, norm, expected=1.0.
    """

    def __init__(self, message: str, details: list[Dict[str, float]]) -> None:
        self.details = details
        super().__init__(message)


def _assert_normalized_sample(
    vectors: Sequence[Sequence[float]],
    sample_indices: tuple[int, ...] = (0, -1),
    atol: float = 1e-6,
) -> None:
    """Assert that a sample of vectors are approximately unit-normalized.

    Samples 3 vectors from *vectors* (first, last, and a random middle one)
    and checks ``np.linalg.norm(vec) ≈ 1.0`` for each.  On failure, logs
    at ERROR level and raises :class:`VectorNotNormalizedError`.

    Args:
        vectors: Full set of stored embedding vectors (list of float lists).
        sample_indices: ``(first_offset, last_offset)`` — kept for
            backward-compat / testability; the function always checks
            first, last, and one random middle vector.
        atol: Absolute tolerance for the norm check.  Must not exceed 1e-6
            without an ADR.

    Raises:
        VectorNotNormalizedError: If any sampled vector has norm outside
            ``[1.0 - atol, 1.0 + atol]``.
    """
    n = len(vectors)
    if n == 0:
        return

    # Build sample indices: first, last, random middle
    indices_to_check: list[int] = [0]
    if n > 1:
        indices_to_check.append(n - 1)
    if n > 2:
        mid = random.randint(1, n - 2)
        indices_to_check.append(mid)

    bad_samples: list[Dict[str, float]] = []

    for idx in indices_to_check:
        vec = np.asarray(vectors[idx], dtype=np.float64)
        norm = float(np.linalg.norm(vec))
        if not np.isclose(norm, 1.0, atol=atol):
            bad_samples.append({"index": float(idx), "norm": norm, "expected": 1.0})

    if bad_samples:
        msg = (
            f"Vector normalization check failed for {len(bad_samples)}/{len(indices_to_check)} "
            f"samples. Details: {bad_samples}"
        )
        logger.error("E0605 VECTOR_NOT_NORMALIZED: %s", msg)
        raise VectorNotNormalizedError(msg, bad_samples)


def check_vector_index_normalized(
    index_vectors: Dict[str, Dict],
) -> None:
    """Convenience wrapper: extract embeddings from a SimpleVectorIndex-style
    dict and run the normalization assertion.

    Args:
        index_vectors: ``SimpleVectorIndex.vectors`` dict where each value
            has an ``"embedding"`` key containing a list[float].

    Raises:
        VectorNotNormalizedError: On failure.
    """
    if not index_vectors:
        return

    embeddings = [v["embedding"] for v in index_vectors.values() if "embedding" in v]
    _assert_normalized_sample(embeddings)


__all__ = [
    "VectorNotNormalizedError",
    "_assert_normalized_sample",
    "check_vector_index_normalized",
]
