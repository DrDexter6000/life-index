#!/usr/bin/env python3
"""Deterministic entity-neighbor traversal helpers."""

from __future__ import annotations

from collections import deque
from typing import Any

from tools.lib.entity_graph import resolve_entity

MAX_HOPS_LIMIT = 3
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _normalize_relations(relations: list[str] | None) -> list[str]:
    if not relations:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for relation in relations:
        text = str(relation).strip()
        if text and text not in seen:
            seen.add(text)
            normalized.append(text)
    return sorted(normalized)


def _entity_summary(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entity.get("id"),
        "type": entity.get("type"),
        "primary_name": entity.get("primary_name"),
        "aliases": list(entity.get("aliases", []) or []),
    }


def _supporting_journal_ids(relationship: dict[str, Any]) -> list[str]:
    raw = (
        relationship.get("supporting_journal_ids")
        or relationship.get("supporting_journals")
        or relationship.get("journal_ids")
        or []
    )
    if not isinstance(raw, list):
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            ids.append(text)
    return ids


def _edge_payload(
    source_id: str,
    target_id: str,
    relationship: dict[str, Any],
    *,
    direction: str,
) -> dict[str, Any]:
    weight = relationship.get("weight", 1.0)
    if not isinstance(weight, (int, float)):
        weight = 1.0
    return {
        "source": source_id,
        "target": target_id,
        "relation": str(relationship.get("relation", "")),
        "direction": direction,
        "weight": float(weight),
        "supporting_journal_ids": _supporting_journal_ids(relationship),
    }


def _candidate_edges(
    graph: list[dict[str, Any]],
    entity_id: str,
    relation_filter: set[str],
) -> list[tuple[str, dict[str, Any]]]:
    edges: list[tuple[str, dict[str, Any]]] = []
    by_id = {str(entity.get("id")): entity for entity in graph}
    source = by_id.get(entity_id)
    if source is not None:
        for relationship in source.get("relationships", []) or []:
            relation = str(relationship.get("relation", ""))
            if relation_filter and relation not in relation_filter:
                continue
            target_id = str(relationship.get("target", ""))
            if target_id in by_id:
                edges.append(
                    (
                        target_id,
                        _edge_payload(entity_id, target_id, relationship, direction="outgoing"),
                    )
                )
    for incoming in graph:
        incoming_id = str(incoming.get("id"))
        for relationship in incoming.get("relationships", []) or []:
            relation = str(relationship.get("relation", ""))
            target_id = str(relationship.get("target", ""))
            if target_id != entity_id:
                continue
            if relation_filter and relation not in relation_filter:
                continue
            edges.append(
                (
                    incoming_id,
                    _edge_payload(incoming_id, entity_id, relationship, direction="incoming"),
                )
            )
    return sorted(
        edges,
        key=lambda item: (
            item[1]["relation"],
            item[0],
            item[1]["source"],
            item[1]["target"],
            item[1]["direction"],
        ),
    )


def build_entity_neighbors_payload(
    graph: list[dict[str, Any]],
    entity: str,
    *,
    max_hops: int = 1,
    relations: list[str] | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return deterministic neighboring entities for an explicit graph entity.

    The caller supplies the entity and optional relation filters. This helper
    only traverses explicit graph edges; it never infers entities or predicates
    from natural language.
    """
    normalized_relations = _normalize_relations(relations)
    relation_filter = set(normalized_relations)
    bounded_hops = max(1, min(int(max_hops), MAX_HOPS_LIMIT))
    bounded_limit = max(1, min(int(limit), MAX_LIMIT))
    resolved = resolve_entity(entity, graph)
    if resolved is None:
        return {
            "query": entity,
            "status": "entity_not_found",
            "resolved_entity": None,
            "max_hops": bounded_hops,
            "relations": normalized_relations,
            "exhaustive": True,
            "neighbor_count": 0,
            "neighbors": [],
        }

    start_id = str(resolved["id"])
    by_id = {str(item.get("id")): item for item in graph}
    queue: deque[tuple[str, int, list[dict[str, Any]]]] = deque([(start_id, 0, [])])
    best: dict[str, dict[str, Any]] = {}
    visited_depth: dict[str, int] = {start_id: 0}

    while queue:
        current_id, depth, path_edges = queue.popleft()
        if depth >= bounded_hops:
            continue
        for next_id, edge in _candidate_edges(graph, current_id, relation_filter):
            if next_id == start_id:
                continue
            next_depth = depth + 1
            if next_depth > bounded_hops:
                continue
            next_path = [*path_edges, edge]
            existing = best.get(next_id)
            candidate_key = (
                next_depth,
                tuple(str(item["relation"]) for item in next_path),
                tuple(str(item["source"]) for item in next_path),
                tuple(str(item["target"]) for item in next_path),
            )
            should_update = existing is None
            if existing is not None:
                existing_key = (
                    int(existing["hops"]),
                    tuple(str(item["relation"]) for item in existing["edges"]),
                    tuple(str(item["source"]) for item in existing["edges"]),
                    tuple(str(item["target"]) for item in existing["edges"]),
                )
                should_update = candidate_key < existing_key
            if should_update:
                target = by_id[next_id]
                best[next_id] = {
                    "entity_id": next_id,
                    "entity_type": target.get("type"),
                    "primary_name": target.get("primary_name"),
                    "aliases": list(target.get("aliases", []) or []),
                    "hops": next_depth,
                    "edges": next_path,
                }
            if visited_depth.get(next_id, bounded_hops + 1) > next_depth:
                visited_depth[next_id] = next_depth
                queue.append((next_id, next_depth, next_path))

    def _neighbor_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
        edges = item.get("edges", []) or []
        first_edge = edges[0] if edges and isinstance(edges[0], dict) else {}
        direction_rank = 0 if first_edge.get("direction") == "outgoing" else 1
        return (int(item["hops"]), direction_rank, str(item["entity_id"]))

    neighbors = sorted(best.values(), key=_neighbor_sort_key)[:bounded_limit]
    return {
        "query": entity,
        "status": "ok",
        "resolved_entity": _entity_summary(resolved),
        "max_hops": bounded_hops,
        "relations": normalized_relations,
        "exhaustive": len(best) <= bounded_limit,
        "neighbor_count": len(neighbors),
        "neighbors": neighbors,
    }
