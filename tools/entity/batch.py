"""Batch entity graph apply primitive."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from tools.entity.candidate_pool import (
    name_conflicts_confirmed,
    relationship_exists,
    stable_candidate_id,
    upsert_candidate_entity,
)
from tools.lib.entity_graph import load_entity_graph, save_entity_graph
from tools.lib.entity_schema import EntityGraphValidationError, validate_entity_graph_payload


def apply_batch_file(
    *, batch_path: Path, graph_path: Path, preview: bool = False
) -> dict[str, Any]:
    try:
        payload = _load_batch(batch_path)
        batch = _normalize_batch(payload)
    except (OSError, ValueError, EntityGraphValidationError) as exc:
        return {"success": False, "data": None, "error": str(exc)}

    graph = load_entity_graph(graph_path)
    try:
        plan = _plan_batch(graph, batch)
    except (ValueError, EntityGraphValidationError) as exc:
        return {"success": False, "data": None, "error": str(exc)}
    data = {
        "preview": preview,
        "new_entities": len(plan["new_entities"]),
        "new_relationships": len(plan["new_relationships"]),
        "conflicts": len(plan["conflicts"]),
        "duplicates_skipped": len(plan["duplicates"]),
        "conflict_items": plan["conflicts"],
    }

    if preview:
        return {"success": True, "data": data, "error": None}

    changed = False
    for entity in plan["new_entities"]:
        graph.append(entity)
        changed = True

    for conflict in plan["conflicts"]:
        _entity, created, updated = upsert_candidate_entity(
            graph,
            primary_name=conflict["primary_name"],
            entity_type=conflict["type"],
            source="user",
            reason=conflict["reason"],
            evidence=[],
            requested_id=conflict["candidate_id"],
            aliases=[],
        )
        changed = changed or created or updated

    for relationship in plan["new_relationships"]:
        source = next(entity for entity in graph if entity["id"] == relationship["source"])
        source.setdefault("relationships", []).append(
            {
                "target": relationship["target"],
                "relation": relationship["relation"],
                "source": "user",
                "status": "confirmed",
                "created_at": plan["created_at"],
                "evidence": [],
            }
        )
        changed = True

    if changed:
        validate_entity_graph_payload({"entities": graph})
        save_entity_graph(graph, graph_path)

    return {"success": True, "data": data, "error": None}


def _load_batch(batch_path: Path) -> dict[str, Any]:
    if not batch_path.exists():
        raise ValueError(f"batch file not found: {batch_path}")
    text = batch_path.read_text(encoding="utf-8")
    if batch_path.suffix.lower() == ".json":
        payload = json.loads(text)
    else:
        payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError("batch file must contain an object")
    return payload


def _normalize_batch(payload: dict[str, Any]) -> dict[str, Any]:
    raw_entities = payload.get("entities", [])
    raw_relationships = payload.get("relationships", [])
    if not isinstance(raw_entities, list):
        raise ValueError("entities must be a list")
    if not isinstance(raw_relationships, list):
        raise ValueError("relationships must be a list")

    entities: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_entities):
        if not isinstance(raw, dict):
            raise ValueError(f"entities[{index}] must be an object")
        for field in ("id", "type", "primary_name"):
            value = raw.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"entities[{index}].{field} must be a non-empty string")
        entity_id = str(raw["id"]).strip()
        if entity_id in seen_ids:
            raise ValueError(f"entities[{index}].id duplicates {entity_id}")
        seen_ids.add(entity_id)
        aliases = raw.get("aliases", []) or []
        if not isinstance(aliases, list):
            raise ValueError(f"entities[{index}].aliases must be a list")
        entities.append(
            {
                "id": entity_id,
                "type": str(raw["type"]).strip(),
                "primary_name": str(raw["primary_name"]).strip(),
                "aliases": _string_list(aliases),
                "attributes": raw.get("attributes", {}) or {},
                "relationships": [],
                "source": "user",
                "status": "confirmed",
                "evidence": [],
            }
        )

    relationships: list[dict[str, str]] = []
    for index, raw in enumerate(raw_relationships):
        if not isinstance(raw, dict):
            raise ValueError(f"relationships[{index}] must be an object")
        normalized: dict[str, str] = {}
        for field in ("source", "target", "relation"):
            value = raw.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"relationships[{index}].{field} must be a non-empty string")
            normalized[field] = value.strip()
        relationships.append(normalized)

    return {"entities": entities, "relationships": relationships}


def _plan_batch(graph: list[dict[str, Any]], batch: dict[str, Any]) -> dict[str, Any]:
    from tools.entity.candidate_pool import now_iso

    created_at = now_iso()
    new_entities: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    duplicates: list[dict[str, str]] = []
    blocked_entity_ids: set[str] = set()
    existing_ids = {entity["id"] for entity in graph}

    for entity in batch["entities"]:
        if entity["id"] in existing_ids:
            duplicates.append({"kind": "entity", "id": entity["id"]})
            continue
        if name_conflicts_confirmed(
            [*graph, *new_entities],
            primary_name=entity["primary_name"],
            aliases=entity.get("aliases", []),
            entity_id=entity["id"],
        ):
            reason = f"Batch name conflict for {entity['primary_name']}; human review required."
            conflicts.append(
                {
                    "kind": "entity",
                    "id": entity["id"],
                    "primary_name": entity["primary_name"],
                    "type": entity["type"],
                    "reason": reason,
                    "candidate_id": stable_candidate_id(
                        entity_type=entity["type"],
                        primary_name=entity["primary_name"],
                        reason=reason,
                    ),
                }
            )
            blocked_entity_ids.add(entity["id"])
            continue
        stamped = dict(entity)
        stamped["created_at"] = created_at
        new_entities.append(stamped)
        existing_ids.add(entity["id"])

    final_ids = {entity["id"] for entity in graph} | {entity["id"] for entity in new_entities}
    new_relationships: list[dict[str, str]] = []
    for index, relationship in enumerate(batch["relationships"]):
        source_id = relationship["source"]
        target_id = relationship["target"]
        if source_id in blocked_entity_ids or target_id in blocked_entity_ids:
            duplicates.append({"kind": "relationship", "id": f"relationships[{index}].blocked"})
            continue
        if source_id not in final_ids:
            raise ValueError(f"relationships[{index}].source references unknown entity")
        if target_id not in final_ids:
            raise ValueError(f"relationships[{index}].target references unknown entity")
        if relationship_exists(
            graph,
            source_id=source_id,
            target_id=target_id,
            relation=relationship["relation"],
            status="confirmed",
        ):
            duplicates.append(
                {
                    "kind": "relationship",
                    "id": f"{source_id}:{relationship['relation']}:{target_id}",
                }
            )
            continue
        if any(
            item["source"] == source_id
            and item["target"] == target_id
            and item["relation"] == relationship["relation"]
            for item in new_relationships
        ):
            duplicates.append(
                {
                    "kind": "relationship",
                    "id": f"{source_id}:{relationship['relation']}:{target_id}",
                }
            )
            continue
        new_relationships.append(relationship)

    validate_entity_graph_payload({"entities": [*graph, *new_entities]})
    return {
        "created_at": created_at,
        "new_entities": new_entities,
        "new_relationships": new_relationships,
        "conflicts": conflicts,
        "duplicates": duplicates,
    }


def _string_list(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
