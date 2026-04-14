#!/usr/bin/env python3
"""
Entity graph statistics — Round 7 Phase 3 Task 9.

Provides `entity --stats` CLI command with structured graph statistics.

CLI entry: `life-index entity --stats`
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph
from tools.lib.paths import resolve_user_data_dir

try:
    from tools.lib.logger import get_logger

    logger = get_logger("entity_stats")
except ImportError:
    import logging

    logger = logging.getLogger("entity_stats")


def _default_graph_path() -> Path:
    return resolve_user_data_dir() / "entity_graph.yaml"


def compute_stats(
    *,
    graph_path: Path | None = None,
) -> dict[str, Any]:
    """Compute entity graph statistics.

    Args:
        graph_path: Optional override for entity graph path (testing).

    Returns:
        Structured stats dict with total_entities, by_type, total_aliases,
        total_relationships, top_referenced, and top_cooccurrence pairs.
    """
    graph_path = graph_path or _default_graph_path()
    entities = load_entity_graph(graph_path)

    if not entities:
        return {
            "success": True,
            "data": {
                "total_entities": 0,
                "by_type": {},
                "total_aliases": 0,
                "total_relationships": 0,
                "top_referenced": [],
                "top_cooccurrence": [],
            },
            "error": None,
        }

    # Type breakdown
    by_type: dict[str, int] = {}
    for entity in entities:
        etype = entity.get("type", "unknown")
        by_type[etype] = by_type.get(etype, 0) + 1

    # Total aliases
    total_aliases = sum(len(e.get("aliases", []) or []) for e in entities)

    # Total relationships
    total_relationships = sum(len(e.get("relationships", []) or []) for e in entities)

    # Top referenced entities (incoming relationship count)
    incoming: dict[str, int] = {}
    for entity in entities:
        for rel in entity.get("relationships", []):
            target = rel.get("target", "")
            if target:
                incoming[target] = incoming.get(target, 0) + 1

    top_referenced = sorted(
        [
            {"entity_id": eid, "incoming_count": count}
            for eid, count in incoming.items()
        ],
        key=lambda x: x["incoming_count"],
        reverse=True,
    )[:10]

    # Top co-occurrence pairs (entities that reference each other)
    pair_counts: dict[frozenset[str], int] = {}
    for entity in entities:
        for rel in entity.get("relationships", []):
            target = rel.get("target", "")
            if target and target != entity["id"]:
                pair = frozenset([entity["id"], target])
                pair_counts[pair] = pair_counts.get(pair, 0) + 1

    top_cooccurrence = sorted(
        [
            {"entities": sorted(list(pair)), "cooccurrence": count}
            for pair, count in pair_counts.items()
        ],
        key=lambda x: x["cooccurrence"],
        reverse=True,
    )[:10]

    return {
        "success": True,
        "data": {
            "total_entities": len(entities),
            "by_type": by_type,
            "total_aliases": total_aliases,
            "total_relationships": total_relationships,
            "top_referenced": top_referenced,
            "top_cooccurrence": top_cooccurrence,
        },
        "error": None,
    }
