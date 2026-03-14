#!/usr/bin/env python3
"""
Unit tests for tools/search_journals/core.py

Tests cover:
- Hierarchical search function
- Level 1/2/3 search integration
- Result merging and ranking
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestHierarchicalSearch:
    """Tests for hierarchical_search function"""

    def test_search_level1_by_topic(self):
        """Level 1 search by topic"""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index") as mock_l1:
            mock_l1.return_value = [{"path": "test.md", "date": "2026-03-14"}]
            result = hierarchical_search(topic="work", level=1)

        assert result["success"] is True
        assert len(result["l1_results"]) >= 1
        mock_l1.assert_called_once_with("topic", "work")

    def test_search_level1_by_project(self):
        """Level 1 search by project"""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index") as mock_l1:
            mock_l1.return_value = [{"path": "test.md", "date": "2026-03-14"}]
            result = hierarchical_search(project="Life-Index", level=1)

        assert result["success"] is True
        mock_l1.assert_called_once_with("project", "Life-Index")

    def test_search_level1_by_tags(self):
        """Level 1 search by tags"""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index") as mock_l1:
            mock_l1.return_value = [{"path": "test.md", "date": "2026-03-14"}]
            result = hierarchical_search(tags=["python", "testing"], level=1)

        assert result["success"] is True
        assert mock_l1.call_count == 2  # One call per tag

    def test_search_level2_metadata(self):
        """Level 2 search with metadata"""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l2_metadata") as mock_l2:
            mock_l2.return_value = [{"path": "test.md", "date": "2026-03-14"}]
            result = hierarchical_search(
                location="Beijing",
                date_from="2026-01-01",
                date_to="2026-03-31",
                level=2,
            )

        assert result["success"] is True
        mock_l2.assert_called_once()

    def test_search_level3_content(self):
        """Level 3 search with content query"""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l3_content") as mock_l3:
            with patch(
                "tools.search_journals.core.merge_and_rank_results"
            ) as mock_rank:
                mock_l3.return_value = [{"path": "test.md", "relevance": 0.9}]
                mock_rank.return_value = [{"path": "test.md", "score": 0.9}]
                result = hierarchical_search(query="Python", level=3)

        assert result["success"] is True

    def test_search_semantic_enabled(self):
        """Search with semantic enabled"""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_semantic") as mock_sem:
            with patch("tools.search_journals.core.search_l3_content") as mock_l3:
                with patch(
                    "tools.search_journals.core.merge_and_rank_results_hybrid"
                ) as mock_rank:
                    mock_sem.return_value = [{"path": "test.md", "similarity": 0.8}]
                    mock_l3.return_value = []
                    mock_rank.return_value = [{"path": "test.md", "score": 0.8}]
                    result = hierarchical_search(query="Python", level=3, semantic=True)

        assert result["success"] is True

    def test_search_no_results(self):
        """Search with no matching results"""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index") as mock_l1:
            mock_l1.return_value = []
            result = hierarchical_search(topic="nonexistent", level=1)

        assert result["success"] is True
        assert result["total_found"] == 0

    def test_search_deduplication(self):
        """Results are deduplicated"""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index") as mock_l1:
            # Return duplicate paths
            mock_l1.return_value = [
                {"path": "same.md", "date": "2026-03-14"},
                {"path": "same.md", "date": "2026-03-14"},
            ]
            result = hierarchical_search(topic="work", level=1)

        # Should deduplicate
        paths = [r["path"] for r in result["l1_results"]]
        assert paths.count("same.md") <= 1

    def test_search_includes_performance_metrics(self):
        """Search includes performance metrics"""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index") as mock_l1:
            mock_l1.return_value = []
            result = hierarchical_search(topic="work", level=1)

        assert "performance" in result


class TestSearchParams:
    """Tests for search parameters"""

    def test_query_params_recorded(self):
        """Query parameters are recorded in result"""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index") as mock_l1:
            mock_l1.return_value = []
            result = hierarchical_search(
                query="test",
                topic="work",
                project="Project",
                tags=["tag1"],
                date_from="2026-01-01",
                date_to="2026-12-31",
                level=2,
            )

        assert result["query_params"]["query"] == "test"
        assert result["query_params"]["topic"] == "work"
        assert result["query_params"]["project"] == "Project"
        assert result["query_params"]["level"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
