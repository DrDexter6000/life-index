#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tools.lib.entity_schema import EntityGraphValidationError
from tools.lib.entity_schema import validate_entity_graph_payload


def load_entity_graph(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {"entities": []}

    return validate_entity_graph_payload(payload)


def save_entity_graph(entities: list[dict[str, Any]], path: Path) -> None:
    validated = validate_entity_graph_payload({"entities": entities})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump({"entities": validated}, f, allow_unicode=True, sort_keys=False)


def resolve_entity(query: str, graph: list[dict[str, Any]]) -> dict[str, Any] | None:
    needle = query.strip()
    for entity in graph:
        if needle in {entity["id"], entity["primary_name"], *entity.get("aliases", [])}:
            return entity
    return None


def resolve_relationship(
    source_id: str, relation: str, graph: list[dict[str, Any]]
) -> dict[str, Any] | None:
    source = resolve_entity(source_id, graph)
    if source is None:
        return None

    for relationship in source.get("relationships", []):
        if relationship.get("relation") == relation:
            return resolve_entity(relationship["target"], graph)
    return None


def check_graph_status(graph_path: Path) -> dict[str, Any]:
    """
    Check entity graph initialization status.

    Returns:
        {
            "status": "initialized" | "not_initialized" | "empty",
            "entity_count": int,
            "suggested_action": dict | None,
        }
    """
    result: dict[str, Any] = {
        "status": "not_initialized",
        "entity_count": 0,
        "suggested_action": {
            "command": "life-index entity --seed",
            "reason": "entity graph not found; search results may miss alias-based expansion",
        },
    }

    if not graph_path.exists():
        return result

    try:
        entities = load_entity_graph(graph_path)
    except EntityGraphValidationError:
        result["status"] = "not_initialized"
        result["suggested_action"] = {
            "command": "life-index entity --seed",
            "reason": (
                "entity graph is invalid or legacy; "
                "search will continue without graph expansion until it is repaired"
            ),
        }
        return result

    result["entity_count"] = len(entities)

    if len(entities) == 0:
        result["status"] = "empty"
        return result

    result["status"] = "initialized"
    result["suggested_action"] = None
    return result
