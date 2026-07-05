"""Maintain delete workflow for Entity Graph records."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from tools.lib.entity_graph import load_entity_graph
from tools.lib.entity_graph import save_entity_graph
from tools.lib.entity_schema import validate_entity_graph_payload


def run_delete(
    *,
    graph_path: Path,
    entity_id: str | None,
    preview: bool,
    apply: bool,
    backup: bool,
) -> dict[str, Any]:
    """Run the maintain delete workflow."""
    if not entity_id:
        return _error("ENTITY_MAINTAIN_DELETE_ID_REQUIRED", "--delete requires --id.")
    if preview == apply:
        return _error(
            "ENTITY_MAINTAIN_DELETE_MODE_REQUIRED",
            "Specify exactly one of --preview or --apply.",
        )
    if apply and not backup:
        return _error(
            "ENTITY_MAINTAIN_DELETE_BACKUP_REQUIRED",
            "entity maintain --delete --apply requires --backup.",
        )

    plan = _build_delete_plan(graph_path=graph_path, entity_id=entity_id)
    if plan["error"] is not None:
        return cast(dict[str, Any], plan["error"])
    if preview:
        return _success(plan=plan, preview=True, applied=False, backup_path=None)

    backup_path = _create_backup(graph_path)
    _write_graph_atomically(graph_path=graph_path, entities=plan["remaining_entities"])
    return _success(plan=plan, preview=False, applied=True, backup_path=backup_path)


def _build_delete_plan(*, graph_path: Path, entity_id: str) -> dict[str, Any]:
    entities = load_entity_graph(graph_path)
    source = next((entity for entity in entities if entity["id"] == entity_id), None)
    if source is None:
        return {
            "error": _error(
                "ENTITY_MAINTAIN_DELETE_NOT_FOUND",
                f"Entity not found: {entity_id}",
            )
        }

    refs: list[dict[str, str]] = []
    remaining_entities: list[dict[str, Any]] = []
    for entity in entities:
        if entity["id"] == entity_id:
            continue
        cleaned_relationships = []
        for relationship in entity.get("relationships", []):
            if relationship.get("target") == entity_id:
                refs.append(
                    {
                        "entity_id": entity["id"],
                        "relation": relationship.get("relation", ""),
                    }
                )
                continue
            cleaned_relationships.append(relationship)
        if len(cleaned_relationships) != len(entity.get("relationships", [])):
            entity = dict(entity)
            entity["relationships"] = cleaned_relationships
        remaining_entities.append(entity)

    validate_entity_graph_payload({"entities": remaining_entities})
    return {
        "error": None,
        "deleted_id": entity_id,
        "deleted_name": source.get("primary_name", ""),
        "cleaned_refs": refs,
        "remaining_entities": remaining_entities,
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
            "workflow": "maintain.delete",
            "preview": preview,
            "applied": applied,
            "backup_path": str(backup_path) if backup_path is not None else None,
            "deleted_id": plan["deleted_id"],
            "deleted_name": plan["deleted_name"],
            "cleaned_refs": plan["cleaned_refs"],
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
