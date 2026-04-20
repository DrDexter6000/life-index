"""
Tests for entity_graph_status in search response (Round 10, T1.2).

Validates D4: search output exposes whether entity graph is
initialized, with suggested_action when missing.
"""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from tools.lib.index_freshness import FreshnessReport


@pytest.fixture(autouse=True)
def _mock_fresh_index_state():
    fresh_report = FreshnessReport(
        fts_fresh=True,
        vector_fresh=True,
        overall_fresh=True,
        issues=[],
    )
    with patch("tools.lib.index_freshness.check_full_freshness", return_value=fresh_report):
        with patch("tools.lib.pending_writes.has_pending", return_value=False):
            yield


class TestEntityGraphStatus:
    """Verify entity_graph_status appears in search response."""

    def test_missing_graph_returns_not_initialized(
        self, isolated_data_dir: Path
    ) -> None:
        """When entity_graph.yaml doesn't exist, status = not_initialized."""
        from tools.lib.entity_graph import check_graph_status

        graph_path = isolated_data_dir / "entity_graph.yaml"
        status = check_graph_status(graph_path)

        assert status["status"] == "not_initialized"
        assert status["suggested_action"] is not None
        assert "entity --seed" in status["suggested_action"]["command"]

    def test_empty_graph_returns_empty(self, isolated_data_dir: Path) -> None:
        """When entity_graph.yaml exists but has empty entities list."""
        from tools.lib.entity_graph import check_graph_status

        graph_path = isolated_data_dir / "entity_graph.yaml"
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        graph_path.write_text("entities: []\n", encoding="utf-8")

        status = check_graph_status(graph_path)
        assert status["status"] == "empty"
        assert status["suggested_action"] is not None

    def test_populated_graph_returns_initialized(self, isolated_data_dir: Path) -> None:
        """When graph has entities, status = initialized, no suggested_action."""
        from tools.lib.entity_graph import check_graph_status

        graph_path = isolated_data_dir / "entity_graph.yaml"
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        graph_path.write_text(
            "entities:\n"
            "  - id: e1\n"
            "    type: person\n"
            "    primary_name: 乐乐\n"
            "    aliases: []\n"
            "    attributes: {}\n"
            "    relationships: []\n",
            encoding="utf-8",
        )

        status = check_graph_status(graph_path)
        assert status["status"] == "initialized"
        assert status["suggested_action"] is None
        assert status["entity_count"] == 1

    def test_search_response_includes_status(self, isolated_data_dir: Path) -> None:
        """Search response dict must contain entity_graph_status field."""
        from tools.search_journals.core import hierarchical_search

        # Ensure no graph exists
        graph_path = isolated_data_dir / "entity_graph.yaml"
        assert not graph_path.exists()

        result = hierarchical_search(
            query="测试",
            level=1,
            use_index=False,
            semantic=False,
        )

        assert "entity_graph_status" in result
        assert result["entity_graph_status"]["status"] == "not_initialized"
