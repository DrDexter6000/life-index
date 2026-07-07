"""Preview-first user-confirmed entity relationship writes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from tools.lib.entity_graph import load_entity_graph, save_entity_graph
from tools.lib.entity_relations import CANONICAL_RELATIONS, normalize_relation
from tools.lib.entity_schema import validate_entity_graph_payload

WORKFLOW = "maintain.add_relationship"
REVIEW_COMMAND = "life-index entity --review --json"


def run_add_relationship(
    *,
    graph_path: Path,
    source_id: str | None,
    target_id: str | None,
    relation: str | None,
    preview: bool,
    apply: bool,
) -> dict[str, Any]:
    """Preview or apply a user-confirmed relationship edge."""
    if not source_id:
        return _error(
            "ENTITY_RELATIONSHIP_SOURCE_REQUIRED",
            "--add-relationship requires --id SOURCE_ID.",
        )
    if not target_id:
        return _error(
            "ENTITY_RELATIONSHIP_TARGET_REQUIRED",
            "--add-relationship requires --target-id TARGET_ID.",
        )
    if not relation:
        return _error(
            "ENTITY_RELATIONSHIP_RELATION_REQUIRED",
            "--add-relationship requires --relation RELATION.",
        )
    if preview == apply:
        return _error(
            "ENTITY_RELATIONSHIP_MODE_REQUIRED",
            "Specify exactly one of --preview or --apply.",
        )

    canonical_relation = normalize_relation(relation.strip())
    if canonical_relation not in CANONICAL_RELATIONS:
        return _error(
            "ENTITY_RELATIONSHIP_INVALID_RELATION",
            f"Unknown relationship relation: {relation}",
            data={
                "relation": relation,
                "allowed_relations": sorted(CANONICAL_RELATIONS),
            },
        )

    graph = load_entity_graph(graph_path)
    plan = _build_plan(
        graph=graph,
        source_id=source_id,
        target_id=target_id,
        relation=canonical_relation,
        input_relation=relation,
    )
    if plan.get("error") is not None:
        return cast(dict[str, Any], plan["error"])

    if preview:
        return _success(plan=plan, preview=True, applied=False)

    if plan["operation"] == "add":
        plan["source_entity"].setdefault("relationships", []).append(
            _new_relationship(target_id=target_id, relation=canonical_relation)
        )
    elif plan["operation"] == "promote_candidate":
        existing = plan["existing_relationship"]
        existing["relation"] = canonical_relation
        existing["source"] = "user"
        existing["status"] = "confirmed"
        existing["created_at"] = _now_iso()
        existing["evidence"] = _dedupe_strings(existing.get("evidence"))

    if plan["operation"] in {"add", "promote_candidate"}:
        validate_entity_graph_payload({"entities": graph})
        save_entity_graph(graph, graph_path)

    return _success(plan=plan, preview=False, applied=True)


def _build_plan(
    *,
    graph: list[dict[str, Any]],
    source_id: str,
    target_id: str,
    relation: str,
    input_relation: str,
) -> dict[str, Any]:
    source_entity = _find_entity(graph, source_id)
    if source_entity is None:
        return {
            "error": _error(
                "ENTITY_RELATIONSHIP_SOURCE_NOT_FOUND",
                f"Source entity not found: {source_id}",
                data={"source_id": source_id},
            )
        }
    target_entity = _find_entity(graph, target_id)
    if target_entity is None:
        return {
            "error": _error(
                "ENTITY_RELATIONSHIP_TARGET_NOT_FOUND",
                f"Target entity not found: {target_id}",
                data={"target_id": target_id},
            )
        }

    for role, entity in (("source", source_entity), ("target", target_entity)):
        status = entity.get("status", "confirmed")
        if status != "confirmed":
            return {
                "error": _error(
                    "ENTITY_RELATIONSHIP_ENTITY_NOT_CONFIRMED",
                    (
                        f"{role} entity must be confirmed before writing a "
                        "confirmed relationship edge"
                    ),
                    data={
                        f"{role}_id": entity["id"],
                        "status": status,
                    },
                    suggested_command=REVIEW_COMMAND,
                )
            }

    existing = _find_relationship(
        source_entity.get("relationships", []),
        target_id=target_id,
        relation=relation,
    )
    operation = "add"
    changed = True
    if existing is not None:
        if existing.get("status", "confirmed") == "candidate":
            operation = "promote_candidate"
        else:
            operation = "already_exists"
            changed = False

    return {
        "error": None,
        "source_id": source_id,
        "source_name": source_entity.get("primary_name", ""),
        "target_id": target_id,
        "target_name": target_entity.get("primary_name", ""),
        "relation": relation,
        "input_relation": input_relation,
        "operation": operation,
        "changed": changed,
        "source_entity": source_entity,
        "existing_relationship": existing,
    }


def _find_entity(graph: list[dict[str, Any]], entity_id: str) -> dict[str, Any] | None:
    return next((entity for entity in graph if entity["id"] == entity_id), None)


def _find_relationship(
    relationships: list[dict[str, Any]],
    *,
    target_id: str,
    relation: str,
) -> dict[str, Any] | None:
    for relationship in relationships:
        existing_relation = normalize_relation(str(relationship.get("relation", "")))
        if relationship.get("target") == target_id and existing_relation == relation:
            return relationship
    return None


def _new_relationship(*, target_id: str, relation: str) -> dict[str, Any]:
    return {
        "target": target_id,
        "relation": relation,
        "source": "user",
        "status": "confirmed",
        "created_at": _now_iso(),
        "evidence": [],
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _success(*, plan: dict[str, Any], preview: bool, applied: bool) -> dict[str, Any]:
    return {
        "success": True,
        "data": {
            "workflow": WORKFLOW,
            "preview": preview,
            "applied": applied,
            "source_id": plan["source_id"],
            "source_name": plan["source_name"],
            "target_id": plan["target_id"],
            "target_name": plan["target_name"],
            "relation": plan["relation"],
            "input_relation": plan["input_relation"],
            "operation": plan["operation"],
            "changed": plan["changed"],
        },
        "error": None,
    }


def _error(
    code: str,
    message: str,
    *,
    data: dict[str, Any] | None = None,
    suggested_command: str | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if suggested_command:
        error["suggested_command"] = suggested_command
    return {
        "success": False,
        "data": data,
        "error": error,
    }
