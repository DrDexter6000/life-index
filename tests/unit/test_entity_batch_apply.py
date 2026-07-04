#!/usr/bin/env python3
"""Batch entity import preview/apply contract."""

from __future__ import annotations

import json
from pathlib import Path

from tools.lib.entity_graph import load_entity_graph, save_entity_graph


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _base_graph(data_dir: Path) -> Path:
    graph_path = data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-alice",
                "type": "person",
                "primary_name": "Alice",
                "aliases": [],
                "source": "user",
                "status": "confirmed",
                "relationships": [],
            }
        ],
        graph_path,
    )
    return graph_path


def _batch_payload() -> dict:
    return {
        "entities": [
            {
                "id": "person-bob",
                "type": "person",
                "primary_name": "Bob",
                "aliases": ["B. Example"],
            },
            {
                "id": "person-alice-conflict",
                "type": "person",
                "primary_name": "Alice",
                "aliases": [],
            },
        ],
        "relationships": [
            {
                "source": "person-alice",
                "target": "person-bob",
                "relation": "friend_of",
            }
        ],
    }


def test_apply_batch_preview_reports_counts_without_mutating(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main

    graph_path = _base_graph(isolated_data_dir)
    batch_path = _write_json(isolated_data_dir / "batch.json", _batch_payload())

    main(["--apply-batch", str(batch_path), "--preview"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["success"] is True
    assert payload["data"]["preview"] is True
    assert payload["data"]["new_entities"] == 1
    assert payload["data"]["new_relationships"] == 1
    assert payload["data"]["conflicts"] == 1
    assert payload["data"]["duplicates_skipped"] == 0
    assert [entity["id"] for entity in load_entity_graph(graph_path)] == ["person-alice"]


def test_apply_batch_applies_clean_items_and_queues_conflicts_idempotently(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main
    from tools.entity.review import build_review_queue

    graph_path = _base_graph(isolated_data_dir)
    batch_path = _write_json(isolated_data_dir / "batch.json", _batch_payload())

    main(["--apply-batch", str(batch_path)])
    first_payload = json.loads(capsys.readouterr().out)
    first_graph_text = graph_path.read_text(encoding="utf-8")

    assert first_payload["success"] is True
    graph = load_entity_graph(graph_path)
    bob = next(entity for entity in graph if entity["id"] == "person-bob")
    assert bob["source"] == "user"
    assert bob["status"] == "confirmed"
    alice = next(entity for entity in graph if entity["id"] == "person-alice")
    relationship = alice["relationships"][0]
    assert relationship["target"] == "person-bob"
    assert relationship["source"] == "user"
    assert relationship["status"] == "confirmed"
    assert not any(entity["id"] == "person-alice-conflict" for entity in graph)

    queue = build_review_queue(graph_path=graph_path)
    assert any(
        item["category"] == "candidate_entity"
        and item["primary_name"] == "Alice"
        and item["source"] == "user"
        for item in queue
    )

    main(["--apply-batch", str(batch_path)])
    second_payload = json.loads(capsys.readouterr().out)
    second_graph_text = graph_path.read_text(encoding="utf-8")

    assert second_payload["success"] is True
    assert second_payload["data"]["new_entities"] == 0
    assert second_payload["data"]["new_relationships"] == 0
    assert second_payload["data"]["duplicates_skipped"] >= 2
    assert second_graph_text == first_graph_text


def test_apply_batch_is_atomic_when_entity_row_is_invalid(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main

    graph_path = _base_graph(isolated_data_dir)
    before = graph_path.read_text(encoding="utf-8")
    batch_path = _write_json(
        isolated_data_dir / "invalid-batch.json",
        {
            "entities": [
                {"id": "person-bob", "primary_name": "Bob"},
                {"id": "person-morgan", "type": "person", "primary_name": "Morgan"},
            ],
            "relationships": [],
        },
    )

    main(["--apply-batch", str(batch_path)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["success"] is False
    assert "entities[0].type" in payload["error"]
    assert graph_path.read_text(encoding="utf-8") == before


def test_apply_batch_is_atomic_when_relationship_row_is_invalid(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main

    graph_path = _base_graph(isolated_data_dir)
    before = graph_path.read_text(encoding="utf-8")
    batch_path = _write_json(
        isolated_data_dir / "invalid-relationship-batch.json",
        {
            "entities": [
                {"id": "person-bob", "type": "person", "primary_name": "Bob"},
            ],
            "relationships": [
                {
                    "source": "person-alice",
                    "target": "person-missing",
                    "relation": "friend_of",
                }
            ],
        },
    )

    main(["--apply-batch", str(batch_path)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["success"] is False
    assert "relationships[0].target" in payload["error"]
    assert graph_path.read_text(encoding="utf-8") == before
