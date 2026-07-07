#!/usr/bin/env python3
"""
Entity Review Hub — Round 7 Phase 2 Task 7.

Provides the review queue builder, preview generator, and action applicator
for entity graph review workflow.

CLI entry: `life-index entity review`
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph, save_entity_graph
from tools.lib.paths import get_user_data_dir

# Deprecated alias — kept for monkeypatch compatibility (Round 13 lesson)
USER_DATA_DIR = get_user_data_dir()

try:
    from tools.lib.logger import get_logger

    logger = get_logger("entity_review")
except ImportError:
    import logging

    logger = logging.getLogger("entity_review")


def _graph_path() -> Path:
    return get_user_data_dir() / "entity_graph.yaml"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe_strings(values: list[str] | None) -> list[str]:
    if not values:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _stamp_relationship(
    relationship: dict[str, Any],
    *,
    source: str,
    created_at: str,
    status: str = "confirmed",
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    stamped = dict(relationship)
    stamped["source"] = source
    stamped["created_at"] = created_at
    stamped["status"] = status
    stamped["evidence"] = _dedupe_strings(
        evidence if evidence is not None else stamped.get("evidence")
    )
    return stamped


def _relationship_key(relationship: dict[str, Any]) -> tuple[str, str]:
    return (str(relationship.get("target", "")), str(relationship.get("relation", "")))


def _find_entity(graph: list[dict[str, Any]], entity_id: str) -> dict[str, Any] | None:
    return next((entity for entity in graph if entity["id"] == entity_id), None)


def _distinct_record(target_id: str, *, source: str, created_at: str) -> dict[str, str]:
    return {"target": target_id, "source": source, "created_at": created_at}


def _upsert_distinct_record(
    entity: dict[str, Any], target_id: str, *, source: str, created_at: str
) -> None:
    records = [
        record
        for record in entity.get("not_duplicate_of", []) or []
        if record.get("target") != target_id
    ]
    records.append(_distinct_record(target_id, source=source, created_at=created_at))
    entity["not_duplicate_of"] = records


def _remove_distinct_record(entity: dict[str, Any], target_id: str) -> bool:
    records = entity.get("not_duplicate_of", []) or []
    remaining = [record for record in records if record.get("target") != target_id]
    if remaining:
        entity["not_duplicate_of"] = remaining
    else:
        entity.pop("not_duplicate_of", None)
    return len(remaining) != len(records)


def _remove_aliases(entity: dict[str, Any], aliases: list[str]) -> None:
    to_remove = set(aliases)
    entity["aliases"] = [alias for alias in entity.get("aliases", []) if alias not in to_remove]
    alias_metadata = entity.get("alias_metadata")
    if isinstance(alias_metadata, dict):
        for alias in to_remove:
            alias_metadata.pop(alias, None)


def build_review_queue(
    graph_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Build a risk-prioritized review queue from audit issues.

    Aggregates issues from entity audit and organizes them by risk level:
    - high: duplicates, conflicts, alias collisions
    - medium: relationship candidates
    - low: new entity candidates

    Args:
        graph_path: Optional override for entity graph path (testing).

    Returns:
        Sorted list of review items, each with:
            item_id, risk_level, category, description, action_choices, entity_ids
    """
    graph_path = graph_path or _graph_path()
    graph = load_entity_graph(graph_path)
    entity_names_by_id = {entity["id"]: entity.get("primary_name", "") for entity in graph}

    if not graph:
        return []

    # Import audit lazily to avoid circular imports
    from tools.entity.audit import audit_entity_graph

    journals_dir = graph_path.parent / "Journals"
    report = audit_entity_graph(
        graph_path,
        journals_dir=journals_dir if journals_dir.exists() else None,
    )
    issues = report.get("issues", [])

    queue: list[dict[str, Any]] = []
    item_counter = 0

    action_map = {
        "possible_duplicate": ["merge_as_alias", "keep_separate", "skip"],
        "incomplete_relationship": ["add_relationship", "skip"],
        "candidate_entity": ["confirm_candidate", "reject_candidate", "skip"],
        "candidate_relationship": ["confirm_candidate", "reject_candidate", "skip"],
    }

    for issue in issues:
        item_counter += 1
        issue_type = issue.get("type", "unknown")
        severity = issue.get("severity", "low")

        # Use severity directly for risk level, mapping to our 3-tier system
        risk_level = severity if severity in ("high", "medium", "low") else "medium"

        entity_ids = issue.get("entity_ids")
        if not isinstance(entity_ids, list):
            entity_ids = (
                issue.get("entities", [])
                if isinstance(issue.get("entities"), list)
                else [issue.get("entity_id", "")]
            )
        evidence = issue.get("evidence_paths", [])
        if not isinstance(evidence, list):
            evidence = []
        why = issue.get("why") or issue.get("message") or issue.get("evidence", "")
        entity_refs = issue.get("entity_refs")
        if not isinstance(entity_refs, list):
            entity_refs = [
                {
                    "entity_id": str(entity_id),
                    "primary_name": entity_names_by_id.get(str(entity_id), ""),
                }
                for entity_id in entity_ids
                if entity_id
            ]

        queue.append(
            {
                "item_id": f"review-{item_counter}",
                "risk_level": risk_level,
                "category": issue_type,
                "description": issue.get("evidence") or issue.get("message", ""),
                "action_choices": action_map.get(issue_type, ["skip"]),
                "entity_ids": entity_ids,
                "entities": entity_refs,
                "why": str(why),
                "evidence": evidence,
                "suggested_action": issue.get("suggested_action", ""),
                "primary_name": issue.get("primary_name", ""),
                "source": issue.get("source", ""),
                "status": issue.get("status", ""),
                "relation": issue.get("relation", ""),
            }
        )

    # Sort by risk: high → medium → low
    risk_order = {"high": 0, "medium": 1, "low": 2}
    queue.sort(key=lambda item: risk_order.get(item["risk_level"], 99))

    return queue


def generate_preview(
    *,
    item_id: str,
    action: str,
    source_id: str | None = None,
    target_id: str | None = None,
    relation: str | None = None,
    graph_path: Path | None = None,
) -> dict[str, Any]:
    """Generate a preview of what an action will do before committing.

    Args:
        item_id: The review item being actioned.
        action: The action to preview.
        source_id: Source entity id (for merge).
        target_id: Target entity id (for merge).
        relation: Relationship label for add_relationship preview.
        graph_path: Optional override for entity graph path (testing).

    Returns:
        Preview dict describing the changes.
    """
    graph_path = graph_path or _graph_path()
    preview: dict[str, Any] = {
        "item_id": item_id,
        "action": action,
        "changes": [],
    }

    if action == "merge_as_alias" and source_id and target_id:
        graph = load_entity_graph(graph_path)
        source = next((e for e in graph if e["id"] == source_id), None)
        target = next((e for e in graph if e["id"] == target_id), None)

        if source and target:
            preview["changes"] = [
                {
                    "type": "merge",
                    "source": {
                        "id": source["id"],
                        "primary_name": source["primary_name"],
                        "aliases": source.get("aliases", []),
                    },
                    "target": {
                        "id": target["id"],
                        "primary_name": target["primary_name"],
                    },
                    "result": {
                        "id": target["id"],
                        "new_aliases": [
                            a
                            for a in [
                                source["primary_name"],
                                *source.get("aliases", []),
                            ]
                            if a not in target.get("aliases", []) and a != target["primary_name"]
                        ],
                    },
                }
            ]

    elif action == "keep_separate" and source_id and target_id:
        preview["changes"] = [
            {
                "type": "mark_distinct",
                "source_id": source_id,
                "target_id": target_id,
                "result": {"source": "user"},
            }
        ]

    elif action == "undo_keep_separate" and source_id and target_id:
        preview["changes"] = [
            {
                "type": "remove_distinct_mark",
                "source_id": source_id,
                "target_id": target_id,
            }
        ]

    elif action == "keep_separate":
        preview["changes"] = [{"type": "mark_distinct"}]

    elif action == "add_relationship" and source_id and target_id and relation:
        preview["changes"] = [
            {
                "type": "add_relationship",
                "source_id": source_id,
                "target_id": target_id,
                "relation": relation,
                "result": {
                    "source": "review",
                    "status": "confirmed",
                },
            }
        ]

    elif action in {"confirm_candidate", "reject_candidate"} and source_id:
        preview["changes"] = [
            {
                "type": action,
                "source_id": source_id,
                "target_id": target_id,
                "relation": relation,
            }
        ]

    elif action == "skip":
        preview["changes"] = [{"type": "no_change"}]

    return preview


def apply_action(
    *,
    action: str,
    source_id: str | None = None,
    target_id: str | None = None,
    relation: str | None = None,
    evidence: list[str] | None = None,
    source: str = "review",
    graph_path: Path | None = None,
) -> dict[str, Any]:
    """Apply a review action to the entity graph.

    Supported actions:
    - merge_as_alias: Merge source into target (source's names become target's aliases)
    - keep_separate: Persist a user-confirmed non-duplicate decision
    - undo_keep_separate: Remove a previously persisted non-duplicate decision
    - add_relationship: Add a confirmed edge from source to target
    - skip: Skip this review item

    Args:
        action: The action to apply.
        source_id: Source entity id.
        target_id: Target entity id (for merge).
        relation: Relationship label for add_relationship.
        evidence: Journal rel_paths supporting the action.
        source: Provenance source for graph writes.
        graph_path: Optional override for entity graph path (testing).

    Returns:
        Result dict with success status and details.
    """
    if action == "skip":
        return {"success": True, "action": "skip", "skipped": True}

    if action in {"keep_separate", "undo_keep_separate"}:
        if not source_id or not target_id:
            return {
                "success": False,
                "action": action,
                "error": "source_id and target_id required for keep_separate",
            }

        graph_path = graph_path or _graph_path()
        graph = load_entity_graph(graph_path)
        source_entity = _find_entity(graph, source_id)
        target_entity = _find_entity(graph, target_id)
        if source_entity is None:
            return {
                "success": False,
                "action": action,
                "error": f"Source entity not found: {source_id}",
            }
        if target_entity is None:
            return {
                "success": False,
                "action": action,
                "error": f"Target entity not found: {target_id}",
            }

        if action == "undo_keep_separate":
            removed_source = _remove_distinct_record(source_entity, target_id)
            removed_target = _remove_distinct_record(target_entity, source_id)
            save_entity_graph(graph, graph_path)
            return {
                "success": True,
                "action": "undo_keep_separate",
                "source_id": source_id,
                "target_id": target_id,
                "removed": removed_source or removed_target,
            }

        created_at = _now_iso()
        _upsert_distinct_record(source_entity, target_id, source="user", created_at=created_at)
        _upsert_distinct_record(target_entity, source_id, source="user", created_at=created_at)
        save_entity_graph(graph, graph_path)
        return {
            "success": True,
            "action": "keep_separate",
            "source_id": source_id,
            "target_id": target_id,
            "changes": [
                {
                    "type": "mark_distinct",
                    "source_id": source_id,
                    "target_id": target_id,
                    "source": "user",
                }
            ],
        }

    if action in {"confirm_candidate", "reject_candidate"}:
        if not source_id:
            return {
                "success": False,
                "action": action,
                "error": "source_id required for candidate review",
            }
        graph_path = graph_path or _graph_path()
        graph = load_entity_graph(graph_path)
        source_entity = _find_entity(graph, source_id)
        if source_entity is None:
            return {
                "success": False,
                "action": action,
                "error": f"Source entity not found: {source_id}",
            }

        if target_id and relation:
            return _apply_candidate_relationship_action(
                action=action,
                graph=graph,
                graph_path=graph_path,
                source_entity=source_entity,
                target_id=target_id,
                relation=relation,
                source=source,
            )

        return _apply_candidate_entity_action(
            action=action,
            graph=graph,
            graph_path=graph_path,
            source_entity=source_entity,
            source=source,
        )

    if action == "add_relationship":
        if not source_id or not target_id or not relation:
            return {
                "success": False,
                "action": action,
                "error": "source_id, target_id, and relation required for add_relationship",
            }

        graph_path = graph_path or _graph_path()
        graph = load_entity_graph(graph_path)
        source_entity = _find_entity(graph, source_id)
        target_entity = _find_entity(graph, target_id)
        if source_entity is None:
            return {
                "success": False,
                "action": action,
                "error": f"Source entity not found: {source_id}",
            }
        if target_entity is None:
            return {
                "success": False,
                "action": action,
                "error": f"Target entity not found: {target_id}",
            }

        created_at = _now_iso()
        relationships = source_entity.setdefault("relationships", [])
        key = (target_id, relation)
        existing = next((rel for rel in relationships if _relationship_key(rel) == key), None)
        stamped = _stamp_relationship(
            {"target": target_id, "relation": relation},
            source=source,
            created_at=created_at,
            evidence=evidence,
        )
        if existing is None:
            relationships.append(stamped)
        else:
            existing.update(stamped)

        save_entity_graph(graph, graph_path)
        return {
            "success": True,
            "action": "add_relationship",
            "source_id": source_id,
            "target_id": target_id,
            "relation": relation,
        }

    if action == "merge_as_alias":
        if not source_id or not target_id:
            return {
                "success": False,
                "action": action,
                "error": "source_id and target_id required for merge",
            }

        graph_path = graph_path or _graph_path()
        graph = load_entity_graph(graph_path)

        source_entity = _find_entity(graph, source_id)
        target = _find_entity(graph, target_id)

        if source_entity is None:
            return {
                "success": False,
                "action": action,
                "error": f"Source entity not found: {source_id}",
            }
        if target is None:
            return {
                "success": False,
                "action": action,
                "error": f"Target entity not found: {target_id}",
            }

        created_at = _now_iso()
        source_snapshot = deepcopy(source_entity)

        # Transfer source's primary_name + aliases to target's aliases
        names_to_transfer = [source_entity["primary_name"], *source_entity.get("aliases", [])]
        target_aliases = target.setdefault("aliases", [])
        target_alias_metadata = target.setdefault("alias_metadata", {})
        transferred_aliases: list[str] = []

        for name in names_to_transfer:
            if name not in target_aliases and name != target["primary_name"]:
                target_aliases.append(name)
                target_alias_metadata[name] = {
                    "source": source,
                    "confidence": 1.0,
                    "created_at": created_at,
                }
                transferred_aliases.append(name)

        # Transfer source's relationships to target (avoid duplicates)
        target_rels = target.setdefault("relationships", [])
        existing_rels = {_relationship_key(r) for r in target_rels}
        transferred_relationships: list[dict[str, Any]] = []

        for rel in source_entity.get("relationships", []):
            key = _relationship_key(rel)
            if key not in existing_rels:
                stamped = _stamp_relationship(deepcopy(rel), source=source, created_at=created_at)
                target_rels.append(stamped)
                transferred_relationships.append(deepcopy(stamped))
                existing_rels.add(key)

        # Remove source entity
        graph = [e for e in graph if e["id"] != source_id]

        # Update reverse references: any entity pointing to source now points to target
        rewired_relationships: list[dict[str, Any]] = []
        for entity in graph:
            for rel in entity.get("relationships", []):
                if rel["target"] == source_id:
                    rewired_relationships.append(
                        {
                            "entity_id": entity["id"],
                            "relationship": deepcopy(rel),
                        }
                    )
                    rel["target"] = target_id
                    rel.update(
                        _stamp_relationship(
                            rel,
                            source=source,
                            created_at=created_at,
                            evidence=rel.get("evidence"),
                        )
                    )

        target.setdefault("merged_entities", []).append(
            {
                "id": source_id,
                "target_id": target_id,
                "source": source,
                "merged_at": created_at,
                "entity": source_snapshot,
                "transferred_aliases": transferred_aliases,
                "transferred_relationships": transferred_relationships,
                "rewired_relationships": rewired_relationships,
            }
        )

        save_entity_graph(graph, graph_path)

        return {
            "success": True,
            "action": "merge_as_alias",
            "source_id": source_id,
            "target_id": target_id,
            "transferred_names": names_to_transfer,
        }

    return {"success": False, "action": action, "error": f"Unknown action: {action}"}


def _apply_candidate_entity_action(
    *,
    action: str,
    graph: list[dict[str, Any]],
    graph_path: Path,
    source_entity: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    if source_entity.get("status") != "candidate":
        return {
            "success": False,
            "action": action,
            "error": f"Entity is not a candidate: {source_entity['id']}",
        }

    if action == "reject_candidate":
        graph = [entity for entity in graph if entity["id"] != source_entity["id"]]
        save_entity_graph(graph, graph_path)
        return {
            "success": True,
            "action": action,
            "rejected_id": source_entity["id"],
        }

    source_entity["status"] = "confirmed"
    source_entity["source"] = source
    source_entity["created_at"] = _now_iso()
    source_entity.setdefault("evidence", [])
    save_entity_graph(graph, graph_path)
    return {
        "success": True,
        "action": action,
        "confirmed_id": source_entity["id"],
    }


def _apply_candidate_relationship_action(
    *,
    action: str,
    graph: list[dict[str, Any]],
    graph_path: Path,
    source_entity: dict[str, Any],
    target_id: str,
    relation: str,
    source: str,
) -> dict[str, Any]:
    relationships = source_entity.get("relationships", []) or []
    relationship = next(
        (
            item
            for item in relationships
            if item.get("target") == target_id
            and item.get("relation") == relation
            and item.get("status", "confirmed") == "candidate"
        ),
        None,
    )
    if relationship is None:
        return {
            "success": False,
            "action": action,
            "error": (
                "Candidate relationship not found: " f"{source_entity['id']} {relation} {target_id}"
            ),
        }

    if action == "reject_candidate":
        source_entity["relationships"] = [
            item for item in relationships if item is not relationship
        ]
        save_entity_graph(graph, graph_path)
        return {
            "success": True,
            "action": action,
            "source_id": source_entity["id"],
            "target_id": target_id,
            "relation": relation,
        }

    relationship["status"] = "confirmed"
    relationship["source"] = source
    relationship["created_at"] = _now_iso()
    relationship.setdefault("evidence", [])
    save_entity_graph(graph, graph_path)
    return {
        "success": True,
        "action": action,
        "source_id": source_entity["id"],
        "target_id": target_id,
        "relation": relation,
    }


def unmerge_entity(
    *,
    merged_id: str,
    target_id: str,
    graph_path: Path | None = None,
) -> dict[str, Any]:
    """Restore an entity from a merge tombstone."""
    graph_path = graph_path or _graph_path()
    graph = load_entity_graph(graph_path)
    target = _find_entity(graph, target_id)
    if target is None:
        return {
            "success": False,
            "action": "unmerge",
            "error": f"Target entity not found: {target_id}",
        }
    if _find_entity(graph, merged_id) is not None:
        return {
            "success": False,
            "action": "unmerge",
            "error": f"Entity already exists: {merged_id}",
        }

    tombstones = target.get("merged_entities", []) or []
    tombstone = next((item for item in tombstones if item.get("id") == merged_id), None)
    if tombstone is None:
        return {
            "success": False,
            "action": "unmerge",
            "error": f"Merge tombstone not found: {merged_id}",
        }

    restored = deepcopy(tombstone["entity"])
    _remove_aliases(target, tombstone.get("transferred_aliases", []) or [])

    transferred_keys = {
        _relationship_key(relationship)
        for relationship in tombstone.get("transferred_relationships", []) or []
    }
    if transferred_keys:
        target["relationships"] = [
            relationship
            for relationship in target.get("relationships", []) or []
            if _relationship_key(relationship) not in transferred_keys
        ]

    for rewired in tombstone.get("rewired_relationships", []) or []:
        owner = _find_entity(graph, rewired.get("entity_id", ""))
        original = rewired.get("relationship", {})
        if owner is None or not original:
            continue
        for index, relationship in enumerate(owner.get("relationships", []) or []):
            if relationship.get("target") == target_id and relationship.get(
                "relation"
            ) == original.get("relation"):
                owner["relationships"][index] = deepcopy(original)
                break

    remaining_tombstones = [item for item in tombstones if item.get("id") != merged_id]
    if remaining_tombstones:
        target["merged_entities"] = remaining_tombstones
    else:
        target.pop("merged_entities", None)
    graph.append(restored)
    save_entity_graph(graph, graph_path)
    return {
        "success": True,
        "action": "unmerge",
        "restored_id": merged_id,
        "target_id": target_id,
    }
