"""
Performance benchmark tests for Life Index search subsystem.

Uses pytest-benchmark to measure and track performance of:
- FTS5 full-text search (L3)
- RRF fusion ranking
- Keyword pipeline (L1 → L2 → L3)
- Semantic pipeline (mocked embedding model)
- hierarchical_search() at all levels

Run: pytest tests/benchmark/ --benchmark-only -v
Skip: pytest tests/ -m "not benchmark"

These tests use synthetic data and mocked I/O to measure pure algorithmic
performance, not disk/network latency.
"""

import json
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

    def test_fts_search_single_keyword_100(
        self, benchmark: Any, fts_db_100: Path
    ) -> None:
        """FTS search with single keyword over 100 entries."""
        from tools.lib.fts_search import search_fts

        benchmark(search_fts, fts_db_100, "benchmark")

    def test_fts_search_single_keyword_500(
        self, benchmark: Any, fts_db_500: Path
    ) -> None:
        """FTS search with single keyword over 500 entries."""
        from tools.lib.fts_search import search_fts

        benchmark(search_fts, fts_db_500, "benchmark")

    def test_fts_search_multi_keyword_or(
        self, benchmark: Any, fts_db_500: Path
    ) -> None:
        """FTS search with OR query over 500 entries."""
        from tools.lib.fts_search import search_fts

        benchmark(search_fts, fts_db_500, "benchmark OR parenting OR reflection")

    def test_fts_search_chinese_keyword(self, benchmark: Any, fts_db_500: Path) -> None:
        """FTS search with Chinese keyword over 500 entries."""
        from tools.lib.fts_search import search_fts

        benchmark(search_fts, fts_db_500, "乐乐")

    def test_fts_search_with_date_filter(
        self, benchmark: Any, fts_db_500: Path
    ) -> None:
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
# RRF Fusion Benchmarks
# ===========================================================================


def _make_l3_results(n: int) -> List[Dict[str, Any]]:
    """Generate n synthetic L3 (FTS) results for ranking tests."""
    return [
        {
            "date": f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
            "title": f"Result {i}",
            "path": f"Journals/2026/{(i % 12) + 1:02d}/life-index_2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}_{i:03d}.md",
            "journal_route_path": f"Journals/2026/{(i % 12) + 1:02d}/life-index_2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}_{i:03d}.md",
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
        for i in range(n)
    ]


def _make_semantic_results(n: int) -> List[Dict[str, Any]]:
    """Generate n synthetic semantic results for ranking tests."""
    return [
        {
            "path": f"Journals/2026/{(i % 12) + 1:02d}/life-index_2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}_{i + 50:03d}.md",
            "journal_route_path": f"Journals/2026/{(i % 12) + 1:02d}/life-index_2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}_{i + 50:03d}.md",
            "title": f"Semantic result {i}",
            "date": f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
            "similarity": max(0.3, 0.95 - i * 0.02),
            "source": "semantic",
            "location": "",
            "weather": "",
            "topic": ["think"],
            "project": "",
            "tags": ["semantic"],
            "mood": [],
            "people": [],
        }
        for i in range(n)
    ]


class TestRRFFusionBenchmark:
    """Benchmark RRF fusion ranking performance."""

    def test_rrf_fusion_small(self, benchmark: Any) -> None:
        """RRF fusion with small result sets (10 FTS + 10 semantic)."""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l3 = _make_l3_results(10)
        sem = _make_semantic_results(10)
        benchmark(merge_and_rank_results_hybrid, [], [], l3, sem, "benchmark")

    def test_rrf_fusion_medium(self, benchmark: Any) -> None:
        """RRF fusion with medium result sets (50 FTS + 30 semantic)."""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l3 = _make_l3_results(50)
        sem = _make_semantic_results(30)
        benchmark(merge_and_rank_results_hybrid, [], [], l3, sem, "benchmark")

    def test_rrf_fusion_large(self, benchmark: Any) -> None:
        """RRF fusion with large result sets (200 FTS + 100 semantic)."""
        from tools.search_journals.ranking import merge_and_rank_results_hybrid

        l3 = _make_l3_results(200)
        sem = _make_semantic_results(100)
        benchmark(merge_and_rank_results_hybrid, [], [], l3, sem, "benchmark")

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
# Semantic Pipeline Benchmarks (mocked model)
# ===========================================================================


class TestSemanticPipelineBenchmark:
    """Benchmark semantic pipeline with mocked embedding model."""

    @patch("tools.search_journals.semantic_pipeline.get_semantic_runtime_status")
    @patch("tools.search_journals.semantic_pipeline.search_semantic")
    def test_semantic_pipeline_available(
        self,
        mock_search: MagicMock,
        mock_status: MagicMock,
        benchmark: Any,
    ) -> None:
        """Semantic pipeline when model is available."""
        from tools.search_journals.semantic_pipeline import run_semantic_pipeline

        mock_status.return_value = {"available": True, "reason": "", "note": ""}
        mock_search.return_value = (
            _make_semantic_results(20),
            {"semantic_time_ms": 50.0},
        )

        benchmark(run_semantic_pipeline, query="benchmark test")

    @patch("tools.search_journals.semantic_pipeline.get_semantic_runtime_status")
    @patch("tools.search_journals.semantic_pipeline.search_semantic")
    def test_semantic_pipeline_degraded(
        self,
        mock_search: MagicMock,
        mock_status: MagicMock,
        benchmark: Any,
    ) -> None:
        """Semantic pipeline when model is unavailable (graceful degradation).

        Note: because search_semantic is patched with a Mock, the pipeline's
        ``isinstance(search_semantic, Mock)`` check returns True, bypassing
        the early return.  We therefore must provide a valid return value so
        the function can proceed without ValueError.
        """
        from tools.search_journals.semantic_pipeline import run_semantic_pipeline

        mock_status.return_value = {
            "available": False,
            "reason": "model_not_loaded",
            "note": "fastembed not available",
        }
        # Even though unavailable, the Mock isinstance check lets it through
        mock_search.return_value = ([], {"semantic_time_ms": 0.0})

        benchmark(run_semantic_pipeline, query="benchmark test")


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
            {"path": f"p{i}.md", "title": f"T{i}", "date": "2026-01-01"}
            for i in range(50)
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
            {"path": f"p{i}.md", "title": f"T{i}", "date": "2026-01-01"}
            for i in range(30)
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

    @patch("tools.search_journals.core.run_semantic_pipeline")
    @patch("tools.search_journals.core.run_keyword_pipeline")
    def test_level_3_dual_pipeline(
        self,
        mock_kw: MagicMock,
        mock_sem: MagicMock,
        benchmark: Any,
    ) -> None:
        """Level 3: dual pipeline (keyword + semantic) with RRF fusion."""
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
        mock_sem.return_value = (
            _make_semantic_results(20),  # sem_results
            {"semantic_time_ms": 50.0},  # perf
            True,  # semantic_available
            None,  # semantic_note
        )

        benchmark(hierarchical_search, query="benchmark", level=3)

    @patch("tools.search_journals.core.run_semantic_pipeline")
    @patch("tools.search_journals.core.run_keyword_pipeline")
    def test_level_3_keyword_only_fallback(
        self,
        mock_kw: MagicMock,
        mock_sem: MagicMock,
        benchmark: Any,
    ) -> None:
        """Level 3: keyword-only fallback when semantic returns nothing."""
        from tools.search_journals.core import hierarchical_search

        mock_kw.return_value = (
            [],
            [],
            _make_l3_results(50),
            False,
            0,
            {"l1_time_ms": 1.0, "l2_time_ms": 5.0, "l3_time_ms": 15.0},
        )
        mock_sem.return_value = (
            [],  # no semantic results
            {},
            False,
            "fastembed not available",
        )

        benchmark(hierarchical_search, query="benchmark", level=3, semantic=False)
