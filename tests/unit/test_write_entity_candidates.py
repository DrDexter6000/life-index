"""
Tests for write-side entity_candidates with frontmatter fallback (Round 10, T1.4).

Validates D5/D17: entity_candidates always returns useful data,
even when entity graph doesn't exist (frontmatter fallback).
"""

import json
from pathlib import Path
from typing import Any

import pytest


class TestEntityCandidatesFallback:
    """Verify entity candidates work with and without entity graph."""

    def test_no_graph_returns_frontmatter_candidates(self) -> None:
        """
        When graph is empty/missing, extract_entity_candidates should
        still return candidates from frontmatter with source="frontmatter_fallback".
        """
        from tools.lib.entity_candidates import extract_entity_candidates

        metadata = {
            "people": ["团团"],
            "location": "Lagos",
            "tags": ["亲子"],
        }
        candidates = extract_entity_candidates(
            metadata=metadata,
            content="看到团团很开心",
            graph=[],  # Empty graph
        )

        # Should return candidates even without graph
        assert len(candidates) > 0, "Should return frontmatter fallback candidates"

        names = {c["text"] for c in candidates}
        assert "团团" in names

        # Source should indicate fallback
        tuantuan = next(c for c in candidates if c["text"] == "团团")
        assert tuantuan["source"] == "frontmatter_fallback"
        assert tuantuan["suggested_action"] == "add_entity"

    def test_no_graph_candidate_has_suggested_command(self) -> None:
        """
        Fallback candidates should have a suggested_command field
        that can be directly executed by the Agent.
        """
        from tools.lib.entity_candidates import extract_entity_candidates

        metadata = {"people": ["团团"]}
        candidates = extract_entity_candidates(
            metadata=metadata,
            content="",
            graph=[],
        )

        assert len(candidates) > 0
        c = candidates[0]
        assert "suggested_command" in c
        assert "entity --add" in c["suggested_command"]
        # Verify the JSON in the command is valid
        cmd = c["suggested_command"]
        json_start = cmd.index("{")
        json_end = cmd.rindex("}") + 1
        entity_json = json.loads(cmd[json_start:json_end])
        assert entity_json["primary_name"] == "团团"
        assert entity_json["type"] == "person"

    def test_with_graph_returns_graph_delta_candidates(self) -> None:
        """
        When graph exists and already contains "团团", new mention of
        "团团" should show as confirm_match, while "新朋友" should show
        as add_entity with source="frontmatter".
        """
        from tools.lib.entity_candidates import extract_entity_candidates

        graph = [
            {
                "id": "e1",
                "type": "person",
                "primary_name": "团团",
                "aliases": [],
                "attributes": {},
                "relationships": [],
            }
        ]

        metadata = {"people": ["团团", "新朋友"]}
        candidates = extract_entity_candidates(
            metadata=metadata,
            content="",
            graph=graph,
        )

        assert len(candidates) > 0

        tuantuan = next((c for c in candidates if c["text"] == "团团"), None)
        assert tuantuan is not None
        assert tuantuan["matched_entity_id"] == "e1"
        assert tuantuan["suggested_action"] == "confirm_match"

        new_friend = next((c for c in candidates if c["text"] == "新朋友"), None)
        assert new_friend is not None
        assert new_friend["matched_entity_id"] is None
        assert new_friend["suggested_action"] == "add_entity"

    def test_empty_metadata_no_candidates(self) -> None:
        """Empty metadata + no graph → no candidates."""
        from tools.lib.entity_candidates import extract_entity_candidates

        candidates = extract_entity_candidates(
            metadata={},
            content="",
            graph=[],
        )
        assert candidates == []
