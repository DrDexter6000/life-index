#!/usr/bin/env python3
"""TDD tests for weak-keyword supplement proxy helpers.

The accepted proxy is based on max keyword FTS score, not title-query overlap.
This module is intentionally private and unwired from public/default search.
"""

from __future__ import annotations


class TestMaxFtsScore:
    """Unit tests for extracting the strongest keyword score."""

    def test_uses_relevance_from_raw_keyword_results(self):
        from tools.search_journals.supplement_policy import _max_fts_score

        results = [
            {"path": "weak.md", "relevance": 72},
            {"path": "strong.md", "relevance": 85},
        ]

        assert _max_fts_score(results) == 85.0

    def test_uses_fts_score_from_ranked_results(self):
        from tools.search_journals.supplement_policy import _max_fts_score

        results = [
            {"path": "weak.md", "fts_score": 71.5},
            {"path": "strong.md", "fts_score": 80.25},
        ]

        assert _max_fts_score(results) == 80.25

    def test_uses_relevance_score_as_backward_compat_alias(self):
        from tools.search_journals.supplement_policy import _max_fts_score

        results = [{"path": "alias.md", "relevance_score": 77}]

        assert _max_fts_score(results) == 77.0

    def test_uses_explain_keyword_pipeline_score_when_available(self):
        from tools.search_journals.supplement_policy import _max_fts_score

        results = [
            {
                "path": "explained.md",
                "explain": {"keyword_pipeline": {"fts_score": 79}},
            }
        ]

        assert _max_fts_score(results) == 79.0

    def test_missing_or_invalid_scores_are_zero(self):
        from tools.search_journals.supplement_policy import _max_fts_score

        results = [
            {"path": "missing.md"},
            {"path": "none.md", "relevance": None},
            {"path": "bad.md", "fts_score": "not-a-number"},
        ]

        assert _max_fts_score(results) == 0.0

    def test_negative_scores_do_not_lower_default_zero(self):
        from tools.search_journals.supplement_policy import _max_fts_score

        results = [{"path": "negative.md", "relevance": -5}]

        assert _max_fts_score(results) == 0.0


class TestShouldSupplement:
    """Unit tests for the score-based supplement gate."""

    def test_empty_keyword_results_returns_true(self):
        from tools.search_journals.supplement_policy import _should_supplement

        assert _should_supplement([]) is True

    def test_weak_keyword_score_supplements(self):
        from tools.search_journals.supplement_policy import _should_supplement

        results = [{"path": "weak.md", "relevance": 72}]

        assert _should_supplement(results) is True

    def test_boundary_score_supplements(self):
        from tools.search_journals.supplement_policy import _should_supplement

        results = [{"path": "boundary.md", "relevance": 76}]

        assert _should_supplement(results) is True

    def test_strong_keyword_score_does_not_supplement(self):
        from tools.search_journals.supplement_policy import _should_supplement

        results = [{"path": "strong.md", "relevance": 85}]

        assert _should_supplement(results) is False

    def test_strongest_keyword_score_controls_decision(self):
        from tools.search_journals.supplement_policy import _should_supplement

        results = [
            {"path": "weak.md", "relevance": 60},
            {"path": "strong.md", "relevance": 90},
        ]

        assert _should_supplement(results) is False

    def test_custom_threshold_override(self):
        from tools.search_journals.supplement_policy import _should_supplement

        results = [{"path": "custom.md", "relevance": 80}]

        assert _should_supplement(results, max_fts_threshold=85) is True
        assert _should_supplement(results, max_fts_threshold=75) is False

    def test_missing_scores_supplement_conservatively(self):
        from tools.search_journals.supplement_policy import _should_supplement

        results = [{"path": "missing.md"}]

        assert _should_supplement(results) is True


class TestModuleContracts:
    """Module-level import and isolation contracts."""

    def test_module_imports(self):
        import tools.search_journals.supplement_policy  # noqa: F401

    def test_exports_expected_private_helpers(self):
        from tools.search_journals.supplement_policy import _max_fts_score, _should_supplement

        assert callable(_max_fts_score)
        assert callable(_should_supplement)

    def test_no_public_default_change(self):
        import tools.search_journals.supplement_policy as sp

        assert not hasattr(sp, "SEMANTIC_POLICY")
        assert not hasattr(sp, "MAX_RESULTS")

    def test_no_module_level_threshold_constant(self):
        import tools.search_journals.supplement_policy as sp

        assert not hasattr(sp, "_SUPPLEMENT_FIRST_MATCH_RANK_THRESHOLD")
        assert not hasattr(sp, "_SUPPLEMENT_MAX_FTS_THRESHOLD")

    def test_title_overlap_is_not_exported_as_proxy(self):
        import tools.search_journals.supplement_policy as sp

        assert not hasattr(sp, "_compute_first_title_match_rank")
