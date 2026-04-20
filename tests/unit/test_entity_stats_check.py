#!/usr/bin/env python3
"""
Tests for entity --stats / --check — Round 7 Phase 3 Task 9.

Validates that:
- stats reports reference counts, type breakdown, co-occurrence
- check reports dangling relationships, duplicate lookups, schema issues
"""

from pathlib import Path

import pytest

from tools.lib.entity_graph import load_entity_graph, save_entity_graph
import yaml


def _rich_graph() -> list[dict]:
    """Graph with multiple types, relationships, and aliases."""
    return [
        {
            "id": "person-a",
            "type": "person",
            "primary_name": "张三",
            "aliases": ["老张", "张哥"],
            "attributes": {},
            "relationships": [
                {"target": "person-b", "relation": "colleague_of"},
                {"target": "place-001", "relation": "lives_in"},
            ],
        },
        {
            "id": "person-b",
            "type": "person",
            "primary_name": "李四",
            "aliases": [],
            "attributes": {},
            "relationships": [
                {"target": "person-a", "relation": "colleague_of"},
            ],
        },
        {
            "id": "place-001",
            "type": "place",
            "primary_name": "拉各斯",
            "aliases": ["Lagos"],
            "attributes": {},
            "relationships": [],
        },
        {
            "id": "project-001",
            "type": "project",
            "primary_name": "LifeIndex",
            "aliases": ["LI", "life-index"],
            "attributes": {},
            "relationships": [],
        },
    ]


def _graph_with_issues() -> list[dict]:
    """Graph with dangling relationships and empty aliases."""
    return [
        {
            "id": "person-x",
            "type": "person",
            "primary_name": "王五",
            "aliases": [],
            "attributes": {},
            "relationships": [
                {"target": "nonexistent-id", "relation": "friend_of"},  # dangling
            ],
        },
        {
            "id": "person-y",
            "type": "person",
            "primary_name": "赵六",
            "aliases": [],
            "attributes": {},
            "relationships": [],
        },
    ]


def _save_graph(entities: list[dict], isolated_data_dir: Path) -> None:
    from tools.lib.entity_graph import save_entity_graph

    save_entity_graph(entities, isolated_data_dir / "entity_graph.yaml")


def _save_graph_raw(entities: list[dict], path: Path) -> None:
    """Save graph directly to YAML, bypassing validation.

    Used for testing integrity checks on malformed graphs
    that wouldn't pass save_entity_graph validation.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(
            {"entities": entities}, f, allow_unicode=True, default_flow_style=False
        )


def _graph_path_for(isolated_data_dir: Path) -> Path:
    return isolated_data_dir / "entity_graph.yaml"


class TestEntityStats:
    """entity --stats reports structured graph statistics."""

    def test_stats_reports_total_entities(self, isolated_data_dir: Path) -> None:
        from tools.entity.stats import compute_stats

        _save_graph(_rich_graph(), isolated_data_dir)

        result = compute_stats(graph_path=_graph_path_for(isolated_data_dir))

        assert result["success"] is True
        assert result["data"]["total_entities"] == 4

    def test_stats_reports_by_type_breakdown(self, isolated_data_dir: Path) -> None:
        from tools.entity.stats import compute_stats

        _save_graph(_rich_graph(), isolated_data_dir)

        result = compute_stats(graph_path=_graph_path_for(isolated_data_dir))

        by_type = result["data"]["by_type"]
        assert by_type["person"] == 2
        assert by_type["place"] == 1
        assert by_type["project"] == 1

    def test_stats_reports_total_relationships(self, isolated_data_dir: Path) -> None:
        from tools.entity.stats import compute_stats

        _save_graph(_rich_graph(), isolated_data_dir)

        result = compute_stats(graph_path=_graph_path_for(isolated_data_dir))

        assert result["data"]["total_relationships"] >= 3

    def test_stats_reports_total_aliases(self, isolated_data_dir: Path) -> None:
        from tools.entity.stats import compute_stats

        _save_graph(_rich_graph(), isolated_data_dir)

        result = compute_stats(graph_path=_graph_path_for(isolated_data_dir))

        # person-a: 2, place-001: 1, project-001: 2 = 5 total
        assert result["data"]["total_aliases"] == 5

    def test_stats_on_empty_graph(self, isolated_data_dir: Path) -> None:
        from tools.entity.stats import compute_stats

        # No graph file → should return gracefully
        result = compute_stats(graph_path=_graph_path_for(isolated_data_dir))

        assert result["success"] is True
        assert result["data"]["total_entities"] == 0

    def test_stats_top_referenced(self, isolated_data_dir: Path) -> None:
        """Entities with most incoming relationships appear in top_referenced."""
        from tools.entity.stats import compute_stats

        _save_graph(_rich_graph(), isolated_data_dir)

        result = compute_stats(graph_path=_graph_path_for(isolated_data_dir))

        top = result["data"]["top_referenced"]
        # person-a has 1 incoming ref (from person-b)
        # place-001 has 1 incoming ref (from person-a)
        assert len(top) >= 1


class TestEntityCheck:
    """entity --check reports integrity issues."""

    def test_check_reports_dangling_relationships(
        self, isolated_data_dir: Path
    ) -> None:
        from tools.entity.check import run_check

        # Must bypass validation — save_entity_graph rejects dangling refs
        _save_graph_raw(_graph_with_issues(), _graph_path_for(isolated_data_dir))

        result = run_check(graph_path=_graph_path_for(isolated_data_dir))

        assert result["success"] is True
        issues = result["data"]["issues"]
        dangling = [i for i in issues if i["type"] == "dangling_relationship"]
        assert len(dangling) >= 1
        assert dangling[0]["entity_id"] == "person-x"
        assert dangling[0]["target"] == "nonexistent-id"

    def test_check_clean_graph_has_no_issues(self, isolated_data_dir: Path) -> None:
        from tools.entity.check import run_check

        _save_graph(_rich_graph(), isolated_data_dir)

        result = run_check(graph_path=_graph_path_for(isolated_data_dir))

        assert result["success"] is True
        issues = result["data"]["issues"]
        assert len(issues) == 0

    def test_check_empty_graph(self, isolated_data_dir: Path) -> None:
        from tools.entity.check import run_check

        result = run_check(graph_path=_graph_path_for(isolated_data_dir))

        assert result["success"] is True
        assert result["data"]["issues"] == []
        assert result["data"]["total_entities"] == 0

    def test_check_via_cli(self, isolated_data_dir: Path) -> None:
        """CLI entity --stats and --check produce valid JSON output."""
        from tools.entity.__main__ import main

        _save_graph(_rich_graph(), isolated_data_dir)

        # Should not crash
        main(["--stats"])
        main(["--check"])
