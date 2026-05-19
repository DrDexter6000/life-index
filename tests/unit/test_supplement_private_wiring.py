#!/usr/bin/env python3
"""TDD tests for the private supplement decision seam in search core.

These tests verify ``_should_run_semantic_supplement``, a private helper in
``tools.search_journals.core`` that delegates to
``tools.search_journals.supplement_policy._should_supplement`` without being
wired into public search flow.

Contract:
  1. Returns ``False`` when semantic is disabled.
  2. Returns ``True`` for weak keyword results (score 72).
  3. Returns ``True`` for boundary score 76.
  4. Returns ``False`` for strong score 85.
  5. Passes through a custom ``max_fts_threshold``.
  6. Existing public-contract tests continue to pass (no public exposure).

Tests must not require real user data or semantic model downloads.
"""

from __future__ import annotations

from tools.search_journals.core import _should_run_semantic_supplement

# ---------------------------------------------------------------------------
# 1. Returns False when semantic is disabled
# ---------------------------------------------------------------------------


class TestSemanticDisabled:
    """When semantic=False, supplement must not be suggested."""

    def test_returns_false_when_semantic_disabled(self):
        result = _should_run_semantic_supplement([{"fts_score": 72}], semantic=False)
        assert result is False

    def test_returns_false_when_semantic_disabled_even_with_weak_results(self):
        result = _should_run_semantic_supplement([{"fts_score": 10}], semantic=False)
        assert result is False

    def test_returns_false_when_semantic_disabled_empty_results(self):
        result = _should_run_semantic_supplement([], semantic=False)
        assert result is False


# ---------------------------------------------------------------------------
# 2. Returns True for weak keyword results (score 72)
# ---------------------------------------------------------------------------


class TestWeakKeywordResults:
    """Score well below threshold should suggest supplement."""

    def test_returns_true_for_score_72(self):
        result = _should_run_semantic_supplement([{"fts_score": 72}], semantic=True)
        assert result is True

    def test_returns_true_for_very_weak_score(self):
        result = _should_run_semantic_supplement([{"fts_score": 30}], semantic=True)
        assert result is True


# ---------------------------------------------------------------------------
# 3. Returns True for boundary score 76
# ---------------------------------------------------------------------------


class TestBoundaryScore:
    """Score exactly at default threshold (76.0) should suggest supplement."""

    def test_returns_true_for_score_76(self):
        result = _should_run_semantic_supplement([{"fts_score": 76}], semantic=True)
        assert result is True

    def test_returns_true_for_score_76_0_float(self):
        result = _should_run_semantic_supplement([{"fts_score": 76.0}], semantic=True)
        assert result is True


# ---------------------------------------------------------------------------
# 4. Returns False for strong score 85
# ---------------------------------------------------------------------------


class TestStrongScore:
    """Score above threshold should NOT suggest supplement."""

    def test_returns_false_for_score_85(self):
        result = _should_run_semantic_supplement([{"fts_score": 85}], semantic=True)
        assert result is False

    def test_returns_false_for_score_100(self):
        result = _should_run_semantic_supplement([{"fts_score": 100}], semantic=True)
        assert result is False


# ---------------------------------------------------------------------------
# 5. Passes through custom max_fts_threshold
# ---------------------------------------------------------------------------


class TestCustomThreshold:
    """Custom threshold should override the default 76.0."""

    def test_custom_threshold_allows_score_80(self):
        """Score 80 above default 76, but allowed with threshold=90."""
        result = _should_run_semantic_supplement(
            [{"fts_score": 80}], semantic=True, max_fts_threshold=90.0
        )
        assert result is True

    def test_custom_threshold_blocks_score_80(self):
        """Score 80 blocked when threshold is 70."""
        result = _should_run_semantic_supplement(
            [{"fts_score": 80}], semantic=True, max_fts_threshold=70.0
        )
        assert result is False

    def test_custom_threshold_boundary_exact(self):
        """Score exactly at custom threshold should suggest supplement."""
        result = _should_run_semantic_supplement(
            [{"fts_score": 50.0}], semantic=True, max_fts_threshold=50.0
        )
        assert result is True


# ---------------------------------------------------------------------------
# 6. Empty results edge case
# ---------------------------------------------------------------------------


class TestEmptyResults:
    """Empty keyword results should suggest supplement (delegate behavior)."""

    def test_returns_true_for_empty_results_semantic_enabled(self):
        result = _should_run_semantic_supplement([], semantic=True)
        assert result is True
