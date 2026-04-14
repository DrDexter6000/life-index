#!/usr/bin/env python3
"""
Tests for relation vocabulary normalization — Round 7 Phase 3 Task 10.

Validates that:
- normalize_relation maps aliases to canonical forms
- relation_aliases returns all known aliases for a canonical relation
- Both Chinese and English relation labels are handled
"""

import pytest


class TestNormalizeRelation:
    """normalize_relation maps various labels to canonical form."""

    def test_normalize_spouse_aliases(self) -> None:
        from tools.lib.entity_relations import normalize_relation

        assert normalize_relation("wife") == "spouse_of"
        assert normalize_relation("老婆") == "spouse_of"
        assert normalize_relation("丈夫") == "spouse_of"
        assert normalize_relation("husband") == "spouse_of"

    def test_normalize_parent_aliases(self) -> None:
        from tools.lib.entity_relations import normalize_relation

        assert normalize_relation("妈妈") == "parent_of"
        assert normalize_relation("父亲") == "parent_of"
        assert normalize_relation("mom") == "parent_of"
        assert normalize_relation("father") == "parent_of"

    def test_normalize_child_alias(self) -> None:
        from tools.lib.entity_relations import normalize_relation

        assert normalize_relation("女儿") == "child_of"
        assert normalize_relation("son") == "child_of"

    def test_normalize_colleague(self) -> None:
        from tools.lib.entity_relations import normalize_relation

        assert normalize_relation("同事") == "colleague_of"
        assert normalize_relation("colleague") == "colleague_of"

    def test_normalize_already_canonical(self) -> None:
        from tools.lib.entity_relations import normalize_relation

        assert normalize_relation("spouse_of") == "spouse_of"
        assert normalize_relation("colleague_of") == "colleague_of"

    def test_normalize_unknown_returns_as_is(self) -> None:
        from tools.lib.entity_relations import normalize_relation

        # Unknown relations pass through unchanged
        assert normalize_relation("custom_relation") == "custom_relation"

    def test_normalize_case_insensitive(self) -> None:
        from tools.lib.entity_relations import normalize_relation

        assert normalize_relation("Wife") == "spouse_of"
        assert normalize_relation("MOM") == "parent_of"


class TestRelationAliases:
    """relation_aliases returns known aliases for canonical forms."""

    def test_spouse_aliases(self) -> None:
        from tools.lib.entity_relations import relation_aliases

        aliases = relation_aliases("spouse_of")
        assert "wife" in aliases
        assert "老婆" in aliases
        assert "husband" in aliases

    def test_parent_aliases(self) -> None:
        from tools.lib.entity_relations import relation_aliases

        aliases = relation_aliases("parent_of")
        assert "妈妈" in aliases
        assert "father" in aliases

    def test_unknown_canonical_returns_empty(self) -> None:
        from tools.lib.entity_relations import relation_aliases

        aliases = relation_aliases("nonexistent_relation")
        assert aliases == []

    def test_canonical_form_not_in_aliases(self) -> None:
        """The canonical form itself should not appear in the alias list."""
        from tools.lib.entity_relations import relation_aliases

        aliases = relation_aliases("spouse_of")
        assert "spouse_of" not in aliases


class TestCanonicalRelations:
    """CANONICAL_RELATIONS constant provides the full vocabulary."""

    def test_canonical_relations_is_dict(self) -> None:
        from tools.lib.entity_relations import CANONICAL_RELATIONS

        assert isinstance(CANONICAL_RELATIONS, dict)

    def test_all_canonicals_have_aliases(self) -> None:
        from tools.lib.entity_relations import CANONICAL_RELATIONS

        for canonical, aliases in CANONICAL_RELATIONS.items():
            assert isinstance(aliases, list), f"{canonical} aliases must be a list"
            assert len(aliases) >= 1, f"{canonical} must have at least one alias"
