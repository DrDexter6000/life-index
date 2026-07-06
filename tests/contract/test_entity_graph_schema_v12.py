#!/usr/bin/env python3
"""Contract tests for v1.2 entity relationship metadata backcompat."""

from __future__ import annotations

from pathlib import Path


def _base_entities(relationship: dict) -> list[dict]:
    return [
        {
            "id": "person-alice",
            "type": "actor",
            "primary_name": "Alice",
            "aliases": [],
            "attributes": {"kind": "human"},
            "relationships": [relationship],
        },
        {
            "id": "person-bob",
            "type": "actor",
            "primary_name": "Bob",
            "aliases": [],
            "attributes": {"kind": "human"},
            "relationships": [],
        },
    ]


class TestRelationshipMetadataBackcompat:
    def test_legacy_bare_relationship_loads_with_v12_defaults(self) -> None:
        from tools.lib.entity_schema import validate_entity_graph_payload

        fixed_time = "2026-07-04T00:00:00+00:00"
        validated = validate_entity_graph_payload(
            {"entities": _base_entities({"target": "person-bob", "relation": "friend_of"})},
            load_time=fixed_time,
        )

        relationship = validated[0]["relationships"][0]
        assert relationship["target"] == "person-bob"
        assert relationship["relation"] == "friend_of"
        assert relationship["evidence"] == []
        assert relationship["source"] == "system"
        assert relationship["created_at"] == fixed_time
        assert relationship["status"] == "confirmed"

    def test_relationship_v12_metadata_is_preserved(self) -> None:
        from tools.lib.entity_schema import validate_entity_graph_payload

        validated = validate_entity_graph_payload(
            {
                "entities": _base_entities(
                    {
                        "target": "person-bob",
                        "relation": "friend_of",
                        "evidence": [
                            "Journals/2026/07/life-index_2026-07-01_001.md",
                            "Journals/2026/07/life-index_2026-07-01_001.md",
                        ],
                        "source": "review",
                        "created_at": "2026-07-04T00:00:00+00:00",
                        "status": "candidate",
                        "start": "2026-07-01",
                        "end": "2026-07-31",
                    }
                )
            }
        )

        relationship = validated[0]["relationships"][0]
        assert relationship["evidence"] == ["Journals/2026/07/life-index_2026-07-01_001.md"]
        assert relationship["source"] == "review"
        assert relationship["status"] == "candidate"
        assert relationship["start"] == "2026-07-01"
        assert relationship["end"] == "2026-07-31"

    def test_save_load_preserves_v12_relationship_metadata(self, tmp_path: Path) -> None:
        from tools.lib.entity_graph import load_entity_graph, save_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        save_entity_graph(
            _base_entities(
                {
                    "target": "person-bob",
                    "relation": "friend_of",
                    "evidence": ["Journals/2026/07/life-index_2026-07-01_001.md"],
                    "source": "user",
                    "created_at": "2026-07-04T00:00:00+00:00",
                    "status": "confirmed",
                }
            ),
            graph_path,
        )

        loaded = load_entity_graph(graph_path)
        relationship = loaded[0]["relationships"][0]
        assert relationship["source"] == "user"
        assert relationship["evidence"] == ["Journals/2026/07/life-index_2026-07-01_001.md"]


class TestEntityRuntimeMixedRelationshipShapes:
    def test_runtime_view_reads_legacy_and_v12_relationship_edges(self, tmp_path: Path) -> None:
        from tools.lib.entity_graph import save_entity_graph
        from tools.lib.entity_runtime import load_runtime_view

        graph_path = tmp_path / "entity_graph.yaml"
        save_entity_graph(
            [
                {
                    "id": "person-alice",
                    "type": "actor",
                    "primary_name": "Alice",
                    "aliases": [],
                    "attributes": {"kind": "human"},
                    "relationships": [
                        {"target": "person-bob", "relation": "friend_of"},
                        {
                            "target": "person-morgan",
                            "relation": "colleague_of",
                            "source": "review",
                            "created_at": "2026-07-04T00:00:00+00:00",
                            "status": "confirmed",
                            "evidence": ["Journals/2026/07/life-index_2026-07-01_001.md"],
                        },
                    ],
                },
                {
                    "id": "person-bob",
                    "type": "actor",
                    "primary_name": "Bob",
                    "aliases": [],
                    "attributes": {"kind": "human"},
                    "relationships": [],
                },
                {
                    "id": "person-morgan",
                    "type": "actor",
                    "primary_name": "Morgan",
                    "aliases": [],
                    "attributes": {"kind": "human"},
                    "relationships": [],
                },
            ],
            graph_path,
        )

        view = load_runtime_view(graph_path)

        assert view.reverse_relationships["person-bob"] == [("person-alice", "friend_of")]
        assert view.reverse_relationships["person-morgan"] == [("person-alice", "colleague_of")]
