#!/usr/bin/env python3
"""
Unit tests for tools/search_journals/ranking.py

Tests cover:
- merge_and_rank_results function
- merge_and_rank_results_hybrid function
- Score calculation and normalization
- Tier-based ranking
- FTS and semantic result merging
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestMergeAndRankResults:
    """Tests for merge_and_rank_results function"""

    def test_empty_results(self):
        """Test with empty input lists"""
        from tools.search_journals.ranking import merge_and_rank_results

        results = merge_and_rank_results([], [], [], query="test")

        assert results == []

    def test_l3_results_priority(self):
        """Test L3 results have highest priority"""
        from tools.search_journals.ranking import merge_and_rank_results

        l1 = [{"path": "/test/doc.md", "title": "Doc"}]
        l2 = [{"path": "/test/doc.md", "title": "Doc"}]
        l3 = [{"path": "/test/doc.md", "title": "Doc", "relevance": 85}]

        results = merge_and_rank_results(l1, l2, l3, query="test")

        # L3 should be highest tier
        assert len(results) == 1
        assert results[0]["relevance_score"] >= 85

    def test_l3_title_match_bonus(self):
        """Test L3 results get bonus for title match"""
        from tools.search_journals.ranking import merge_and_rank_results

        l3 = [
            {
                "path": "/test/doc.md",
                "title": "Doc",
                "relevance": 50,
                "title_match": True,
            }
        ]

        results = merge_and_rank_results([], [], l3, query="test")

        # Should get 10 point bonus: 50 + 10 = 60
        assert results[0]["relevance_score"] == 60

    def test_l2_results_added(self):
        """Test L2 results are added when not in L3"""
        from tools.search_journals.ranking import merge_and_rank_results

        l2 = [{"path": "/test/l2.md", "title": "L2 Doc", "metadata": {}}]

        results = merge_and_rank_results([], l2, [], query="test")

        assert len(results) == 1
        assert results[0]["path"] == "/test/l2.md"

    def test_l2_title_match_scoring(self):
        """Test L2 results scoring with title match"""
        from tools.search_journals.ranking import merge_and_rank_results

        l2 = [{"path": "/test/doc.md", "title": "test document", "metadata": {}}]

        results = merge_and_rank_results([], l2, [], query="test")

        # Base 20 + title match 8 = 28
        assert results[0]["relevance_score"] == 28

    def test_l2_abstract_match_scoring(self):
        """Test L2 results scoring with abstract match"""
        from tools.search_journals.ranking import merge_and_rank_results

        l2 = [
            {
                "path": "/test/doc.md",
                "title": "Doc",
                "metadata": {"abstract": "test abstract"},
            }
        ]

        results = merge_and_rank_results([], l2, [], query="test")

        # Base 20 + abstract match 5 = 25
        assert results[0]["relevance_score"] == 25

    def test_l2_tags_match_scoring(self):
        """Test L2 results scoring with tags match"""
        from tools.search_journals.ranking import merge_and_rank_results

        l2 = [
            {
                "path": "/test/doc.md",
                "title": "Doc",
                "metadata": {"tags": ["test", "python"]},
            }
        ]

        results = merge_and_rank_results([], l2, [], query="test")

        # Base 20 + tags match 2 = 22
        assert results[0]["relevance_score"] == 22

    def test_l2_combined_scoring(self):
        """Test L2 results with multiple matches"""
        from tools.search_journals.ranking import merge_and_rank_results

        l2 = [
            {
                "path": "/test/doc.md",
                "title": "test",
                "metadata": {"abstract": "test abstract", "tags": ["test"]},
            }
        ]

        results = merge_and_rank_results([], l2, [], query="test")

        # Base 20 + title 8 + abstract 5 + tags 2 = 35
        assert results[0]["relevance_score"] == 35

    def test_l1_results_added(self):
        """Test L1 results are added when not in L2/L3"""
        from tools.search_journals.ranking import merge_and_rank_results

        l1 = [{"path": "/test/l1.md", "date": "2026-03-14"}]

        results = merge_and_rank_results(l1, [], [], query="test")

        assert len(results) == 1
        assert results[0]["path"] == "/test/l1.md"
        assert results[0]["relevance_score"] == 10

    def test_results_sorted_by_score(self):
        """Test results are sorted by relevance score"""
        from tools.search_journals.ranking import merge_and_rank_results

        l3_high = [{"path": "/test/high.md", "title": "High", "relevance": 90}]
        l3_low = [{"path": "/test/low.md", "title": "Low", "relevance": 30}]

        results = merge_and_rank_results([], [], l3_high + l3_low, query="test")

        assert results[0]["path"] == "/test/high.md"
        assert results[1]["path"] == "/test/low.md"

    def test_search_rank_added(self):
        """Test search_rank field is added to results"""
        from tools.search_journals.ranking import merge_and_rank_results

        l3 = [{"path": "/test/doc.md", "title": "Doc", "relevance": 50}]

        results = merge_and_rank_results([], [], l3, query="test")

        assert "search_rank" in results[0]
        assert results[0]["search_rank"] == 1

    def test_multiple_l3_results(self):
        """Test multiple L3 results are handled correctly"""
        from tools.search_journals.ranking import merge_and_rank_results

        l3 = [
            {"path": "/test/1.md", "title": "Doc1", "relevance": 80},
            {"path": "/test/2.md", "title": "Doc2", "relevance": 60},
            {"path": "/test/3.md", "title": "Doc3", "relevance": 70},
        ]

        results = merge_and_rank_results([], [], l3, query="test")

        assert len(results) == 3
        assert results[0]["path"] == "/test/1.md"  # Highest relevance
        assert results[1]["path"] == "/test/3.md"  # Second highest
        assert results[2]["path"] == "/test/2.md"  # Lowest

    def test_no_query_scoring(self):
        """Test scoring without query parameter"""
        from tools.search_journals.ranking import merge_and_rank_results

        l2 = [{"path": "/test/doc.md", "title": "Doc", "metadata": {}}]

        results = merge_and_rank_results([], l2, [], query=None)

        # Should use base score 20 without query matching
        assert results[0]["relevance_score"] == 20


class TestMergeAndRankResultsHybrid:
    """Tests for merge_and_rank_results_hybrid function"""

    def test_empty_hybrid_results(self):
        """Test hybrid ranking with empty inputs"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        results = merge_and_rank_results_hybrid([], [], [], [], query="test")

        assert results == []

    def test_fts_results_normalized(self):
        """Test FTS results are normalized"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l3 = [{"path": "/test/doc.md", "title": "Doc", "relevance": 80}]

        results = merge_and_rank_results_hybrid([], [], l3, [], query="test")

        # fts_score = 80/100 = 0.8, final_score = 0.8 * 0.6 * 100 = 48.0 (fts_weight=0.6)
        assert results[0]["fts_score"] == 80.0  # Stored as percentage
        assert results[0]["relevance_score"] == 48.0  # 80 * 0.6

    def test_semantic_results_added(self):
        """Test semantic results are added"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        semantic = [{"path": "/test/semantic.md", "similarity": 0.9}]

        with patch(
            "tools.search_journals.ranking.enrich_semantic_result"
        ) as mock_enrich:
            mock_enrich.return_value = {
                "path": "/test/semantic.md",
                "title": "Semantic Doc",
            }

            results = merge_and_rank_results_hybrid([], [], [], semantic, query="test")

        assert len(results) == 1
        assert results[0]["path"] == "/test/semantic.md"

    def test_semantic_score_normalization(self):
        """Test semantic scores are normalized"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        semantic = [{"path": "/test/doc.md", "similarity": 0.8, "final_score": 0.8}]

        with patch(
            "tools.search_journals.ranking.enrich_semantic_result"
        ) as mock_enrich:
            mock_enrich.return_value = {"path": "/test/doc.md", "title": "Doc"}

            results = merge_and_rank_results_hybrid([], [], [], semantic, query="test")

        assert "semantic_score" in results[0]

    def test_fts_and_semantic_merged(self):
        """Test FTS and semantic results are merged"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l3 = [{"path": "/test/doc.md", "title": "Doc", "relevance": 80}]
        semantic = [{"path": "/test/doc.md", "similarity": 0.9, "final_score": 0.9}]

        results = merge_and_rank_results_hybrid(
            [], [], l3, semantic, query="test", fts_weight=0.6, semantic_weight=0.4
        )

        assert len(results) == 1
        assert results[0]["fts_score"] == 80.0  # Stored as percentage (0-100)
        assert results[0]["semantic_score"] == 100.0  # Normalized to 100

    def test_custom_weights(self):
        """Test custom FTS/semantic weights"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l3 = [{"path": "/test/doc.md", "title": "Doc", "relevance": 50}]
        semantic = [{"path": "/test/doc.md", "similarity": 0.9, "final_score": 0.9}]

        results = merge_and_rank_results_hybrid(
            [], [], l3, semantic, query="test", fts_weight=0.3, semantic_weight=0.7
        )

        # With different weights, scores should be different
        assert "relevance_score" in results[0]

    def test_l2_in_hybrid(self):
        """Test L2 results in hybrid mode"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l2 = [{"path": "/test/l2.md", "title": "L2 Doc", "metadata": {}}]

        results = merge_and_rank_results_hybrid([], l2, [], [], query="test")

        assert len(results) == 1
        assert results[0]["path"] == "/test/l2.md"
        assert results[0]["relevance_score"] == 20

    def test_l1_in_hybrid(self):
        """Test L1 results in hybrid mode"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l1 = [{"path": "/test/l1.md", "date": "2026-03-14"}]

        results = merge_and_rank_results_hybrid(l1, [], [], [], query="test")

        assert len(results) == 1
        assert results[0]["path"] == "/test/l1.md"
        assert results[0]["relevance_score"] == 10

    def test_deduplication_in_hybrid(self):
        """Test duplicate paths are merged in hybrid mode"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l3 = [{"path": "/test/doc.md", "title": "Doc", "relevance": 70}]
        l2 = [{"path": "/test/doc.md", "title": "Doc", "metadata": {}}]
        semantic = [{"path": "/test/doc.md", "similarity": 0.8, "final_score": 0.8}]

        with patch(
            "tools.search_journals.ranking.enrich_semantic_result"
        ) as mock_enrich:
            mock_enrich.return_value = {"path": "/test/doc.md", "title": "Doc"}

            results = merge_and_rank_results_hybrid([], l2, l3, semantic, query="test")

        # Should be deduplicated to single result
        assert len(results) == 1

    def test_score_details_in_hybrid(self):
        """Test score details are included in hybrid results"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l3 = [{"path": "/test/doc.md", "title": "Doc", "relevance": 80}]
        semantic = [{"path": "/test/doc.md", "similarity": 0.9, "final_score": 0.9}]

        results = merge_and_rank_results_hybrid([], [], l3, semantic, query="test")

        assert "fts_score" in results[0]
        assert "semantic_score" in results[0]
        assert "relevance_score" in results[0]

    def test_ranking_order_hybrid(self):
        """Test ranking order in hybrid mode"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        # Create results with different scores
        l3_high = [{"path": "/test/high.md", "title": "High", "relevance": 90}]
        l3_low = [{"path": "/test/low.md", "title": "Low", "relevance": 40}]
        l1 = [{"path": "/test/l1.md", "date": "2026-03-14"}]

        results = merge_and_rank_results_hybrid(
            l1, [], l3_high + l3_low, [], query="test"
        )

        # High relevance should be first
        assert results[0]["path"] == "/test/high.md"
        assert results[1]["path"] == "/test/low.md"
        assert results[2]["path"] == "/test/l1.md"


class TestTierPriority:
    """Tests for tier-based priority"""

    def test_tier_ordering(self):
        """Test tier ordering: L3 > L2 > L1"""
        from tools.search_journals.ranking import merge_and_rank_results

        l1 = [{"path": "/test/doc.md", "date": "2026-03-14"}]
        l2 = [{"path": "/test/doc.md", "title": "Doc", "metadata": {}}]
        l3 = [
            {"path": "/test/doc.md", "title": "Doc", "relevance": 15}
        ]  # Low but in L3

        results = merge_and_rank_results(l1, l2, l3, query="test")

        # L3 result should be first even with lower score
        assert len(results) == 1
        assert results[0]["path"] == "/test/doc.md"


class TestResultFields:
    """Tests for result fields"""

    def test_result_data_copied(self):
        """Test original data is copied to result"""
        from tools.search_journals.ranking import merge_and_rank_results

        l3 = [{"path": "/test/doc.md", "title": "Original Title", "relevance": 50}]

        results = merge_and_rank_results([], [], l3, query="test")

        assert results[0]["title"] == "Original Title"
        assert results[0]["path"] == "/test/doc.md"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
