#!/usr/bin/env python3
"""Confidence classification for search results (D10 absolute rules).

Provides deterministic, reproducible confidence labels for each merged result.
Same input always produces same output — no randomness or model calls.
"""

from __future__ import annotations

from typing import Literal

ConfidenceLevel = Literal["high", "medium", "low"]


def classify_confidence(
    *,
    fts_score: float,
    semantic_score: float,
    rrf_score: float,
) -> ConfidenceLevel:
    """Classify a single result's confidence using D10 absolute rules.

    Args:
        fts_score: FTS/BM25 relevance score (0-100 scale)
        semantic_score: Semantic similarity score (0-100 scale, cosine*100)
        rrf_score: RRF fusion score (typically 0.01-0.05)

    Returns:
        "high", "medium", or "low"
    """
    if (fts_score >= 70 and semantic_score >= 55) or rrf_score >= 0.018:
        return "high"
    if fts_score >= 50 or semantic_score >= 45 or rrf_score >= 0.010:
        return "medium"
    return "low"


def compute_no_confident_match(results: list[dict]) -> bool:
    """Determine if no result has confident match.

    Phase 4 T4.3 tightening: When FTS has no results (all fts_score == 0) and
    the top result's confidence is ≤ medium, reject even if some results have
    medium confidence. Only high semantic confidence overrides FTS absence.

    Old logic: reject when ALL results have low/none confidence.
    New logic: also reject when FTS=0 + top confidence ≤ medium.
    """
    if not results:
        return True

    # Check if FTS has any results (any fts_score > 0)
    has_fts = any(float(r.get("fts_score", 0.0)) > 0 for r in results)

    # If FTS has results, use per-result confidence (old logic)
    if has_fts:
        return all(result.get("confidence") in {"low", "none"} for result in results)

    # Phase 4 tightening: FTS=0, check top result confidence
    top_confidence = results[0].get("confidence", "none")
    return top_confidence in {"low", "medium", "none"}
