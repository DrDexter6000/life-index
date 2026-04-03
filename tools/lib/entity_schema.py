#!/usr/bin/env python3

from __future__ import annotations

from typing import Any


ENTITY_TYPES = {"person", "place", "project", "event", "concept"}
RESERVED_RELATIONSHIP_TARGETS: set[str] = set()


class EntityGraphValidationError(ValueError):
    pass


def _ensure_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EntityGraphValidationError(f"{field} must be a non-empty string")
    return value.strip()


def validate_entity_graph_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
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
        for alias in aliases:
            normalized = _ensure_non_empty_string(alias, "alias")
            owner = alias_owners.get(normalized)
            if owner and owner != entity_id:
                raise EntityGraphValidationError(f"alias conflict: {normalized}")
            alias_owners[normalized] = entity_id
            normalized_aliases.append(normalized)

        relationships = raw.get("relationships", []) or []
        if not isinstance(relationships, list):
            raise EntityGraphValidationError("relationships must be a list")
        normalized_relationships: list[dict[str, str]] = []
        for relationship in relationships:
            if not isinstance(relationship, dict):
                raise EntityGraphValidationError("relationship must be an object")
            target = _ensure_non_empty_string(
                relationship.get("target"), "relationship.target"
            )
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
