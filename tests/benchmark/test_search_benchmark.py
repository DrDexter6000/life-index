"""
Performance benchmark tests for Life Index search subsystem.

Uses pytest-benchmark to measure and track performance of:
- FTS5 full-text search (L3)
- Keyword pipeline (L1 → L2 → L3)
- hierarchical_search() at all levels

Run: pytest tests/benchmark/ --benchmark-only -v
Skip: pytest tests/ -m "not benchmark"

These tests use synthetic data and mocked I/O to measure pure algorithmic
performance, not disk/network latency.
"""

from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mark all tests in this module as benchmark
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.benchmark


# ===========================================================================
# FTS5 Search Benchmarks
# ===========================================================================


class TestFTSSearchBenchmark:
    """Benchmark FTS5 full-text search performance."""

    def test_fts_search_single_keyword_100(self, benchmark: Any, fts_db_100: Path) -> None:
        """FTS search with single keyword over 100 entries."""
        from tools.lib.fts_search import search_fts

        benchmark(search_fts, fts_db_100, "benchmark")

    def test_fts_search_single_keyword_500(self, benchmark: Any, fts_db_500: Path) -> None:
        """FTS search with single keyword over 500 entries."""
        from tools.lib.fts_search import search_fts

        benchmark(search_fts, fts_db_500, "benchmark")

    def test_fts_search_multi_keyword_or(self, benchmark: Any, fts_db_500: Path) -> None:
        """FTS search with OR query over 500 entries."""
        from tools.lib.fts_search import search_fts

        benchmark(search_fts, fts_db_500, "benchmark OR parenting OR reflection")

    def test_fts_search_chinese_keyword(self, benchmark: Any, fts_db_500: Path) -> None:
        """FTS search with Chinese keyword over 500 entries."""
        from tools.lib.fts_search import search_fts

        benchmark(search_fts, fts_db_500, "晴岚")

    def test_fts_search_with_date_filter(self, benchmark: Any, fts_db_500: Path) -> None:
        """FTS search with date range filter over 500 entries."""
        from tools.lib.fts_search import search_fts

        benchmark(
            search_fts,
            fts_db_500,
            "benchmark",
            date_from="2026-03-01",
            date_to="2026-06-30",
        )


# ===========================================================================
# Keyword Ranking Benchmarks
# ===========================================================================


def _make_l3_results(n: int) -> List[Dict[str, Any]]:
    """Generate n synthetic L3 (FTS) results for ranking tests."""
    results = []
    for i in range(n):
        month = (i % 12) + 1
        day = (i % 28) + 1
        file_name = f"life-index_2026-{month:02d}-{day:02d}_{i:03d}.md"
        route_path = f"Journals/2026/{month:02d}/{file_name}"
        results.append(
            {
                "date": f"2026-{month:02d}-{day:02d}",
                "title": f"Result {i}",
                "path": route_path,
                "journal_route_path": route_path,
                "snippet": f"<mark>benchmark</mark> result {i}",
                "match_count": 1,
                "source": "fts_index",
                "relevance": max(30, 100 - i),
                "location": "",
                "weather": "",
                "topic": ["work"],
                "project": "LifeIndex",
                "tags": ["test"],
                "mood": ["专注"],
                "people": [],
                "abstract": f"Abstract for result {i}",
            }
        )
    return results


class TestRankingBenchmark:
    """Benchmark keyword-only ranking performance."""

    def test_keyword_only_ranking_medium(self, benchmark: Any) -> None:
        """Keyword-only ranking (no semantic) with 50 results."""
        from tools.search_journals.ranking import merge_and_rank_results

        l1 = [
            {
                "path": f"p{i}.md",
                "title": f"T{i}",
                "date": f"2026-01-{(i % 28) + 1:02d}",
            }
            for i in range(20)
        ]
        l2 = [
            {
                "path": f"p{i}.md",
                "title": f"T{i}",
                "date": f"2026-01-{(i % 28) + 1:02d}",
                "abstract": f"Abstract {i}",
                "tags": ["test"],
                "topic": ["work"],
                "project": "LifeIndex",
            }
            for i in range(30)
        ]
        l3 = _make_l3_results(50)
        benchmark(merge_and_rank_results, l1, l2, l3, "benchmark")


# ===========================================================================
# Keyword Pipeline Benchmarks (mocked I/O)
# ===========================================================================


class TestKeywordPipelineBenchmark:
    """Benchmark keyword pipeline with mocked data sources."""

    def _make_l1_mock(self, n: int = 20) -> MagicMock:
        """Create a mock for search_l1_index."""
        mock = MagicMock()
        mock.return_value = [
            {
                "path": f"Journals/2026/01/j_{i:03d}.md",
                "title": f"J{i}",
                "date": "2026-01-01",
            }
            for i in range(n)
        ]
        return mock

    def _make_l2_mock(self, n: int = 30) -> MagicMock:
        """Create a mock for search_l2_metadata."""
        mock = MagicMock()
        mock.return_value = {
            "results": [
                {
                    "path": f"Journals/2026/01/j_{i:03d}.md",
                    "title": f"J{i}",
                    "date": "2026-01-01",
                    "location": "Lagos",
                    "weather": "Sunny",
                    "topic": ["work"],
                    "project": "LifeIndex",
                    "tags": ["test"],
                    "mood": ["专注"],
                    "people": [],
                    "abstract": f"Abstract {i}",
                }
                for i in range(n)
            ],
            "truncated": False,
            "total_available": n,
        }
        return mock

    def _make_l3_content_mock(self, n: int = 15) -> MagicMock:
        """Create a mock for search_l3_content."""
        mock = MagicMock()
        mock.return_value = _make_l3_results(n)
        return mock

    def _make_fts_mock(self, n: int = 20) -> MagicMock:
        """Create a mock for search_fts."""
        mock = MagicMock()
        mock.return_value = [
            {
                "path": f"Journals/2026/01/j_{i:03d}.md",
                "title": f"FTS result {i}",
                "date": "2026-01-01",
                "snippet": f"<mark>keyword</mark> match {i}",
                "relevance": max(30, 90 - i * 2),
                "location": "",
                "weather": "",
                "topic": ["work"],
                "project": "LifeIndex",
                "tags": ["test"],
                "mood": [],
                "people": [],
            }
            for i in range(n)
        ]
        return mock

    @patch("tools.search_journals.keyword_pipeline.search_l1_index")
    @patch("tools.search_journals.keyword_pipeline.search_l2_metadata")
    @patch("tools.search_journals.keyword_pipeline.search_l3_content")
    def test_keyword_pipeline_with_query(
        self,
        mock_l3: MagicMock,
        mock_l2: MagicMock,
        mock_l1: MagicMock,
        benchmark: Any,
    ) -> None:
        """Full keyword pipeline with query and all filters."""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        mock_l1.side_effect = lambda *a, **kw: self._make_l1_mock(20).return_value
        mock_l2.return_value = self._make_l2_mock(30).return_value
        mock_l3.return_value = self._make_l3_content_mock(15).return_value

        # Also mock the FTS import inside keyword_pipeline
        with patch(
            "tools.search_journals.keyword_pipeline.search_l1_index",
            side_effect=lambda *a, **kw: [
                {
                    "path": f"Journals/2026/01/j_{i:03d}.md",
                    "title": f"J{i}",
                    "date": "2026-01-01",
                }
                for i in range(20)
            ],
        ):
            benchmark(
                run_keyword_pipeline,
                query="benchmark",
                topic="work",
                tags=["test"],
            )


# ===========================================================================
# hierarchical_search() Integration Benchmarks (all mocked)
# ===========================================================================


class TestHierarchicalSearchBenchmark:
    """Benchmark hierarchical_search() at each level with mocked data."""

    @patch("tools.search_journals.core.scan_all_indices")
    @patch("tools.search_journals.core.search_l1_index")
    def test_level_1_search(
        self,
        mock_l1: MagicMock,
        mock_scan: MagicMock,
        benchmark: Any,
    ) -> None:
        """Level 1: index-only search."""
        from tools.search_journals.core import hierarchical_search

        mock_l1.return_value = [
            {"path": f"p{i}.md", "title": f"T{i}", "date": "2026-01-01"} for i in range(50)
        ]
        mock_scan.return_value = []

        benchmark(hierarchical_search, topic="work", level=1)

    @patch("tools.search_journals.core.search_l2_metadata")
    @patch("tools.search_journals.core.search_l1_index")
    def test_level_2_search(
        self,
        mock_l1: MagicMock,
        mock_l2: MagicMock,
        benchmark: Any,
    ) -> None:
        """Level 2: index + metadata search."""
        from tools.search_journals.core import hierarchical_search

        mock_l1.return_value = [
            {"path": f"p{i}.md", "title": f"T{i}", "date": "2026-01-01"} for i in range(30)
        ]
        mock_l2.return_value = {
            "results": [
                {
                    "path": f"p{i}.md",
                    "title": f"T{i}",
                    "date": "2026-01-01",
                    "tags": ["test"],
                    "topic": ["work"],
                }
                for i in range(50)
            ],
            "truncated": False,
        }

        benchmark(hierarchical_search, query="benchmark", topic="work", level=2)

    @patch("tools.search_journals.core.run_keyword_pipeline")
    def test_level_3_keyword_pipeline_with_deprecated_semantic_flag(
        self,
        mock_kw: MagicMock,
        benchmark: Any,
    ) -> None:
        """Level 3: semantic flag accepted but keyword pipeline is benchmarked."""
        from tools.search_journals.core import hierarchical_search

        l3_results = _make_l3_results(30)
        mock_kw.return_value = (
            [],  # l1
            [],  # l2
            l3_results,  # l3
            False,  # l2_truncated
            0,  # l2_total_available
            {"l1_time_ms": 1.0, "l2_time_ms": 5.0, "l3_time_ms": 10.0},  # perf
        )

        benchmark(hierarchical_search, query="benchmark", level=3, semantic=True)

    @patch("tools.search_journals.core.run_keyword_pipeline")
    def test_level_3_keyword_only_no_semantic_fallback(
        self,
        mock_kw: MagicMock,
        benchmark: Any,
    ) -> None:
        """Level 3: keyword-only path without semantic fallback."""
        from tools.search_journals.core import hierarchical_search

        mock_kw.return_value = (
            [],
            [],
            _make_l3_results(50),
            False,
            0,
            {"l1_time_ms": 1.0, "l2_time_ms": 5.0, "l3_time_ms": 15.0},
        )

        benchmark(hierarchical_search, query="benchmark", level=3, semantic=False)
