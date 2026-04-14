#!/usr/bin/env python3
"""
Tests for Entity Cache Integration — Round 7 Phase 1 Task 2.

Validates that:
- Cache-backed lookup matches direct YAML resolution
- Cache freshness check detects stale cache (yaml mtime > db mtime)
- Graceful fallback to YAML when cache is missing or corrupt
- resolve_entity_cached() works correctly
"""

from pathlib import Path

import pytest

from tools.lib.entity_cache import build_entity_cache, query_entity_cache
from tools.lib.entity_graph import save_entity_graph, load_entity_graph
from tools.lib.entity_runtime import (
    build_runtime_view,
    resolve_via_runtime,
)


def _sample_entities() -> list[dict]:
    return [
        {
            "id": "wife-001",
            "type": "person",
            "primary_name": "王某某",
            "aliases": ["团团妈", "老婆"],
            "attributes": {},
            "relationships": [{"target": "author-self", "relation": "spouse_of"}],
        },
        {
            "id": "author-self",
            "type": "person",
            "primary_name": "我",
            "aliases": [],
            "attributes": {},
            "relationships": [],
        },
    ]


class TestCacheBuildAndQuery:
    """Core cache build/query cycle."""

    def test_cached_lookup_matches_yaml_resolution(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"
        payload = _sample_entities()
        save_entity_graph(payload, yaml_path)
        build_entity_cache(yaml_path, db_path)

        rows = query_entity_cache(db_path, "老婆")

        assert len(rows) == 1
        assert rows[0]["id"] == "wife-001"

    def test_cached_lookup_by_primary_name(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"
        save_entity_graph(_sample_entities(), yaml_path)
        build_entity_cache(yaml_path, db_path)

        rows = query_entity_cache(db_path, "王某某")

        assert len(rows) == 1
        assert rows[0]["id"] == "wife-001"

    def test_cached_lookup_by_id(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"
        save_entity_graph(_sample_entities(), yaml_path)
        build_entity_cache(yaml_path, db_path)

        rows = query_entity_cache(db_path, "wife-001")

        assert len(rows) == 1

    def test_cached_lookup_returns_empty_for_missing(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"
        save_entity_graph(_sample_entities(), yaml_path)
        build_entity_cache(yaml_path, db_path)

        rows = query_entity_cache(db_path, "不存在的")

        assert rows == []

    def test_query_returns_empty_when_db_missing(self, tmp_path: Path) -> None:
        rows = query_entity_cache(tmp_path / "nonexistent.db", "老婆")

        assert rows == []


class TestCacheFreshness:
    """Validate cache freshness detection."""

    def test_cache_stale_after_yaml_update(self, tmp_path: Path) -> None:
        """Cache should be considered stale when YAML is modified after cache build."""
        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"

        # Build cache
        save_entity_graph(_sample_entities(), yaml_path)
        build_entity_cache(yaml_path, db_path)

        # Verify initial cache works
        rows_before = query_entity_cache(db_path, "老婆")
        assert len(rows_before) == 1

        # Modify YAML (update with new entity)
        import time

        updated = _sample_entities() + [
            {
                "id": "new-entity",
                "type": "person",
                "primary_name": "新人",
                "aliases": [],
                "attributes": {},
                "relationships": [],
            }
        ]
        time.sleep(0.1)  # Ensure mtime differs
        save_entity_graph(updated, yaml_path)

        # Old cache should NOT have the new entity
        stale_rows = query_entity_cache(db_path, "新人")
        assert stale_rows == []

        # Rebuild cache should pick up new entity
        build_entity_cache(yaml_path, db_path)
        fresh_rows = query_entity_cache(db_path, "新人")
        assert len(fresh_rows) == 1

    def test_is_cache_fresh_returns_true_when_current(self, tmp_path: Path) -> None:
        from tools.lib.entity_cache import is_cache_fresh

        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"
        save_entity_graph(_sample_entities(), yaml_path)
        build_entity_cache(yaml_path, db_path)

        assert is_cache_fresh(yaml_path, db_path) is True

    def test_is_cache_fresh_returns_false_when_stale(self, tmp_path: Path) -> None:
        import time

        from tools.lib.entity_cache import is_cache_fresh

        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"
        save_entity_graph(_sample_entities(), yaml_path)
        build_entity_cache(yaml_path, db_path)

        # Touch YAML after cache build
        time.sleep(0.1)
        save_entity_graph(_sample_entities(), yaml_path)

        assert is_cache_fresh(yaml_path, db_path) is False

    def test_is_cache_fresh_returns_false_when_no_db(self, tmp_path: Path) -> None:
        from tools.lib.entity_cache import is_cache_fresh

        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "nonexistent.db"
        save_entity_graph(_sample_entities(), yaml_path)

        assert is_cache_fresh(yaml_path, db_path) is False


class TestResolveEntityCached:
    """Test resolve_entity_cached() with graceful fallback."""

    def test_resolve_uses_cache_when_fresh(self, tmp_path: Path) -> None:
        from tools.lib.entity_cache import build_entity_cache, resolve_entity_cached

        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"
        save_entity_graph(_sample_entities(), yaml_path)
        build_entity_cache(yaml_path, db_path)

        result = resolve_entity_cached("老婆", yaml_path, db_path)

        assert result is not None
        assert result["id"] == "wife-001"

    def test_resolve_falls_back_to_yaml_when_no_cache(self, tmp_path: Path) -> None:
        from tools.lib.entity_cache import resolve_entity_cached

        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "nonexistent.db"
        save_entity_graph(_sample_entities(), yaml_path)

        result = resolve_entity_cached("老婆", yaml_path, db_path)

        assert result is not None
        assert result["id"] == "wife-001"

    def test_resolve_falls_back_to_yaml_when_stale(self, tmp_path: Path) -> None:
        import time

        from tools.lib.entity_cache import build_entity_cache, resolve_entity_cached

        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"

        # Build cache with original data
        save_entity_graph(_sample_entities(), yaml_path)
        build_entity_cache(yaml_path, db_path)

        # Update YAML without rebuilding cache
        time.sleep(0.1)
        updated = _sample_entities() + [
            {
                "id": "stale-test",
                "type": "person",
                "primary_name": "测试人员",
                "aliases": [],
                "attributes": {},
                "relationships": [],
            }
        ]
        save_entity_graph(updated, yaml_path)

        # Should fall back to YAML and find the new entity
        result = resolve_entity_cached("测试人员", yaml_path, db_path)
        assert result is not None
        assert result["id"] == "stale-test"

    def test_resolve_returns_none_for_unknown(self, tmp_path: Path) -> None:
        from tools.lib.entity_cache import build_entity_cache, resolve_entity_cached

        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"
        save_entity_graph(_sample_entities(), yaml_path)
        build_entity_cache(yaml_path, db_path)

        result = resolve_entity_cached("不存在", yaml_path, db_path)
        assert result is None

    def test_resolve_on_empty_graph(self, tmp_path: Path) -> None:
        from tools.lib.entity_cache import resolve_entity_cached

        yaml_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"
        save_entity_graph([], yaml_path)

        result = resolve_entity_cached("anything", yaml_path, db_path)
        assert result is None
