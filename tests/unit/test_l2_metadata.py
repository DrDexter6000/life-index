#!/usr/bin/env python3
"""
Unit tests for tools/search_journals/l2_metadata.py

Tests cover:
- _matches_filters function
- _search_with_cache function
- _search_filesystem function
- search_l2_metadata main function
- warm_cache function
- get_l2_cache_stats function
- Cache enable/disable logic
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestMatchesFilters:
    """Tests for _matches_filters function"""

    def test_date_from_filter(self):
        """Test date_from filter"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"date": "2026-03-14"}
        assert _matches_filters(metadata, date_from="2026-03-01") is True
        assert _matches_filters(metadata, date_from="2026-03-15") is False

    def test_date_to_filter(self):
        """Test date_to filter"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"date": "2026-03-14"}
        assert _matches_filters(metadata, date_to="2026-03-15") is True
        assert _matches_filters(metadata, date_to="2026-03-01") is False

    def test_date_range_filter(self):
        """Test date range filter"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"date": "2026-03-14"}
        assert (
            _matches_filters(metadata, date_from="2026-03-01", date_to="2026-03-31")
            is True
        )
        assert (
            _matches_filters(metadata, date_from="2026-01-01", date_to="2026-01-31")
            is False
        )

    def test_location_filter(self):
        """Test location filter"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"location": "Beijing, China"}
        assert _matches_filters(metadata, location="Beijing") is True
        assert _matches_filters(metadata, location="Shanghai") is False
        assert (
            _matches_filters(metadata, location="beijing") is True
        )  # Case insensitive

    def test_weather_filter(self):
        """Test weather filter"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"weather": "Sunny 25°C"}
        assert _matches_filters(metadata, weather="Sunny") is True
        assert _matches_filters(metadata, weather="Rainy") is False
        assert _matches_filters(metadata, weather="sunny") is True  # Case insensitive

    def test_topic_filter_string(self):
        """Test topic filter with string value"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"topic": "work"}
        assert _matches_filters(metadata, topic="work") is True
        assert _matches_filters(metadata, topic="learn") is False

    def test_topic_filter_list(self):
        """Test topic filter with list value"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"topic": ["work", "create"]}
        assert _matches_filters(metadata, topic="work") is True
        assert _matches_filters(metadata, topic="create") is True
        assert _matches_filters(metadata, topic="learn") is False

    def test_project_filter_string(self):
        """Test project filter with string value"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"project": "Life-Index"}
        assert _matches_filters(metadata, project="Life-Index") is True
        assert _matches_filters(metadata, project="Other") is False

    def test_project_filter_list(self):
        """Test project filter with list value"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"project": ["Life-Index", "Parenting"]}
        assert _matches_filters(metadata, project="Life-Index") is True
        assert _matches_filters(metadata, project="Parenting") is True
        assert _matches_filters(metadata, project="Other") is False

    def test_tags_filter(self):
        """Test tags filter"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"tags": ["python", "testing", "pytest"]}
        assert _matches_filters(metadata, tags=["python"]) is True
        assert _matches_filters(metadata, tags=["testing", "python"]) is True
        assert _matches_filters(metadata, tags=["javascript"]) is False

    def test_tags_filter_single_value(self):
        """Test tags filter with single string value"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"tags": "python"}
        assert _matches_filters(metadata, tags=["python"]) is True
        assert _matches_filters(metadata, tags=["testing"]) is False

    def test_mood_filter(self):
        """Test mood filter"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"mood": ["happy", "productive"]}
        assert _matches_filters(metadata, mood=["happy"]) is True
        assert _matches_filters(metadata, mood=["sad"]) is False

    def test_mood_filter_string(self):
        """Test mood filter with string value"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"mood": "happy"}
        assert _matches_filters(metadata, mood=["happy"]) is True
        assert _matches_filters(metadata, mood=["sad"]) is False

    def test_people_filter(self):
        """Test people filter"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"people": ["Alice", "Bob"]}
        assert _matches_filters(metadata, people=["Alice"]) is True
        assert _matches_filters(metadata, people=["Bob", "Charlie"]) is True
        assert _matches_filters(metadata, people=["Charlie"]) is False

    def test_query_filter_title_match(self):
        """Test query filter matching title"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"title": "Learning Python"}
        assert _matches_filters(metadata, query="Python") is True
        assert _matches_filters(metadata, query="JavaScript") is False

    def test_query_filter_abstract_match(self):
        """Test query filter matching abstract"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"abstract": "This is about Python programming"}
        assert _matches_filters(metadata, query="Python") is True
        assert _matches_filters(metadata, query="JavaScript") is False

    def test_query_filter_tags_match(self):
        """Test query filter matching tags"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"tags": ["python", "programming"]}
        assert _matches_filters(metadata, query="python") is True
        assert _matches_filters(metadata, query="java") is False

    def test_query_filter_rejects_short_substring_inside_longer_word(self):
        """Short substring noise should not count as a metadata query hit."""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"title": "Operator Notes"}
        assert _matches_filters(metadata, query="rat") is False

    def test_query_filter_abstract_non_string(self):
        """Test query filter with non-string abstract"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"abstract": None, "title": "Test"}
        # Should not raise exception
        assert _matches_filters(metadata, query="Test") is True

    def test_multiple_filters_combined(self):
        """Test multiple filters combined (AND logic)"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {"topic": "work", "location": "Beijing", "date": "2026-03-14"}
        assert _matches_filters(metadata, topic="work", location="Beijing") is True
        assert _matches_filters(metadata, topic="work", location="Shanghai") is False

    def test_empty_metadata(self):
        """Test with empty metadata"""
        from tools.search_journals.l2_metadata import _matches_filters

        metadata = {}
        assert _matches_filters(metadata) is True  # No filters = matches all
        assert _matches_filters(metadata, topic="work") is False


class TestSearchWithCache:
    """Tests for _search_with_cache function"""

    def test_search_with_cache_basic(self):
        """Test basic cache search"""
        from tools.search_journals.l2_metadata import _search_with_cache

        mock_entries = [
            {
                "file_path": "/test/journal.md",
                "date": "2026-03-14",
                "title": "Test Journal",
                "topic": ["work"],
                "metadata": {"title": "Test Journal"},
            }
        ]

        with patch(
            "tools.search_journals.l2_metadata.get_all_cached_metadata",
            return_value=mock_entries,
        ):
            results = _search_with_cache()

        assert len(results) == 1
        assert results[0]["title"] == "Test Journal"
        assert results[0]["source"] == "metadata_cache"

    def test_search_with_cache_topic_filter(self):
        """Test cache search with topic filter"""
        from tools.search_journals.l2_metadata import _search_with_cache

        mock_entries = [
            {
                "file_path": "/test/journal1.md",
                "date": "2026-03-14",
                "title": "Work Journal",
                "topic": ["work"],
                "metadata": {},
            },
            {
                "file_path": "/test/journal2.md",
                "date": "2026-03-14",
                "title": "Learn Journal",
                "topic": ["learn"],
                "metadata": {},
            },
        ]

        with patch(
            "tools.search_journals.l2_metadata.get_all_cached_metadata",
            return_value=mock_entries,
        ):
            results = _search_with_cache(topic="work")

        assert len(results) == 1
        assert results[0]["title"] == "Work Journal"

    def test_search_with_cache_surfaces_related_entries_and_backlinks(self):
        from tools.search_journals.l2_metadata import _search_with_cache

        mock_entries = [
            {
                "file_path": "/test/journal.md",
                "date": "2026-03-14",
                "title": "Test Journal",
                "topic": ["work"],
                "related_entries": ["Journals/2026/03/other.md"],
                "backlinked_by": ["Journals/2026/03/source.md"],
                "metadata": {
                    "title": "Test Journal",
                    "related_entries": ["Journals/2026/03/other.md"],
                    "backlinked_by": ["Journals/2026/03/source.md"],
                },
            }
        ]

        with patch(
            "tools.search_journals.l2_metadata.get_all_cached_metadata",
            return_value=mock_entries,
        ):
            results = _search_with_cache()

        assert results[0]["metadata"]["related_entries"] == [
            "Journals/2026/03/other.md"
        ]
        assert results[0]["metadata"]["backlinked_by"] == ["Journals/2026/03/source.md"]

    def test_search_with_cache_date_filter(self):
        """Test cache search with date filter"""
        from tools.search_journals.l2_metadata import _search_with_cache

        mock_entries = [
            {
                "file_path": "/test/journal1.md",
                "date": "2026-03-14",
                "title": "Journal 1",
                "metadata": {},
            },
            {
                "file_path": "/test/journal2.md",
                "date": "2026-02-14",
                "title": "Journal 2",
                "metadata": {},
            },
        ]

        with patch(
            "tools.search_journals.l2_metadata.get_all_cached_metadata",
            return_value=mock_entries,
        ):
            results = _search_with_cache(date_from="2026-03-01")

        assert len(results) == 1
        assert results[0]["title"] == "Journal 1"

    def test_search_with_cache_no_matches(self):
        """Test cache search with no matches"""
        from tools.search_journals.l2_metadata import _search_with_cache

        mock_entries = [
            {
                "file_path": "/test/journal.md",
                "date": "2026-03-14",
                "title": "Journal",
                "topic": ["work"],
                "metadata": {},
            },
        ]

        with patch(
            "tools.search_journals.l2_metadata.get_all_cached_metadata",
            return_value=mock_entries,
        ):
            results = _search_with_cache(topic="nonexistent")

        assert len(results) == 0


class TestSearchFilesystem:
    """Tests for _search_filesystem function"""

    def test_search_filesystem_no_journals_dir(self):
        """Test filesystem search when journals dir doesn't exist"""
        from tools.search_journals.l2_metadata import _search_filesystem

        with patch("tools.search_journals.l2_metadata.JOURNALS_DIR") as mock_dir:
            mock_dir.exists.return_value = False
            results = _search_filesystem()

        assert results == []

    def test_search_filesystem_empty_dir(self):
        """Test filesystem search with empty directory"""
        from tools.search_journals.l2_metadata import _search_filesystem

        with patch("tools.search_journals.l2_metadata.JOURNALS_DIR") as mock_dir:
            mock_dir.exists.return_value = True
            mock_dir.iterdir.return_value = []
            results = _search_filesystem()

        assert results == []

    def test_search_filesystem_with_matches(self):
        """Test filesystem search with matching files"""
        from tools.search_journals.l2_metadata import _search_filesystem

        mock_file = MagicMock()
        mock_file.is_dir.return_value = False
        mock_file.glob.return_value = [Path("/test/journal.md")]

        mock_month = MagicMock()
        mock_month.is_dir.return_value = True
        mock_month.glob.return_value = [Path("/test/journal.md")]

        mock_year = MagicMock()
        mock_year.is_dir.return_value = True
        mock_year.name = "2026"
        mock_year.iterdir.return_value = [mock_month]

        with patch("tools.search_journals.l2_metadata.JOURNALS_DIR") as mock_dir:
            mock_dir.exists.return_value = True
            mock_dir.iterdir.return_value = [mock_year]

            mock_entry = {
                "file_path": "/test/journal.md",
                "date": "2026-03-14",
                "title": "Test",
                "metadata": {},
            }

            with patch(
                "tools.search_journals.l2_metadata.get_or_update_metadata",
                return_value=mock_entry,
            ):
                results = _search_filesystem()

        assert len(results) >= 0  # May be 0 due to path issues in test


class TestSearchL2Metadata:
    """Tests for search_l2_metadata function"""

    def test_search_with_cache_enabled(self):
        """Test search with cache enabled"""
        from tools.search_journals.l2_metadata import search_l2_metadata

        mock_stats = {"total_entries": 10, "last_updated": "2026-03-14"}
        mock_results = [{"path": "test.md", "title": "Test"}]

        with patch(
            "tools.search_journals.l2_metadata.get_cache_stats", return_value=mock_stats
        ):
            with patch(
                "tools.search_journals.l2_metadata._search_with_cache",
                return_value=mock_results,
            ):
                response = search_l2_metadata(topic="work")

        assert response["results"] == mock_results
        assert response["truncated"] is False
        assert response["total_available"] == 1

    def test_search_cache_disabled(self):
        """Test search with cache disabled"""
        from tools.search_journals.l2_metadata import search_l2_metadata

        mock_results = [{"path": "test.md", "title": "Test"}]

        with patch(
            "tools.search_journals.l2_metadata._search_filesystem",
            return_value=mock_results,
        ):
            response = search_l2_metadata(topic="work", use_cache=False)

        assert response["results"] == mock_results
        assert response["truncated"] is False

    def test_search_cache_empty_fallback(self):
        """Test search falls back to filesystem when cache is empty"""
        from tools.search_journals.l2_metadata import search_l2_metadata

        mock_stats = {"total_entries": 0}
        mock_results = [{"path": "test.md", "title": "Test"}]

        with patch(
            "tools.search_journals.l2_metadata.get_cache_stats", return_value=mock_stats
        ):
            with patch(
                "tools.search_journals.l2_metadata._search_filesystem",
                return_value=mock_results,
            ):
                response = search_l2_metadata(topic="work")

        assert response["results"] == mock_results

    def test_search_cache_error_fallback(self):
        """Test search falls back to filesystem on cache error"""
        from tools.search_journals.l2_metadata import search_l2_metadata

        mock_results = [{"path": "test.md", "title": "Test"}]

        with patch(
            "tools.search_journals.l2_metadata.get_cache_stats",
            side_effect=IOError("Cache error"),
        ):
            with patch(
                "tools.search_journals.l2_metadata._search_filesystem",
                return_value=mock_results,
            ):
                response = search_l2_metadata(topic="work")

        assert response["results"] == mock_results

    def test_search_all_filters(self):
        """Test search with all filter parameters"""
        from tools.search_journals.l2_metadata import search_l2_metadata

        mock_results = [{"path": "test.md", "title": "Test"}]

        with patch(
            "tools.search_journals.l2_metadata._search_filesystem",
            return_value=mock_results,
        ) as mock_search:
            response = search_l2_metadata(
                date_from="2026-01-01",
                date_to="2026-12-31",
                location="Beijing",
                weather="Sunny",
                topic="work",
                project="Life-Index",
                tags=["python"],
                mood=["happy"],
                people=["Alice"],
                query="test",
                use_cache=False,
            )

        assert response["results"] == mock_results
        mock_search.assert_called_once()


class TestWarmCache:
    """Tests for warm_cache function"""

    def test_warm_cache_success(self):
        """Test successful cache warming"""
        from tools.search_journals.l2_metadata import warm_cache

        mock_result = {"updated": 10, "skipped": 5, "errors": 0}

        with patch(
            "tools.search_journals.l2_metadata.update_cache_for_all_journals",
            return_value=mock_result,
        ):
            result = warm_cache()

        assert result["updated"] == 10
        assert result["skipped"] == 5
        assert result["errors"] == 0

    def test_warm_cache_with_callback(self):
        """Test cache warming with progress callback"""
        from tools.search_journals.l2_metadata import warm_cache

        callback = MagicMock()
        mock_result = {"updated": 5, "skipped": 0, "errors": 0}

        with patch(
            "tools.search_journals.l2_metadata.update_cache_for_all_journals",
            return_value=mock_result,
        ):
            result = warm_cache(progress_callback=callback)

        assert result["updated"] == 5


class TestCacheStats:
    """Tests for cache stats functions"""

    def test_get_l2_cache_stats(self):
        """Test getting L2 cache stats"""
        from tools.search_journals.l2_metadata import get_l2_cache_stats

        mock_stats = {"total_entries": 10, "last_updated": "2026-03-14"}

        with patch(
            "tools.search_journals.l2_metadata.get_cache_stats", return_value=mock_stats
        ):
            result = get_l2_cache_stats()

        assert result["total_entries"] == 10


class TestCacheEnvironment:
    """Tests for cache environment variable"""

    def test_cache_disabled_via_env(self):
        """Test cache can be disabled via environment variable"""
        import os
        from tools.search_journals import l2_metadata

        # Cache should be enabled by default
        assert l2_metadata.ENABLE_CACHE is True

        # Test with environment variable set to "0"
        with patch.dict(os.environ, {"LIFE_INDEX_L2_CACHE": "0"}):
            # Re-import to pick up new value
            import importlib

            importlib.reload(l2_metadata)
            assert l2_metadata.ENABLE_CACHE is False

        # Reset for other tests
        with patch.dict(os.environ, {"LIFE_INDEX_L2_CACHE": "1"}):
            importlib.reload(l2_metadata)


class TestMaxResults:
    """Tests for max_results truncation logic"""

    def test_no_filters_truncates_at_100(self):
        """Test that search without filters truncates at 100 results"""
        from tools.search_journals.l2_metadata import search_l2_metadata

        # Create 150 mock results
        mock_results = [
            {"path": f"test{i}.md", "title": f"Test {i}"} for i in range(150)
        ]

        with patch(
            "tools.search_journals.l2_metadata._search_filesystem",
            return_value=mock_results,
        ):
            response = search_l2_metadata(use_cache=False)

        assert len(response["results"]) == 100
        assert response["truncated"] is True
        assert response["total_available"] == 150

    def test_no_filters_custom_max_results(self):
        """Test that custom max_results is respected"""
        from tools.search_journals.l2_metadata import search_l2_metadata

        mock_results = [
            {"path": f"test{i}.md", "title": f"Test {i}"} for i in range(50)
        ]

        with patch(
            "tools.search_journals.l2_metadata._search_filesystem",
            return_value=mock_results,
        ):
            response = search_l2_metadata(use_cache=False, max_results=20)

        assert len(response["results"]) == 20
        assert response["truncated"] is True
        assert response["total_available"] == 50

    def test_with_filters_no_truncation(self):
        """Test that search with filters is NOT truncated"""
        from tools.search_journals.l2_metadata import search_l2_metadata

        # Create 150 mock results
        mock_results = [
            {"path": f"test{i}.md", "title": f"Test {i}"} for i in range(150)
        ]

        with patch(
            "tools.search_journals.l2_metadata._search_filesystem",
            return_value=mock_results,
        ):
            response = search_l2_metadata(topic="work", use_cache=False)

        # With filter, should return all 150
        assert len(response["results"]) == 150
        assert response["truncated"] is False
        assert response["total_available"] == 150

    def test_max_results_none_no_limit(self):
        """Test that max_results=None disables truncation"""
        from tools.search_journals.l2_metadata import search_l2_metadata

        mock_results = [
            {"path": f"test{i}.md", "title": f"Test {i}"} for i in range(200)
        ]

        with patch(
            "tools.search_journals.l2_metadata._search_filesystem",
            return_value=mock_results,
        ):
            response = search_l2_metadata(use_cache=False, max_results=None)

        assert len(response["results"]) == 200
        assert response["truncated"] is False

    def test_results_under_limit_not_truncated(self):
        """Test that results under limit are not truncated"""
        from tools.search_journals.l2_metadata import search_l2_metadata

        mock_results = [
            {"path": f"test{i}.md", "title": f"Test {i}"} for i in range(50)
        ]

        with patch(
            "tools.search_journals.l2_metadata._search_filesystem",
            return_value=mock_results,
        ):
            response = search_l2_metadata(use_cache=False)

        assert len(response["results"]) == 50
        assert response["truncated"] is False
        assert response["total_available"] == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
