#!/usr/bin/env python3
"""
Tests for Search Expansion v2 — Round 7 Phase 1 Task 3.

Validates that the new phrase registry expands:
- Role labels (老婆, 妻子 → spouse entity's all names)
- Kinship phrase patterns (X的奶奶, X的妈妈, X的老婆)
- Place phrases (老家 → place entity expansion)
- Backward compatibility with existing alias expansion
"""

from pathlib import Path

import pytest

from tools.lib.entity_graph import save_entity_graph


def _spouse_family_graph() -> list[dict]:
    """Entity graph with spouse + family relationships."""
    return [
        {
            "id": "wife-001",
            "type": "person",
            "primary_name": "王某某",
            "aliases": ["乐乐妈", "老婆", "妻子"],
            "attributes": {},
            "relationships": [{"target": "author-self", "relation": "spouse_of"}],
        },
        {
            "id": "author-self",
            "type": "person",
            "primary_name": "我",
            "aliases": [],
            "attributes": {},
            "relationships": [{"target": "wife-001", "relation": "spouse_of"}],
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


def _save_graph(entities: list[dict], isolated_data_dir: Path) -> None:
    from tools.lib.entity_graph import save_entity_graph

    save_entity_graph(entities, isolated_data_dir / "entity_graph.yaml")


class TestRoleLabelExpansion:
    """Role labels like 老婆 should expand to entity's full name group."""

    def test_wife_expands_to_all_names(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)

        expanded = expand_query_with_entity_graph("老婆")

        assert "乐乐妈" in expanded
        assert "妻子" in expanded
        assert "王某某" in expanded

    def test_alias_expansion_still_works(self, isolated_data_dir: Path) -> None:
        """Backward compat: alias expansion via exact match still works."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)

        expanded = expand_query_with_entity_graph("婆婆")

        assert "妈妈" in expanded
        assert "老妈" in expanded


class TestRelationshipPhrasePatterns:
    """Phrase patterns like X的奶奶 should use the registry."""

    def test_granddaughter_of_grandma(self, isolated_data_dir: Path) -> None:
        """乐乐的奶奶 → expand mama entity names."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)

        expanded = expand_query_with_entity_graph("乐乐的奶奶")

        assert "妈妈" in expanded
        assert "婆婆" in expanded
        assert "老妈" in expanded

    def test_x_wife_phrase(self, isolated_data_dir: Path) -> None:
        """我的老婆 → expand wife entity names."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)

        expanded = expand_query_with_entity_graph("我的老婆")

        assert "王某某" in expanded
        assert "乐乐妈" in expanded

    def test_x_mother_phrase(self, isolated_data_dir: Path) -> None:
        """我的妈妈 → expand mama entity names."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)

        expanded = expand_query_with_entity_graph("我的妈妈")

        assert "老妈" in expanded
        assert "婆婆" in expanded

    def test_x_daughter_phrase(self, isolated_data_dir: Path) -> None:
        """我女儿 → expand child entity names via reverse relationship lookup."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)

        expanded = expand_query_with_entity_graph("我女儿")

        assert "乐乐" in expanded
        assert "圆圆" in expanded

    def test_x_child_phrase(self, isolated_data_dir: Path) -> None:
        """我的孩子 → expand child entity names via reverse relationship lookup."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)

        expanded = expand_query_with_entity_graph("我的孩子")

        assert "乐乐" in expanded
        assert "圆圆" in expanded

    def test_phrase_unknown_subject_passthrough(self, isolated_data_dir: Path) -> None:
        """X的老婆 where X is unknown → no crash, meaningful passthrough."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)

        expanded = expand_query_with_entity_graph("陌生人的老婆")

        # Should not crash; should still contain the query parts
        assert "陌生人" in expanded


class TestPlacePhraseExpansion:
    """Place-related phrases should expand correctly."""

    def test_hometown_expansion(self, isolated_data_dir: Path) -> None:
        """老家 should expand to hometown entity aliases."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)

        expanded = expand_query_with_entity_graph("老家的照片")

        assert "重庆" in expanded
        assert "山城" in expanded


class TestBackwardCompat:
    """Existing behavior must not regress."""

    def test_no_entity_match_passthrough(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import expand_query_with_entity_graph

        expanded = expand_query_with_entity_graph("完全陌生的查询")

        assert expanded == "完全陌生的查询"

    def test_empty_graph_passthrough(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import expand_query_with_entity_graph

        expanded = expand_query_with_entity_graph("任何查询")

        assert expanded == "任何查询"

    def test_project_alias_still_works(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import expand_query_with_entity_graph

        graph = _spouse_family_graph() + [
            {
                "id": "life-index",
                "type": "project",
                "primary_name": "Life Index",
                "aliases": ["LobsterAI Journal", "日志系统"],
                "attributes": {},
                "relationships": [],
            }
        ]
        _save_graph(graph, isolated_data_dir)

        expanded = expand_query_with_entity_graph("LobsterAI Journal")

        assert "Life Index" in expanded
        assert "日志系统" in expanded
