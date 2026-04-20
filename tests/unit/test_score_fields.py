"""Tests for unified rrf_score / final_score / relevance_score fields (T4.2)."""

import pytest
from unittest.mock import patch


class TestHybridScoreFields:
    """T4.2: hybrid path must output rrf_score + final_score + relevance_score on every result."""

    def test_all_results_have_three_score_fields(self):
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        fts = [{"path": "a.md", "relevance": 70, "title": "Test"}]
        sem = [{"path": "b.md", "similarity": 0.6, "final_score": 0.6}]

        with patch("tools.search_journals.ranking.enrich_semantic_result", side_effect=lambda x: x):
            results = merge_and_rank_results_hybrid([], [], fts, sem, query="test", min_rrf_score=0)

        for r in results:
            assert "rrf_score" in r, f"Missing rrf_score in {r.get('path')}"
            assert "final_score" in r, f"Missing final_score in {r.get('path')}"
            assert "relevance_score" in r, f"Missing relevance_score in {r.get('path')}"
            assert r["rrf_score"] >= 0
            assert r["final_score"] >= 0

    def test_relevance_score_equals_rrf_score_in_hybrid(self):
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        fts = [{"path": "a.md", "relevance": 70, "title": "Test"}]
        sem = [{"path": "a.md", "similarity": 0.6, "final_score": 0.6}]  # Same path = dual hit

        with patch("tools.search_journals.ranking.enrich_semantic_result", side_effect=lambda x: x):
            results = merge_and_rank_results_hybrid([], [], fts, sem, query="test", min_rrf_score=0)

        for r in results:
            if r.get("rrf_score", 0) > 0:
                assert r["relevance_score"] == pytest.approx(r["rrf_score"], abs=1e-4)

    def test_fts_only_result_has_rrf_score(self):
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        fts = [{"path": "a.md", "relevance": 70, "title": "Test"}]

        with patch("tools.search_journals.ranking.enrich_semantic_result", side_effect=lambda x: x):
            results = merge_and_rank_results_hybrid([], [], fts, [], query="test", min_rrf_score=0)

        assert len(results) >= 1
        r = results[0]
        assert r["rrf_score"] > 0  # FTS-only still gets RRF score via FTS ranking
        assert r["final_score"] > 0
        assert r["relevance_score"] > 0

    def test_semantic_only_result_has_all_fields(self):
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        sem = [{"path": "a.md", "similarity": 0.8, "final_score": 0.8}]

        with patch("tools.search_journals.ranking.enrich_semantic_result", side_effect=lambda x: x):
            results = merge_and_rank_results_hybrid([], [], [], sem, query="test", min_rrf_score=0)

        assert len(results) >= 1
        r = results[0]
        assert "rrf_score" in r
        assert "final_score" in r
        assert "relevance_score" in r


class TestNonHybridScoreFields:
    """T4.2: non-hybrid path must output rrf_score (=0) + final_score + relevance_score."""

    def test_non_hybrid_has_three_fields(self):
        from tools.search_journals.ranking import merge_and_rank_results

        fts = [{"path": "a.md", "relevance": 70, "title": "Test"}]
        results = merge_and_rank_results([], [], fts, query="test")

        for r in results:
            assert "rrf_score" in r
            assert "final_score" in r
            assert "relevance_score" in r

    def test_non_hybrid_rrf_score_is_zero(self):
        from tools.search_journals.ranking import merge_and_rank_results

        fts = [{"path": "a.md", "relevance": 70, "title": "Test"}]
        results = merge_and_rank_results([], [], fts, query="test")

        for r in results:
            assert r["rrf_score"] == 0.0

    def test_non_hybrid_relevance_equals_final_score(self):
        from tools.search_journals.ranking import merge_and_rank_results

        fts = [{"path": "a.md", "relevance": 70, "title": "Test"}]
        results = merge_and_rank_results([], [], fts, query="test")

        for r in results:
            assert r["relevance_score"] == r["final_score"]
