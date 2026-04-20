#!/usr/bin/env python3
"""
Tests for Write-Time Entity Candidates — Round 7 Phase 2 Task 6.

Validates that:
- write_journal returns structured entity_candidates
- entity_candidates covers frontmatter + content sources
- Each candidate has required fields: text, source, kind, matched_entity_id, suggested_action, risk_level
- new_entities_detected remains as legacy output (backward compat)
- dry_run returns entity_candidates without writing to disk
"""

from pathlib import Path

import pytest

from tools.lib.entity_graph import save_entity_graph


def _wife_graph() -> list[dict]:
    return [
        {
            "id": "wife-001",
            "type": "person",
            "primary_name": "王某某",
            "aliases": ["乐乐妈"],
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
    save_entity_graph(entities, isolated_data_dir / "entity_graph.yaml")


class TestEntityCandidatesPresent:
    """entity_candidates must be in write_journal result."""

    def test_write_returns_entity_candidates_key(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        _save_graph(_wife_graph(), isolated_data_dir)

        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "家庭记录",
                "content": "今天和乐乐妈一起带孩子出去。",
            },
            dry_run=True,
        )

        assert "entity_candidates" in result

    def test_entity_candidates_is_list(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        _save_graph(_wife_graph(), isolated_data_dir)

        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "测试",
                "content": "普通内容",
            },
            dry_run=True,
        )

        assert isinstance(result["entity_candidates"], list)


class TestEntityCandidatesFromContent:
    """Content body mentions should produce candidates."""

    def test_content_alias_match(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        _save_graph(_wife_graph(), isolated_data_dir)

        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "家庭记录",
                "content": "今天和乐乐妈一起带孩子出去。",
            },
            dry_run=True,
        )

        candidates = result["entity_candidates"]
        wife_candidates = [
            c for c in candidates if c.get("matched_entity_id") == "wife-001"
        ]
        assert len(wife_candidates) >= 1

        c = wife_candidates[0]
        assert c["source"] == "content"
        assert c["text"] == "乐乐妈"
        assert c["kind"] == "person"
        assert c["matched_entity_id"] == "wife-001"

    def test_content_place_alias_match(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        _save_graph(_wife_graph(), isolated_data_dir)

        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "回老家",
                "content": "今天回到了老家，感觉很亲切。",
            },
            dry_run=True,
        )

        candidates = result["entity_candidates"]
        place_candidates = [
            c for c in candidates if c.get("matched_entity_id") == "chongqing"
        ]
        assert len(place_candidates) >= 1
        assert place_candidates[0]["text"] == "老家"
        assert place_candidates[0]["source"] == "content"


class TestEntityCandidatesFromFrontmatter:
    """Frontmatter people/location/project should also produce candidates."""

    def test_frontmatter_known_person(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        _save_graph(_wife_graph(), isolated_data_dir)

        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "家庭记录",
                "content": "普通内容",
                "people": ["乐乐妈"],
            },
            dry_run=True,
        )

        candidates = result["entity_candidates"]
        wife_candidates = [
            c for c in candidates if c.get("matched_entity_id") == "wife-001"
        ]
        assert len(wife_candidates) >= 1
        assert wife_candidates[0]["source"] == "frontmatter"

    def test_frontmatter_new_person(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        _save_graph(_wife_graph(), isolated_data_dir)

        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "新朋友",
                "content": "今天认识了小李。",
                "people": ["小李"],
            },
            dry_run=True,
        )

        candidates = result["entity_candidates"]
        new_candidates = [c for c in candidates if c.get("text") == "小李"]
        assert len(new_candidates) >= 1
        assert new_candidates[0]["matched_entity_id"] is None
        assert new_candidates[0]["suggested_action"] == "add_entity"

    def test_frontmatter_known_location(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        _save_graph(_wife_graph(), isolated_data_dir)

        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "在重庆",
                "content": "普通内容",
                "location": "重庆",
            },
            dry_run=True,
        )

        candidates = result["entity_candidates"]
        loc_candidates = [c for c in candidates if c.get("kind") == "place"]
        assert len(loc_candidates) >= 1


class TestEntityCandidatesStructure:
    """Validate candidate field structure."""

    def test_candidate_has_required_fields(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        _save_graph(_wife_graph(), isolated_data_dir)

        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "家庭记录",
                "content": "和乐乐妈一起。",
            },
            dry_run=True,
        )

        candidates = result["entity_candidates"]
        assert len(candidates) >= 1

        required_fields = {
            "text",
            "source",
            "kind",
            "matched_entity_id",
            "suggested_action",
            "risk_level",
        }
        for c in candidates:
            assert required_fields.issubset(c.keys()), (
                f"Missing fields: {required_fields - c.keys()}"
            )

    def test_matched_candidate_has_match_info(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        _save_graph(_wife_graph(), isolated_data_dir)

        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "家庭",
                "content": "和乐乐妈出去。",
            },
            dry_run=True,
        )

        matched = [
            c for c in result["entity_candidates"] if c["matched_entity_id"] is not None
        ]
        assert len(matched) >= 1
        assert matched[0]["suggested_action"] == "confirm_match"

    def test_unmatched_candidate_suggests_add(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        _save_graph(_wife_graph(), isolated_data_dir)

        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "新人物",
                "content": "今天遇到了小明。",
                "people": ["小明"],
            },
            dry_run=True,
        )

        unmatched = [
            c for c in result["entity_candidates"] if c["matched_entity_id"] is None
        ]
        assert len(unmatched) >= 1
        assert unmatched[0]["suggested_action"] == "add_entity"


class TestEntityCandidatesBackwardCompat:
    """new_entities_detected must still work."""

    def test_new_entities_detected_still_present(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        _save_graph(_wife_graph(), isolated_data_dir)

        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "新朋友",
                "content": "今天认识了小明。",
                "people": ["小明"],
            },
            dry_run=True,
        )

        # Legacy field must still exist
        assert "new_entities_detected" in result
        assert "小明" in result["new_entities_detected"]

    def test_no_graph_no_crash(self, isolated_data_dir: Path) -> None:
        from tools.write_journal.core import write_journal

        # No entity graph saved
        result = write_journal(
            {
                "date": "2026-04-13",
                "title": "普通",
                "content": "普通内容",
            },
            dry_run=True,
        )

        assert "entity_candidates" in result
        assert isinstance(result["entity_candidates"], list)
