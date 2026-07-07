"""Contract tests for deterministic entity names beside entity ids."""

from __future__ import annotations

from tools.entity.audit import audit_entity_graph
from tools.entity.review import build_review_queue
from tools.entity.stats import compute_stats
from tools.lib.entity_graph import save_entity_graph


def _name_floor_graph() -> list[dict]:
    return [
        {
            "id": "actor-alice",
            "type": "actor",
            "primary_name": "Alice",
            "attributes": {"kind": "human"},
            "relationships": [
                {
                    "target": "actor-bob",
                    "relation": "friend_of",
                    "source": "user",
                    "status": "confirmed",
                    "created_at": "2026-07-07T00:00:00Z",
                },
                {
                    "target": "actor-morgan",
                    "relation": "colleague_of",
                    "source": "agent",
                    "status": "candidate",
                    "reason": "Observed in abstract fixture.",
                    "created_at": "2026-07-07T00:00:00Z",
                },
            ],
            "source": "user",
            "status": "confirmed",
        },
        {
            "id": "actor-bob",
            "type": "actor",
            "primary_name": "Bob",
            "attributes": {"kind": "human"},
            "relationships": [
                {
                    "target": "actor-alice",
                    "relation": "friend_of",
                    "source": "user",
                    "status": "confirmed",
                    "created_at": "2026-07-07T00:00:00Z",
                }
            ],
            "source": "user",
            "status": "confirmed",
        },
        {
            "id": "actor-morgan",
            "type": "actor",
            "primary_name": "Morgan",
            "attributes": {"kind": "human"},
            "relationships": [],
            "source": "agent",
            "status": "candidate",
            "reason": "Observed in abstract fixture.",
        },
    ]


def test_stats_entity_id_surfaces_include_primary_names(isolated_data_dir) -> None:
    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(_name_floor_graph(), graph_path)

    payload = compute_stats(graph_path=graph_path)

    assert {
        "entity_id": "actor-alice",
        "primary_name": "Alice",
        "incoming_count": 1,
    } in payload[
        "data"
    ]["top_referenced"]
    assert {
        "entity_id": "actor-bob",
        "primary_name": "Bob",
        "incoming_count": 1,
    } in payload[
        "data"
    ]["top_referenced"]
    assert {
        "entities": [
            {"entity_id": "actor-alice", "primary_name": "Alice"},
            {"entity_id": "actor-bob", "primary_name": "Bob"},
        ],
        "cooccurrence": 2,
    } in payload["data"]["top_cooccurrence"]


def test_audit_facts_and_review_queue_include_primary_names(isolated_data_dir) -> None:
    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(_name_floor_graph(), graph_path)
    journals_dir = isolated_data_dir / "Journals"
    journals_dir.mkdir(exist_ok=True)

    audit = audit_entity_graph(graph_path, journals_dir=journals_dir)
    queue = build_review_queue(graph_path=graph_path)

    assert audit["facts"]["zero_journal_reference_entities"] == [
        {"entity_id": "actor-alice", "primary_name": "Alice"},
        {"entity_id": "actor-bob", "primary_name": "Bob"},
        {"entity_id": "actor-morgan", "primary_name": "Morgan"},
    ]
    candidate_relationship = next(
        item for item in audit["issues"] if item["type"] == "candidate_relationship"
    )
    assert candidate_relationship["entity_refs"] == [
        {"entity_id": "actor-alice", "primary_name": "Alice"},
        {"entity_id": "actor-morgan", "primary_name": "Morgan"},
    ]
    review_item = next(item for item in queue if item["category"] == "candidate_relationship")
    assert review_item["entities"] == [
        {"entity_id": "actor-alice", "primary_name": "Alice"},
        {"entity_id": "actor-morgan", "primary_name": "Morgan"},
    ]
