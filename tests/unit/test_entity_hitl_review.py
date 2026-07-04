#!/usr/bin/env python3
"""HITL review queue and provenance tests for entity graph decisions."""

from __future__ import annotations

from pathlib import Path

from tools.lib.entity_graph import load_entity_graph, save_entity_graph


def _graph() -> list[dict]:
    return [
        {
            "id": "person-alice",
            "type": "person",
            "primary_name": "Alice",
            "aliases": [],
            "attributes": {},
            "relationships": [],
        },
        {
            "id": "person-bob",
            "type": "person",
            "primary_name": "Bob",
            "aliases": [],
            "attributes": {},
            "relationships": [],
        },
    ]


def _save_graph(data_dir: Path, graph: list[dict] | None = None) -> Path:
    graph_path = data_dir / "entity_graph.yaml"
    save_entity_graph(graph or _graph(), graph_path)
    return graph_path


def _write_cooccurrence_journals(data_dir: Path) -> list[str]:
    rel_paths: list[str] = []
    journals_dir = data_dir / "Journals" / "2026" / "07"
    journals_dir.mkdir(parents=True, exist_ok=True)
    for day in range(1, 4):
        rel_path = f"Journals/2026/07/life-index_2026-07-0{day}_001.md"
        rel_paths.append(rel_path)
        (data_dir / rel_path).write_text(
            "---\n"
            f"title: Abstract fixture {day}\n"
            f"date: 2026-07-0{day}\n"
            'people: ["Alice", "Bob"]\n'
            "---\n\n"
            "Alice and Bob appeared in the same abstract fixture.\n",
            encoding="utf-8",
        )
    return rel_paths


def test_review_queue_exposes_why_evidence_and_choices(isolated_data_dir: Path) -> None:
    from tools.entity.review import build_review_queue

    graph_path = _save_graph(isolated_data_dir)
    evidence_paths = _write_cooccurrence_journals(isolated_data_dir)

    queue = build_review_queue(graph_path=graph_path)

    item = next(item for item in queue if item["category"] == "incomplete_relationship")
    assert "co-occur" in item["why"]
    assert item["evidence"] == evidence_paths
    assert item["action_choices"] == ["add_relationship", "skip"]
    assert item["entity_ids"] == ["person-alice", "person-bob"]


def test_review_add_relationship_writes_confirmed_provenance(
    isolated_data_dir: Path,
) -> None:
    from tools.entity.review import apply_action

    graph_path = _save_graph(isolated_data_dir)
    evidence_paths = _write_cooccurrence_journals(isolated_data_dir)

    result = apply_action(
        action="add_relationship",
        source_id="person-alice",
        target_id="person-bob",
        relation="friend_of",
        evidence=evidence_paths,
        source="review",
        graph_path=graph_path,
    )

    assert result["success"] is True
    graph = load_entity_graph(graph_path)
    alice = next(entity for entity in graph if entity["id"] == "person-alice")
    relationship = alice["relationships"][0]
    assert relationship["target"] == "person-bob"
    assert relationship["relation"] == "friend_of"
    assert relationship["source"] == "review"
    assert relationship["status"] == "confirmed"
    assert relationship["evidence"] == evidence_paths
    assert isinstance(relationship["created_at"], str)
    assert relationship["created_at"]


def test_cli_review_add_relationship_accepts_relation_flag(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main

    graph_path = _save_graph(isolated_data_dir)

    main(
        [
            "--review",
            "--action",
            "add_relationship",
            "--id",
            "person-alice",
            "--target-id",
            "person-bob",
            "--relation",
            "friend_of",
        ]
    )
    capsys.readouterr()

    graph = load_entity_graph(graph_path)
    alice = next(entity for entity in graph if entity["id"] == "person-alice")
    relationship = alice["relationships"][0]
    assert relationship["relation"] == "friend_of"
    assert relationship["source"] == "review"


def test_cli_review_preview_with_relation_describes_add_relationship(
    isolated_data_dir: Path,
    capsys,
) -> None:
    import json

    from tools.entity.__main__ import main

    _save_graph(isolated_data_dir)

    main(
        [
            "--review",
            "--action",
            "preview",
            "--id",
            "person-alice",
            "--target-id",
            "person-bob",
            "--relation",
            "friend_of",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    change = payload["data"]["changes"][0]
    assert change["type"] == "add_relationship"
    assert change["relation"] == "friend_of"


def test_cli_add_alias_without_update_stamps_user_metadata(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main

    graph_path = _save_graph(isolated_data_dir)

    main(["--add-alias", "A. Example", "--id", "person-alice"])
    capsys.readouterr()

    graph = load_entity_graph(graph_path)
    alice = next(entity for entity in graph if entity["id"] == "person-alice")
    assert "A. Example" in alice["aliases"]
    assert alice["alias_metadata"]["A. Example"]["source"] == "user"
    assert alice["alias_metadata"]["A. Example"]["created_at"]


def test_high_confidence_duplicate_is_queued_not_auto_merged(
    isolated_data_dir: Path,
) -> None:
    from tools.entity.review import build_review_queue

    graph_path = _save_graph(
        isolated_data_dir,
        [
            {
                "id": "person-alice",
                "type": "person",
                "primary_name": "Alice",
                "aliases": ["A. Example"],
                "relationships": [],
            },
            {
                "id": "person-allyce",
                "type": "person",
                "primary_name": "Alyce",
                "aliases": [],
                "relationships": [],
            },
        ],
    )

    queue = build_review_queue(graph_path=graph_path)
    graph = load_entity_graph(graph_path)

    assert any(item["category"] == "possible_duplicate" for item in queue)
    assert {entity["id"] for entity in graph} == {"person-alice", "person-allyce"}
