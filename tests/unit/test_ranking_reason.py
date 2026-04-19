"""Tests for ranking_reason natural language explanation (D16 / T4.5)."""

import pytest

from tools.search_journals.ranking_reason import compose


class TestComposeRankingReason:
    """T4.5: compose(result) produces a human-readable ranking explanation."""

    def test_title_promoted_fts_semantic(self):
        """Dual-hit with title promotion mentions all three signals."""
        result = {
            "title": "Claude Opus 4.6 的 CTO 级别技术评审",
            "fts_score": 68,
            "semantic_score": 52,
            "source": "fts,semantic",
            "title_promoted": True,
            "query": "Claude Opus",
        }
        reason = compose(result)
        assert "标题" in reason or "title" in reason.lower()
        assert "1.5" in reason
        assert len(reason) <= 120

    def test_pure_semantic_hit(self):
        """Semantic-only result mentions similarity, no FTS."""
        result = {
            "title": "想念尿片侠",
            "fts_score": 0,
            "semantic_score": 60,
            "source": "semantic",
            "title_promoted": False,
            "query": "missing my daughter",
        }
        reason = compose(result)
        assert "语义" in reason or "semantic" in reason.lower()
        assert "0.60" in reason or "60" in reason

    def test_pure_fts_hit(self):
        """FTS-only result mentions keyword score, no semantic."""
        result = {
            "title": "重构搜索模块的思考",
            "fts_score": 80,
            "semantic_score": 0,
            "source": "fts",
            "title_promoted": False,
            "query": "重构搜索模块",
        }
        reason = compose(result)
        assert "关键词" in reason or "FTS" in reason or "fts" in reason.lower()

    def test_max_length_120(self):
        """Reason must never exceed 120 characters."""
        result = {
            "title": "A" * 200,
            "fts_score": 99.99,
            "semantic_score": 88.88,
            "source": "fts,semantic",
            "title_promoted": True,
            "query": "B" * 100,
        }
        reason = compose(result)
        assert len(reason) <= 120

    def test_l2_no_pipeline_hit(self):
        """L2-only result (no FTS, no semantic) gets a sensible reason."""
        result = {
            "title": "团团日记",
            "fts_score": 0,
            "semantic_score": 0,
            "source": "none",
            "title_promoted": False,
            "query": "团团",
        }
        reason = compose(result)
        assert len(reason) > 0
        assert len(reason) <= 120

    def test_numbers_two_decimal_places(self):
        """Scores in the reason should be formatted to 2 decimal places."""
        result = {
            "title": "测试日志",
            "fts_score": 68.456,
            "semantic_score": 52.789,
            "source": "fts,semantic",
            "title_promoted": False,
            "query": "测试",
        }
        reason = compose(result)
        # At least one score should appear with ≤2 decimal places
        assert "68.46" in reason or "52.79" in reason or "68.5" in reason

    def test_title_promoted_mentioned_first(self):
        """Title promotion should be the first segment in the reason."""
        result = {
            "title": "重构搜索模块思考",
            "fts_score": 50,
            "semantic_score": 40,
            "source": "fts,semantic",
            "title_promoted": True,
            "query": "重构搜索模块",
        }
        reason = compose(result)
        # "标题" should appear before "关键词"/"语义" if promoted
        title_pos = reason.find("标题")
        if title_pos == -1:
            title_pos = reason.lower().find("title")
        assert title_pos >= 0
        # Verify it's early in the string (within first 30 chars)
        assert title_pos < 30
