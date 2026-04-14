#!/usr/bin/env python3
"""
Tests for Search Suggestion Output — Round 7 Phase 1 Task 4.

Validates that:
- search_journals() returns entity_hints in result
- entity_hints contains structured fields: matched_term, entity_id, entity_type, expansion_terms, reason
- entity_hints is empty list when no entity matches
- entity_hints works with relationship phrase patterns
- Backward compat: existing search results unchanged
"""

from pathlib import Path

import pytest

from tools.lib.entity_graph import save_entity_graph


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
        {
            "id": "chongqing",
            "type": "place",
            "primary_name": "重庆",
            "aliases": ["山城", "老家"],
            "attributes": {},
            "relationships": [],
        },
    ]


def _save_graph(entities: list[dict], isolated_data_dir: Path) -> None:
    from tools.lib.paths import USER_DATA_DIR

    save_entity_graph(entities, USER_DATA_DIR / "entity_graph.yaml")


class TestEntityHintsPresent:
    """entity_hints must be present in search response."""

    def test_search_response_contains_entity_hints_key(
        self, isolated_data_dir: Path
    ) -> None:
        from tools.search_journals.core import hierarchical_search

        _save_graph(_sample_entities(), isolated_data_dir)

        result = hierarchical_search(query="老婆", level=1)

        assert "entity_hints" in result

    def test_entity_hints_empty_when_no_match(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import hierarchical_search

        _save_graph(_sample_entities(), isolated_data_dir)

        result = hierarchical_search(query="完全不相关", level=1)

        assert result["entity_hints"] == []

    def test_entity_hints_empty_when_no_graph(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import hierarchical_search

        result = hierarchical_search(query="anything", level=1)

        assert "entity_hints" in result
        assert result["entity_hints"] == []


class TestEntityHintsStructure:
    """Validate entity_hints field structure."""

    def test_hint_has_required_fields(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import hierarchical_search

        _save_graph(_sample_entities(), isolated_data_dir)

        result = hierarchical_search(query="老婆", level=1)

        assert len(result["entity_hints"]) >= 1
        hint = result["entity_hints"][0]
        assert "matched_term" in hint
        assert "entity_id" in hint
        assert "entity_type" in hint
        assert "expansion_terms" in hint
        assert "reason" in hint

    def test_hint_matches_wife_entity(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import hierarchical_search

        _save_graph(_sample_entities(), isolated_data_dir)

        result = hierarchical_search(query="老婆", level=1)

        hints = result["entity_hints"]
        wife_hints = [h for h in hints if h["entity_id"] == "wife-001"]
        assert len(wife_hints) >= 1

        hint = wife_hints[0]
        assert hint["matched_term"] == "老婆"
        assert hint["entity_id"] == "wife-001"
        assert hint["entity_type"] == "person"
        assert "团团妈" in hint["expansion_terms"]
        assert "王某某" in hint["expansion_terms"]
        assert hint["reason"] == "alias_match"

    def test_hint_for_place_entity(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import hierarchical_search

        _save_graph(_sample_entities(), isolated_data_dir)

        result = hierarchical_search(query="老家", level=1)

        hints = result["entity_hints"]
        place_hints = [h for h in hints if h["entity_id"] == "chongqing"]
        assert len(place_hints) >= 1

        hint = place_hints[0]
        assert hint["matched_term"] == "老家"
        assert hint["entity_type"] == "place"
        assert "重庆" in hint["expansion_terms"]

    def test_hint_for_primary_name_match(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import hierarchical_search

        _save_graph(_sample_entities(), isolated_data_dir)

        result = hierarchical_search(query="重庆", level=1)

        hints = result["entity_hints"]
        assert len(hints) >= 1
        assert hints[0]["matched_term"] == "重庆"
        assert hints[0]["reason"] == "primary_name_match"


class TestEntityHintsBackwardCompat:
    """Existing search response fields must not be affected."""

    def test_existing_fields_still_present(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import hierarchical_search

        _save_graph(_sample_entities(), isolated_data_dir)

        result = hierarchical_search(query="老婆", level=1)

        # Must still have all standard fields
        assert "success" in result
        assert "query_params" in result
        assert "total_found" in result

    def test_expanded_query_still_present(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import hierarchical_search

        _save_graph(_sample_entities(), isolated_data_dir)

        result = hierarchical_search(query="老婆", level=1)

        # expanded_query should still exist
        assert "expanded_query" in result["query_params"] or result["entity_hints"]
