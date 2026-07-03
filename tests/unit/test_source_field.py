"""Tests for source field reflecting actual pipeline hits (T4.3)."""


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
