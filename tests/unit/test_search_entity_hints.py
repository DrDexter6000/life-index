#!/usr/bin/env python3
"""
Tests for Search Suggestion Output — Round 7 Phase 1 Task 4.

Validates that:
- search_journals() returns entity_hints in result
- entity_hints contains structured fields: matched_term, entity_id, entity_type,
  expansion_terms, reason
- entity_hints is empty list when no entity matches
- entity_hints works with relationship phrase patterns
- Backward compat: existing search results unchanged
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.lib.entity_graph import save_entity_graph
from tools.lib.index_freshness import FreshnessReport


@pytest.fixture(autouse=True)
def _mock_fresh_index_state():
    fresh_report = FreshnessReport(
        fts_fresh=True,
        vector_fresh=True,
        overall_fresh=True,
        issues=[],
    )
    with patch("tools.lib.index_freshness.check_full_freshness", return_value=fresh_report):
        with patch("tools.lib.pending_writes.has_pending", return_value=False):
            yield


def _sample_entities() -> list[dict]:
    return [
        {
            "id": "wife-001",
            "type": "actor",
            "primary_name": "王某某",
            "aliases": ["晴岚妈", "老婆"],
            "attributes": {},
            "relationships": [{"target": "author-self", "relation": "spouse_of"}],
        },
        {
            "id": "author-self",
            "type": "actor",
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


def _payoff_entities() -> list[dict]:
    return [
        {
            "id": "actor-alice",
            "type": "actor",
            "primary_name": "Alice",
            "aliases": ["Ally"],
            "attributes": {"kind": "human"},
            "relationships": [],
            "source": "user",
            "status": "confirmed",
        },
        {
            "id": "actor-morgan",
            "type": "actor",
            "primary_name": "Morgan",
            "aliases": [],
            "attributes": {"kind": "human"},
            "relationships": [],
            "source": "user",
            "status": "confirmed",
        },
    ]


def _relationship_payoff_entities() -> list[dict]:
    return [
        {
            "id": "actor-alice",
            "type": "actor",
            "primary_name": "Alice",
            "aliases": ["Ally"],
            "attributes": {"kind": "human"},
            "relationships": [
                {
                    "target": "actor-morgan",
                    "relation": "child_of",
                    "source": "user",
                    "status": "confirmed",
                    "created_at": "2026-07-06T00:00:00Z",
                }
            ],
            "source": "user",
            "status": "confirmed",
        },
        {
            "id": "actor-clara",
            "type": "actor",
            "primary_name": "Clara",
            "aliases": ["Cee"],
            "attributes": {"kind": "human"},
            "relationships": [
                {
                    "target": "actor-morgan",
                    "relation": "child_of",
                    "source": "user",
                    "status": "confirmed",
                    "created_at": "2026-07-06T00:00:00Z",
                }
            ],
            "source": "user",
            "status": "confirmed",
        },
        {
            "id": "actor-morgan",
            "type": "actor",
            "primary_name": "Morgan",
            "aliases": [],
            "attributes": {"kind": "human"},
            "relationships": [],
            "source": "user",
            "status": "confirmed",
        },
    ]


def _save_graph(entities: list[dict], isolated_data_dir: Path) -> None:

    save_entity_graph(entities, isolated_data_dir / "entity_graph.yaml")


def _write_search_fixture_journal(isolated_data_dir: Path) -> Path:
    journal_dir = isolated_data_dir / "Journals" / "2026" / "03"
    journal_dir.mkdir(parents=True, exist_ok=True)
    journal_path = journal_dir / "life-index_2026-03-15_001.md"
    journal_path.write_text(
        "---\n"
        'title: "Project Status Fixture"\n'
        "date: 2026-03-15\n"
        "topic: [work]\n"
        "tags: [projectstatus]\n"
        "---\n\n"
        "Alice shared projectstatus notes after lunch.\n",
        encoding="utf-8",
    )
    return journal_path


def _write_relationship_search_fixture_journal(isolated_data_dir: Path) -> Path:
    journal_dir = isolated_data_dir / "Journals" / "2026" / "04"
    journal_dir.mkdir(parents=True, exist_ok=True)
    journal_path = journal_dir / "life-index_2026-04-10_001.md"
    journal_path.write_text(
        "---\n"
        'title: "Sleep Fixture"\n'
        "date: 2026-04-10\n"
        "topic: [health]\n"
        "tags: [sleepfixture]\n"
        "---\n\n"
        "Alice wrote sleepfixture notes about 睡眠 habits.\n",
        encoding="utf-8",
    )
    return journal_path


class TestEntityHintsPresent:
    """entity_hints must be present in search response."""

    def test_search_response_contains_entity_hints_key(self, isolated_data_dir: Path) -> None:
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
        assert hint["entity_type"] == "actor"
        assert "晴岚妈" in hint["expansion_terms"]
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


class TestEntityExpansionAttribution:
    """S1 payoff: search explains deterministic Entity Graph query expansion."""

    def test_alias_only_query_reports_entity_expansion_attribution(
        self, isolated_data_dir: Path
    ) -> None:
        from tools.lib.search_index import update_index
        from tools.search_journals.core import hierarchical_search

        _save_graph(_payoff_entities(), isolated_data_dir)
        journal_path = _write_search_fixture_journal(isolated_data_dir)
        assert update_index(incremental=False)["success"] is True

        result = hierarchical_search(query="Ally projectstatus", level=3, semantic=False)

        assert any(
            str(item.get("path", "")).endswith(journal_path.name)
            for item in result["merged_results"]
        )
        assert result["entity_expansion"] == {
            "applied": True,
            "expansions": [
                {
                    "from": "Ally",
                    "to": ["Alice"],
                    "via": "alias",
                    "entity_id": "actor-alice",
                }
            ],
        }

    def test_no_entity_match_reports_empty_entity_expansion(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import hierarchical_search

        _save_graph(_payoff_entities(), isolated_data_dir)

        result = hierarchical_search(query="unrelated projectstatus", level=3, semantic=False)

        assert result["entity_expansion"] == {"applied": False, "expansions": []}

    def test_entity_expansion_shape_is_stable(self, isolated_data_dir: Path) -> None:
        from tools.search_journals.core import hierarchical_search

        _save_graph(_payoff_entities(), isolated_data_dir)

        result = hierarchical_search(query="Ally", level=1, semantic=False)
        expansion = result["entity_expansion"]

        assert set(expansion) == {"applied", "expansions"}
        assert isinstance(expansion["applied"], bool)
        assert isinstance(expansion["expansions"], list)
        assert set(expansion["expansions"][0]) == {"from", "to", "via", "entity_id"}
        assert expansion["expansions"][0]["via"] in {"alias", "relation"}

    def test_relation_query_expands_confirmed_edges_for_search(
        self, isolated_data_dir: Path
    ) -> None:
        from tools.lib.search_index import update_index
        from tools.search_journals.core import hierarchical_search

        _save_graph(_relationship_payoff_entities(), isolated_data_dir)
        journal_path = _write_relationship_search_fixture_journal(isolated_data_dir)
        assert update_index(incremental=False)["success"] is True

        result = hierarchical_search(query="女儿 睡眠", level=3, semantic=False)

        assert any(
            str(item.get("path", "")).endswith(journal_path.name)
            for item in result["merged_results"]
        )
        assert {
            "from": "女儿",
            "to": ["Alice", "Ally"],
            "via": "relation",
            "entity_id": "actor-alice",
        } in result["entity_expansion"]["expansions"]
        assert {
            "matched_term": "女儿",
            "entity_id": "actor-alice",
            "entity_type": "actor",
            "expansion_terms": ["Alice", "Ally"],
            "reason": "relation_match",
        } in result["entity_hints"]

    def test_relation_query_expands_all_matching_confirmed_edges(
        self, isolated_data_dir: Path
    ) -> None:
        from tools.search_journals.core import hierarchical_search

        _save_graph(_relationship_payoff_entities(), isolated_data_dir)

        result = hierarchical_search(query="女儿", level=1, semantic=False)

        relation_expansions = [
            item for item in result["entity_expansion"]["expansions"] if item["via"] == "relation"
        ]
        assert {
            "from": "女儿",
            "to": ["Alice", "Ally"],
            "via": "relation",
            "entity_id": "actor-alice",
        } in relation_expansions
        assert {
            "from": "女儿",
            "to": ["Clara", "Cee"],
            "via": "relation",
            "entity_id": "actor-clara",
        } in relation_expansions

    def test_relation_query_without_graph_keeps_empty_expansion(
        self, isolated_data_dir: Path
    ) -> None:
        from tools.lib.search_index import update_index
        from tools.search_journals.core import hierarchical_search

        _write_relationship_search_fixture_journal(isolated_data_dir)
        assert update_index(incremental=False)["success"] is True

        result = hierarchical_search(query="女儿 睡眠", level=3, semantic=False)

        assert result["entity_expansion"] == {"applied": False, "expansions": []}
