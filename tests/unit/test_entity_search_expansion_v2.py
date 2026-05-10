#!/usr/bin/env python3
"""
Tests for Search Expansion v2 — Round 7 Phase 1 Task 3.

Validates that the new phrase registry expands:
- Role labels (老婆, 妻子 → spouse entity's all names)
- Kinship phrase patterns (X的奶奶, X的妈妈, X的老婆)
- Place phrases (老家 → place entity expansion)
- Backward compatibility with existing alias expansion

R2-A1 expansion grammar fix tests:
- Single-character alias (渝) excluded from OR groups
- No recursive/nested OR from str.replace mutation
- Position-aware non-overlapping replacement
- Multi-character aliases (Chongqing, 山城) retained
- Parentheses balanced in expanded output
"""

from pathlib import Path


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


# ---------------------------------------------------------------------------
# R2-A1 Expansion Grammar Fix Tests
# ---------------------------------------------------------------------------


def _chongqing_with_short_alias_graph() -> list[dict]:
    """Entity graph matching production place-chongqing: includes 渝 alias."""
    return [
        {
            "id": "person-zhouyu",
            "type": "person",
            "primary_name": "周渝",
            "aliases": [],
            "attributes": {},
            "relationships": [],
        },
        {
            "id": "place-chongqing",
            "type": "place",
            "primary_name": "重庆",
            "aliases": ["渝", "Chongqing", "山城"],
            "attributes": {},
            "relationships": [],
        },
    ]


def _count_substring(text: str, sub: str) -> int:
    return text.count(sub)


def _parentheses_balanced(text: str) -> bool:
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth < 0:
            return False
    return depth == 0


class TestExpansionGrammarFix:
    """R2-A1: position-aware replacement, no recursive expansion, short-alias filter."""

    def test_expansion_excludes_single_char_yu(self, isolated_data_dir: Path) -> None:
        """Single-character alias 渝 must NOT appear in the expanded query."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_chongqing_with_short_alias_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("在重庆发生过的事")

        assert "渝" not in expanded

    def test_chongqing_appears_exactly_once(self, isolated_data_dir: Path) -> None:
        """Chongqing must appear exactly once (not recursively duplicated)."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_chongqing_with_short_alias_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("在重庆发生过的事")

        assert _count_substring(expanded, "Chongqing") == 1

    def test_mountain_city_appears_exactly_once(self, isolated_data_dir: Path) -> None:
        """山城 must appear exactly once (not recursively duplicated)."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_chongqing_with_short_alias_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("在重庆发生过的事")

        assert _count_substring(expanded, "山城") == 1

    def test_no_nested_or_groups(self, isolated_data_dir: Path) -> None:
        """Expanded query must not contain nested OR groups.

        A valid expansion looks like: 在(重庆 OR Chongqing OR 山城)发生过的事
        Nested would be: 在(重庆 OR (重庆 OR Chongqing) OR 山城)发生过的事
        """
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_chongqing_with_short_alias_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("在重庆发生过的事")

        # Check: no "OR" appears inside an already-open parenthesis group
        # that itself contains "OR". Simpler: primary_name should appear
        # exactly once in the expanded query (not nested).
        assert _count_substring(expanded, "重庆") == 1

    def test_parentheses_balanced(self, isolated_data_dir: Path) -> None:
        """Parentheses in the expanded query must be balanced."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_chongqing_with_short_alias_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("在重庆发生过的事")

        assert _parentheses_balanced(expanded)

    def test_embedded_or_group_has_explicit_fts_boundaries(self, isolated_data_dir: Path) -> None:
        """Embedded OR groups must have FTS5-valid AND separators, not glued.

        All expansion grammar properties verified in one focused test:
        - explicit AND boundaries around the OR group
        - single-char alias (渝) excluded
        - Chongqing and 山城 appear exactly once
        - no nested OR from recursive expansion
        - balanced parentheses
        """
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_chongqing_with_short_alias_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("在重庆发生过的事")

        # Exact expected FTS5-valid form
        assert expanded == "在 AND (重庆 OR Chongqing OR 山城) AND 发生过的事"

        # Single-char alias excluded
        assert "渝" not in expanded

        # Multi-char aliases appear exactly once
        assert _count_substring(expanded, "Chongqing") == 1
        assert _count_substring(expanded, "山城") == 1

        # No nested OR (primary name appears once total)
        assert _count_substring(expanded, "重庆") == 1

        # Parentheses balanced
        assert _parentheses_balanced(expanded)

    def test_multi_char_aliases_retained(self, isolated_data_dir: Path) -> None:
        """Multi-character aliases Chongqing and 山城 must still be in OR group."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_chongqing_with_short_alias_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("在重庆发生过的事")

        assert "Chongqing" in expanded
        assert "山城" in expanded
        assert "重庆" in expanded

    def test_surrounding_text_preserved(self, isolated_data_dir: Path) -> None:
        """Text around the matched entity must be preserved."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_chongqing_with_short_alias_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("在重庆发生过的事")

        assert expanded.startswith("在")
        assert expanded.endswith("发生过的事")

    def test_primary_name_first_in_or_group(self, isolated_data_dir: Path) -> None:
        """Primary name 重庆 must be the first term in the OR group."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_chongqing_with_short_alias_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("在重庆发生过的事")

        # Find the OR group and check 重庆 appears first
        or_group_start = expanded.index("(")
        or_group_end = expanded.index(")", or_group_start)
        or_content = expanded[or_group_start + 1 : or_group_end]
        terms = [t.strip() for t in or_content.split(" OR ")]
        assert terms[0] == "重庆"

    def test_overlapping_matches_longest_wins(self, isolated_data_dir: Path) -> None:
        """When two entity names overlap at the same position, longest wins."""
        from tools.search_journals.core import expand_query_with_entity_graph

        graph = _chongqing_with_short_alias_graph() + [
            {
                "id": "place-chongqing-city",
                "type": "place",
                "primary_name": "重庆城",
                "aliases": ["山城重庆"],
                "attributes": {},
                "relationships": [],
            },
        ]
        _save_graph(graph, isolated_data_dir)
        expanded = expand_query_with_entity_graph("在重庆城里散步")

        # Both 重庆 and 重庆城 match at position 1; longest (重庆城) should win
        assert "重庆城" in expanded

    def test_phrase_expansion_still_works_with_fix(self, isolated_data_dir: Path) -> None:
        """Family phrase patterns (我的老婆 etc.) must not regress."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("我的老婆")

        assert "王某某" in expanded
        assert "乐乐妈" in expanded


# ---------------------------------------------------------------------------
# R2-A4 Path 2/3 Explicit AND Tests
# ---------------------------------------------------------------------------


class TestPath23ExplicitAnd:
    """R2-A4: Paths 2/3 must insert explicit AND around parenthesized OR groups.

    FTS5 rejects `(OR group) token` and `token (OR group)` adjacency —
    explicit AND is required at every parenthesized-group boundary.
    """

    def test_entity_token_with_following_plain_token(self, isolated_data_dir: Path) -> None:
        """Direct entity token + following plain token → explicit AND."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("老婆 生日")

        assert "生日" in expanded
        # No implicit adjacency: `(group) 生日` is forbidden
        assert ") 生日" not in expanded
        # Must have explicit AND: `(group) AND 生日`
        assert ") AND 生日" in expanded

    def test_entity_token_with_leading_and_trailing_plain_tokens(
        self, isolated_data_dir: Path
    ) -> None:
        """Plain tokens on both sides of entity → AND before and after OR group."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("买 老婆 礼物")

        assert "买" in expanded
        assert "礼物" in expanded
        # AND before OR group
        assert "买 AND (" in expanded
        # AND after OR group
        assert ") AND 礼物" in expanded
        # No implicit adjacency
        assert ") 礼物" not in expanded
        assert "买 (" not in expanded

    def test_phrase_expansion_with_surrounding_token(self, isolated_data_dir: Path) -> None:
        """Phrase-pattern expansion with leading plain token → explicit AND."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("关于 我的老婆")

        assert "关于" in expanded
        # AND between plain token and OR group
        assert "关于 AND (" in expanded
        # No implicit adjacency
        assert "关于 (" not in expanded

    def test_path1_behavior_preserved(self, isolated_data_dir: Path) -> None:
        """Path 1 substring replacement output must not regress."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_chongqing_with_short_alias_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("在重庆发生过的事")

        assert expanded == "在 AND (重庆 OR Chongqing OR 山城) AND 发生过的事"

    def test_single_entity_or_group_no_extra_and(self, isolated_data_dir: Path) -> None:
        """Single-token entity expansion stays as plain OR group, no leading/trailing AND."""
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("老婆")

        assert expanded.startswith("(")
        assert expanded.endswith(")")
        assert "王某某" in expanded
        assert "AND" not in expanded


class TestCaseInsensitiveExpansion:
    """Entity expansion should work with different casing."""

    def test_case_insensitive_alias_expansion(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("chongqing")

        assert "重庆" in expanded

    def test_case_insensitive_primary_name_expansion(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("CHONGQING")

        assert "重庆" in expanded

    def test_case_insensitive_resolve_query_entities(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import resolve_query_entities

        _save_graph(_spouse_family_graph(), isolated_data_dir)
        hints = resolve_query_entities("chongqing")

        assert len(hints) == 1
        assert hints[0]["entity_id"] == "chongqing"

    def test_case_insensitive_substring_expansion(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import expand_query_with_entity_graph

        _save_graph(_spouse_family_graph(), isolated_data_dir)
        expanded = expand_query_with_entity_graph("在chongqing发生的事")

        assert "重庆" in expanded
