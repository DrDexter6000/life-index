#!/usr/bin/env python3
"""Tests for the preview-first user-confirmed relationship primitive."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph, save_entity_graph


def _run_entity_cli(argv: list[str]) -> tuple[dict[str, Any], int | None]:
    from tools.entity.__main__ import main

    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer
    exit_code: int | None = None
    try:
        try:
            main(argv)
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 1
    finally:
        sys.stdout = old_stdout
    return json.loads(buffer.getvalue()), exit_code


def _base_graph() -> list[dict[str, Any]]:
    return [
        {
            "id": "actor-alice",
            "type": "actor",
            "primary_name": "Alice",
            "aliases": [],
            "attributes": {"kind": "human"},
            "relationships": [],
            "source": "user",
            "status": "confirmed",
        },
        {
            "id": "actor-bob",
            "type": "actor",
            "primary_name": "Bob",
            "aliases": [],
            "attributes": {"kind": "human"},
            "relationships": [],
            "source": "user",
            "status": "confirmed",
        },
    ]


def _save_graph(data_dir: Path, graph: list[dict[str, Any]] | None = None) -> Path:
    graph_path = data_dir / "entity_graph.yaml"
    save_entity_graph(graph or _base_graph(), graph_path)
    return graph_path


def _relationship(graph_path: Path) -> dict[str, Any]:
    graph = load_entity_graph(graph_path)
    alice = next(entity for entity in graph if entity["id"] == "actor-alice")
    return alice["relationships"][0]


def test_maintain_add_relationship_preview_is_read_only_and_json(
    isolated_data_dir: Path,
) -> None:
    graph_path = _save_graph(isolated_data_dir)
    before = graph_path.read_bytes()

    payload, exit_code = _run_entity_cli(
        [
            "maintain",
            "--add-relationship",
            "--id",
            "actor-alice",
            "--target-id",
            "actor-bob",
            "--relation",
            "friend_of",
            "--preview",
            "--json",
        ]
    )

    assert exit_code in (None, 0)
    assert payload["success"] is True
    assert payload["data"]["workflow"] == "maintain.add_relationship"
    assert payload["data"]["preview"] is True
    assert payload["data"]["applied"] is False
    assert payload["data"]["relation"] == "friend_of"
    assert payload["data"]["operation"] == "add"
    assert graph_path.read_bytes() == before


def test_maintain_add_relationship_apply_writes_user_confirmed_edge(
    isolated_data_dir: Path,
) -> None:
    graph_path = _save_graph(isolated_data_dir)

    payload, exit_code = _run_entity_cli(
        [
            "maintain",
            "--add-relationship",
            "--id",
            "actor-alice",
            "--target-id",
            "actor-bob",
            "--relation",
            "friend_of",
            "--apply",
            "--json",
        ]
    )

    assert exit_code in (None, 0)
    assert payload["success"] is True
    assert payload["data"]["applied"] is True
    relationship = _relationship(graph_path)
    assert relationship["target"] == "actor-bob"
    assert relationship["relation"] == "friend_of"
    assert relationship["source"] == "user"
    assert relationship["status"] == "confirmed"
    assert relationship["evidence"] == []
    assert isinstance(relationship["created_at"], str)
    assert relationship["created_at"]


def test_maintain_add_relationship_is_idempotent(isolated_data_dir: Path) -> None:
    graph_path = _save_graph(isolated_data_dir)

    for _ in range(2):
        payload, exit_code = _run_entity_cli(
            [
                "maintain",
                "--add-relationship",
                "--id",
                "actor-alice",
                "--target-id",
                "actor-bob",
                "--relation",
                "friend_of",
                "--apply",
                "--json",
            ]
        )
        assert exit_code in (None, 0)
        assert payload["success"] is True

    graph = load_entity_graph(graph_path)
    alice = next(entity for entity in graph if entity["id"] == "actor-alice")
    assert [
        relationship
        for relationship in alice["relationships"]
        if relationship["target"] == "actor-bob" and relationship["relation"] == "friend_of"
    ] == [alice["relationships"][0]]


def test_maintain_add_relationship_promotes_candidate_edge_with_evidence(
    isolated_data_dir: Path,
) -> None:
    graph_path = _save_graph(
        isolated_data_dir,
        [
            {
                **_base_graph()[0],
                "relationships": [
                    {
                        "target": "actor-bob",
                        "relation": "friend_of",
                        "source": "agent",
                        "status": "candidate",
                        "reason": "Host-agent hypothesis.",
                        "evidence": ["Journals/2026/07/life-index_2026-07-01_001.md"],
                    }
                ],
            },
            _base_graph()[1],
        ],
    )

    payload, exit_code = _run_entity_cli(
        [
            "maintain",
            "--add-relationship",
            "--id",
            "actor-alice",
            "--target-id",
            "actor-bob",
            "--relation",
            "friend_of",
            "--apply",
            "--json",
        ]
    )

    assert exit_code in (None, 0)
    assert payload["success"] is True
    assert payload["data"]["operation"] == "promote_candidate"
    graph = load_entity_graph(graph_path)
    alice = next(entity for entity in graph if entity["id"] == "actor-alice")
    assert len(alice["relationships"]) == 1
    relationship = alice["relationships"][0]
    assert relationship["source"] == "user"
    assert relationship["status"] == "confirmed"
    assert relationship["evidence"] == ["Journals/2026/07/life-index_2026-07-01_001.md"]


def test_maintain_add_relationship_rejects_candidate_entities_without_writes(
    isolated_data_dir: Path,
) -> None:
    graph_path = _save_graph(
        isolated_data_dir,
        [
            {**_base_graph()[0], "status": "candidate", "source": "agent"},
            _base_graph()[1],
        ],
    )
    before = graph_path.read_bytes()

    payload, exit_code = _run_entity_cli(
        [
            "maintain",
            "--add-relationship",
            "--id",
            "actor-alice",
            "--target-id",
            "actor-bob",
            "--relation",
            "friend_of",
            "--apply",
            "--json",
        ]
    )

    assert exit_code in (None, 2)
    assert payload["success"] is False
    assert payload["error"]["code"] == "ENTITY_RELATIONSHIP_ENTITY_NOT_CONFIRMED"
    assert "entity --review" in payload["error"]["suggested_command"]
    assert graph_path.read_bytes() == before


def test_maintain_add_relationship_rejects_unknown_relation_without_writes(
    isolated_data_dir: Path,
) -> None:
    graph_path = _save_graph(isolated_data_dir)
    before = graph_path.read_bytes()

    payload, exit_code = _run_entity_cli(
        [
            "maintain",
            "--add-relationship",
            "--id",
            "actor-alice",
            "--target-id",
            "actor-bob",
            "--relation",
            "invented_relation",
            "--apply",
            "--json",
        ]
    )

    assert exit_code in (None, 2)
    assert payload["success"] is False
    assert payload["error"]["code"] == "ENTITY_RELATIONSHIP_INVALID_RELATION"
    assert graph_path.read_bytes() == before


def test_top_level_add_relationship_action_points_to_maintain_replacement(
    isolated_data_dir: Path,
) -> None:
    _save_graph(isolated_data_dir)

    payload, exit_code = _run_entity_cli(
        [
            "--action",
            "add_relationship",
            "--id",
            "actor-alice",
            "--target-id",
            "actor-bob",
            "--relation",
            "friend_of",
            "--json",
        ]
    )

    assert exit_code == 2
    assert payload["success"] is False
    assert payload["error"]["code"] == "ENTITY_RELATIONSHIP_ACTION_REQUIRES_REVIEW"
    assert "entity maintain --add-relationship" in payload["error"]["suggested_command"]
