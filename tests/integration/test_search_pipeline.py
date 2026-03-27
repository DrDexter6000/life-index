# -*- coding: utf-8 -*-
"""
Life Index Integration Tests - Search Pipeline
=============================================

Tests cover the complete dual-pipeline search architecture:
- Pipeline A (Keyword): L1 index → L2 metadata → L3 FTS content
- Pipeline B (Semantic): Vector similarity search
- Fusion: RRF (Reciprocal Rank Fusion, k=60)

This module provides integration-level tests that verify the complete
search pipeline from query input to merged results output.

Usage:
    python -m pytest tests/integration/test_search_pipeline.py -v
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
import time

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestDualPipelineParallelExecution:
    """Tests for dual-pipeline parallel execution architecture."""

    def test_pipelines_execute_in_parallel(self):
        """Verify keyword and semantic pipelines execute concurrently using ThreadPoolExecutor."""
        from tools.search_journals.core import hierarchical_search

        execution_log = []

        def mock_l1(*args, **kwargs):
            execution_log.append(("l1_start", time.perf_counter()))
            time.sleep(0.05)  # Simulate work
            execution_log.append(("l1_end", time.perf_counter()))
            return []

        def mock_l2(*args, **kwargs):
            return {"results": [], "truncated": False}

        def mock_l3(*args, **kwargs):
            return []

        def mock_semantic(*args, **kwargs):
            execution_log.append(("sem_start", time.perf_counter()))
            time.sleep(0.05)  # Simulate work
            execution_log.append(("sem_end", time.perf_counter()))
            return [], {"semantic_encode_ms": 1.0, "semantic_search_ms": 1.0}

        with patch("tools.search_journals.core.search_l1_index", side_effect=mock_l1):
            with patch(
                "tools.search_journals.core.search_l2_metadata", side_effect=mock_l2
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", side_effect=mock_l3
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        side_effect=mock_semantic,
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": True,
                                "reason": "",
                                "note": "",
                            }

                            # Add topic to trigger L1 search
                            start = time.perf_counter()
                            result = hierarchical_search(
                                query="test", topic="work", level=3, semantic=True
                            )
                            total_time = time.perf_counter() - start

        # Extract start times from log
        l1_start = next(t for name, t in execution_log if name == "l1_start")
        sem_start = next(t for name, t in execution_log if name == "sem_start")

        # Both pipelines should have started within 20ms of each other (parallel execution)
        time_diff = abs(l1_start - sem_start)
        assert time_diff < 0.02, (
            f"Pipelines did not start in parallel (time diff: {time_diff * 1000:.1f}ms)"
        )

        # Total time should be ~0.05s (parallel) not ~0.1s (sequential)
        assert total_time < 0.09, (
            f"Total time {total_time * 1000:.1f}ms suggests sequential execution"
        )

    def test_keyword_pipeline_completes_when_semantic_unavailable(self):
        """Keyword pipeline should complete when semantic is unavailable."""
        from tools.search_journals.core import hierarchical_search

        def mock_l3(*args, **kwargs):
            return [{"path": "/test/doc.md", "title": "Test", "relevance": 80}]

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", side_effect=mock_l3
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "vector index not found",
                                "note": "向量索引未建立，请运行 life-index index",
                            }

                            result = hierarchical_search(
                                query="test", level=3, semantic=True
                            )

        # Should still return FTS results with graceful degradation
        assert result["success"] is True
        assert len(result["l3_results"]) == 1
        assert result["l3_results"][0]["path"] == "/test/doc.md"
        assert result["semantic_available"] is False
        assert "semantic_note" in result

    def test_threadpool_executor_shutdown_clean(self):
        """ThreadPoolExecutor should shut down cleanly after search."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", return_value=[]
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "test",
                                "note": "",
                            }

                            # Should complete without hanging
                            result = hierarchical_search(query="test", level=3)

        assert result["success"] is True


class TestRRFFusion:
    """Tests for RRF (Reciprocal Rank Fusion) integration."""

    def test_rrf_fuses_fts_and_semantic_rankings(self):
        """RRF should fuse FTS and semantic rankings correctly."""
        from tools.search_journals.ranking import (
            merge_and_rank_results_hybrid,
            reciprocal_rank_fusion,
        )

        # FTS ranks doc_a first, doc_b second
        fts_results = [
            {"path": "/test/doc_a.md", "title": "Doc A", "relevance": 80},
            {"path": "/test/doc_b.md", "title": "Doc B", "relevance": 60},
        ]

        # Semantic ranks doc_b first, doc_a second
        semantic_results = [
            {"path": "/test/doc_b.md", "title": "Doc B", "similarity": 0.9},
            {"path": "/test/doc_a.md", "title": "Doc A", "similarity": 0.8},
        ]

        with patch(
            "tools.search_journals.ranking.enrich_semantic_result"
        ) as mock_enrich:

            def enrich_side_effect(r):
                return {"path": r["path"], "title": r["title"]}

            mock_enrich.side_effect = enrich_side_effect

            merged = merge_and_rank_results_hybrid(
                [], [], fts_results, semantic_results, query="test"
            )

        # Equal weights (1.0, 1.0): RRF scores are equal for both docs.
        # doc_a ranks first because it has higher FTS score (80 > 60),
        # which is the secondary sort key after RRF score.
        assert len(merged) == 2
        doc_a_score = next(r["relevance_score"] for r in merged if "doc_a" in r["path"])
        doc_b_score = next(r["relevance_score"] for r in merged if "doc_b" in r["path"])
        assert doc_a_score > doc_b_score

    def test_rrf_with_empty_semantic_results(self):
        """Core search falls back to pure keyword ranking when semantic is empty."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content",
                    return_value=[
                        {"path": "/test/doc_a.md", "title": "Doc A", "relevance": 80},
                        {"path": "/test/doc_b.md", "title": "Doc B", "relevance": 60},
                    ],
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "",
                                "note": "",
                            }
                            result = hierarchical_search(query="test", level=3)

        merged = result["merged_results"]
        assert len(merged) == 2
        assert merged[0]["path"] == "/test/doc_a.md"
        assert merged[1]["path"] == "/test/doc_b.md"

    def test_rrf_k60_parameter(self):
        """RRF should use k=60 as specified in architecture."""
        from tools.search_journals.ranking import reciprocal_rank_fusion

        scores = reciprocal_rank_fusion(
            ranked_lists=[
                ["doc_a", "doc_b"],
                ["doc_a", "doc_b"],
            ],
            k=60,
        )

        # doc_a at rank 1 in both lists: 1/(60+1) + 1/(60+1) = 2/61
        # doc_b at rank 2 in both lists: 1/(60+2) + 1/(60+2) = 2/62
        assert scores["doc_a"] > scores["doc_b"]
        assert abs(scores["doc_a"] - 2 / 61) < 1e-9
        assert abs(scores["doc_b"] - 2 / 62) < 1e-9


class TestSemanticSearchDegradation:
    """Tests for semantic search graceful degradation."""

    def test_search_degrades_when_vector_index_missing(self):
        """Search should return keyword results when vector index is missing."""
        from tools.search_journals.core import hierarchical_search

        l3_results = [{"path": "/test/doc.md", "title": "Test Doc", "relevance": 80}]

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content",
                    return_value=l3_results,
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "vector index not found",
                                "note": "向量索引未建立，请运行 life-index index",
                            }

                            result = hierarchical_search(
                                query="test", level=3, semantic=True
                            )

        assert result["success"] is True
        assert len(result["l3_results"]) == 1
        assert result["semantic_available"] is False
        assert "semantic_note" in result
        assert "life-index index" in result["semantic_note"]

    def test_search_degrades_when_fastembed_not_installed(self):
        """Search should degrade when fastembed is not installed."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", return_value=[]
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "fastembed dependency is not installed",
                                "note": "fastembed 未安装，当前已降级为关键词搜索。",
                            }

                            result = hierarchical_search(query="test", level=3)

        assert result["success"] is True
        assert result["semantic_available"] is False

    def test_no_semantic_flag_disables_semantic(self):
        """--no-semantic flag should disable semantic search entirely."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", return_value=[]
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic"
                    ) as mock_semantic:
                        result = hierarchical_search(
                            query="test", level=3, semantic=False
                        )

        # Semantic should not be called
        mock_semantic.assert_not_called()
        assert "semantic_note" in result
        assert "--no-semantic" in result["semantic_note"]


class TestEndToEndSearch:
    """End-to-end integration tests for search pipeline."""

    def test_full_pipeline_returns_correct_structure(self):
        """Full pipeline should return complete result structure."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", return_value=[]
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "",
                                "note": "",
                            }

                            result = hierarchical_search(query="test query", level=3)

        # Verify complete structure
        assert "success" in result
        assert "query_params" in result
        assert "l1_results" in result
        assert "l2_results" in result
        assert "l3_results" in result
        assert "semantic_results" in result
        assert "merged_results" in result
        assert "total_found" in result
        assert "semantic_available" in result
        assert "performance" in result

        # Verify query params
        assert result["query_params"]["query"] == "test query"
        assert result["query_params"]["level"] == 3

    def test_performance_timing_recorded(self):
        """Performance timings should be recorded for each pipeline stage."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", return_value=[]
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "",
                                "note": "",
                            }

                            result = hierarchical_search(query="test", level=3)

        assert "total_time_ms" in result["performance"]
        assert result["performance"]["total_time_ms"] > 0

    def test_semantic_substep_timings_are_reported(self):
        """Semantic pipeline should expose encode/search timing metrics."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", return_value=[]
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=(
                            [],
                            {"semantic_encode_ms": 12.3, "semantic_search_ms": 4.5},
                        ),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": True,
                                "reason": "",
                                "note": "",
                            }

                            result = hierarchical_search(query="test", level=3)

        assert result["performance"]["semantic_encode_ms"] == 12.3
        assert result["performance"]["semantic_search_ms"] == 4.5

    def test_level_1_returns_l1_only(self):
        """Level 1 search should return only L1 results."""
        from tools.search_journals.core import hierarchical_search

        with patch(
            "tools.search_journals.core.scan_all_indices",
            return_value=[
                {"path": "/test/doc1.md", "date": "2026-03-14"},
                {"path": "/test/doc2.md", "date": "2026-03-15"},
            ],
        ):
            result = hierarchical_search(level=1)

        assert result["success"] is True
        assert len(result["l1_results"]) == 2
        assert result["l2_results"] == []
        assert result["l3_results"] == []
        assert result["merged_results"] == []

    def test_level_2_returns_l1_and_l2(self):
        """Level 2 search should return L1 and L2 results."""
        from tools.search_journals.core import hierarchical_search

        with patch(
            "tools.search_journals.core.search_l1_index",
            return_value=[{"path": "/test/doc1.md", "date": "2026-03-14"}],
        ):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={
                    "results": [{"path": "/test/doc1.md", "title": "Doc 1"}],
                    "truncated": False,
                },
            ):
                result = hierarchical_search(topic="work", level=2)

        assert result["success"] is True
        assert len(result["l1_results"]) == 1
        assert len(result["l2_results"]) == 1
        assert result["l3_results"] == []


class TestSearchWithFilters:
    """Tests for search with various filters."""

    def test_search_with_date_range(self):
        """Search should filter by date range."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch("tools.search_journals.core.search_l2_metadata") as mock_l2:
                mock_l2.return_value = {"results": [], "truncated": False}
                with patch(
                    "tools.search_journals.core.search_l3_content", return_value=[]
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "",
                                "note": "",
                            }

                            result = hierarchical_search(
                                query="test",
                                date_from="2026-01-01",
                                date_to="2026-03-31",
                                level=3,
                            )

        mock_l2.assert_called_once()
        call_kwargs = mock_l2.call_args[1]
        assert call_kwargs["date_from"] == "2026-01-01"
        assert call_kwargs["date_to"] == "2026-03-31"

    def test_search_with_topic_filter(self):
        """Search should filter by topic."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index") as mock_l1:
            mock_l1.return_value = []
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", return_value=[]
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "",
                                "note": "",
                            }

                            result = hierarchical_search(topic="work", level=3)

        mock_l1.assert_called_with("topic", "work")

    def test_search_with_multiple_tags(self):
        """Search should handle multiple tags."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index") as mock_l1:
            mock_l1.return_value = []
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", return_value=[]
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "",
                                "note": "",
                            }

                            result = hierarchical_search(
                                tags=["python", "testing"], level=3
                            )

        # Should call search_l1_index for each tag
        assert mock_l1.call_count == 2
        mock_l1.assert_any_call("tag", "python")
        mock_l1.assert_any_call("tag", "testing")


class TestSearchWeights:
    """Tests for search weight configuration."""

    def test_fts_weight_parameter_accepted(self):
        """fts_weight parameter should be accepted."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", return_value=[]
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "",
                                "note": "",
                            }

                            # Should not raise
                            result = hierarchical_search(
                                query="test",
                                level=3,
                                fts_weight=0.7,
                                semantic_weight=0.3,
                            )

        assert result["success"] is True

    def test_semantic_weight_parameter_accepted(self):
        """semantic_weight parameter should be accepted."""
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_l3_content", return_value=[]
                ):
                    with patch(
                        "tools.search_journals.core.search_semantic",
                        return_value=([], {}),
                    ):
                        with patch(
                            "tools.search_journals.core.get_semantic_runtime_status"
                        ) as mock_status:
                            mock_status.return_value = {
                                "available": False,
                                "reason": "",
                                "note": "",
                            }

                            result = hierarchical_search(
                                query="test", level=3, semantic_weight=0.5
                            )

        assert result["success"] is True

    def test_low_fts_recall_supplements_with_full_corpus_scan(self):
        from tools.search_journals.core import hierarchical_search

        with patch("tools.search_journals.core.search_l1_index", return_value=[]):
            with patch(
                "tools.search_journals.core.search_l2_metadata",
                return_value={"results": [], "truncated": False},
            ):
                with patch(
                    "tools.search_journals.core.search_fts",
                    return_value=[
                        {
                            "date": "2026-03-10",
                            "title": "FTS 命中",
                            "path": "Journals/2026/03/a.md",
                            "relevance": 80,
                        }
                    ],
                    create=True,
                ):
                    with patch(
                        "tools.search_journals.core.search_l3_content",
                        return_value=[
                            {
                                "path": "Journals/2026/03/a.md",
                                "journal_route_path": "2026/03/a.md",
                                "title": "FTS 命中",
                            },
                            {
                                "path": "Journals/2026/03/b.md",
                                "journal_route_path": "2026/03/b.md",
                                "title": "补搜命中",
                            },
                        ],
                    ) as mock_l3:
                        with patch(
                            "tools.search_journals.core.search_semantic",
                            return_value=([], {}),
                        ):
                            with patch(
                                "tools.search_journals.core.get_semantic_runtime_status"
                            ) as mock_status:
                                mock_status.return_value = {
                                    "available": False,
                                    "reason": "",
                                    "note": "",
                                }

                                result = hierarchical_search(query="补搜测试", level=3)

        assert result["success"] is True
        assert mock_l3.call_count == 1
        paths = {item.get("journal_route_path") for item in result["l3_results"]}
        assert "2026/03/a.md" in paths
        assert "2026/03/b.md" in paths


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
