"""Deterministic entity profile assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph
from tools.lib.entity_schema import EntityGraphValidationError
from tools.lib.search_index import search_fts

MENTION_LIMIT = 20
MENTION_SCAN_LIMIT = 200


def _names_for_entity(entity: dict[str, Any]) -> list[str]:
    names = [entity["primary_name"], *entity.get("aliases", [])]
    deduped: list[str] = []
    for name in names:
        name_str = str(name).strip()
        if name_str and name_str not in deduped:
            deduped.append(name_str)
    return deduped


def _candidate_summary(entity: dict[str, Any]) -> dict[str, str]:
    return {
        "entity_id": entity["id"],
        "primary_name": entity["primary_name"],
        "status": entity.get("status", "confirmed"),
    }


def _find_entity_by_id(entities: list[dict[str, Any]], entity_id: str) -> dict[str, Any] | None:
    return next((entity for entity in entities if entity["id"] == entity_id), None)


def _find_entities_by_name(entities: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    needle = name.strip().lower()
    matches: list[dict[str, Any]] = []
    for entity in entities:
        names = [entity["primary_name"], *entity.get("aliases", [])]
        if any(str(candidate).strip().lower() == needle for candidate in names):
            matches.append(entity)
    return matches


def _confirmed_relationships(
    entity: dict[str, Any],
    entities_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    for relationship in entity.get("relationships", []) or []:
        if relationship.get("status", "confirmed") != "confirmed":
            continue
        target_id = relationship.get("target")
        target = entities_by_id.get(str(target_id))
        if target is None or target.get("status", "confirmed") != "confirmed":
            continue
        item: dict[str, Any] = {
            "target": target["id"],
            "target_name": target["primary_name"],
            "relation": relationship.get("relation"),
            "source": relationship.get("source", "system"),
            "created_at": relationship.get("created_at"),
            "status": relationship.get("status", "confirmed"),
            "evidence": list(relationship.get("evidence", []) or []),
        }
        for optional_key in ("start", "end"):
            if optional_key in relationship:
                item[optional_key] = relationship[optional_key]
        relationships.append(item)
    return relationships


def _dedupe_evidence(relationships: list[dict[str, Any]]) -> list[str]:
    evidence: list[str] = []
    for relationship in relationships:
        for rel_path in relationship.get("evidence", []) or []:
            rel_path_str = str(rel_path)
            if rel_path_str and rel_path_str not in evidence:
                evidence.append(rel_path_str)
    return evidence


def _mentions_for_terms(terms: list[str]) -> list[dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}
    for term in terms:
        for item in search_fts(term, limit=MENTION_SCAN_LIMIT, min_relevance=0):
            rel_path = str(item.get("rel_path") or item.get("path") or "")
            if not rel_path or rel_path in by_path:
                continue
            by_path[rel_path] = {
                "rel_path": rel_path,
                "date": item.get("date") or "",
                "title": item.get("title") or "",
            }
    mentions = list(by_path.values())
    mentions.sort(
        key=lambda item: (str(item.get("date") or ""), str(item["rel_path"])), reverse=True
    )
    return mentions[:MENTION_LIMIT]


def _stats(
    *,
    mentions: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    dates = [str(mention.get("date") or "") for mention in mentions if mention.get("date")]
    return {
        "first_mention": min(dates) if dates else None,
        "latest_mention": max(dates) if dates else None,
        "mention_count": len(mentions),
        "relationship_count": len(relationships),
    }


def _schema_error_payload(exc: EntityGraphValidationError) -> dict[str, Any]:
    return {
        "success": False,
        "data": {
            "details": dict(exc.details),
            "suggested_command": exc.details.get(
                "replacement_command",
                "life-index entity --check",
            ),
        },
        "error": {
            "code": exc.code,
            "message": str(exc),
        },
    }


def _profile_payload(entity: dict[str, Any], entities: list[dict[str, Any]]) -> dict[str, Any]:
    confirmed_entities_by_id = {
        item["id"]: item for item in entities if item.get("status", "confirmed") == "confirmed"
    }
    relationships = _confirmed_relationships(entity, confirmed_entities_by_id)
    mentions = _mentions_for_terms(_names_for_entity(entity))
    return {
        "identity": {
            "entity_id": entity["id"],
            "primary_name": entity["primary_name"],
            "aliases": list(entity.get("aliases", []) or []),
            "type": entity["type"],
            "kind": (entity.get("attributes") or {}).get("kind"),
            "status": entity.get("status", "confirmed"),
        },
        "relationships": relationships,
        "mentions": mentions,
        "evidence": _dedupe_evidence(relationships),
        "stats": _stats(mentions=mentions, relationships=relationships),
    }


def build_entity_profile(
    *,
    graph_path: Path,
    entity_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Assemble a confirmed entity profile from graph + FTS index data."""

    if bool(entity_id) == bool(name):
        return {
            "success": False,
            "data": {"required": "exactly one of --id or --name"},
            "error": {
                "code": "ENTITY_PROFILE_SELECTOR_REQUIRED",
                "message": "entity profile requires exactly one of --id or --name",
            },
        }

    try:
        entities = load_entity_graph(graph_path)
    except EntityGraphValidationError as exc:
        return _schema_error_payload(exc)

    entity: dict[str, Any] | None = None
    if entity_id:
        entity = _find_entity_by_id(entities, entity_id)
        if entity is None:
            return {
                "success": False,
                "data": {"entity_id": entity_id},
                "error": {
                    "code": "ENTITY_PROFILE_NOT_FOUND",
                    "message": "entity not found",
                },
            }
    else:
        assert name is not None
        matches = _find_entities_by_name(entities, name)
        if len(matches) > 1:
            return {
                "success": False,
                "data": {
                    "query": name,
                    "candidates": [_candidate_summary(match) for match in matches],
                },
                "error": {
                    "code": "ENTITY_PROFILE_AMBIGUOUS_NAME",
                    "message": "--name matched multiple entities; rerun with --id",
                },
            }
        if not matches:
            return {
                "success": False,
                "data": {"query": name},
                "error": {
                    "code": "ENTITY_PROFILE_NOT_FOUND",
                    "message": "entity not found",
                },
            }
        entity = matches[0]

    if entity.get("status", "confirmed") != "confirmed":
        return {
            "success": False,
            "data": {
                "entity_id": entity["id"],
                "status": entity.get("status", "candidate"),
                "suggested_command": "life-index entity --review",
            },
            "error": {
                "code": "ENTITY_PROFILE_CANDIDATE",
                "message": "candidate entities do not have confirmed profiles",
            },
        }

    return {
        "success": True,
        "data": _profile_payload(entity, entities),
        "error": None,
    }
