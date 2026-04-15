#!/usr/bin/env python3
"""
Entity Runtime View — Round 7 Phase 1 Task 1.

Provides a derived serving layer over entity_graph.yaml:
- by_lookup: dict mapping any lookup key (id, primary_name, alias) → entity dict
- reverse_relationships: dict mapping target_id → [(source_id, relation)]
- phrase_patterns: registered relationship/role phrase patterns
- entities: the original entity list

This is a read-only derived view. It never writes back to YAML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph

# ---------------------------------------------------------------------------
# Phrase Pattern Registry
# ---------------------------------------------------------------------------

# Maps a Chinese suffix pattern to the relation type it implies.
# Used by search expansion to resolve "X的老婆" → spouse_of, etc.
RELATION_PHRASE_PATTERNS: list[dict[str, str]] = [
    {"suffix": "的老婆", "relation": "spouse_of"},
    {"suffix": "的妻子", "relation": "spouse_of"},
    {"suffix": "的老公", "relation": "spouse_of"},
    {"suffix": "的丈夫", "relation": "spouse_of"},
    {"suffix": "的妈妈", "relation": "parent_of"},
    {"suffix": "的母亲", "relation": "parent_of"},
    {"suffix": "的爸爸", "relation": "parent_of"},
    {"suffix": "的父亲", "relation": "parent_of"},
    {"suffix": "的奶奶", "relation": "grandmother_of"},
    {"suffix": "的爷爷", "relation": "grandfather_of"},
    {"suffix": "的女儿", "relation": "child_of"},
    {"suffix": "的儿子", "relation": "child_of"},
    {"suffix": "的孩子", "relation": "child_of"},
    {"suffix": "的老家", "relation": "hometown"},
]

# Role labels that can directly map to an entity (e.g., "老婆" → wife entity)
# These are common Chinese kinship/role terms that should expand to entity aliases
ROLE_LABELS: frozenset[str] = frozenset(
    {
        "老婆",
        "妻子",
        "老公",
        "丈夫",
        "妈妈",
        "母亲",
        "爸",
        "爸爸",
        "父亲",
        "女儿",
        "儿子",
        "孩子",
        "奶奶",
        "爷爷",
        "老家",
    }
)


@dataclass
class EntityRuntimeView:
    """Derived serving view over entity graph data.

    Attributes:
        entities: The original entity list.
        by_lookup: Maps any lookup key (id, primary_name, alias) → entity dict.
        reverse_relationships: Maps target_id → [(source_id, relation)].
        phrase_patterns: Registered relationship/role phrase patterns.
    """

    entities: list[dict[str, Any]]
    by_lookup: dict[str, dict[str, Any]] = field(default_factory=dict)
    reverse_relationships: dict[str, list[tuple[str, str]]] = field(
        default_factory=dict
    )
    phrase_patterns: list[dict[str, str]] = field(default_factory=list)


def build_runtime_view(graph: list[dict[str, Any]]) -> EntityRuntimeView:
    """Build a runtime view from an entity graph list.

    Args:
        graph: List of entity dicts (as returned by load_entity_graph).

    Returns:
        EntityRuntimeView with populated lookup maps and reverse relationships.
    """
    by_lookup: dict[str, dict[str, Any]] = {}
    reverse_relationships: dict[str, list[tuple[str, str]]] = {}

    for entity in graph:
        lookup_keys = {
            entity["id"],
            entity["primary_name"],
            *entity.get("aliases", []),
        }
        for key in lookup_keys:
            by_lookup[key] = entity

        for rel in entity.get("relationships", []):
            target_id = rel["target"]
            relation = rel["relation"]
            if target_id not in reverse_relationships:
                reverse_relationships[target_id] = []
            reverse_relationships[target_id].append((entity["id"], relation))

    return EntityRuntimeView(
        entities=list(graph),  # shallow copy
        by_lookup=by_lookup,
        reverse_relationships=reverse_relationships,
        phrase_patterns=list(RELATION_PHRASE_PATTERNS),
    )


def load_runtime_view(graph_path: Path) -> EntityRuntimeView:
    """Load entity graph from YAML and build runtime view.

    Returns an empty view if the file doesn't exist.

    Args:
        graph_path: Path to entity_graph.yaml.

    Returns:
        EntityRuntimeView built from the loaded graph.
    """
    graph = load_entity_graph(graph_path)
    return build_runtime_view(graph)


def resolve_via_runtime(query: str, view: EntityRuntimeView) -> dict[str, Any] | None:
    """Resolve an entity by any lookup key using the runtime view.

    Args:
        query: id, primary_name, or alias to look up.
        view: The runtime view to search.

    Returns:
        Entity dict if found, None otherwise.
    """
    return view.by_lookup.get(query.strip())
