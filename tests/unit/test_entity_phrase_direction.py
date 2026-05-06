#!/usr/bin/env python3
"""
Tests for relationship phrase directionality and family_role_labels filtering.

D6-R1 fix: ensures that:
- X的老婆/老公 uses symmetric traversal + spouse_perspective filter
- X的妈妈/爸爸 uses reverse traversal + child_perspective filter
- X的女儿/儿子 uses reverse traversal + parent_perspective filter
- X的孩子 uses reverse traversal + parent_perspective filter (daughter + son)
"""

from pathlib import Path

from tools.lib.entity_graph import save_entity_graph
from tools.search_journals.core import expand_query_with_entity_graph, resolve_query_entities


def _d6_family_graph() -> list[dict]:
    """Entity graph mirroring the D6 sandbox design."""
    return [
        {
            "id": "person-wang-daming",
            "type": "person",
            "primary_name": "李维杰",
            "aliases": ["Dexter"],
            "attributes": {
                "family_role_labels": {
                    "child_perspective": {"primary": "爸爸", "aliases": []},
                    "spouse_perspective": {"primary": "老公", "aliases": []},
                }
            },
            "relationships": [
                {"target": "person-chen-xiaohong", "relation": "spouse_of"},
                {"target": "person-wang-lele", "relation": "parent_of"},
                {"target": "person-wang-xiaobai", "relation": "parent_of"},
                {"target": "person-tu-xiuying", "relation": "child_of"},
                {"target": "person-li-jianguo", "relation": "child_of"},
            ],
        },
        {
            "id": "person-chen-xiaohong",
            "type": "person",
            "primary_name": "陈小红",
            "aliases": ["Mia", "小米", "乐乐妈", "小柏妈"],
            "attributes": {
                "family_role_labels": {
                    "child_perspective": {"primary": "妈妈", "aliases": []},
                    "spouse_perspective": {"primary": "老婆", "aliases": []},
                }
            },
            "relationships": [
                {"target": "person-wang-daming", "relation": "spouse_of"},
                {"target": "person-wang-lele", "relation": "parent_of"},
                {"target": "person-wang-xiaobai", "relation": "parent_of"},
            ],
        },
        {
            "id": "person-wang-lele",
            "type": "person",
            "primary_name": "王乐乐",
            "aliases": ["小豆丁", "小英雄"],
            "attributes": {
                "family_role_labels": {
                    "parent_perspective": {"primary": "女儿", "aliases": []},
                }
            },
            "relationships": [
                {"target": "person-wang-daming", "relation": "child_of"},
                {"target": "person-chen-xiaohong", "relation": "child_of"},
            ],
        },
        {
            "id": "person-wang-xiaobai",
            "type": "person",
            "primary_name": "王小柏",
            "aliases": ["柏宝", "小柏"],
            "attributes": {
                "family_role_labels": {
                    "parent_perspective": {"primary": "儿子", "aliases": []},
                }
            },
            "relationships": [
                {"target": "person-wang-daming", "relation": "child_of"},
                {"target": "person-chen-xiaohong", "relation": "child_of"},
            ],
        },
        {
            "id": "person-tu-xiuying",
            "type": "person",
            "primary_name": "凃秀英",
            "aliases": [],
            "attributes": {
                "family_role_labels": {
                    "child_perspective": {"primary": "婆婆", "aliases": ["奶奶"]},
                }
            },
            "relationships": [
                {"target": "person-wang-daming", "relation": "parent_of"},
            ],
        },
        {
            "id": "person-li-jianguo",
            "type": "person",
            "primary_name": "李建国",
            "aliases": [],
            "attributes": {
                "family_role_labels": {
                    "child_perspective": {"primary": "爷爷", "aliases": []},
                }
            },
            "relationships": [
                {"target": "person-wang-daming", "relation": "parent_of"},
            ],
        },
        {
            "id": "person-li-yulan",
            "type": "person",
            "primary_name": "李玉兰",
            "aliases": ["岳母"],
            "attributes": {
                "family_role_labels": {
                    "by_observer": {
                        "person-chen-xiaohong": {"primary": "妈妈", "aliases": []},
                        "person-wang-lele": {"primary": "外婆", "aliases": ["姥姥"]},
                        "person-wang-xiaobai": {"primary": "外婆", "aliases": ["姥姥"]},
                    }
                }
            },
            "relationships": [
                {"target": "person-chen-xiaohong", "relation": "parent_of"},
                {"target": "person-wang-lele", "relation": "grandmother_of"},
                {"target": "person-wang-xiaobai", "relation": "grandmother_of"},
            ],
        },
        {
            "id": "person-zhang-guoqiang",
            "type": "person",
            "primary_name": "张国强",
            "aliases": ["岳父"],
            "attributes": {
                "family_role_labels": {
                    "by_observer": {
                        "person-chen-xiaohong": {"primary": "爸爸", "aliases": []},
                        "person-wang-lele": {"primary": "外公", "aliases": ["姥爷"]},
                        "person-wang-xiaobai": {"primary": "外公", "aliases": ["姥爷"]},
                    }
                }
            },
            "relationships": [
                {"target": "person-chen-xiaohong", "relation": "parent_of"},
                {"target": "person-wang-lele", "relation": "grandfather_of"},
                {"target": "person-wang-xiaobai", "relation": "grandfather_of"},
            ],
        },
    ]


def _save_graph(entities: list[dict], isolated_data_dir: Path) -> None:
    save_entity_graph(entities, isolated_data_dir / "entity_graph.yaml")


class TestSpouseDirection:
    """spouse_of is symmetric — both directions should resolve."""

    def test_liweijie_wife(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("李维杰的老婆")
        assert "陈小红" in expanded
        assert "Mia" in expanded
        assert "老婆" in expanded
        assert "李维杰" not in expanded  # should not expand to self

    def test_zhangyanhan_husband(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("陈小红的老公")
        assert "李维杰" in expanded
        assert "Dexter" in expanded
        assert "老公" in expanded
        assert "陈小红" not in expanded

    def test_wife_role_filter_excludes_husband(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        hints = resolve_query_entities("李维杰的老婆")
        ids = [h["entity_id"] for h in hints]
        assert "person-chen-xiaohong" in ids
        assert "person-wang-daming" not in ids


class TestParentDirection:
    """parent_of with reverse traversal + child_perspective filter."""

    def test_limucheng_mother(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("王乐乐的妈妈")
        assert "陈小红" in expanded
        assert "妈妈" in expanded
        assert "李维杰" not in expanded  # filtered by child_perspective (爸爸 != 妈妈)

    def test_limucheng_father(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("王乐乐的爸爸")
        assert "李维杰" in expanded
        assert "爸爸" in expanded
        assert "陈小红" not in expanded  # filtered by child_perspective (妈妈 != 爸爸)

    def test_mother_entity_hint_only_mother(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        hints = resolve_query_entities("王乐乐的妈妈")
        ids = [h["entity_id"] for h in hints]
        assert "person-chen-xiaohong" in ids
        assert "person-wang-daming" not in ids


class TestChildDirection:
    """child_of with reverse traversal + parent_perspective filter."""

    def test_liweijie_daughter(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("李维杰的女儿")
        assert "王乐乐" in expanded
        assert "小豆丁" in expanded
        assert "女儿" in expanded
        # Must NOT include son or parents
        assert "王小柏" not in expanded
        assert "凃秀英" not in expanded
        assert "李建国" not in expanded

    def test_liweijie_son(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("李维杰的儿子")
        assert "王小柏" in expanded
        assert "柏宝" in expanded
        assert "儿子" in expanded
        # Must NOT include daughter or parents
        assert "王乐乐" not in expanded
        assert "凃秀英" not in expanded
        assert "李建国" not in expanded

    def test_liweijie_children(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("李维杰的孩子")
        assert "王乐乐" in expanded
        assert "王小柏" in expanded
        assert "女儿" in expanded
        assert "儿子" in expanded
        # Must NOT include parents
        assert "凃秀英" not in expanded
        assert "李建国" not in expanded

    def test_daughter_entity_hint_no_parents(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        hints = resolve_query_entities("李维杰的女儿")
        ids = [h["entity_id"] for h in hints]
        assert "person-wang-lele" in ids
        assert "person-wang-xiaobai" not in ids
        assert "person-tu-xiuying" not in ids
        assert "person-li-jianguo" not in ids


class TestGrandparentDirection:
    """grandmother_of / grandfather_of with reverse traversal + child_perspective filter."""

    def test_limucheng_grandmother(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("王乐乐的外婆")
        assert "李玉兰" in expanded
        assert "外婆" in expanded
        assert "姥姥" in expanded
        assert "张国强" not in expanded

    def test_limucheng_grandmother_alias_laolao(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("王乐乐的姥姥")
        assert "李玉兰" in expanded

    def test_limucheng_grandfather(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("王乐乐的外公")
        assert "张国强" in expanded
        assert "外公" in expanded
        assert "姥爷" in expanded
        assert "李玉兰" not in expanded

    def test_limucheng_grandfather_alias_laoye(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("王乐乐的姥爷")
        assert "张国强" in expanded

    def test_limubai_grandmother(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("王小柏的外婆")
        assert "李玉兰" in expanded

    def test_zhangyanhan_mother_via_by_observer(self, isolated_data_dir: Path) -> None:
        """李玉兰's by_observer for 陈小红 is 妈妈, so 妈妈 filter matches her."""
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("陈小红的妈妈")
        assert "李玉兰" in expanded
        assert "妈妈" in expanded
        assert "张国强" not in expanded

    def test_zhangyanhan_father_via_by_observer(self, isolated_data_dir: Path) -> None:
        """张国强's by_observer for 陈小红 is 爸爸, so 爸爸 filter matches him."""
        _save_graph(_d6_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("陈小红的爸爸")
        assert "张国强" in expanded
        assert "爸爸" in expanded
        assert "李玉兰" not in expanded

    def test_grandmother_entity_hint_only_grandmother(self, isolated_data_dir: Path) -> None:
        _save_graph(_d6_family_graph(), isolated_data_dir)
        hints = resolve_query_entities("王乐乐的外婆")
        ids = [h["entity_id"] for h in hints]
        assert "person-li-yulan" in ids
        assert "person-zhang-guoqiang" not in ids


class TestBackwardCompatNoLabels:
    """Entities without family_role_labels should still pass through."""

    def test_no_labels_entity_passes_through(self, isolated_data_dir: Path) -> None:
        graph = [
            {
                "id": "parent",
                "type": "person",
                "primary_name": "Parent",
                "aliases": [],
                "attributes": {},  # no family_role_labels
                "relationships": [{"target": "child", "relation": "parent_of"}],
            },
            {
                "id": "child",
                "type": "person",
                "primary_name": "Child",
                "aliases": [],
                "attributes": {},
                "relationships": [],
            },
        ]
        _save_graph(graph, isolated_data_dir)
        expanded = expand_query_with_entity_graph("Child的妈妈")
        assert "Parent" in expanded
