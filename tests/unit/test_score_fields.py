"""Tests for unified score fields (T4.2)."""


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
