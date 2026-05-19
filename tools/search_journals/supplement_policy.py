#!/usr/bin/env python3
"""Weak-keyword supplement proxy helpers.

This module contains deterministic, test-covered private helpers for deciding
whether keyword search results look weak enough to merit future semantic
pipeline supplementation.

The accepted proxy is based on max keyword FTS score, not title-query overlap:
keyword results supplement when the strongest known FTS score is at or below
the default threshold of 76.0.

This module is **not wired into public/default search behavior**. It exports
pure private helpers for a future supplement policy path.
"""

from __future__ import annotations

from typing import Any, Iterable

_SCORE_KEYS = ("fts_score", "relevance", "relevance_score")


def _coerce_non_negative_float(value: Any) -> float:
    """Convert a score-like value to a non-negative float."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0

    return score if score > 0.0 else 0.0


def _candidate_fts_scores(result: dict[str, Any]) -> Iterable[float]:
    """Yield score candidates from known keyword result shapes."""
    for key in _SCORE_KEYS:
        if key in result:
            yield _coerce_non_negative_float(result.get(key))

    explain = result.get("explain")
    if not isinstance(explain, dict):
        return

    keyword_pipeline = explain.get("keyword_pipeline")
    if isinstance(keyword_pipeline, dict):
        yield _coerce_non_negative_float(keyword_pipeline.get("fts_score"))


def _max_fts_score(keyword_results: list[dict[str, Any]]) -> float:
    """Return the strongest known FTS score across keyword results."""
    return max(
        (score for result in keyword_results for score in _candidate_fts_scores(result)),
        default=0.0,
    )


def _should_supplement(
    keyword_results: list[dict[str, Any]],
    *,
    max_fts_threshold: float = 76.0,
) -> bool:
    """Return True when keyword results should receive semantic supplement."""
    if not keyword_results:
        return True

    return _max_fts_score(keyword_results) <= max_fts_threshold
