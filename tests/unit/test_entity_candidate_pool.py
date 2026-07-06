#!/usr/bin/env python3
"""Persistent candidate pool behavior for write-time and agent proposals."""

from __future__ import annotations

import json
from pathlib import Path

from tools.lib.entity_graph import load_entity_graph, save_entity_graph


def _write_entry(day: int, people: list[str]) -> dict:
    from tools.write_journal.core import write_journal

    return write_journal(
        {
            "date": f"2026-07-{day:02d}",
            "title": f"Fixture {day}",
            "content": "Abstract fixture content.",
            "people": people,
            "location": "Test Lab",
            "weather": "Clear",
            "topic": ["life"],
            "mood": [],
            "tags": [],
        },
        dry_run=False,
    )


def test_unknown_person_is_persisted_only_after_repeated_write_threshold(
    isolated_data_dir: Path,
) -> None:
    from tools.entity.review import build_review_queue

    first = _write_entry(1, ["Morgan"])
    assert first["success"] is True
    assert not (isolated_data_dir / "entity_graph.yaml").exists()

    second = _write_entry(2, ["Morgan"])
    assert second["success"] is True

    graph = load_entity_graph(isolated_data_dir / "entity_graph.yaml")
    candidate = next(entity for entity in graph if entity["primary_name"] == "Morgan")
    assert candidate["type"] == "actor"
    assert candidate["attributes"]["kind"] == "human"
    assert candidate["status"] == "candidate"
    assert candidate["source"] == "seed"
    assert len(candidate["evidence"]) == 2

    queue = build_review_queue(graph_path=isolated_data_dir / "entity_graph.yaml")
    assert any(
        item["category"] == "candidate_entity" and item["entity_ids"] == [candidate["id"]]
        for item in queue
    )


def test_write_time_candidate_threshold_is_configurable(
    isolated_data_dir: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LIFE_INDEX_ENTITY_CANDIDATE_THRESHOLD", "3")

    _write_entry(1, ["Morgan"])
    _write_entry(2, ["Morgan"])
    assert not (isolated_data_dir / "entity_graph.yaml").exists()

    _write_entry(3, ["Morgan"])
    graph = load_entity_graph(isolated_data_dir / "entity_graph.yaml")
    assert any(entity["primary_name"] == "Morgan" for entity in graph)


def test_agent_propose_entity_persists_candidate_without_search_expansion(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main
    from tools.search_journals.core import resolve_query_entities

    proposal = {
        "kind": "entity",
        "id": "actor-morgan",
        "entity_type": "actor",
        "primary_name": "Morgan",
        "attributes": {"kind": "human"},
        "reason": "Host agent saw repeated evidence.",
        "evidence": ["Journals/2026/07/life-index_2026-07-02_001.md"],
    }

    main(["--propose", json.dumps(proposal)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True

    graph = load_entity_graph(isolated_data_dir / "entity_graph.yaml")
    candidate = next(entity for entity in graph if entity["id"] == "actor-morgan")
    assert candidate["type"] == "actor"
    assert candidate["attributes"]["kind"] == "human"
    assert candidate["status"] == "candidate"
    assert candidate["source"] == "agent"
    assert candidate["reason"] == "Host agent saw repeated evidence."
    assert resolve_query_entities("Morgan") == []


def test_agent_propose_entity_does_not_downgrade_confirmed_entity(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main

    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-morgan",
                "type": "actor",
                "primary_name": "Morgan",
                "aliases": [],
                "attributes": {"kind": "human"},
                "source": "user",
                "status": "confirmed",
                "relationships": [],
            }
        ],
        graph_path,
    )

    proposal = {
        "kind": "entity",
        "id": "person-morgan-candidate",
        "entity_type": "actor",
        "primary_name": "Morgan",
        "attributes": {"kind": "human"},
        "reason": "Host agent hypothesis.",
        "evidence": [],
    }

    main(["--propose", json.dumps(proposal)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["success"] is True
    assert payload["data"]["status"] == "already_confirmed"
    graph = load_entity_graph(graph_path)
    assert graph[0]["status"] == "confirmed"
    assert len(graph) == 1


def test_agent_propose_relationship_is_candidate_and_not_runtime_edge(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main
    from tools.lib.entity_runtime import load_runtime_view

    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-alice",
                "type": "actor",
                "primary_name": "Alice",
                "aliases": [],
                "attributes": {"kind": "human"},
                "relationships": [],
            },
            {
                "id": "person-bob",
                "type": "actor",
                "primary_name": "Bob",
                "aliases": [],
                "attributes": {"kind": "human"},
                "relationships": [],
            },
        ],
        graph_path,
    )
    proposal = {
        "kind": "relationship",
        "source_id": "person-alice",
        "target_id": "person-bob",
        "relation": "friend_of",
        "reason": "Host agent hypothesis.",
        "evidence": ["Journals/2026/07/life-index_2026-07-03_001.md"],
    }

    main(["--propose", json.dumps(proposal)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True

    graph = load_entity_graph(graph_path)
    alice = next(entity for entity in graph if entity["id"] == "person-alice")
    relationship = alice["relationships"][0]
    assert relationship["source"] == "agent"
    assert relationship["status"] == "candidate"
    assert relationship["reason"] == "Host agent hypothesis."
    assert relationship["evidence"] == ["Journals/2026/07/life-index_2026-07-03_001.md"]

    view = load_runtime_view(graph_path)
    assert "person-bob" not in view.reverse_relationships

    from tools.entity.review import build_review_queue

    queue = build_review_queue(graph_path=graph_path)
    item = next(item for item in queue if item["category"] == "candidate_relationship")
    assert "Host agent hypothesis." in item["why"]
