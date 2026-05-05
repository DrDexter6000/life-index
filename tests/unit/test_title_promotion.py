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
        assert should_promote("团", "关于乐乐") is False  # < 3 non-stop chars

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

    def test_hybrid_priority_bucket_preserved(self):
        """D2-3: source=none metadata hits must not outrank real retrieval hits
        solely because of score magnitude differences (RRF ~0.05 vs L2 raw ~33).
        """
        results = [
            # FTS+semantic hit (priority 5) with low RRF score
            {
                "title": "算力投资思考",
                "final_score": 0.05,
                "rrf_score": 0.05,
                "fts_score": 100.0,
                "semantic_score": 40.0,
                "source": "fts,semantic",
                "_hybrid_priority": 5,
            },
            # L2 metadata hit (priority 4) with high raw score
            {
                "title": "家庭吵架反思",
                "final_score": 33.0,
                "rrf_score": 0.0,
                "fts_score": 0.0,
                "semantic_score": 0.0,
                "source": "none",
                "_hybrid_priority": 4,
            },
        ]
        promoted = apply_title_promotion(results, "投资思考")
        # Title "算力投资思考" is promoted (0.05 * 1.5 = 0.075)
        # Title "家庭吵架反思" is NOT promoted (unrelated)
        # Even though 33.0 >> 0.075, the FTS hit must stay on top
        # because priority 5 > priority 4.
        assert promoted[0]["title"] == "算力投资思考"
        assert promoted[1]["title"] == "家庭吵架反思"

    def test_hybrid_promotion_within_bucket_only(self):
        """D2-3: Title promotion should reorder within a bucket but not cross buckets."""
        results = [
            {
                "title": "算力投资思考",
                "final_score": 0.05,
                "rrf_score": 0.05,
                "fts_score": 100.0,
                "semantic_score": 40.0,
                "source": "fts,semantic",
                "_hybrid_priority": 5,
            },
            {
                "title": "投资研究笔记",
                "final_score": 0.04,
                "rrf_score": 0.04,
                "fts_score": 80.0,
                "semantic_score": 30.0,
                "source": "fts,semantic",
                "_hybrid_priority": 5,
            },
            {
                "title": "家庭吵架反思",
                "final_score": 33.0,
                "rrf_score": 0.0,
                "fts_score": 0.0,
                "semantic_score": 0.0,
                "source": "none",
                "_hybrid_priority": 4,
            },
        ]
        promoted = apply_title_promotion(results, "投资思考")
        # Both retrieval hits are promoted; metadata hit is not.
        # 0.05 * 1.5 = 0.075, 0.04 * 1.5 = 0.06
        # Both should remain above the 33.0 metadata hit.
        assert promoted[0]["title"] == "算力投资思考"
        assert promoted[1]["title"] == "投资研究笔记"
        assert promoted[2]["title"] == "家庭吵架反思"

    def test_hybrid_full_priority_ordering(self):
        """D2-4: Exact 4-tier priority must be preserved:
        FTS (5) > L2 metadata (4) > L1 index (3) > semantic-only (2).
        """
        results = [
            {
                "title": "语义回填结果",
                "final_score": 0.08,
                "rrf_score": 0.08,
                "fts_score": 0.0,
                "semantic_score": 35.0,
                "source": "semantic",
                "_hybrid_priority": 2,
            },
            {
                "title": "L2 元数据命中",
                "final_score": 33.0,
                "rrf_score": 0.0,
                "fts_score": 0.0,
                "semantic_score": 0.0,
                "source": "none",
                "_hybrid_priority": 4,
            },
            {
                "title": "FTS 内容命中",
                "final_score": 0.06,
                "rrf_score": 0.06,
                "fts_score": 100.0,
                "semantic_score": 0.0,
                "source": "fts",
                "_hybrid_priority": 5,
            },
            {
                "title": "L1 索引存在",
                "final_score": 10.0,
                "rrf_score": 0.0,
                "fts_score": 0.0,
                "semantic_score": 0.0,
                "source": "none",
                "_hybrid_priority": 3,
            },
        ]
        promoted = apply_title_promotion(results, "投资思考")
        # No title matches "投资思考", so no promotion happens.
        # Order must follow _hybrid_priority strictly.
        assert promoted[0]["title"] == "FTS 内容命中"  # priority 5
        assert promoted[1]["title"] == "L2 元数据命中"  # priority 4
        assert promoted[2]["title"] == "L1 索引存在"  # priority 3
        assert promoted[3]["title"] == "语义回填结果"  # priority 2

    def test_hybrid_semantic_does_not_outrank_l2(self):
        """D2-4: Semantic-only (priority 2) must NOT outrank L2 metadata
        (priority 4) even if its RRF score is higher than L2's raw score.
        """
        results = [
            {
                "title": "L2 元数据命中",
                "final_score": 20.0,
                "rrf_score": 0.0,
                "fts_score": 0.0,
                "semantic_score": 0.0,
                "source": "none",
                "_hybrid_priority": 4,
            },
            {
                "title": "语义回填结果",
                "final_score": 0.50,
                "rrf_score": 0.50,
                "fts_score": 0.0,
                "semantic_score": 35.0,
                "source": "semantic",
                "_hybrid_priority": 2,
            },
        ]
        promoted = apply_title_promotion(results, "投资思考")
        # 0.50 > 20.0 numerically, but priority 4 > priority 2.
        assert promoted[0]["title"] == "L2 元数据命中"
        assert promoted[1]["title"] == "语义回填结果"

    def test_non_hybrid_global_sort_unchanged(self):
        """Non-hybrid results (uniform scale) still use global final_score sort."""
        results = [
            {
                "title": "红烧肉做法",
                "final_score": 0.04,
                "rrf_score": 0.0,
                "fts_score": 40.0,
                "semantic_score": 0.0,
                "source": "fts",
            },
            {
                "title": "量子计算笔记",
                "final_score": 0.03,
                "rrf_score": 0.0,
                "fts_score": 30.0,
                "semantic_score": 0.0,
                "source": "fts",
            },
        ]
        promoted = apply_title_promotion(results, "量子计算")
        # 0.03 * 1.5 = 0.045 > 0.04, so B should outrank A
        assert promoted[0]["title"] == "量子计算笔记"
        assert promoted[1]["title"] == "红烧肉做法"
