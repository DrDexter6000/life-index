"""Tests for source field reflecting actual pipeline hits (T4.3)."""

import pytest
from unittest.mock import patch


class TestHybridSourceField:
    """T4.3: hybrid path source field must reflect fts / semantic / fts,semantic."""

    def test_fts_only(self):
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        fts = [{"path": "a.md", "relevance": 70, "title": "Test"}]

        with patch("tools.search_journals.ranking.enrich_semantic_result", side_effect=lambda x: x):
            results = merge_and_rank_results_hybrid([], [], fts, [], query="test", min_rrf_score=0)

        assert results[0]["source"] == "fts"

    def test_semantic_only(self):
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        sem = [{"path": "a.md", "similarity": 0.8, "final_score": 0.8}]

        with patch("tools.search_journals.ranking.enrich_semantic_result", side_effect=lambda x: x):
            results = merge_and_rank_results_hybrid([], [], [], sem, query="test", min_rrf_score=0)

        assert results[0]["source"] == "semantic"

    def test_dual_hit(self):
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        fts = [{"path": "a.md", "relevance": 70, "title": "Test"}]
        sem = [{"path": "a.md", "similarity": 0.8, "final_score": 0.8}]

        with patch("tools.search_journals.ranking.enrich_semantic_result", side_effect=lambda x: x):
            results = merge_and_rank_results_hybrid([], [], fts, sem, query="test", min_rrf_score=0)

        assert results[0]["source"] == "fts,semantic"

    def test_valid_sources_only(self):
        """All source values must be in the allowed set."""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        fts = [{"path": "a.md", "relevance": 70, "title": "A"}]
        sem = [{"path": "b.md", "similarity": 0.5, "final_score": 0.5}]
        allowed = {"fts", "semantic", "fts,semantic", "none"}

        with patch("tools.search_journals.ranking.enrich_semantic_result", side_effect=lambda x: x):
            results = merge_and_rank_results_hybrid([], [], fts, sem, query="test", min_rrf_score=0)

        for r in results:
            assert r["source"] in allowed, f"Invalid source: {r['source']}"


class TestNonHybridSourceField:
    """T4.3: non-hybrid path source field."""

    def test_fts_result_source(self):
        from tools.search_journals.ranking import merge_and_rank_results

        fts = [{"path": "a.md", "relevance": 70, "title": "Test"}]
        results = merge_and_rank_results([], [], fts, query="test")

        assert len(results) >= 1
        assert results[0]["source"] == "fts"

    def test_l2_result_source(self):
        from tools.search_journals.ranking import merge_and_rank_results

        l2 = [{"path": "a.md", "title": "Test", "metadata": {}}]
        results = merge_and_rank_results([], l2, [], query=None, min_score=0)

        assert len(results) >= 1
        assert results[0]["source"] == "none"  # L2 tier is not FTS
