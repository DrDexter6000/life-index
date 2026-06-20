from __future__ import annotations


def _entity(
    entity_id: str,
    primary_name: str,
    entity_type: str = "project",
    *,
    aliases: list[str] | None = None,
    relationships: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "id": entity_id,
        "type": entity_type,
        "primary_name": primary_name,
        "aliases": aliases or [],
        "relationships": relationships or [],
    }


def _graph() -> list[dict[str, object]]:
    return [
        _entity(
            "person-alice",
            "Alice",
            "person",
            aliases=["A."],
            relationships=[
                {
                    "target": "project-atlas",
                    "relation": "works_on",
                    "weight": 0.9,
                    "supporting_journal_ids": ["Journals/2026/03/life-index_2026-03-14_001.md"],
                }
            ],
        ),
        _entity(
            "project-atlas",
            "Atlas",
            relationships=[
                {
                    "target": "concept-roadmap",
                    "relation": "mentions",
                    "supporting_journal_ids": ["Journals/2026/04/life-index_2026-04-01_001.md"],
                }
            ],
        ),
        _entity(
            "person-bob",
            "Bob",
            "person",
            relationships=[{"target": "person-alice", "relation": "collaborates_with"}],
        ),
        _entity("concept-roadmap", "Roadmap", "concept"),
        _entity("place-london", "London", "place"),
    ]


def test_entity_neighbors_returns_incoming_outgoing_edges_with_support() -> None:
    from tools.entity.neighbors import build_entity_neighbors_payload

    payload = build_entity_neighbors_payload(_graph(), "Alice")

    assert payload["status"] == "ok"
    assert payload["resolved_entity"]["id"] == "person-alice"
    assert payload["neighbor_count"] == 2
    assert [item["entity_id"] for item in payload["neighbors"]] == [
        "project-atlas",
        "person-bob",
    ]
    atlas = payload["neighbors"][0]
    assert atlas["hops"] == 1
    assert atlas["edges"] == [
        {
            "source": "person-alice",
            "target": "project-atlas",
            "relation": "works_on",
            "direction": "outgoing",
            "weight": 0.9,
            "supporting_journal_ids": ["Journals/2026/03/life-index_2026-03-14_001.md"],
        }
    ]
    bob = payload["neighbors"][1]
    assert bob["edges"][0]["direction"] == "incoming"


def test_entity_neighbors_filters_relation_and_limits_hops() -> None:
    from tools.entity.neighbors import build_entity_neighbors_payload

    one_hop = build_entity_neighbors_payload(_graph(), "Alice", max_hops=1)
    two_hops = build_entity_neighbors_payload(_graph(), "Alice", max_hops=2)
    works_on = build_entity_neighbors_payload(_graph(), "Alice", relations=["works_on"])

    assert "concept-roadmap" not in [item["entity_id"] for item in one_hop["neighbors"]]
    assert "concept-roadmap" in [item["entity_id"] for item in two_hops["neighbors"]]
    assert [item["entity_id"] for item in works_on["neighbors"]] == ["project-atlas"]
    assert works_on["relations"] == ["works_on"]


def test_entity_neighbors_unknown_and_empty_graph_are_exhaustive_empty_results() -> None:
    from tools.entity.neighbors import build_entity_neighbors_payload

    unknown = build_entity_neighbors_payload(_graph(), "Unknown")
    empty = build_entity_neighbors_payload([], "Alice")

    assert unknown["status"] == "entity_not_found"
    assert unknown["resolved_entity"] is None
    assert unknown["neighbors"] == []
    assert unknown["exhaustive"] is True
    assert empty["status"] == "entity_not_found"
    assert empty["neighbors"] == []


def test_entity_neighbors_is_stably_sorted() -> None:
    from tools.entity.neighbors import build_entity_neighbors_payload

    first = build_entity_neighbors_payload(_graph(), "A.", max_hops=2)
    second = build_entity_neighbors_payload(_graph(), "A.", max_hops=2)

    assert first == second
