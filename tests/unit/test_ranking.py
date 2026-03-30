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
from unittest.mock import patch


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

        results = merge_and_rank_results([], l2, [], query=None, min_score=0)

        assert len(results) == 1
        assert results[0]["path"] == "/test/l2.md"

    def test_l2_title_match_scoring(self):
        """Test L2 results scoring with title match"""
        from tools.search_journals.ranking import merge_and_rank_results

        l2 = [{"path": "/test/doc.md", "title": "test document", "metadata": {}}]

        results = merge_and_rank_results([], l2, [], query="test", min_score=0)

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

        results = merge_and_rank_results([], l2, [], query="test", min_score=0)

        # Base 20 + abstract match 4 = 24
        assert results[0]["relevance_score"] == 24

    def test_l2_abstract_only_match_does_not_clear_default_threshold(self):
        """Weak metadata-only abstract hits should be dropped by default."""
        from tools.search_journals.ranking import merge_and_rank_results

        l2 = [
            {
                "path": "/test/doc.md",
                "title": "Doc",
                "metadata": {"abstract": "test abstract"},
            }
        ]

        results = merge_and_rank_results([], l2, [], query="test")

        assert results == []

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

        results = merge_and_rank_results([], l2, [], query="test", min_score=0)

        # Base 20 + tags match 1 = 21
        assert results[0]["relevance_score"] == 21

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

        results = merge_and_rank_results([], l2, [], query="test", min_score=0)

        # Base 20 + title 8 + abstract 4 + tags 1 = 33
        assert results[0]["relevance_score"] == 33

    def test_l1_results_added(self):
        """Test L1 results are added when not in L2/L3"""
        from tools.search_journals.ranking import merge_and_rank_results

        l1 = [{"path": "/test/l1.md", "date": "2026-03-14"}]

        results = merge_and_rank_results(l1, [], [], query="test", min_score=0)

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

        results = merge_and_rank_results([], l2, [], query=None, min_score=0)

        # Should use base score 20 without query matching
        assert results[0]["relevance_score"] == 20


class TestMergeAndRankResultsHybrid:
    """Tests for merge_and_rank_results_hybrid function"""

    def test_empty_hybrid_results(self):
        """Test hybrid ranking with empty inputs"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        results = merge_and_rank_results_hybrid([], [], [], [], query="test")

        assert results == []

    def test_fts_results_use_rrf(self):
        """Test FTS-only hybrid ranking uses weighted RRF score."""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid
        from tools.lib.search_constants import FTS_WEIGHT_DEFAULT

        l3 = [{"path": "/test/doc.md", "title": "Doc", "relevance": 80}]

        results = merge_and_rank_results_hybrid(
            [], [], l3, [], query="test", min_rrf_score=0
        )

        assert results[0]["fts_score"] == 80.0
        # Uses FTS_WEIGHT_DEFAULT (1.0) for weight
        assert results[0]["relevance_score"] == pytest.approx(
            FTS_WEIGHT_DEFAULT / 61, rel=1e-6
        )

    def test_semantic_results_added(self):
        """Test semantic results are added with weighted RRF score."""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        semantic = [{"path": "/test/semantic.md", "similarity": 0.9}]

        with patch(
            "tools.search_journals.ranking.enrich_semantic_result"
        ) as mock_enrich:
            mock_enrich.return_value = {
                "path": "/test/semantic.md",
                "title": "Semantic Doc",
            }

            results = merge_and_rank_results_hybrid(
                [], [], [], semantic, query="test", min_rrf_score=0
            )

        assert len(results) == 1
        assert results[0]["path"] == "/test/semantic.md"
        assert results[0]["relevance_score"] == pytest.approx(0.4 / 61, rel=1e-6)

    def test_semantic_score_exposed_as_percentage(self):
        """Test semantic score is exposed as percentage value"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        semantic = [{"path": "/test/doc.md", "similarity": 0.8, "final_score": 0.8}]

        with patch(
            "tools.search_journals.ranking.enrich_semantic_result"
        ) as mock_enrich:
            mock_enrich.return_value = {"path": "/test/doc.md", "title": "Doc"}

            results = merge_and_rank_results_hybrid(
                [], [], [], semantic, query="test", min_rrf_score=0
            )

        assert "semantic_score" in results[0]
        assert results[0]["semantic_score"] == 80.0

    def test_fts_and_semantic_merged(self):
        """Test FTS and semantic results are merged"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l3 = [{"path": "/test/doc.md", "title": "Doc", "relevance": 80}]
        semantic = [{"path": "/test/doc.md", "similarity": 0.9, "final_score": 0.9}]

        results = merge_and_rank_results_hybrid(
            [], [], l3, semantic, query="test", fts_weight=0.6, semantic_weight=0.4
        )

        assert len(results) == 1
        assert results[0]["fts_score"] == 80.0
        assert results[0]["semantic_score"] == 90.0
        # Same document appears at rank 1 in both lists => 0.6/61 + 0.4/61
        assert results[0]["relevance_score"] == pytest.approx(1 / 61, rel=1e-6)

    def test_custom_weights_change_hybrid_ordering(self):
        """Test custom weights can change ordering between hybrid candidates."""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l3 = [
            {"path": "/fts-first.md", "title": "FTS First", "relevance": 80},
            {"path": "/shared.md", "title": "Shared", "relevance": 70},
        ]
        semantic = [
            {"path": "/shared.md", "similarity": 0.99},
            {"path": "/fts-first.md", "similarity": 0.95},
        ]

        with patch(
            "tools.search_journals.ranking.enrich_semantic_result"
        ) as mock_enrich:
            mock_enrich.side_effect = lambda item: {
                "path": item["path"],
                "title": item["path"],
            }

            results_fts_heavy = merge_and_rank_results_hybrid(
                [], [], l3, semantic, query="test", fts_weight=0.9, semantic_weight=0.1
            )
            results_semantic_heavy = merge_and_rank_results_hybrid(
                [], [], l3, semantic, query="test", fts_weight=0.1, semantic_weight=0.9
            )

        assert results_fts_heavy[0]["path"] == "/fts-first.md"
        assert results_semantic_heavy[0]["path"] == "/shared.md"

    def test_l2_in_hybrid(self):
        """Test L2 results in hybrid mode"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l2 = [{"path": "/test/l2.md", "title": "L2 Doc", "metadata": {}}]

        results = merge_and_rank_results_hybrid(
            [], l2, [], [], query=None, min_non_rrf_score=0
        )

        assert len(results) == 1
        assert results[0]["path"] == "/test/l2.md"
        assert results[0]["relevance_score"] == 20

    def test_l2_hybrid_abstract_only_match_does_not_clear_default_threshold(self):
        """Weak L2-only matches should not survive hybrid fallback thresholds."""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l2 = [
            {
                "path": "/test/l2.md",
                "title": "Doc",
                "metadata": {"abstract": "test abstract"},
            }
        ]

        results = merge_and_rank_results_hybrid(
            [], l2, [], [], query="test", min_non_rrf_score=0
        )

        assert results[0]["relevance_score"] == 24

    def test_l1_in_hybrid(self):
        """Test L1 results in hybrid mode"""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l1 = [{"path": "/test/l1.md", "date": "2026-03-14"}]

        results = merge_and_rank_results_hybrid(
            l1, [], [], [], query="test", min_non_rrf_score=0
        )

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
            l1,
            [],
            l3_high + l3_low,
            [],
            query="test",
            min_non_rrf_score=0,
            min_rrf_score=0,
        )

        # High relevance should be first
        assert results[0]["path"] == "/test/high.md"
        assert results[1]["path"] == "/test/low.md"
        assert results[2]["path"] == "/test/l1.md"


class TestReciprocalRankFusion:
    """Tests for reciprocal_rank_fusion helper"""

    def test_overlap_document_gets_higher_score(self):
        """Document present in two lists should rank first"""
        from tools.search_journals.ranking import reciprocal_rank_fusion

        scores = reciprocal_rank_fusion(
            ranked_lists=[
                ["doc_a", "doc_b", "doc_c"],
                ["doc_x", "doc_a", "doc_y"],
            ],
            k=60,
        )

        assert scores["doc_a"] == pytest.approx(1 / 61 + 1 / 62, rel=1e-6)
        assert scores["doc_a"] > scores["doc_b"]


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

        results = merge_and_rank_results(l1, l2, l3, query="test", min_score=0)

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
