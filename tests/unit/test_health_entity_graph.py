"""
Tests for health check detecting missing entity graph (Round 10, T1.3).

Validates D6: life-index health emits entity_graph_missing event
when entity_graph.yaml doesn't exist or is empty.
"""

from pathlib import Path
from typing import Any

import pytest


class TestHealthEntityGraphCheck:
    """Verify health check detects missing entity graph."""

    def test_missing_graph_emits_warning(self, isolated_data_dir: Path) -> None:
        """Graph not existing → entity_graph check status=warning."""
        from tools.__main__ import _check_entity_graph

        graph_path = isolated_data_dir / "entity_graph.yaml"
        check = _check_entity_graph(graph_path)

        assert check["name"] == "entity_graph"
        assert check["status"] == "warning"
        assert (
            "not found" in check.get("issue", "").lower()
            or "not_initialized" in check.get("issue", "").lower()
        )

    def test_empty_graph_emits_warning(self, isolated_data_dir: Path) -> None:
        """Graph exists but empty → warning."""
        from tools.__main__ import _check_entity_graph

        graph_path = isolated_data_dir / "entity_graph.yaml"
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        graph_path.write_text("entities: []\n", encoding="utf-8")

        check = _check_entity_graph(graph_path)
        assert check["status"] == "warning"

    def test_populated_graph_is_ok(self, isolated_data_dir: Path) -> None:
        """Graph with entities → status=ok."""
        from tools.__main__ import _check_entity_graph

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

        check = _check_entity_graph(graph_path)
        assert check["status"] == "ok"
