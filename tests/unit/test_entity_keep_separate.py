"""Successor tests for persistent keep_separate entity review decisions."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.lib.entity_graph import save_entity_graph


def _graph_path(root: Path) -> Path:
    return root / "entity_graph.yaml"


def _entity(entity_id: str, name: str) -> dict:
    return {
        "id": entity_id,
        "type": "person",
        "primary_name": name,
        "aliases": [],
        "attributes": {},
        "relationships": [],
    }


def _save_close_name_graph(root: Path) -> Path:
    graph_path = _graph_path(root)
    save_entity_graph(
        [
            _entity("person-alan", "Alan"),
            _entity("person-alen", "Alen"),
        ],
        graph_path,
    )
    return graph_path


def _duplicate_pairs(graph_path: Path) -> set[frozenset[str]]:
    from tools.entity.audit import audit_entity_graph

    report = audit_entity_graph(graph_path, journals_dir=None)
    return {
        frozenset(issue["entity_ids"])
        for issue in report["issues"]
        if issue["type"] == "possible_duplicate"
    }


def test_keep_separate_persists_user_decision_and_suppresses_duplicate_audit(
    isolated_data_dir: Path,
) -> None:
    from tools.entity.review import apply_action
    from tools.lib.entity_graph import load_entity_graph

    graph_path = _save_close_name_graph(isolated_data_dir)
    pair = frozenset({"person-alan", "person-alen"})
    assert pair in _duplicate_pairs(graph_path)

    result = apply_action(
        action="keep_separate",
        source_id="person-alan",
        target_id="person-alen",
        source="user",
        graph_path=graph_path,
    )

    assert result["success"] is True
    assert result["action"] == "keep_separate"
    assert result["source_id"] == "person-alan"
    assert result["target_id"] == "person-alen"

    reloaded = load_entity_graph(graph_path)
    by_id = {entity["id"]: entity for entity in reloaded}
    alan_record = by_id["person-alan"]["not_duplicate_of"][0]
    alen_record = by_id["person-alen"]["not_duplicate_of"][0]
    assert alan_record["target"] == "person-alen"
    assert alen_record["target"] == "person-alan"
    assert alan_record["source"] == "user"
    assert alen_record["source"] == "user"
    assert isinstance(alan_record["created_at"], str)
    assert isinstance(alen_record["created_at"], str)

    assert pair not in _duplicate_pairs(graph_path)


def test_keep_separate_is_symmetric_and_reversible(isolated_data_dir: Path) -> None:
    from tools.entity.review import apply_action
    from tools.lib.entity_graph import load_entity_graph

    graph_path = _save_close_name_graph(isolated_data_dir)
    pair = frozenset({"person-alan", "person-alen"})

    apply_action(
        action="keep_separate",
        source_id="person-alan",
        target_id="person-alen",
        source="user",
        graph_path=graph_path,
    )
    assert pair not in _duplicate_pairs(graph_path)

    result = apply_action(
        action="undo_keep_separate",
        source_id="person-alen",
        target_id="person-alan",
        source="user",
        graph_path=graph_path,
    )

    assert result["success"] is True
    assert result["action"] == "undo_keep_separate"
    assert pair in _duplicate_pairs(graph_path)
    reloaded = load_entity_graph(graph_path)
    assert all("not_duplicate_of" not in entity for entity in reloaded)


def test_keep_separate_does_not_silence_unreviewed_duplicates(
    isolated_data_dir: Path,
) -> None:
    from tools.entity.review import apply_action

    graph_path = _graph_path(isolated_data_dir)
    save_entity_graph(
        [
            _entity("person-alan", "Alan"),
            _entity("person-alen", "Alen"),
            _entity("person-cara", "Cara"),
            _entity("person-cora", "Cora"),
        ],
        graph_path,
    )

    apply_action(
        action="keep_separate",
        source_id="person-alan",
        target_id="person-alen",
        source="user",
        graph_path=graph_path,
    )

    pairs = _duplicate_pairs(graph_path)
    assert frozenset({"person-alan", "person-alen"}) not in pairs
    assert frozenset({"person-cara", "person-cora"}) in pairs


def test_not_duplicate_of_schema_validates_provenance_and_targets() -> None:
    from tools.lib.entity_schema import EntityGraphValidationError
    from tools.lib.entity_schema import validate_entity_graph_payload

    payload = {
        "entities": [
            {
                **_entity("person-alan", "Alan"),
                "not_duplicate_of": [
                    {
                        "target": "person-alen",
                        "source": "user",
                        "created_at": "2026-07-04T00:00:00+00:00",
                    }
                ],
            },
            _entity("person-alen", "Alen"),
        ]
    }

    validated = validate_entity_graph_payload(payload)
    assert validated[0]["not_duplicate_of"] == [
        {
            "target": "person-alen",
            "source": "user",
            "created_at": "2026-07-04T00:00:00+00:00",
        }
    ]

    invalid_source = {
        "entities": [
            {
                **_entity("person-alan", "Alan"),
                "not_duplicate_of": [
                    {
                        "target": "person-alen",
                        "source": "invalid",
                        "created_at": "2026-07-04T00:00:00+00:00",
                    }
                ],
            },
            _entity("person-alen", "Alen"),
        ]
    }
    with pytest.raises(EntityGraphValidationError, match="not_duplicate_of.source"):
        validate_entity_graph_payload(invalid_source)

    unknown_target = {
        "entities": [
            {
                **_entity("person-alan", "Alan"),
                "not_duplicate_of": [
                    {
                        "target": "person-missing",
                        "source": "user",
                        "created_at": "2026-07-04T00:00:00+00:00",
                    }
                ],
            },
        ]
    }
    with pytest.raises(EntityGraphValidationError, match="unknown not_duplicate_of target"):
        validate_entity_graph_payload(unknown_target)
