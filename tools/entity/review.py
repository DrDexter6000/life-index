#!/usr/bin/env python3
"""
Entity Review Hub — Round 7 Phase 2 Task 7.

Provides the review queue builder, preview generator, and action applicator
for entity graph review workflow.

CLI entry: `life-index entity review`
"""

from __future__ import annotations

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

    if not graph:
        return []

    # Import audit lazily to avoid circular imports
    from tools.entity.audit import audit_entity_graph

    report = audit_entity_graph(graph_path, journals_dir=None)
    issues = report.get("issues", [])

    queue: list[dict[str, Any]] = []
    item_counter = 0

    action_map = {
        "possible_duplicate": ["merge_as_alias", "keep_separate", "skip"],
        "orphan_entity": ["keep", "archive", "skip"],
        "incomplete_relationship": ["add_relationship", "skip"],
    }

    for issue in issues:
        item_counter += 1
        issue_type = issue.get("type", "unknown")
        severity = issue.get("severity", "low")

        # Use severity directly for risk level, mapping to our 3-tier system
        risk_level = severity if severity in ("high", "medium", "low") else "medium"

        queue.append(
            {
                "item_id": f"review-{item_counter}",
                "risk_level": risk_level,
                "category": issue_type,
                "description": issue.get("evidence") or issue.get("message", ""),
                "action_choices": action_map.get(issue_type, ["skip"]),
                "entity_ids": (
                    issue.get("entities", [])
                    if isinstance(issue.get("entities"), list)
                    else [issue.get("entity_id", "")]
                ),
                "suggested_action": issue.get("suggested_action", ""),
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
    graph_path: Path | None = None,
) -> dict[str, Any]:
    """Generate a preview of what an action will do before committing.

    Args:
        item_id: The review item being actioned.
        action: The action to preview.
        source_id: Source entity id (for merge).
        target_id: Target entity id (for merge).
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

    elif action == "keep_separate":
        preview["changes"] = [{"type": "no_change"}]

    elif action == "skip":
        preview["changes"] = [{"type": "no_change"}]

    return preview


def apply_action(
    *,
    action: str,
    source_id: str | None = None,
    target_id: str | None = None,
    graph_path: Path | None = None,
) -> dict[str, Any]:
    """Apply a review action to the entity graph.

    Supported actions:
    - merge_as_alias: Merge source into target (source's names become target's aliases)
    - keep_separate: No change, acknowledge as distinct
    - skip: Skip this review item

    Args:
        action: The action to apply.
        source_id: Source entity id.
        target_id: Target entity id (for merge).
        graph_path: Optional override for entity graph path (testing).

    Returns:
        Result dict with success status and details.
    """
    if action == "skip":
        return {"success": True, "action": "skip", "skipped": True}

    if action == "keep_separate":
        return {"success": True, "action": "keep_separate", "changes": []}

    if action == "merge_as_alias":
        if not source_id or not target_id:
            return {
                "success": False,
                "action": action,
                "error": "source_id and target_id required for merge",
            }

        graph_path = graph_path or _graph_path()
        graph = load_entity_graph(graph_path)

        source = next((e for e in graph if e["id"] == source_id), None)
        target = next((e for e in graph if e["id"] == target_id), None)

        if source is None:
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

        # Transfer source's primary_name + aliases to target's aliases
        names_to_transfer = [source["primary_name"], *source.get("aliases", [])]
        target_aliases = target.setdefault("aliases", [])

        for name in names_to_transfer:
            if name not in target_aliases and name != target["primary_name"]:
                target_aliases.append(name)

        # Transfer source's relationships to target (avoid duplicates)
        target_rels = target.setdefault("relationships", [])
        existing_rels = {(r["target"], r["relation"]) for r in target_rels}

        for rel in source.get("relationships", []):
            key = (rel["target"], rel["relation"])
            if key not in existing_rels:
                target_rels.append(rel)
                existing_rels.add(key)

        # Remove source entity
        graph = [e for e in graph if e["id"] != source_id]

        # Update reverse references: any entity pointing to source now points to target
        for entity in graph:
            for rel in entity.get("relationships", []):
                if rel["target"] == source_id:
                    rel["target"] = target_id

        save_entity_graph(graph, graph_path)

        return {
            "success": True,
            "action": "merge_as_alias",
            "source_id": source_id,
            "target_id": target_id,
            "transferred_names": names_to_transfer,
        }

    return {"success": False, "action": action, "error": f"Unknown action: {action}"}
