#!/usr/bin/env python3
"""
Contract tests: search_journals response shape

Verifies that hierarchical_search() output conforms to the contract
documented in docs/API.md:
1. Response contains all documented fields
2. Field types match documentation
3. Level-specific early-return contracts
4. Empty results vs failure distinction

Note: After Phase 2B refactoring, mock targets changed:
- Level 1/2: patch at core module
- Level 3: patch at keyword_pipeline and semantic_pipeline modules
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from tools.search_journals.core import hierarchical_search

# ── Documented response fields ──

REQUIRED_RESPONSE_FIELDS = {
    "success",
    "query_params",
    "l1_results",
    "l2_results",
    "l3_results",
    "semantic_results",
    "merged_results",
    "total_found",
    "performance",
    "warnings",  # Phase 2C: added warnings field
}


def _load_golden(name: str) -> dict:
    return json.loads(
        (Path(__file__).parent / "goldens" / name).read_text(encoding="utf-8")
    )


def _normalize_search_snapshot(result: dict) -> dict:
    normalized = json.loads(json.dumps(result))
    performance = normalized.get("performance", {})
    if isinstance(performance, dict):
        performance["total_time_ms"] = 10.0
    # index_status is dynamic (fts_document_count, last_updated change per run).
    # Normalize to a stable shape for snapshot comparison.
    index_status = normalized.get("index_status")
    if isinstance(index_status, dict):
        normalized["index_status"] = {
            k: ("__normalized__" if k in ("fts_document_count", "last_updated") else v)
            for k, v in index_status.items()
        }
    return normalized


@pytest.fixture(autouse=True)
def mock_search_dependencies():
    """Mock all search dependencies to isolate contract testing."""
    # Level 1/2 use core module directly
    with patch("tools.search_journals.core.search_l1_index", return_value=[]):
        with patch(
            "tools.search_journals.core.search_l2_metadata",
            return_value={"results": [], "truncated": False, "total_available": 0},
        ):
            with patch("tools.search_journals.core.scan_all_indices", return_value=[]):
                # Level 3 uses keyword_pipeline and semantic_pipeline modules
                with patch(
                    "tools.search_journals.keyword_pipeline.search_l3_content",
                    return_value=[],
                ):
                    with patch(
                        "tools.search_journals.keyword_pipeline.search_l2_metadata",
                        return_value={
                            "results": [],
                            "truncated": False,
                            "total_available": 0,
                        },
                    ):
                        with patch(
                            "tools.search_journals.keyword_pipeline.search_l1_index",
                            return_value=[],
                        ):
                            with patch(
                                "tools.search_journals.semantic_pipeline.search_semantic",
                                return_value=([], {}),
                            ):
                                with patch(
                                    "tools.search_journals.semantic_pipeline.get_semantic_runtime_status",
                                    return_value={
                                        "available": True,
                                        "reason": "",
                                        "note": "",
                                    },
                                ):
                                    yield


class TestSearchResponseShape:
    """hierarchical_search() response shape matches API.md."""

    def test_level1_response_has_all_required_fields(self):
        """Level 1 search returns all documented fields."""
        result = hierarchical_search(topic="work", level=1)

        for field in REQUIRED_RESPONSE_FIELDS:
            assert field in result, f"Missing required field: {field}"

    def test_level2_response_has_all_required_fields(self):
        """Level 2 search returns all documented fields."""
        result = hierarchical_search(
            location="Beijing",
            date_from="2026-01-01",
            date_to="2026-03-31",
            level=2,
        )

        for field in REQUIRED_RESPONSE_FIELDS:
            assert field in result, f"Missing required field: {field}"

    def test_level3_response_has_all_required_fields(self):
        """Level 3 (full dual-pipeline) search returns all documented fields."""
        result = hierarchical_search(query="test", level=3)

        for field in REQUIRED_RESPONSE_FIELDS:
            assert field in result, f"Missing required field: {field}"


class TestSearchFieldTypes:
    """Field types match API.md documentation."""

    def test_success_is_bool(self):
        """success field is boolean."""
        result = hierarchical_search(topic="work", level=1)
        assert isinstance(result["success"], bool)

    def test_result_arrays_are_lists(self):
        """l1/l2/l3/semantic/merged results are all lists."""
        result = hierarchical_search(query="test", level=3)

        assert isinstance(result["l1_results"], list)
        assert isinstance(result["l2_results"], list)
        assert isinstance(result["l3_results"], list)
        assert isinstance(result["semantic_results"], list)
        assert isinstance(result["merged_results"], list)

    def test_total_found_is_int(self):
        """total_found is an integer."""
        result = hierarchical_search(topic="work", level=1)
        assert isinstance(result["total_found"], int)

    def test_performance_is_dict(self):
        """performance is a dictionary."""
        result = hierarchical_search(topic="work", level=1)
        assert isinstance(result["performance"], dict)

    def test_query_params_is_dict(self):
        """query_params is a dictionary reflecting input parameters."""
        result = hierarchical_search(
            query="test",
            topic="work",
            level=3,
            semantic=True,
        )
        assert isinstance(result["query_params"], dict)
        assert result["query_params"]["query"] == "test"
        assert result["query_params"]["topic"] == "work"
        assert result["query_params"]["level"] == 3
        assert result["query_params"]["semantic"] is True

    def test_warnings_is_list(self):
        """warnings field is a list."""
        result = hierarchical_search(query="test", level=3)
        assert isinstance(result["warnings"], list)


class TestSearchEmptyVsFailure:
    """Empty results and failures are properly distinguished (API.md contract)."""

    def test_empty_results_is_success(self):
        """No results found is success=True with empty arrays (not a failure)."""
        result = hierarchical_search(query="nonexistent_query_xyz", level=3)

        assert result["success"] is True
        assert result["total_found"] == 0

    def test_success_true_on_valid_search(self):
        """A valid search execution always returns success=True."""
        result = hierarchical_search(topic="work", level=1)
        assert result["success"] is True


class TestSearchPerformanceFields:
    """Performance metrics are present and correctly typed."""

    def test_level1_has_timing(self):
        """Level 1 search includes l1_time_ms and total_time_ms."""
        result = hierarchical_search(topic="work", level=1)

        assert "l1_time_ms" in result["performance"]
        assert "total_time_ms" in result["performance"]
        assert isinstance(result["performance"]["l1_time_ms"], (int, float))
        assert isinstance(result["performance"]["total_time_ms"], (int, float))

    def test_level2_has_timing(self):
        """Level 2 search includes l2_time_ms and total_time_ms."""
        result = hierarchical_search(location="Beijing", level=2)

        assert "total_time_ms" in result["performance"]


class TestSearchQueryParamsContract:
    """query_params echoes input parameters accurately."""

    def test_query_params_reflects_inputs(self):
        """query_params contains the search parameters that were used."""
        result = hierarchical_search(
            query="test query",
            topic="work",
            project="Life-Index",
            tags=["tag1", "tag2"],
            mood=["happy"],
            people=["Alice"],
            date_from="2026-01-01",
            date_to="2026-03-31",
            level=3,
            semantic=False,
        )

        qp = result["query_params"]
        assert qp["query"] == "test query"
        assert qp["topic"] == "work"
        assert qp["project"] == "Life-Index"
        assert qp["tags"] == ["tag1", "tag2"]
        assert qp["mood"] == ["happy"]
        assert qp["people"] == ["Alice"]
        assert qp["date_from"] == "2026-01-01"
        assert qp["date_to"] == "2026-03-31"
        assert qp["level"] == 3
        assert qp["semantic"] is False


class TestSearchGoldenSnapshots:
    def test_search_result_matches_golden_snapshot(self):
        l1_results = [{"path": "C:/tmp/a.md", "title": "A"}]
        l2_results = [{"path": "C:/tmp/a.md", "metadata": {"topic": ["work"]}}]
        l3_results = [{"path": "C:/tmp/a.md", "content": "Golden hit"}]
        semantic_results = [
            {"path": "C:/tmp/a.md", "score": 0.91, "title": "A semantic"}
        ]
        merged_results = [
            {
                "path": "C:/tmp/a.md",
                "rel_path": "Journals/2026/03/a.md",
                "title": "A",
                "date": "2026-03-14",
                "rrf_score": 0.88,
            }
        ]

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=(
                    l1_results,
                    l2_results,
                    l3_results,
                    False,
                    0,
                    {"l1_time_ms": 1.0, "l2_time_ms": 2.0, "l3_time_ms": 3.0},
                ),
            ),
            patch(
                "tools.search_journals.core.run_semantic_pipeline",
                return_value=(
                    semantic_results,
                    {"semantic_time_ms": 4.0},
                    True,
                    "",
                ),
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results_hybrid",
                return_value=merged_results,
            ),
        ):
            result = hierarchical_search(query="golden", level=3)

        assert _normalize_search_snapshot(result) == _load_golden("search_result.json")
