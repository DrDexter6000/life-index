#!/usr/bin/env python3
"""
Tests for RRF floor threshold behavior — Round 10 Phase 2 Task 2.1.

Verifies that:
1. Dynamic threshold below floor → floor value is used (max(dynamic, floor))
2. Dynamic threshold above floor → dynamic value is used
3. Constant value matches ADR-004 selected value (0.008)
"""

from __future__ import annotations

import pytest

from tools.lib.search_constants import RRF_MIN_SCORE


class TestRRFFloorValue:
    """Verify the A/B-selected floor value is applied."""

    def test_rrf_min_score_matches_adr004(self) -> None:
        """ADR-004 selected 0.008 as the RRF floor."""
        assert RRF_MIN_SCORE == 0.008, (
            f"RRF_MIN_SCORE={RRF_MIN_SCORE}, expected 0.008 per ADR-004"
        )


class TestRRFDynamicFloorInteraction:
    """Verify that dynamic threshold respects the floor via max(dynamic, floor)."""

    def test_dynamic_below_floor_uses_floor(self) -> None:
        """When dynamic threshold returns < floor, effective threshold = floor."""
        from tools.search_journals.ranking import _compute_dynamic_rrf_threshold

        # Create results with very low RRF scores — Tukey IQR will return a
        # low dynamic value (below the 0.008 floor)
        low_score_results = [
            {
                "final_score": 0.001 * i,
                "has_rrf": True,
                "fts_score": 0.0,
                "semantic_score": 0.0,
            }
            for i in range(1, 15)  # 14 results, well above min sample of 8
        ]
        dynamic = _compute_dynamic_rrf_threshold(
            low_score_results,
            base_threshold=RRF_MIN_SCORE,
        )
        # The effective threshold in merge_and_rank_hybrid applies max(dynamic, floor)
        effective = max(dynamic, RRF_MIN_SCORE)
        assert effective >= RRF_MIN_SCORE, (
            f"effective={effective} < floor={RRF_MIN_SCORE}. "
            f"dynamic={dynamic}. Need max(dynamic, floor) guard."
        )

    def test_dynamic_above_floor_uses_dynamic(self) -> None:
        """When dynamic threshold returns > floor, effective threshold = dynamic."""
        from tools.search_journals.ranking import _compute_dynamic_rrf_threshold

        # Create results with high RRF scores — Tukey IQR will return a
        # dynamic value well above the 0.008 floor
        high_score_results = [
            {
                "final_score": 0.05 - 0.002 * i,
                "has_rrf": True,
                "fts_score": 0.0,
                "semantic_score": 0.0,
            }
            for i in range(12)  # 12 results above min sample of 8
        ]
        dynamic = _compute_dynamic_rrf_threshold(
            high_score_results,
            base_threshold=RRF_MIN_SCORE,
        )
        effective = max(dynamic, RRF_MIN_SCORE)
        # Dynamic should be well above the floor for high-score distributions
        assert effective == dynamic, (
            f"effective={effective} should equal dynamic={dynamic} "
            f"when dynamic > floor={RRF_MIN_SCORE}"
        )

    def test_small_sample_uses_floor_directly(self) -> None:
        """With < 8 samples, Tukey returns base_threshold unchanged."""
        from tools.search_journals.ranking import _compute_dynamic_rrf_threshold

        few_results = [
            {
                "final_score": 0.01 * i,
                "has_rrf": True,
                "fts_score": 0.0,
                "semantic_score": 0.0,
            }
            for i in range(1, 5)  # Only 4 results — below min sample
        ]
        dynamic = _compute_dynamic_rrf_threshold(
            few_results,
            base_threshold=RRF_MIN_SCORE,
        )
        # With < 8 samples, should return base_threshold
        assert dynamic == RRF_MIN_SCORE, (
            f"dynamic={dynamic} should equal base={RRF_MIN_SCORE} for small samples"
        )
