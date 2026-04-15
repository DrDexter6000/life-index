#!/usr/bin/env python3
"""
Tests for Entity Runtime View — Round 7 Phase 1 Task 1.

Validates that build_runtime_view produces correct:
- by_lookup map (alias → entity, primary_name → entity, id → entity)
- reverse_relationships map (target_id → [(source_id, relation)])
- phrase_patterns list
- resolve_via_runtime lookup
"""

from pathlib import Path

import pytest

from tools.lib.entity_runtime import (
    EntityRuntimeView,
    build_runtime_view,
    load_runtime_view,
    resolve_via_runtime,
)


def _sample_graph() -> list[dict]:
    return [
        {
            "id": "wife-001",
            "type": "person",
            "primary_name": "王某某",
            "aliases": ["乐乐妈", "老婆"],
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
        {
            "id": "mama",
            "type": "person",
            "primary_name": "妈妈",
            "aliases": ["老妈", "婆婆"],
            "attributes": {},
            "relationships": [
                {"target": "author-self", "relation": "mother_of"},
                {"target": "tuantuan", "relation": "grandmother_of"},
            ],
        },
        {
            "id": "tuantuan",
            "type": "person",
            "primary_name": "乐乐",
            "aliases": ["圆圆"],
            "attributes": {},
            "relationships": [{"target": "author-self", "relation": "child_of"}],
        },
        {
            "id": "chongqing",
            "type": "place",
            "primary_name": "重庆",
            "aliases": ["Chongqing", "山城", "老家"],
            "attributes": {},
            "relationships": [],
        },
    ]


class TestBuildRuntimeView:
    """Tests for build_runtime_view() producing correct derived structures."""

    def test_builds_lookup_by_alias(self) -> None:
        view = build_runtime_view(_sample_graph())

        assert view.by_lookup["老婆"]["id"] == "wife-001"
        assert view.by_lookup["乐乐妈"]["id"] == "wife-001"

    def test_builds_lookup_by_primary_name(self) -> None:
        view = build_runtime_view(_sample_graph())

        assert view.by_lookup["王某某"]["id"] == "wife-001"
        assert view.by_lookup["我"]["id"] == "author-self"
        assert view.by_lookup["妈妈"]["id"] == "mama"

    def test_builds_lookup_by_id(self) -> None:
        view = build_runtime_view(_sample_graph())

        assert view.by_lookup["wife-001"]["id"] == "wife-001"
        assert view.by_lookup["chongqing"]["id"] == "chongqing"

    def test_reverse_relationships_maps_target_to_sources(self) -> None:
        view = build_runtime_view(_sample_graph())

        # author-self is target of wife-001's spouse_of and mama's mother_of
        reverse = view.reverse_relationships["author-self"]
        source_ids = {pair[0] for pair in reverse}
        relations = {pair[1] for pair in reverse}

        assert "wife-001" in source_ids
        assert "mama" in source_ids
        assert "spouse_of" in relations
        assert "mother_of" in relations

    def test_reverse_relationships_single_source(self) -> None:
        view = build_runtime_view(_sample_graph())

        # tuantuan is target of mama's grandmother_of
        reverse = view.reverse_relationships["tuantuan"]
        assert len(reverse) == 1
        assert reverse[0] == ("mama", "grandmother_of")

    def test_reverse_relationships_empty_for_no_incoming(self) -> None:
        view = build_runtime_view(_sample_graph())

        # wife-001 has no incoming relationships
        assert view.reverse_relationships.get("wife-001", []) == []

    def test_entities_stored(self) -> None:
        view = build_runtime_view(_sample_graph())

        assert len(view.entities) == 5
        ids = {e["id"] for e in view.entities}
        assert ids == {"wife-001", "author-self", "mama", "tuantuan", "chongqing"}

    def test_empty_graph_produces_empty_view(self) -> None:
        view = build_runtime_view([])

        assert view.entities == []
        assert view.by_lookup == {}
        assert view.reverse_relationships == {}

    def test_phrase_patterns_not_empty(self) -> None:
        view = build_runtime_view(_sample_graph())

        # Should have at least the default relationship phrase patterns
        assert len(view.phrase_patterns) > 0

    def test_phrase_patterns_use_grandparent_relations(self) -> None:
        view = build_runtime_view(_sample_graph())

        assert {
            pattern["suffix"]: pattern["relation"] for pattern in view.phrase_patterns
        }["的奶奶"] == "grandmother_of"
        assert {
            pattern["suffix"]: pattern["relation"] for pattern in view.phrase_patterns
        }["的爷爷"] == "grandfather_of"

    def test_phrase_patterns_include_child_suffixes(self) -> None:
        view = build_runtime_view(_sample_graph())

        relation_by_suffix = {
            pattern["suffix"]: pattern["relation"] for pattern in view.phrase_patterns
        }

        assert relation_by_suffix["的女儿"] == "child_of"
        assert relation_by_suffix["的儿子"] == "child_of"
        assert relation_by_suffix["的孩子"] == "child_of"


class TestResolveViaRuntime:
    """Tests for resolve_via_runtime() using the runtime view."""

    def test_resolve_by_alias(self) -> None:
        view = build_runtime_view(_sample_graph())

        result = resolve_via_runtime("老婆", view)

        assert result is not None
        assert result["id"] == "wife-001"

    def test_resolve_by_primary_name(self) -> None:
        view = build_runtime_view(_sample_graph())

        result = resolve_via_runtime("重庆", view)

        assert result is not None
        assert result["id"] == "chongqing"

    def test_resolve_by_id(self) -> None:
        view = build_runtime_view(_sample_graph())

        result = resolve_via_runtime("mama", view)

        assert result is not None
        assert result["primary_name"] == "妈妈"

    def test_resolve_not_found(self) -> None:
        view = build_runtime_view(_sample_graph())

        result = resolve_via_runtime("不存在的实体", view)

        assert result is None

    def test_resolve_on_empty_view(self) -> None:
        view = build_runtime_view([])

        result = resolve_via_runtime("anything", view)

        assert result is None


class TestLoadRuntimeView:
    """Tests for load_runtime_view() loading from YAML file."""

    def test_loads_from_yaml_file(self, tmp_path: Path) -> None:
        from tools.lib.entity_graph import save_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        save_entity_graph(_sample_graph(), graph_path)

        view = load_runtime_view(graph_path)

        assert view.by_lookup["老婆"]["id"] == "wife-001"
        assert "author-self" in view.reverse_relationships

    def test_loads_empty_when_file_missing(self, tmp_path: Path) -> None:
        view = load_runtime_view(tmp_path / "nonexistent.yaml")

        assert view.entities == []
        assert view.by_lookup == {}
