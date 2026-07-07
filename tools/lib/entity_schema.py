#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ENTITY_TYPES = {"actor", "artifact", "place", "project", "event", "concept"}
LEGACY_ENTITY_TYPES = {"person"}
ENTITY_KIND_VALUES = {
    "human",
    "software_agent",
    "organization",
    "ai_model",
    "app",
    "book",
    "document",
    "device",
}
ENTITY_NORMALIZE_PREVIEW_COMMAND = "life-index entity maintain --normalize --preview --json"
RESERVED_RELATIONSHIP_TARGETS: set[str] = set()
RELATIONSHIP_SOURCES = {"seed", "review", "user", "agent", "system"}
RELATIONSHIP_STATUSES = {"confirmed", "candidate"}
ENTITY_SOURCES = RELATIONSHIP_SOURCES
ENTITY_STATUSES = RELATIONSHIP_STATUSES

BOOST_DECAY_DEFAULTS = {
    "formula": "1 / (1 + k * (n - 1)^2)",
    "k": 0.001,
    "note": "Placeholder constant. To be calibrated via eval gate in v1.2.0 Cycle 2.",
}


def get_boost_decay_defaults() -> dict[str, Any]:
    return dict(BOOST_DECAY_DEFAULTS)


class EntityGraphValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "ENTITY_SCHEMA_INVALID",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


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


def _normalize_supporting_journal_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EntityGraphValidationError("relationship.supporting_journal_ids must be a list")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _ensure_non_empty_string(item, "relationship.supporting_journal_ids[]")
        if text not in seen:
            seen.add(text)
            normalized.append(text)
    return normalized


def _normalize_string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EntityGraphValidationError(f"{field} must be a list")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _ensure_non_empty_string(item, f"{field}[]")
        if text not in seen:
            seen.add(text)
            normalized.append(text)
    return normalized


def _normalize_relationship(relationship: Any, load_time: str) -> dict[str, Any]:
    if not isinstance(relationship, dict):
        raise EntityGraphValidationError("relationship must be an object")
    target = _ensure_non_empty_string(relationship.get("target"), "relationship.target")
    relation = _ensure_non_empty_string(relationship.get("relation"), "relationship.relation")
    normalized_relationship: dict[str, Any] = {"target": target, "relation": relation}
    if "weight" in relationship:
        weight = relationship.get("weight")
        if not isinstance(weight, (int, float)):
            raise EntityGraphValidationError("relationship.weight must be a number")
        normalized_relationship["weight"] = float(weight)
    if "supporting_journal_ids" in relationship:
        normalized_relationship["supporting_journal_ids"] = _normalize_supporting_journal_ids(
            relationship.get("supporting_journal_ids")
        )

    normalized_relationship["evidence"] = _normalize_string_list(
        relationship.get("evidence"), "relationship.evidence"
    )

    source = relationship.get("source", "system")
    if source not in RELATIONSHIP_SOURCES:
        raise EntityGraphValidationError("relationship.source must be one of the allowed sources")
    normalized_relationship["source"] = source

    created_at = relationship.get("created_at", load_time)
    if not isinstance(created_at, str):
        raise EntityGraphValidationError("relationship.created_at must be a string")
    normalized_relationship["created_at"] = created_at

    status = relationship.get("status", "confirmed")
    if status not in RELATIONSHIP_STATUSES:
        raise EntityGraphValidationError("relationship.status must be confirmed or candidate")
    normalized_relationship["status"] = status

    if "reason" in relationship:
        reason = relationship.get("reason")
        if not isinstance(reason, str):
            raise EntityGraphValidationError("relationship.reason must be a string")
        normalized_relationship["reason"] = reason

    for field in ("start", "end"):
        if field in relationship and relationship[field] is not None:
            normalized_relationship[field] = _ensure_non_empty_string(
                relationship[field], f"relationship.{field}"
            )

    return normalized_relationship


def _normalize_not_duplicate_of(value: Any, load_time: str) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EntityGraphValidationError("not_duplicate_of must be a list")

    normalized: list[dict[str, str]] = []
    seen_targets: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise EntityGraphValidationError("not_duplicate_of[] must be an object")
        target = _ensure_non_empty_string(item.get("target"), "not_duplicate_of.target")
        if target in seen_targets:
            continue
        source = item.get("source", "system")
        if source not in RELATIONSHIP_SOURCES:
            raise EntityGraphValidationError(
                "not_duplicate_of.source must be one of the allowed sources"
            )
        created_at = item.get("created_at", load_time)
        if not isinstance(created_at, str):
            raise EntityGraphValidationError("not_duplicate_of.created_at must be a string")
        normalized.append(
            {
                "target": target,
                "source": source,
                "created_at": created_at,
            }
        )
        seen_targets.add(target)
    return normalized


def _normalize_entity_core(
    raw: dict[str, Any],
    load_time: str,
    alias_owners: dict[str, str] | None = None,
    *,
    allow_legacy_entity_types: bool = False,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise EntityGraphValidationError("each entity must be an object")

    entity_id = _ensure_non_empty_string(raw.get("id"), "id")
    entity_type = _ensure_non_empty_string(raw.get("type"), "type")
    primary_name = _ensure_non_empty_string(raw.get("primary_name"), "primary_name")

    if entity_type in LEGACY_ENTITY_TYPES and not allow_legacy_entity_types:
        raise EntityGraphValidationError(
            (
                f"legacy entity type '{entity_type}' is no longer accepted; "
                f"run `{ENTITY_NORMALIZE_PREVIEW_COMMAND}` first"
            ),
            code="ENTITY_SCHEMA_LEGACY",
            details={
                "legacy_type": entity_type,
                "replacement_command": ENTITY_NORMALIZE_PREVIEW_COMMAND,
            },
        )
    if entity_type not in ENTITY_TYPES and not (
        allow_legacy_entity_types and entity_type in LEGACY_ENTITY_TYPES
    ):
        raise EntityGraphValidationError(f"invalid entity type: {entity_type}")
    attributes = raw.get("attributes", {}) or {}
    if not isinstance(attributes, dict):
        raise EntityGraphValidationError("attributes must be an object")
    self_anchor = attributes.get("self")
    if self_anchor is not None and not isinstance(self_anchor, bool):
        raise EntityGraphValidationError("attributes.self must be a boolean")
    kind = attributes.get("kind")
    if (
        kind is not None
        and kind not in ENTITY_KIND_VALUES
        and not (allow_legacy_entity_types and entity_type in LEGACY_ENTITY_TYPES)
    ):
        raise EntityGraphValidationError(f"invalid entity kind: {kind}")

    aliases = raw.get("aliases", []) or []
    if not isinstance(aliases, list):
        raise EntityGraphValidationError("aliases must be a list")
    normalized_aliases: list[str] = []
    alias_metadata: dict[str, Any] = {}
    for alias in aliases:
        name, metadata = _normalize_alias(alias, load_time)
        if alias_owners is not None:
            owner = alias_owners.get(name)
            if owner and owner != entity_id:
                raise EntityGraphValidationError(f"alias conflict: {name}")
            alias_owners[name] = entity_id
        normalized_aliases.append(name)
        alias_metadata[name] = metadata

    raw_alias_metadata = raw.get("alias_metadata", {}) or {}
    if isinstance(raw_alias_metadata, dict):
        for name, metadata in raw_alias_metadata.items():
            if name in normalized_aliases and isinstance(metadata, dict):
                alias_metadata[name].update(metadata)

    relationships = raw.get("relationships", []) or []
    if not isinstance(relationships, list):
        raise EntityGraphValidationError("relationships must be a list")

    normalized_entity = {
        "id": entity_id,
        "type": entity_type,
        "primary_name": primary_name,
        "aliases": normalized_aliases,
        "alias_metadata": alias_metadata,
        "attributes": attributes,
        "relationships": [
            _normalize_relationship(relationship, load_time) for relationship in relationships
        ],
    }

    if "source" in raw:
        source = raw.get("source")
        if source not in ENTITY_SOURCES:
            raise EntityGraphValidationError("entity.source must be one of the allowed sources")
        normalized_entity["source"] = source

    if "status" in raw:
        status = raw.get("status")
        if status not in ENTITY_STATUSES:
            raise EntityGraphValidationError("entity.status must be confirmed or candidate")
        normalized_entity["status"] = status

    if "created_at" in raw:
        created_at = raw.get("created_at")
        if not isinstance(created_at, str):
            raise EntityGraphValidationError("entity.created_at must be a string")
        normalized_entity["created_at"] = created_at

    if "evidence" in raw:
        normalized_entity["evidence"] = _normalize_string_list(
            raw.get("evidence"), "entity.evidence"
        )

    if "reason" in raw:
        reason = raw.get("reason")
        if not isinstance(reason, str):
            raise EntityGraphValidationError("entity.reason must be a string")
        normalized_entity["reason"] = reason

    not_duplicate_of = _normalize_not_duplicate_of(raw.get("not_duplicate_of"), load_time)
    if not_duplicate_of:
        normalized_entity["not_duplicate_of"] = not_duplicate_of

    return normalized_entity


def _normalize_merged_entities(
    value: Any,
    load_time: str,
    *,
    allow_legacy_entity_types: bool = False,
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EntityGraphValidationError("merged_entities must be a list")

    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise EntityGraphValidationError("merged_entities[] must be an object")
        raw_entity = item.get("entity")
        if not isinstance(raw_entity, dict):
            raise EntityGraphValidationError("merged_entities[].entity must be an object")
        entity = _normalize_entity_core(
            raw_entity,
            load_time,
            allow_legacy_entity_types=allow_legacy_entity_types,
        )
        tombstone: dict[str, Any] = {
            "id": _ensure_non_empty_string(item.get("id"), "merged_entities[].id"),
            "target_id": _ensure_non_empty_string(
                item.get("target_id"), "merged_entities[].target_id"
            ),
            "source": _ensure_non_empty_string(item.get("source"), "merged_entities[].source"),
            "merged_at": _ensure_non_empty_string(
                item.get("merged_at"), "merged_entities[].merged_at"
            ),
            "entity": entity,
            "transferred_aliases": _normalize_string_list(
                item.get("transferred_aliases"), "merged_entities[].transferred_aliases"
            ),
            "transferred_relationships": [
                _normalize_relationship(relationship, load_time)
                for relationship in item.get("transferred_relationships", []) or []
            ],
            "rewired_relationships": [],
        }
        if tombstone["source"] not in RELATIONSHIP_SOURCES:
            raise EntityGraphValidationError("merged_entities[].source is invalid")
        rewired = item.get("rewired_relationships", []) or []
        if not isinstance(rewired, list):
            raise EntityGraphValidationError(
                "merged_entities[].rewired_relationships must be a list"
            )
        for rewired_item in rewired:
            if not isinstance(rewired_item, dict):
                raise EntityGraphValidationError("rewired_relationships[] must be an object")
            tombstone["rewired_relationships"].append(
                {
                    "entity_id": _ensure_non_empty_string(
                        rewired_item.get("entity_id"), "rewired_relationships[].entity_id"
                    ),
                    "relationship": _normalize_relationship(
                        rewired_item.get("relationship"), load_time
                    ),
                }
            )
        normalized.append(tombstone)
    return normalized


def validate_entity_graph_payload(
    payload: dict[str, Any],
    load_time: str | None = None,
    *,
    allow_legacy_entity_types: bool = False,
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

        if entity_id in seen_ids:
            raise EntityGraphValidationError(f"duplicate entity id: {entity_id}")
        normalized_entity = _normalize_entity_core(
            raw,
            load_time,
            alias_owners,
            allow_legacy_entity_types=allow_legacy_entity_types,
        )
        merged_entities = _normalize_merged_entities(
            raw.get("merged_entities", []),
            load_time,
            allow_legacy_entity_types=allow_legacy_entity_types,
        )
        if merged_entities:
            normalized_entity["merged_entities"] = merged_entities
        validated.append(normalized_entity)
        seen_ids.add(entity_id)

    valid_targets = seen_ids
    for entity in validated:
        for relationship in entity["relationships"]:
            if relationship["target"] not in valid_targets:
                raise EntityGraphValidationError(
                    f"unknown relationship target: {relationship['target']}"
                )
        for distinct_record in entity.get("not_duplicate_of", []):
            if distinct_record["target"] not in valid_targets:
                raise EntityGraphValidationError(
                    f"unknown not_duplicate_of target: {distinct_record['target']}"
                )
            if distinct_record["target"] == entity["id"]:
                raise EntityGraphValidationError("not_duplicate_of target cannot be self")

    self_entities = [
        entity for entity in validated if (entity.get("attributes") or {}).get("self") is True
    ]
    if len(self_entities) > 1:
        raise EntityGraphValidationError(
            "entity graph must contain exactly one self entity when attributes.self is set",
            code="ENTITY_SCHEMA_SELF_ANCHOR",
            details={"self_entity_ids": [entity["id"] for entity in self_entities]},
        )
    if self_entities and self_entities[0].get("status", "confirmed") != "confirmed":
        raise EntityGraphValidationError(
            "self entity must be confirmed",
            code="ENTITY_SCHEMA_SELF_ANCHOR",
            details={"self_entity_id": self_entities[0]["id"]},
        )

    return validated
