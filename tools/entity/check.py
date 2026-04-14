#!/usr/bin/env python3
"""
Entity graph integrity check — Round 7 Phase 3 Task 9.

Provides `entity --check` CLI command for quick integrity validation.

CLI entry: `life-index entity --check`

Unlike `--audit` (which focuses on quality issues like duplicates and orphans),
`--check` focuses on structural integrity: dangling refs, schema violations,
and lookup consistency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph
from tools.lib.paths import resolve_user_data_dir

try:
    from tools.lib.logger import get_logger

    logger = get_logger("entity_check")
except ImportError:
    import logging

    logger = logging.getLogger("entity_check")

import yaml


def _default_graph_path() -> Path:
    return resolve_user_data_dir() / "entity_graph.yaml"


def run_check(
    *,
    graph_path: Path | None = None,
) -> dict[str, Any]:
    """Run entity graph integrity check.

    Checks for:
    - Dangling relationship targets (references to non-existent entities)
    - Duplicate lookup entries (same alias/primary_name resolving to multiple entities)
    - Schema field completeness

    Args:
        graph_path: Optional override for entity graph path (testing).

    Returns:
        Structured check result with issues list and summary.
    """
    graph_path = graph_path or _default_graph_path()

    # Read raw YAML — check must be able to inspect malformed graphs
    # that would fail load_entity_graph's validation
    if not graph_path.exists():
        return {
            "success": True,
            "data": {
                "total_entities": 0,
                "issues": [],
                "summary": {
                    "dangling_relationships": 0,
                    "duplicate_lookups": 0,
                    "schema_issues": 0,
                },
            },
            "error": None,
        }

    with graph_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {"entities": []}

    entities: list[dict[str, Any]] = data.get("entities", [])

    if not entities:
        return {
            "success": True,
            "data": {
                "total_entities": 0,
                "issues": [],
                "summary": {
                    "dangling_relationships": 0,
                    "duplicate_lookups": 0,
                    "schema_issues": 0,
                },
            },
            "error": None,
        }

    entity_ids = {e["id"] for e in entities}
    issues: list[dict[str, Any]] = []

    # 1. Dangling relationships
    for entity in entities:
        for rel in entity.get("relationships", []):
            target = rel.get("target", "")
            if target and target not in entity_ids:
                issues.append(
                    {
                        "type": "dangling_relationship",
                        "severity": "high",
                        "entity_id": entity["id"],
                        "target": target,
                        "relation": rel.get("relation", ""),
                        "description": f"Entity {entity['id']} references non-existent target {target}",
                    }
                )

    # 2. Duplicate lookups (same name/alias resolving to multiple entities)
    name_to_ids: dict[str, list[str]] = {}
    for entity in entities:
        primary = entity.get("primary_name", "")
        if primary:
            name_to_ids.setdefault(primary, []).append(entity["id"])
        for alias in entity.get("aliases", []):
            name_to_ids.setdefault(alias, []).append(entity["id"])

    for name, ids in name_to_ids.items():
        unique_ids = list(set(ids))
        if len(unique_ids) > 1:
            issues.append(
                {
                    "type": "duplicate_lookup",
                    "severity": "medium",
                    "name": name,
                    "entity_ids": unique_ids,
                    "description": f"Name '{name}' resolves to multiple entities: {unique_ids}",
                }
            )

    # 3. Schema completeness (missing required fields)
    required_fields = {"id", "type", "primary_name"}
    for entity in entities:
        missing = required_fields - set(entity.keys())
        if missing:
            issues.append(
                {
                    "type": "schema_issue",
                    "severity": "high",
                    "entity_id": entity.get("id", "<unknown>"),
                    "missing_fields": sorted(missing),
                    "description": f"Entity missing required fields: {sorted(missing)}",
                }
            )

    # Summary
    summary = {
        "dangling_relationships": sum(
            1 for i in issues if i["type"] == "dangling_relationship"
        ),
        "duplicate_lookups": sum(1 for i in issues if i["type"] == "duplicate_lookup"),
        "schema_issues": sum(1 for i in issues if i["type"] == "schema_issue"),
    }

    return {
        "success": True,
        "data": {
            "total_entities": len(entities),
            "issues": issues,
            "summary": summary,
        },
        "error": None,
    }
