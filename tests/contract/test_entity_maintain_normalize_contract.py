"""Contract tests for the Entity Graph maintain normalization facade."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from tools.lib.entity_graph import load_entity_graph
from tools.lib.entity_graph import resolve_entity
from tools.lib.entity_graph import save_entity_graph


def _run_entity_cli(argv: list[str]) -> dict[str, Any]:
    from tools.entity.__main__ import main

    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer
    try:
        main(argv)
    finally:
        sys.stdout = old_stdout
    return json.loads(buffer.getvalue())


def _write_old_type_graph(graph_path: Path) -> None:
    save_entity_graph(
        [
            {
                "id": "person-alice",
                "type": "person",
                "primary_name": "Alice",
                "aliases": ["A."],
                "source": "user",
                "status": "confirmed",
                "created_at": "2026-07-01T00:00:00+00:00",
                "attributes": {"role": "parent"},
                "relationships": [
                    {
                        "relation": "uses",
                        "target": "person-deepseek",
                        "source": "user",
                        "created_at": "2026-07-01T00:00:00+00:00",
                        "status": "confirmed",
                        "evidence": [],
                    }
                ],
                "not_duplicate_of": [
                    {
                        "target": "person-alen",
                        "source": "user",
                        "created_at": "2026-07-01T00:00:00+00:00",
                    }
                ],
                "merged_entities": [
                    {
                        "id": "person-ally",
                        "target_id": "person-alice",
                        "source": "user",
                        "merged_at": "2026-07-01T00:00:00+00:00",
                        "entity": {
                            "id": "person-ally",
                            "type": "person",
                            "primary_name": "Ally",
                            "aliases": [],
                            "relationships": [],
                        },
                        "transferred_aliases": ["Ally"],
                        "transferred_relationships": [],
                        "rewired_relationships": [],
                    }
                ],
            },
            {
                "id": "person-deepseek",
                "type": "person",
                "primary_name": "DeepSeek",
                "source": "user",
                "status": "confirmed",
                "attributes": {"subtype": "ai", "role": "ai_assistant"},
                "relationships": [],
            },
            {
                "id": "person-alen",
                "type": "person",
                "primary_name": "Alen",
                "source": "user",
                "status": "confirmed",
                "attributes": {"kind": "human"},
                "relationships": [],
            },
            {
                "id": "place-home",
                "type": "place",
                "primary_name": "Home",
                "relationships": [],
            },
        ],
        graph_path,
    )


def _write_delete_graph(graph_path: Path) -> None:
    save_entity_graph(
        [
            {
                "id": "person-alice",
                "type": "person",
                "primary_name": "Alice",
                "aliases": [],
                "relationships": [
                    {"target": "person-bob", "relation": "friend_of"},
                ],
            },
            {
                "id": "person-bob",
                "type": "person",
                "primary_name": "Bob",
                "aliases": [],
                "relationships": [],
            },
        ],
        graph_path,
    )


def test_maintain_normalize_preview_returns_plan_without_writes(
    isolated_data_dir: Path,
) -> None:
    """Preview plans old type normalization without mutating the graph."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    _write_old_type_graph(graph_path)
    before = graph_path.read_text(encoding="utf-8")

    payload = _run_entity_cli(["maintain", "--normalize", "--preview", "--json"])

    after = graph_path.read_text(encoding="utf-8")
    assert after == before
    assert payload["success"] is True
    assert payload["data"]["workflow"] == "maintain.normalize"
    assert payload["data"]["preview"] is True
    assert payload["data"]["applied"] is False
    assert payload["data"]["summary"]["change_count"] == 3
    assert payload["data"]["summary"]["review_question_count"] == 0
    assert payload["data"]["changes"] == [
        {
            "entity_id": "person-alice",
            "primary_name": "Alice",
            "from": {"type": "person", "kind": None},
            "to": {"type": "actor", "kind": "human"},
            "reason": "person entity maps to actor/human",
        },
        {
            "entity_id": "person-deepseek",
            "primary_name": "DeepSeek",
            "from": {"type": "person", "kind": None},
            "to": {"type": "actor", "kind": "software_agent"},
            "reason": "AI assistant signals map to actor/software_agent",
        },
        {
            "entity_id": "person-alen",
            "primary_name": "Alen",
            "from": {"type": "person", "kind": "human"},
            "to": {"type": "actor", "kind": "human"},
            "reason": "person entity maps to actor/human",
        },
    ]
    assert payload["data"]["backup_path"] is None


def test_maintain_delete_preview_reports_impact_without_writes(
    isolated_data_dir: Path,
) -> None:
    """Maintain delete preview reports the exact impact without mutating the graph."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    _write_delete_graph(graph_path)
    before = graph_path.read_text(encoding="utf-8")

    payload = _run_entity_cli(["maintain", "--delete", "--id", "person-bob", "--preview", "--json"])

    assert graph_path.read_text(encoding="utf-8") == before
    assert payload["success"] is True
    assert payload["data"] == {
        "workflow": "maintain.delete",
        "preview": True,
        "applied": False,
        "backup_path": None,
        "deleted_id": "person-bob",
        "deleted_name": "Bob",
        "cleaned_refs": [{"entity_id": "person-alice", "relation": "friend_of"}],
    }


def test_maintain_delete_apply_requires_backup_and_removes_refs(
    isolated_data_dir: Path,
) -> None:
    """Destructive delete is only available through maintain apply with backup."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    _write_delete_graph(graph_path)
    before = graph_path.read_text(encoding="utf-8")

    missing_backup = _run_entity_cli(
        ["maintain", "--delete", "--id", "person-bob", "--apply", "--json"]
    )

    assert missing_backup["success"] is False
    assert missing_backup["error"]["code"] == "ENTITY_MAINTAIN_DELETE_BACKUP_REQUIRED"
    assert graph_path.read_text(encoding="utf-8") == before
    assert list(isolated_data_dir.glob("entity_graph.yaml.backup_*")) == []

    payload = _run_entity_cli(
        ["maintain", "--delete", "--id", "person-bob", "--apply", "--backup", "--json"]
    )

    assert payload["success"] is True
    assert payload["data"]["workflow"] == "maintain.delete"
    assert payload["data"]["preview"] is False
    assert payload["data"]["applied"] is True
    backup_path = Path(payload["data"]["backup_path"])
    assert backup_path.exists()
    assert backup_path.parent == isolated_data_dir
    graph = {entity["id"]: entity for entity in load_entity_graph(graph_path)}
    assert set(graph) == {"person-alice"}
    assert graph["person-alice"]["relationships"] == []


def test_maintain_normalize_apply_requires_backup_and_preserves_graph_records(
    isolated_data_dir: Path,
) -> None:
    """Apply writes atomically with a backup while preserving user assertions."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    _write_old_type_graph(graph_path)

    missing_backup = _run_entity_cli(["maintain", "--normalize", "--apply", "--json"])

    assert missing_backup["success"] is False
    assert missing_backup["error"]["code"] == "ENTITY_NORMALIZE_BACKUP_REQUIRED"
    assert len(list(isolated_data_dir.glob("entity_graph.yaml.backup_*"))) == 0

    payload = _run_entity_cli(["maintain", "--normalize", "--apply", "--backup", "--json"])

    assert payload["success"] is True
    assert payload["data"]["applied"] is True
    assert payload["data"]["preview"] is False
    backup_path = Path(payload["data"]["backup_path"])
    assert backup_path.exists()
    assert backup_path.parent == isolated_data_dir

    graph = {entity["id"]: entity for entity in load_entity_graph(graph_path)}
    assert graph["person-alice"]["type"] == "actor"
    assert graph["person-alice"]["attributes"]["kind"] == "human"
    assert graph["person-alice"]["id"] == "person-alice"
    assert graph["person-alice"]["aliases"] == ["A."]
    assert graph["person-alice"]["source"] == "user"
    assert graph["person-alice"]["status"] == "confirmed"
    assert graph["person-alice"]["created_at"] == "2026-07-01T00:00:00+00:00"
    assert graph["person-alice"]["relationships"][0]["target"] == "person-deepseek"
    assert graph["person-alice"]["relationships"][0]["source"] == "user"
    assert graph["person-alice"]["relationships"][0]["status"] == "confirmed"
    assert graph["person-alice"]["relationships"][0]["evidence"] == []
    assert graph["person-alice"]["not_duplicate_of"][0]["target"] == "person-alen"
    assert graph["person-alice"]["merged_entities"][0]["entity"]["id"] == "person-ally"
    assert graph["person-alice"]["merged_entities"][0]["entity"]["type"] == "person"
    assert graph["person-deepseek"]["type"] == "actor"
    assert graph["person-deepseek"]["attributes"]["kind"] == "software_agent"
    assert graph["person-alen"]["type"] == "actor"
    assert graph["place-home"]["type"] == "place"

    check = _run_entity_cli(["--check"])
    assert check["success"] is True
    assert check["data"]["issues"] == []
    assert check["data"]["summary"] == {
        "dangling_relationships": 0,
        "duplicate_lookups": 0,
        "schema_issues": 0,
    }


def test_legacy_person_graph_loads_resolves_and_expands_before_normalize(
    isolated_data_dir: Path,
) -> None:
    """Old `type=person` graphs remain valid and searchable before migration."""
    from tools.search_journals.core import expand_query_with_entity_graph

    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-alice",
                "type": "person",
                "primary_name": "Alice",
                "aliases": ["Ally"],
                "relationships": [{"target": "person-bob", "relation": "friend_of"}],
            },
            {
                "id": "person-bob",
                "type": "person",
                "primary_name": "Bob",
                "aliases": [],
                "relationships": [],
            },
        ],
        graph_path,
    )

    graph = load_entity_graph(graph_path)
    assert resolve_entity("Ally", graph)["id"] == "person-alice"

    expanded = expand_query_with_entity_graph("Ally")

    assert "Alice" in expanded
    assert "Ally" in expanded


def test_maintain_normalize_keeps_candidate_state_out_of_runtime(
    isolated_data_dir: Path,
) -> None:
    """Candidate entities and relationships stay candidate after normalize."""
    from tools.lib.entity_runtime import load_runtime_view

    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-alice",
                "type": "person",
                "primary_name": "Alice",
                "source": "agent",
                "status": "candidate",
                "created_at": "2026-07-01T00:00:00+00:00",
                "evidence": ["Journals/2026/07/life-index_2026-07-01_001.md"],
                "reason": "Repeated mention in notes",
                "attributes": {"kind": "human"},
                "relationships": [
                    {
                        "relation": "friend_of",
                        "target": "person-bob",
                        "source": "agent",
                        "created_at": "2026-07-01T00:00:00+00:00",
                        "status": "candidate",
                        "evidence": ["Journals/2026/07/life-index_2026-07-01_001.md"],
                    }
                ],
            },
            {
                "id": "person-bob",
                "type": "person",
                "primary_name": "Bob",
                "status": "confirmed",
                "attributes": {"kind": "human"},
                "relationships": [],
            },
        ],
        graph_path,
    )

    payload = _run_entity_cli(["maintain", "--normalize", "--apply", "--backup", "--json"])

    assert payload["success"] is True
    graph = {entity["id"]: entity for entity in load_entity_graph(graph_path)}
    assert graph["person-alice"]["type"] == "actor"
    assert graph["person-alice"]["attributes"]["kind"] == "human"
    assert graph["person-alice"]["status"] == "candidate"
    assert graph["person-alice"]["source"] == "agent"
    assert graph["person-alice"]["evidence"] == ["Journals/2026/07/life-index_2026-07-01_001.md"]
    assert graph["person-alice"]["relationships"][0]["status"] == "candidate"

    view = load_runtime_view(graph_path)
    assert "Alice" not in view.by_lookup
    assert "person-bob" not in view.reverse_relationships


def test_maintain_normalize_ambiguous_kind_becomes_review_question(
    isolated_data_dir: Path,
) -> None:
    """Ambiguous old person kinds must not be silently rewritten."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-morgan",
                "type": "person",
                "primary_name": "Morgan",
                "attributes": {"kind": "vendor"},
                "relationships": [],
            }
        ],
        graph_path,
    )
    before = graph_path.read_text(encoding="utf-8")

    payload = _run_entity_cli(["maintain", "--normalize", "--preview", "--json"])

    assert graph_path.read_text(encoding="utf-8") == before
    assert payload["success"] is True
    assert payload["data"]["summary"]["change_count"] == 0
    assert payload["data"]["summary"]["review_question_count"] == 1
    assert payload["data"]["review_questions"] == [
        {
            "entity_id": "person-morgan",
            "primary_name": "Morgan",
            "reason": "person kind 'vendor' is ambiguous",
        }
    ]


def test_maintain_normalize_family_role_labels_map_to_actor_human(
    isolated_data_dir: Path,
) -> None:
    """Family role labels are evidence of a human individual, never actor/group."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-alice",
                "type": "person",
                "primary_name": "Alice",
                "attributes": {
                    "role": "family",
                    "family_role_labels": {
                        "parent_perspective": {"primary": "daughter", "aliases": ["child"]},
                        "by_observer": {
                            "person-bob": {"primary": "mother", "aliases": ["mom"]},
                        },
                    },
                },
                "relationships": [],
            },
            {
                "id": "person-bob",
                "type": "person",
                "primary_name": "Bob",
                "attributes": {"kind": "human"},
                "relationships": [],
            },
        ],
        graph_path,
    )
    before = graph_path.read_text(encoding="utf-8")

    payload = _run_entity_cli(["maintain", "--normalize", "--preview", "--json"])

    assert graph_path.read_text(encoding="utf-8") == before
    assert payload["success"] is True
    assert payload["data"]["summary"]["change_count"] == 2
    assert payload["data"]["summary"]["review_question_count"] == 0
    alice_change = next(
        change for change in payload["data"]["changes"] if change["entity_id"] == "person-alice"
    )
    assert alice_change["to"] == {"type": "actor", "kind": "human"}
    assert "family_role_labels" in alice_change["reason"]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert '"group"' not in serialized


def test_maintain_normalize_person_with_explicit_org_like_kind_needs_review(
    isolated_data_dir: Path,
) -> None:
    """A person with explicit organization-like kind is ambiguous and fail-closed."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-acme",
                "type": "person",
                "primary_name": "Acme",
                "attributes": {"kind": "organization"},
                "relationships": [],
            }
        ],
        graph_path,
    )

    payload = _run_entity_cli(["maintain", "--normalize", "--preview", "--json"])

    assert payload["success"] is True
    assert payload["data"]["summary"]["change_count"] == 0
    assert payload["data"]["summary"]["review_question_count"] == 1
    assert payload["data"]["review_questions"] == [
        {
            "entity_id": "person-acme",
            "primary_name": "Acme",
            "reason": "person kind 'organization' is ambiguous",
        }
    ]


def test_maintain_normalize_conflicting_person_signals_need_review(
    isolated_data_dir: Path,
) -> None:
    """Conflicting human and organization signals must not silently rewrite."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-morgan",
                "type": "person",
                "primary_name": "Morgan",
                "attributes": {"kind": "human", "role": "company"},
                "relationships": [],
            }
        ],
        graph_path,
    )

    payload = _run_entity_cli(["maintain", "--normalize", "--preview", "--json"])

    assert payload["success"] is True
    assert payload["data"]["summary"]["change_count"] == 0
    assert payload["data"]["summary"]["review_question_count"] == 1
    assert payload["data"]["review_questions"] == [
        {
            "entity_id": "person-morgan",
            "primary_name": "Morgan",
            "reason": "person has conflicting normalization signals",
        }
    ]


def test_maintain_normalize_invalid_plan_returns_error_without_backup_or_write(
    isolated_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apply validates the whole plan before backup/write and fail-closes."""
    from tools.entity import normalize

    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-alice",
                "type": "person",
                "primary_name": "Alice",
                "relationships": [],
            }
        ],
        graph_path,
    )
    before = graph_path.read_text(encoding="utf-8")

    def invalid_plan(*, graph_path: Path) -> dict[str, Any]:
        return {
            "workflow": "maintain.normalize",
            "normalized_entities": [
                {
                    "id": "dup",
                    "type": "actor",
                    "primary_name": "One",
                    "attributes": {"kind": "human"},
                    "relationships": [],
                },
                {
                    "id": "dup",
                    "type": "actor",
                    "primary_name": "Two",
                    "attributes": {"kind": "human"},
                    "relationships": [],
                },
            ],
            "summary": {"entity_count": 1, "change_count": 2, "review_question_count": 0},
            "changes": [],
            "review_questions": [],
        }

    monkeypatch.setattr(normalize, "build_normalize_plan", invalid_plan)

    payload = normalize.run_normalize(
        graph_path=graph_path,
        preview=False,
        apply=True,
        backup=True,
    )

    assert payload["success"] is False
    assert payload["error"]["code"] == "ENTITY_NORMALIZE_PLAN_INVALID"
    assert graph_path.read_text(encoding="utf-8") == before
    assert list(isolated_data_dir.glob("entity_graph.yaml.backup_*")) == []


def test_api_docs_record_retired_entity_primitives_and_replacements() -> None:
    """API docs must record owner-approved replacements for removed primitives."""
    api_md = Path(__file__).resolve().parents[2] / "docs" / "API.md"
    text = api_md.read_text(encoding="utf-8")

    assert "Retired top-level primitives" in text
    assert "`--seed`" in text
    assert "`entity build --from-journals --preview --json`" in text
    assert "`--merge`" in text
    assert "`entity --review --action merge_as_alias`" in text
    assert "`--delete`" in text
    assert "`entity maintain --delete --id ENTITY_ID --preview --json`" in text
