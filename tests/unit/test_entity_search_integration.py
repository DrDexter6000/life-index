#!/usr/bin/env python3

from pathlib import Path

import pytest


def _entity_graph_payload() -> list[dict]:
    return [
        {
            "id": "author-self",
            "type": "person",
            "primary_name": "我",
            "aliases": ["作者", "自己"],
            "relationships": [],
        },
        {
            "id": "mama",
            "type": "person",
            "primary_name": "妈妈",
            "aliases": ["老妈", "婆婆", "王阿姨"],
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
            "relationships": [{"target": "author-self", "relation": "child_of"}],
        },
        {
            "id": "chongqing",
            "type": "place",
            "primary_name": "重庆",
            "aliases": ["Chongqing", "山城", "老家"],
            "relationships": [],
        },
        {
            "id": "life-index",
            "type": "project",
            "primary_name": "Life Index",
            "aliases": ["LobsterAI Journal", "日志系统"],
            "relationships": [],
        },
    ]


class TestEntityQueryExpansion:
    def test_alias_expansion(self, isolated_data_dir: Path) -> None:
        from tools.lib.entity_graph import save_entity_graph
        from tools.search_journals.core import expand_query_with_entity_graph

        save_entity_graph(_entity_graph_payload(), isolated_data_dir / "entity_graph.yaml")

        expanded = expand_query_with_entity_graph("婆婆")

        assert "妈妈" in expanded
        assert "老妈" in expanded
        assert "王阿姨" in expanded

    def test_relationship_resolution(self, isolated_data_dir: Path) -> None:
        from tools.lib.entity_graph import save_entity_graph
        from tools.search_journals.core import expand_query_with_entity_graph

        save_entity_graph(_entity_graph_payload(), isolated_data_dir / "entity_graph.yaml")

        expanded = expand_query_with_entity_graph("乐乐的奶奶")

        assert "妈妈" in expanded
        assert "婆婆" in expanded
        assert "王阿姨" in expanded

    def test_relationship_resolution_uses_names_not_hardcoded_ids(
        self, isolated_data_dir: Path
    ) -> None:
        from tools.lib.entity_graph import save_entity_graph
        from tools.search_journals.core import expand_query_with_entity_graph

        payload = _entity_graph_payload()
        payload[2]["id"] = "child-001"
        payload[1]["relationships"][1]["target"] = "child-001"

        save_entity_graph(payload, isolated_data_dir / "entity_graph.yaml")

        expanded = expand_query_with_entity_graph("乐乐的奶奶")

        assert "妈妈" in expanded
        assert "婆婆" in expanded
        assert "王阿姨" in expanded

    def test_child_relationship_resolution(self, isolated_data_dir: Path) -> None:
        from tools.lib.entity_graph import save_entity_graph
        from tools.search_journals.core import expand_query_with_entity_graph

        save_entity_graph(_entity_graph_payload(), isolated_data_dir / "entity_graph.yaml")

        expanded = expand_query_with_entity_graph("我女儿")

        assert "乐乐" in expanded
        assert "圆圆" in expanded

    def test_place_alias(self, isolated_data_dir: Path) -> None:
        from tools.lib.entity_graph import save_entity_graph
        from tools.search_journals.core import expand_query_with_entity_graph

        save_entity_graph(_entity_graph_payload(), isolated_data_dir / "entity_graph.yaml")

        expanded = expand_query_with_entity_graph("老家的照片")

        assert "重庆" in expanded
        assert "山城" in expanded

    def test_project_alias(self, isolated_data_dir: Path) -> None:
        from tools.lib.entity_graph import save_entity_graph
        from tools.search_journals.core import expand_query_with_entity_graph

        save_entity_graph(_entity_graph_payload(), isolated_data_dir / "entity_graph.yaml")

        expanded = expand_query_with_entity_graph("LobsterAI Journal")

        assert "Life Index" in expanded
        assert "日志系统" in expanded

    def test_no_entity_match_passthrough(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import expand_query_with_entity_graph

        expanded = expand_query_with_entity_graph("完全陌生的查询")

        assert expanded == "完全陌生的查询"

    def test_expansion_merged_with_original(self, isolated_data_dir: Path) -> None:
        from tools.lib.entity_graph import save_entity_graph
        from tools.search_journals.core import expand_query_with_entity_graph

        save_entity_graph(_entity_graph_payload(), isolated_data_dir / "entity_graph.yaml")

        expanded = expand_query_with_entity_graph("婆婆 照片")

        assert "照片" in expanded
        assert "婆婆" in expanded
        assert "妈妈" in expanded
