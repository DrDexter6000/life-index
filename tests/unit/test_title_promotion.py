"""Tests for title hard promotion post-rank multiplier (D12 / T4.4)."""

import pytest
from tools.search_journals.title_promotion import should_promote, apply_title_promotion


class TestShouldPromote:
    def test_full_coverage_promotes(self):
        assert should_promote("重构搜索模块", "重构搜索模块的思考") is True

    def test_partial_coverage_below_threshold(self):
        # "搜索" is 2 chars out of 6 non-stop chars = 33%
        assert should_promote("重构搜索模块", "Life Index 搜索功能优化") is False

    def test_short_query_skips(self):
        assert should_promote("团", "关于团团") is False  # < 3 non-stop chars

    def test_case_insensitive(self):
        assert should_promote("Claude Opus", "Claude Opus review") is True

    def test_stopwords_excluded_from_calc(self):
        # "的" is a stopword, so non-stop chars = "重构模块" (4 chars)
        # Title "重构模块笔记" covers all 4 = 100%
        assert should_promote("重构的模块", "重构模块笔记") is True

    def test_no_coverage(self):
        assert should_promote("量子计算", "红烧肉做法") is False


class TestApplyTitlePromotion:
    def test_promoted_result_gets_higher_score(self):
        results = [
            {"title": "无关结果", "final_score": 0.04, "confidence": "high"},
            {"title": "重构搜索模块思考", "final_score": 0.03, "confidence": "medium"},
        ]
        promoted = apply_title_promotion(results, "重构搜索模块")
        # The promoted result (0.03 * 1.5 = 0.045) should now outrank the unpromoted 0.04
        assert promoted[0]["title"] == "重构搜索模块思考"
        assert promoted[0]["final_score"] == pytest.approx(0.03 * 1.5)
        assert promoted[0]["title_promoted"] is True

    def test_confidence_unchanged_after_promotion(self):
        """D12: promotion does NOT change confidence labels."""
        results = [
            {"title": "重构搜索模块", "final_score": 0.03, "confidence": "medium"},
        ]
        promoted = apply_title_promotion(results, "重构搜索模块")
        assert promoted[0]["confidence"] == "medium"  # NOT changed to high

    def test_no_promotion_for_unrelated(self):
        results = [
            {"title": "红烧肉做法", "final_score": 0.05, "confidence": "low"},
        ]
        promoted = apply_title_promotion(results, "量子计算")
        assert promoted[0]["title_promoted"] is False
        assert promoted[0]["final_score"] == 0.05  # unchanged

    def test_resort_after_promotion(self):
        """Results must be re-sorted by final_score after promotion."""
        results = [
            {"title": "天气不错", "final_score": 0.04},
            {"title": "重构代码笔记", "final_score": 0.03},
        ]
        promoted = apply_title_promotion(results, "重构代码")
        # 0.03 * 1.5 = 0.045 > 0.04, so promoted result should be first
        assert promoted[0]["title"] == "重构代码笔记"
        assert promoted[0]["final_score"] == pytest.approx(0.03 * 1.5)
        assert promoted[1]["title"] == "天气不错"

    def test_empty_results(self):
        results = apply_title_promotion([], "test")
        assert results == []
