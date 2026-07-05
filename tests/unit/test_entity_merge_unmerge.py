#!/usr/bin/env python3
"""Reversible entity merge tests."""

from __future__ import annotations

from pathlib import Path

from tools.lib.entity_graph import load_entity_graph, save_entity_graph


def _roundtrip_graph() -> list[dict]:
    return [
        {
            "id": "person-alice",
            "type": "person",
            "primary_name": "Alice",
            "aliases": ["A. Example"],
            "attributes": {"role": "owner"},
            "relationships": [
                {"target": "person-morgan", "relation": "colleague_of"},
            ],
        },
        {
            "id": "person-bob",
            "type": "person",
            "primary_name": "Bob",
            "aliases": ["B. Example"],
            "attributes": {"role": "candidate"},
            "relationships": [
                {"target": "person-morgan", "relation": "friend_of"},
            ],
        },
        {
            "id": "person-morgan",
            "type": "person",
            "primary_name": "Morgan",
            "aliases": [],
            "attributes": {},
            "relationships": [
                {"target": "person-bob", "relation": "friend_of"},
            ],
        },
    ]


def _save_graph(data_dir: Path) -> Path:
    graph_path = data_dir / "entity_graph.yaml"
    save_entity_graph(_roundtrip_graph(), graph_path)
    return graph_path


def test_merge_stores_schema_valid_tombstone(isolated_data_dir: Path) -> None:
    from tools.entity.review import apply_action

    graph_path = _save_graph(isolated_data_dir)

    result = apply_action(
        action="merge_as_alias",
        source_id="person-bob",
        target_id="person-alice",
        graph_path=graph_path,
    )

    assert result["success"] is True
    graph = load_entity_graph(graph_path)
    alice = next(entity for entity in graph if entity["id"] == "person-alice")
    tombstone = alice["merged_entities"][0]
    assert tombstone["id"] == "person-bob"
    assert tombstone["target_id"] == "person-alice"
    assert tombstone["source"] == "review"
    assert tombstone["entity"]["primary_name"] == "Bob"
    assert tombstone["entity"]["aliases"] == ["B. Example"]


def test_merge_then_unmerge_restores_absorbed_entity_and_removes_merge_aliases(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main
    from tools.entity.review import apply_action

    graph_path = _save_graph(isolated_data_dir)
    original = load_entity_graph(graph_path)
    original_bob = next(entity for entity in original if entity["id"] == "person-bob")

    apply_action(
        action="merge_as_alias",
        source_id="person-bob",
        target_id="person-alice",
        graph_path=graph_path,
    )

    main(["--unmerge", "--id", "person-bob", "--target-id", "person-alice"])
    capsys.readouterr()

    graph = load_entity_graph(graph_path)
    ids = {entity["id"] for entity in graph}
    assert ids == {"person-alice", "person-bob", "person-morgan"}

    bob = next(entity for entity in graph if entity["id"] == "person-bob")
    assert bob["primary_name"] == original_bob["primary_name"]
    assert bob["aliases"] == original_bob["aliases"]
    assert bob["attributes"] == original_bob["attributes"]
    assert {(rel["target"], rel["relation"]) for rel in bob["relationships"]} == {
        ("person-morgan", "friend_of")
    }

    alice = next(entity for entity in graph if entity["id"] == "person-alice")
    assert "Bob" not in alice["aliases"]
    assert "B. Example" not in alice["aliases"]
    assert alice.get("merged_entities", []) == []

    morgan = next(entity for entity in graph if entity["id"] == "person-morgan")
    assert {(rel["target"], rel["relation"]) for rel in morgan["relationships"]} == {
        ("person-bob", "friend_of")
    }


def test_review_merge_cli_stores_complete_tombstone_and_unmerge_roundtrips(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main

    graph_path = _save_graph(isolated_data_dir)

    main(
        [
            "--review",
            "--action",
            "merge_as_alias",
            "--id",
            "person-bob",
            "--target-id",
            "person-alice",
        ]
    )
    payload = capsys.readouterr().out
    assert '"success": true' in payload

    graph = load_entity_graph(graph_path)
    alice = next(entity for entity in graph if entity["id"] == "person-alice")
    tombstone = alice["merged_entities"][0]
    assert set(tombstone) == {
        "id",
        "target_id",
        "source",
        "merged_at",
        "entity",
        "transferred_aliases",
        "transferred_relationships",
        "rewired_relationships",
    }
    assert tombstone["source"] == "review"
    assert tombstone["entity"]["id"] == "person-bob"
    assert tombstone["entity"]["primary_name"] == "Bob"
    assert tombstone["transferred_aliases"] == ["Bob", "B. Example"]
    assert tombstone["transferred_relationships"][0]["target"] == "person-morgan"
    assert tombstone["rewired_relationships"][0]["entity_id"] == "person-morgan"

    main(["--unmerge", "--id", "person-bob", "--target-id", "person-alice"])
    capsys.readouterr()
    graph = load_entity_graph(graph_path)
    assert {entity["id"] for entity in graph} == {
        "person-alice",
        "person-bob",
        "person-morgan",
    }
