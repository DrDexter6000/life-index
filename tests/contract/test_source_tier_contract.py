"""Contract tests for source-tier ranking boost (gbrain absorption Phase B).

Verifies that --enable-source-tier is opt-in and does not change default behavior.
TDD: RED → GREEN sequence must be preserved in commit history.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tools.search_journals.core import hierarchical_search
from tools.lib.index_freshness import FreshnessReport


@pytest.fixture(autouse=True)
def mock_search_dependencies():
    """Mock all search dependencies to isolate contract testing."""
    fresh_report = FreshnessReport(
        fts_fresh=True,
        vector_fresh=True,
        overall_fresh=True,
        issues=[],
    )
    with patch("tools.search_journals.core.search_l1_index", return_value=[]):
        with patch(
            "tools.search_journals.core.search_l2_metadata",
            return_value={"results": [], "truncated": False, "total_available": 0},
        ):
            with patch("tools.search_journals.core.scan_all_indices", return_value=[]):
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
                                    "tools.search_journals.semantic_pipeline."
                                    "get_semantic_runtime_status",
                                    return_value={
                                        "available": True,
                                        "reason": "",
                                        "note": "",
                                    },
                                ):
                                    with patch(
                                        "tools.lib.index_freshness.check_full_freshness",
                                        return_value=fresh_report,
                                    ):
                                        with patch(
                                            "tools.lib.pending_writes.has_pending",
                                            return_value=False,
                                        ):
                                            yield


class TestSourceTierDefaultBehavior:
    """Default search behavior without --enable-source-tier must be unchanged."""

    def test_default_search_does_not_enable_source_tier(self):
        """hierarchical_search() defaults enable_source_tier to False."""
        result = hierarchical_search(query="test", level=3)
        assert result["success"] is True
        # query_params should contain enable_source_tier=False by default
        assert result["query_params"].get("enable_source_tier") is False

    def test_default_search_does_not_pass_enable_source_tier_to_ranking(self):
        """Default search calls ranking without enable_source_tier."""
        with patch("tools.search_journals.core.merge_and_rank_results") as mock_merge:
            mock_merge.return_value = []
            hierarchical_search(query="test", level=3)
            _, kwargs = mock_merge.call_args
            assert kwargs.get("enable_source_tier") is not True


class TestSourceTierFlag:
    """--enable-source-tier flag is accepted and passed to ranking."""

    def test_enable_source_tier_is_accepted(self):
        """hierarchical_search() accepts enable_source_tier=True."""
        result = hierarchical_search(query="test", level=3, enable_source_tier=True)
        assert result["success"] is True
        assert result["query_params"].get("enable_source_tier") is True

    def test_enable_source_tier_passed_to_hybrid_ranking(self):
        """When semantic results exist, enable_source_tier is passed to hybrid ranking."""
        with patch("tools.search_journals.core.merge_and_rank_results_hybrid") as mock_hybrid:
            mock_hybrid.return_value = []
            with patch(
                "tools.search_journals.semantic_pipeline.search_semantic",
                return_value=([{"path": "x.md", "similarity": 0.5}], {}),
            ):
                hierarchical_search(
                    query="test",
                    level=3,
                    semantic=True,
                    semantic_policy="hybrid",
                    enable_source_tier=True,
                )
                _, kwargs = mock_hybrid.call_args
                assert kwargs.get("enable_source_tier") is True

    def test_enable_source_tier_passed_to_keyword_ranking(self):
        """When no semantic results, enable_source_tier is passed to keyword ranking."""
        with patch("tools.search_journals.core.merge_and_rank_results") as mock_merge:
            mock_merge.return_value = []
            hierarchical_search(query="test", level=3, enable_source_tier=True)
            _, kwargs = mock_merge.call_args
            assert kwargs.get("enable_source_tier") is True


class TestSourceTierRankingEffect:
    """Source-tier boost changes result ordering when enabled."""

    def test_tier_boost_changes_ordering(self):
        """Rich-metadata doc outranks basic doc when enable_source_tier=True."""
        from tools.search_journals.ranking import merge_and_rank_results

        rich = {
            "path": "Journals/2026/03/rich.md",
            "title": "Rich",
            "date": "2026-03-01",
            "metadata": {
                "topic": "work",
                "people": ["Alice"],
                "tags": ["project"],
                "related_entries": ["other.md"],
            },
        }
        basic = {
            "path": "Journals/2026/03/basic.md",
            "title": "Basic",
            "date": "2026-03-02",
            "metadata": {},
        }

        # Without source tier: both get same L2 base score
        results_off = merge_and_rank_results(
            [],
            [rich, basic],
            [],
            query="test",
            enable_source_tier=False,
        )
        paths_off = [r["path"] for r in results_off]

        # With source tier: rich should outrank basic due to metadata richness
        results_on = merge_and_rank_results(
            [],
            [rich, basic],
            [],
            query="test",
            enable_source_tier=True,
        )
        paths_on = [r["path"] for r in results_on]

        assert len(paths_off) == 2
        assert len(paths_on) == 2
        assert (
            paths_on[0] == rich["path"]
        ), f"Rich doc should rank first with tier on, got {paths_on}"
