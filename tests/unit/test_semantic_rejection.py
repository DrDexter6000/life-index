#!/usr/bin/env python3
"""Task 4.3 RED: Semantic rejection tightening.

When FTS=0 and semantic top result confidence ≤ medium, set no_confident_match=true.
Current logic: reject only when ALL results have low/none confidence.
Phase 4 tightening: reject when FTS=0 and top semantic ≤ medium, even if some
results have medium confidence.

Run BEFORE implementation to verify RED phase.
"""

import pytest

from tools.search_journals.confidence import compute_no_confident_match


# ── Test 1: FTS=0 + top confidence=low → reject ────────────────────────


def test_fts_zero_top_low_confidence_rejects() -> None:
    """FTS=0 + top result confidence=low → no_confident_match=True."""
    results = [
        {"path": "/a.md", "confidence": "low", "fts_score": 0.0, "semantic_score": 20.0},
    ]
    assert compute_no_confident_match(results) is True


# ── Test 2: FTS=0 + top confidence=medium → reject ─────────────────────


def test_fts_zero_top_medium_confidence_rejects() -> None:
    """FTS=0 + top result confidence=medium → no_confident_match=True.

    Phase 4 tightening: even medium confidence is rejected when FTS=0.
    """
    results = [
        {"path": "/a.md", "confidence": "medium", "fts_score": 0.0, "semantic_score": 50.0},
        {"path": "/b.md", "confidence": "medium", "fts_score": 0.0, "semantic_score": 45.0},
    ]
    assert compute_no_confident_match(results) is True


# ── Test 3: FTS=0 + top confidence=high → accept ───────────────────────


def test_fts_zero_top_high_confidence_accepts() -> None:
    """FTS=0 + top result confidence=high → no_confident_match=False.

    High semantic confidence is enough to accept.
    """
    results = [
        {"path": "/a.md", "confidence": "high", "fts_score": 0.0, "semantic_score": 80.0},
    ]
    assert compute_no_confident_match(results) is False


# ── Test 4: FTS>0 + weak semantic → accept ─────────────────────────────


def test_fts_present_weak_semantic_accepts() -> None:
    """FTS>0 + weak semantic → no_confident_match=False.

    When FTS has results, we don't reject even with weak semantic.
    """
    results = [
        {"path": "/a.md", "confidence": "low", "fts_score": 30.0, "semantic_score": 10.0},
        {"path": "/b.md", "confidence": "medium", "fts_score": 25.0, "semantic_score": 15.0},
    ]
    assert compute_no_confident_match(results) is False


# ── Test 5: "量子计算机编程" scenario → reject ──────────────────────────


def test_quantum_computing_irrelevant_query_rejects() -> None:
    """Simulating '量子计算机编程' scenario: no FTS, weak semantic match."""
    results = [
        {"path": "/x.md", "confidence": "low", "fts_score": 0.0, "semantic_score": 25.0},
    ]
    assert compute_no_confident_match(results) is True


# ── Test 6: empty results → reject ─────────────────────────────────────


def test_empty_results_rejects() -> None:
    """Empty results → no_confident_match=True."""
    assert compute_no_confident_match([]) is True


# ── Test 7: FTS=0 + mixed confidence levels, top is medium → reject ────


def test_fts_zero_mixed_confidence_top_medium_rejects() -> None:
    """FTS=0 + top is medium, some low below → reject (Phase 4 tightening)."""
    results = [
        {"path": "/a.md", "confidence": "medium", "fts_score": 0.0, "semantic_score": 48.0},
        {"path": "/b.md", "confidence": "low", "fts_score": 0.0, "semantic_score": 20.0},
    ]
    # Old logic: not all low → False. New logic: FTS=0 + top ≤ medium → True
    assert compute_no_confident_match(results) is True
