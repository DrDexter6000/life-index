#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ENTITY_TYPES = {"person", "place", "project", "event", "concept"}
RESERVED_RELATIONSHIP_TARGETS: set[str] = set()

BOOST_DECAY_DEFAULTS = {
    "formula": "1 / (1 + k * (n - 1)^2)",
    "k": 0.001,
    "note": "Placeholder constant. To be calibrated via eval gate in v1.2.0 Cycle 2.",
}


def get_boost_decay_defaults() -> dict[str, Any]:
    return dict(BOOST_DECAY_DEFAULTS)


class EntityGraphValidationError(ValueError):
    pass


def _ensure_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EntityGraphValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_alias(alias: Any, load_time: str) -> tuple[str, dict[str, Any]]:
    """Normalize an alias entry to (name, metadata).

    Accepts:
      - str: plain alias name; metadata defaults to
        source=system, confidence=1.0, created_at=load_time
      - dict: must have 'name'; optional 'source', 'confidence', 'created_at'
    """
    if isinstance(alias, str):
        name = _ensure_non_empty_string(alias, "alias")
        return name, {"source": "system", "confidence": 1.0, "created_at": load_time}

    if isinstance(alias, dict):
        name = _ensure_non_empty_string(alias.get("name"), "alias.name")
        confidence = alias.get("confidence", 1.0)
        if not isinstance(confidence, (int, float)):
            raise EntityGraphValidationError("alias.confidence must be a number")
        if not (0.0 <= float(confidence) <= 1.0):
            raise EntityGraphValidationError("alias.confidence must be between 0.0 and 1.0")
        source = alias.get("source", "system")
        if not isinstance(source, str):
            raise EntityGraphValidationError("alias.source must be a string")
        created_at = alias.get("created_at", load_time)
        if not isinstance(created_at, str):
            raise EntityGraphValidationError("alias.created_at must be a string")
        return name, {"source": source, "confidence": float(confidence), "created_at": created_at}

    raise EntityGraphValidationError("alias must be a string or an object")


def validate_entity_graph_payload(
    payload: dict[str, Any], load_time: str | None = None
) -> list[dict[str, Any]]:
    if load_time is None:
        load_time = datetime.now(timezone.utc).isoformat()

    entities = payload.get("entities")
    if not isinstance(entities, list):
        raise EntityGraphValidationError("entities must be a list")

    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    alias_owners: dict[str, str] = {}

    for raw in entities:
        if not isinstance(raw, dict):
            raise EntityGraphValidationError("each entity must be an object")

        entity_id = _ensure_non_empty_string(raw.get("id"), "id")
        entity_type = _ensure_non_empty_string(raw.get("type"), "type")
        primary_name = _ensure_non_empty_string(raw.get("primary_name"), "primary_name")

        if entity_id in seen_ids:
            raise EntityGraphValidationError(f"duplicate entity id: {entity_id}")
        if entity_type not in ENTITY_TYPES:
            raise EntityGraphValidationError(f"invalid entity type: {entity_type}")

        aliases = raw.get("aliases", []) or []
        if not isinstance(aliases, list):
            raise EntityGraphValidationError("aliases must be a list")
        normalized_aliases: list[str] = []
        alias_metadata: dict[str, Any] = {}
        for alias in aliases:
            name, metadata = _normalize_alias(alias, load_time)
            owner = alias_owners.get(name)
            if owner and owner != entity_id:
                raise EntityGraphValidationError(f"alias conflict: {name}")
            alias_owners[name] = entity_id
            normalized_aliases.append(name)
            alias_metadata[name] = metadata

        # Merge explicit alias_metadata from raw if present
        raw_alias_metadata = raw.get("alias_metadata", {}) or {}
        if isinstance(raw_alias_metadata, dict):
            for name, metadata in raw_alias_metadata.items():
                if name in normalized_aliases and isinstance(metadata, dict):
                    alias_metadata[name].update(metadata)

        relationships = raw.get("relationships", []) or []
        if not isinstance(relationships, list):
            raise EntityGraphValidationError("relationships must be a list")
        normalized_relationships: list[dict[str, str]] = []
        for relationship in relationships:
            if not isinstance(relationship, dict):
                raise EntityGraphValidationError("relationship must be an object")
            target = _ensure_non_empty_string(relationship.get("target"), "relationship.target")
            relation = _ensure_non_empty_string(
                relationship.get("relation"), "relationship.relation"
            )
            normalized_relationships.append({"target": target, "relation": relation})

        validated.append(
            {
                "id": entity_id,
                "type": entity_type,
                "primary_name": primary_name,
                "aliases": normalized_aliases,
                "alias_metadata": alias_metadata,
                "attributes": raw.get("attributes", {}) or {},
                "relationships": normalized_relationships,
            }
        )
        seen_ids.add(entity_id)

    valid_targets = seen_ids
    for entity in validated:
        for relationship in entity["relationships"]:
            if relationship["target"] not in valid_targets:
                raise EntityGraphValidationError(
                    f"unknown relationship target: {relationship['target']}"
                )

    return validated
