"""Agent proposal primitive for entity graph candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.entity.candidate_pool import (
    find_entity_by_name,
    relationship_exists,
    upsert_candidate_entity,
    upsert_candidate_relationship,
)
from tools.lib.entity_graph import load_entity_graph, save_entity_graph


def apply_proposal(*, payload: dict[str, Any], graph_path: Path) -> dict[str, Any]:
    """Persist a host-agent hypothesis as a candidate, never as confirmed graph state."""
    kind = payload.get("kind")
    if kind == "entity":
        return _propose_entity(payload=payload, graph_path=graph_path)
    if kind == "relationship":
        return _propose_relationship(payload=payload, graph_path=graph_path)
    return {
        "success": False,
        "data": None,
        "error": "--propose.kind must be entity or relationship",
    }


def _propose_entity(*, payload: dict[str, Any], graph_path: Path) -> dict[str, Any]:
    primary_name = _required_string(payload, "primary_name")
    entity_type = _required_string(payload, "entity_type", fallback_key="type")
    reason = _required_string(payload, "reason")
    if not primary_name or not entity_type or not reason:
        return {
            "success": False,
            "data": None,
            "error": "entity proposal requires primary_name, entity_type/type, and reason",
        }

    graph = load_entity_graph(graph_path)
    confirmed = find_entity_by_name(graph, primary_name, status="confirmed")
    if confirmed is not None:
        return {
            "success": True,
            "data": {
                "kind": "entity",
                "id": confirmed["id"],
                "created": False,
                "changed": False,
                "status": "already_confirmed",
            },
            "error": None,
        }
    entity, created, changed = upsert_candidate_entity(
        graph,
        primary_name=primary_name,
        entity_type=entity_type,
        source="agent",
        reason=reason,
        evidence=_string_list(payload.get("evidence")),
        requested_id=str(payload["id"]).strip() if payload.get("id") else None,
        aliases=_string_list(payload.get("aliases")),
        attributes=(
            payload.get("attributes") if isinstance(payload.get("attributes"), dict) else None
        ),
    )
    if created or changed:
        save_entity_graph(graph, graph_path)
    return {
        "success": True,
        "data": {
            "kind": "entity",
            "id": entity["id"],
            "created": created,
            "changed": changed,
            "status": "candidate",
        },
        "error": None,
    }


def _propose_relationship(*, payload: dict[str, Any], graph_path: Path) -> dict[str, Any]:
    source_id = _required_string(payload, "source_id")
    target_id = _required_string(payload, "target_id")
    relation = _required_string(payload, "relation")
    reason = _required_string(payload, "reason")
    if not source_id or not target_id or not relation or not reason:
        return {
            "success": False,
            "data": None,
            "error": ("relationship proposal requires source_id, target_id, relation, and reason"),
        }

    graph = load_entity_graph(graph_path)
    if relationship_exists(
        graph,
        source_id=source_id,
        target_id=target_id,
        relation=relation,
        status="confirmed",
    ):
        return {
            "success": True,
            "data": {
                "kind": "relationship",
                "source_id": source_id,
                "target_id": target_id,
                "relation": relation,
                "created": False,
                "changed": False,
                "status": "already_confirmed",
            },
            "error": None,
        }

    relationship, changed = upsert_candidate_relationship(
        graph,
        source_id=source_id,
        target_id=target_id,
        relation=relation,
        source="agent",
        reason=reason,
        evidence=_string_list(payload.get("evidence")),
    )
    if relationship is None:
        return {
            "success": False,
            "data": None,
            "error": "source_id and target_id must reference existing entities",
        }
    if changed:
        save_entity_graph(graph, graph_path)
    return {
        "success": True,
        "data": {
            "kind": "relationship",
            "source_id": source_id,
            "target_id": target_id,
            "relation": relation,
            "changed": changed,
            "status": "candidate",
        },
        "error": None,
    }


def _required_string(
    payload: dict[str, Any],
    key: str,
    *,
    fallback_key: str | None = None,
) -> str:
    value = payload.get(key)
    if value is None and fallback_key is not None:
        value = payload.get(fallback_key)
    if not isinstance(value, str):
        return ""
    return value.strip()


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
