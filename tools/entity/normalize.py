"""Entity Graph normalization planner and applier."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph
from tools.lib.entity_graph import save_entity_graph
from tools.lib.entity_schema import EntityGraphValidationError
from tools.lib.entity_schema import validate_entity_graph_payload

_AI_ASSISTANT_SIGNALS = {"ai", "ai_assistant", "software_agent"}
_ORGANIZATION_SIGNALS = {"organization", "company", "institution", "school"}
_ARTIFACT_KIND_BY_SIGNAL = {
    "ai_model": "ai_model",
    "model": "ai_model",
    "app": "app",
    "application": "app",
    "book": "book",
    "document": "document",
    "doc": "document",
    "device": "device",
}


def run_normalize(
    *,
    graph_path: Path,
    preview: bool,
    apply: bool,
    backup: bool,
) -> dict[str, Any]:
    """Run the maintain normalization workflow."""
    if preview == apply:
        return _error(
            "ENTITY_NORMALIZE_MODE_REQUIRED",
            "Specify exactly one of --preview or --apply.",
        )
    if apply and not backup:
        return _error(
            "ENTITY_NORMALIZE_BACKUP_REQUIRED",
            "entity maintain --normalize --apply requires --backup.",
        )

    plan = build_normalize_plan(graph_path=graph_path)
    if preview:
        return _success(plan=plan, preview=True, applied=False, backup_path=None)
    plan_error = _validate_plan(plan)
    if plan_error is not None:
        return plan_error

    backup_path = _create_backup(graph_path)
    _write_graph_atomically(graph_path=graph_path, entities=plan["normalized_entities"])
    return _success(plan=plan, preview=False, applied=True, backup_path=backup_path)


def build_normalize_plan(*, graph_path: Path) -> dict[str, Any]:
    """Build a deterministic type-normalization plan without writing."""
    entities = load_entity_graph(graph_path, allow_legacy_entity_types=True)
    normalized_entities = deepcopy(entities)
    changes: list[dict[str, Any]] = []
    review_questions: list[dict[str, Any]] = []

    for entity in normalized_entities:
        _normalize_entity_in_place(
            entity,
            changes=changes,
            review_questions=review_questions,
            record_change=True,
        )
        for tombstone in entity.get("merged_entities", []) or []:
            tombstone_entity = tombstone.get("entity")
            if isinstance(tombstone_entity, dict):
                _normalize_entity_in_place(
                    tombstone_entity,
                    changes=changes,
                    review_questions=review_questions,
                    record_change=False,
                )

    validate_entity_graph_payload(
        {"entities": normalized_entities},
        allow_legacy_entity_types=bool(review_questions),
    )
    return {
        "workflow": "maintain.normalize",
        "normalized_entities": normalized_entities,
        "summary": {
            "entity_count": len(entities),
            "change_count": len(changes),
            "review_question_count": len(review_questions),
        },
        "changes": changes,
        "review_questions": review_questions,
    }


def _normalize_entity_in_place(
    entity: dict[str, Any],
    *,
    changes: list[dict[str, Any]],
    review_questions: list[dict[str, Any]],
    record_change: bool,
) -> None:
    decision = _target_type_and_kind(entity)
    if decision["needs_review"]:
        review_questions.append(
            {
                "entity_id": entity["id"],
                "primary_name": entity.get("primary_name", ""),
                "reason": decision["reason"],
            }
        )
        return

    target_type = decision["type"]
    target_kind = decision["kind"]
    attributes = entity.setdefault("attributes", {})
    current_type = entity.get("type")
    current_kind = attributes.get("kind")

    if current_type == target_type and current_kind == target_kind:
        return

    if record_change:
        changes.append(
            {
                "entity_id": entity["id"],
                "primary_name": entity.get("primary_name", ""),
                "from": {"type": current_type, "kind": current_kind},
                "to": {"type": target_type, "kind": target_kind},
                "reason": decision["reason"],
            }
        )
    entity["type"] = target_type
    if target_kind is None:
        attributes.pop("kind", None)
    else:
        attributes["kind"] = target_kind


def _target_type_and_kind(entity: dict[str, Any]) -> dict[str, Any]:
    entity_type = entity.get("type")
    attributes = entity.get("attributes", {}) or {}
    kind = _lower(attributes.get("kind"))

    if entity_type != "person":
        return {
            "type": entity_type,
            "kind": attributes.get("kind"),
            "reason": "type already follows the current schema",
            "needs_review": False,
        }

    subtype = _lower(attributes.get("subtype"))
    role = _lower(attributes.get("role"))
    category = _lower(attributes.get("category"))
    signals = {kind, subtype, role, category}
    signals.discard("")

    artifact_signals = signals & set(_ARTIFACT_KIND_BY_SIGNAL)
    ai_signals = signals & _AI_ASSISTANT_SIGNALS
    organization_signals = signals & _ORGANIZATION_SIGNALS
    human_signal = kind == "human" or bool(attributes.get("family_role_labels"))
    target_families = sum(
        bool(signal_set)
        for signal_set in (artifact_signals, ai_signals, organization_signals, human_signal)
    )
    if target_families > 1:
        return {
            "type": entity_type,
            "kind": attributes.get("kind"),
            "reason": "person has conflicting normalization signals",
            "needs_review": True,
        }

    if artifact_signals:
        signal = sorted(artifact_signals)[0]
        return {
            "type": "artifact",
            "kind": _ARTIFACT_KIND_BY_SIGNAL[signal],
            "reason": f"{signal} signals map to artifact/{_ARTIFACT_KIND_BY_SIGNAL[signal]}",
            "needs_review": False,
        }

    if ai_signals:
        return {
            "type": "actor",
            "kind": "software_agent",
            "reason": "AI assistant signals map to actor/software_agent",
            "needs_review": False,
        }

    if kind in _ORGANIZATION_SIGNALS:
        return {
            "type": entity_type,
            "kind": attributes.get("kind"),
            "reason": f"person kind '{attributes.get('kind')}' is ambiguous",
            "needs_review": True,
        }

    if organization_signals:
        return {
            "type": "actor",
            "kind": "organization",
            "reason": "organization signals map to actor/organization",
            "needs_review": False,
        }

    if attributes.get("family_role_labels"):
        return {
            "type": "actor",
            "kind": "human",
            "reason": "family_role_labels identify a human role-bearing individual",
            "needs_review": False,
        }

    if kind and kind != "human":
        return {
            "type": entity_type,
            "kind": attributes.get("kind"),
            "reason": f"person kind '{attributes.get('kind')}' is ambiguous",
            "needs_review": True,
        }

    return {
        "type": "actor",
        "kind": "human",
        "reason": "person entity maps to actor/human",
        "needs_review": False,
    }


def _create_backup(graph_path: Path) -> Path:
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = graph_path.with_name(f"{graph_path.name}.backup_{timestamp}")
    index = 1
    while backup_path.exists():
        backup_path = graph_path.with_name(f"{graph_path.name}.backup_{timestamp}_{index}")
        index += 1
    backup_path.write_bytes(graph_path.read_bytes() if graph_path.exists() else b"entities: []\n")
    return backup_path


def _write_graph_atomically(*, graph_path: Path, entities: list[dict[str, Any]]) -> None:
    tmp_path = graph_path.with_name(f"{graph_path.name}.tmp")
    save_entity_graph(entities, tmp_path)
    tmp_path.replace(graph_path)


def _validate_plan(plan: dict[str, Any]) -> dict[str, Any] | None:
    try:
        validate_entity_graph_payload({"entities": plan["normalized_entities"]})
    except (EntityGraphValidationError, KeyError, TypeError) as exc:
        return _error("ENTITY_NORMALIZE_PLAN_INVALID", str(exc))
    return None


def _success(
    *,
    plan: dict[str, Any],
    preview: bool,
    applied: bool,
    backup_path: Path | None,
) -> dict[str, Any]:
    return {
        "success": True,
        "data": {
            "workflow": plan["workflow"],
            "preview": preview,
            "applied": applied,
            "summary": plan["summary"],
            "changes": plan["changes"],
            "review_questions": plan["review_questions"],
            "backup_path": str(backup_path) if backup_path is not None else None,
        },
        "error": None,
    }


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _lower(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""
