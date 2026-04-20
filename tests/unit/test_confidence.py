#!/usr/bin/env python3
"""Tests for D10 confidence classification rules."""

from importlib import import_module


confidence = import_module("tools.search_journals.confidence")
classify_confidence = confidence.classify_confidence
compute_no_confident_match = confidence.compute_no_confident_match


class TestClassifyConfidence:
    def test_high_dual_signal(self) -> None:
        """fts=80, sem=60 → high (fts>=70 AND sem>=55)."""
        assert (
            classify_confidence(fts_score=80, semantic_score=60, rrf_score=0.005)
            == "high"
        )

    def test_medium_fts_only(self) -> None:
        """fts=55, sem=0 → medium (fts>=50)."""
        assert (
            classify_confidence(fts_score=55, semantic_score=0, rrf_score=0.005)
            == "medium"
        )

    def test_low_weak_signals(self) -> None:
        """fts=20, sem=42 → low (no medium threshold met)."""
        assert (
            classify_confidence(fts_score=20, semantic_score=42, rrf_score=0.005)
            == "low"
        )

    def test_high_rrf_threshold(self) -> None:
        """rrf=0.020 → high (rrf>=0.018)."""
        assert (
            classify_confidence(fts_score=0, semantic_score=0, rrf_score=0.020)
            == "high"
        )

    def test_medium_rrf_threshold(self) -> None:
        """rrf=0.012 → medium (rrf>=0.010)."""
        assert (
            classify_confidence(fts_score=0, semantic_score=0, rrf_score=0.012)
            == "medium"
        )

    def test_medium_semantic_only(self) -> None:
        """sem=48 → medium (sem>=45)."""
        assert (
            classify_confidence(fts_score=0, semantic_score=48, rrf_score=0.005)
            == "medium"
        )


class TestNoConfidentMatch:
    def test_empty_results(self) -> None:
        assert compute_no_confident_match([]) is True

    def test_all_low(self) -> None:
        results = [{"confidence": "low"}, {"confidence": "low"}]
        assert compute_no_confident_match(results) is True

    def test_has_medium(self) -> None:
        # Phase 4 T4.3: FTS=0 + top confidence=low → reject (tightened)
        results = [{"confidence": "low"}, {"confidence": "medium"}]
        assert compute_no_confident_match(results) is True

    def test_has_high(self) -> None:
        results = [{"confidence": "high"}]
        assert compute_no_confident_match(results) is False

    def test_mixed_with_none(self) -> None:
        results = [{"confidence": "none"}, {"confidence": "low"}]
        assert compute_no_confident_match(results) is True
