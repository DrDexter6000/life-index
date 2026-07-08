"""GUI-facing contract tests for entity review action choices."""

from __future__ import annotations

import json
from pathlib import Path

from tools.lib.entity_graph import load_entity_graph, save_entity_graph


def _graph_path(root: Path) -> Path:
    return root / "entity_graph.yaml"


def _entity(entity_id: str, name: str, *, status: str = "confirmed") -> dict:
    return {
        "id": entity_id,
        "type": "actor",
        "primary_name": name,
        "aliases": [],
        "attributes": {"kind": "human"},
        "relationships": [],
        "source": "user" if status == "confirmed" else "agent",
        "status": status,
    }


def _save_duplicate_graph(root: Path) -> Path:
    graph_path = _graph_path(root)
    save_entity_graph(
        [
            _entity("person-alan", "Alan"),
            _entity("person-alen", "Alen"),
        ],
        graph_path,
    )
    return graph_path


def _review_item(root: Path, category: str = "possible_duplicate") -> dict:
    from tools.entity.review import build_review_queue

    queue = build_review_queue(graph_path=_graph_path(root))
    return next(item for item in queue if item["category"] == category)


def test_review_queue_action_choices_are_stable_payloads(
    isolated_data_dir: Path,
) -> None:
    _save_duplicate_graph(isolated_data_dir)

    item = _review_item(isolated_data_dir)

    assert item["entity_ids"] == ["person-alan", "person-alen"]
    assert item["source_id"] == "person-alan"
    assert item["target_id"] == "person-alen"
    assert item["action_choices"]
    choice = item["action_choices"][0]
    assert choice == {
        "action": "merge_as_alias",
        "source_id": "person-alan",
        "target_id": "person-alen",
        "relation": None,
        "evidence": [],
        "preview_required": True,
        "label": "Same",
        "description": "Preview merging the source entity into the target entity as aliases.",
    }


def test_cli_review_preview_accepts_explicit_review_action_and_is_read_only(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main

    graph_path = _save_duplicate_graph(isolated_data_dir)
    item = _review_item(isolated_data_dir)
    before = graph_path.read_bytes()

    main(
        [
            "--review",
            "--action",
            "preview",
            "--review-action",
            "keep_separate",
            "--id",
            item["item_id"],
            "--source-id",
            "person-alan",
            "--target-id",
            "person-alen",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert graph_path.read_bytes() == before
    assert payload["data"]["item_id"] == item["item_id"]
    assert payload["data"]["action"] == "keep_separate"
    assert payload["data"]["preview"] is True
    assert payload["data"]["will_write"] == [
        {
            "type": "not_duplicate_of",
            "source_id": "person-alan",
            "target_id": "person-alen",
            "source": "user",
        }
    ]
    assert payload["data"]["will_not_write"] == ["No merge will be performed."]
    assert payload["data"]["reversible"] is True


def test_cli_review_apply_accepts_item_id_plus_source_id(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main

    graph_path = _save_duplicate_graph(isolated_data_dir)
    item = _review_item(isolated_data_dir)

    main(
        [
            "--review",
            "--action",
            "keep_separate",
            "--id",
            item["item_id"],
            "--source-id",
            "person-alan",
            "--target-id",
            "person-alen",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["item_id"] == item["item_id"]
    assert payload["applied"] is True
    assert payload["action"] == "keep_separate"

    graph = load_entity_graph(graph_path)
    by_id = {entity["id"]: entity for entity in graph}
    assert by_id["person-alan"]["not_duplicate_of"][0]["target"] == "person-alen"
    assert by_id["person-alen"]["not_duplicate_of"][0]["target"] == "person-alan"


def test_reject_candidate_preview_and_apply_are_explicit(
    isolated_data_dir: Path,
    capsys,
) -> None:
    from tools.entity.__main__ import main

    graph_path = _graph_path(isolated_data_dir)
    save_entity_graph([_entity("person-morgan", "Morgan", status="candidate")], graph_path)
    before = graph_path.read_bytes()

    main(
        [
            "--review",
            "--action",
            "preview",
            "--review-action",
            "reject_candidate",
            "--id",
            "review-candidate-1",
            "--source-id",
            "person-morgan",
            "--json",
        ]
    )
    preview = json.loads(capsys.readouterr().out)
    assert preview["success"] is True
    assert graph_path.read_bytes() == before
    assert preview["data"]["action"] == "reject_candidate"
    assert preview["data"]["will_write"] == [
        {"type": "remove_candidate_entity", "source_id": "person-morgan"}
    ]
    assert preview["data"]["reversible"] is False

    main(
        [
            "--review",
            "--action",
            "reject_candidate",
            "--id",
            "review-candidate-1",
            "--source-id",
            "person-morgan",
            "--json",
        ]
    )
    applied = json.loads(capsys.readouterr().out)
    assert applied["success"] is True
    assert applied["applied"] is True
    assert applied["rejected_id"] == "person-morgan"
    assert load_entity_graph(graph_path) == []
