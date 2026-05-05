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
#
# Fields:
#   suffix:      The Chinese suffix to match (e.g. "的老婆").
#   relation:    The canonical relation type.
#   direction:   How to traverse the graph:
#                "symmetric" — forward + reverse (for spouse_of).
#                "forward"   — only source's own relationships.
#                "reverse"   — only reverse_relationships (who points to source).
#   role_filter: Optional dict filtering by family_role_labels, e.g.
#                {"child_perspective": ["妈妈", "母亲"]}.
RELATION_PHRASE_PATTERNS: list[dict[str, Any]] = [
    {
        "suffix": "的老婆",
        "relation": "spouse_of",
        "direction": "symmetric",
        "role_filter": {"spouse_perspective": ["老婆", "妻子"]},
    },
    {
        "suffix": "的妻子",
        "relation": "spouse_of",
        "direction": "symmetric",
        "role_filter": {"spouse_perspective": ["老婆", "妻子"]},
    },
    {
        "suffix": "的老公",
        "relation": "spouse_of",
        "direction": "symmetric",
        "role_filter": {"spouse_perspective": ["老公", "丈夫"]},
    },
    {
        "suffix": "的丈夫",
        "relation": "spouse_of",
        "direction": "symmetric",
        "role_filter": {"spouse_perspective": ["老公", "丈夫"]},
    },
    {
        "suffix": "的妈妈",
        "relation": "parent_of",
        "direction": "reverse",
        "role_filter": {"child_perspective": ["妈妈", "母亲"]},
    },
    {
        "suffix": "的母亲",
        "relation": "parent_of",
        "direction": "reverse",
        "role_filter": {"child_perspective": ["妈妈", "母亲"]},
    },
    {
        "suffix": "的爸爸",
        "relation": "parent_of",
        "direction": "reverse",
        "role_filter": {"child_perspective": ["爸爸", "父亲"]},
    },
    {
        "suffix": "的父亲",
        "relation": "parent_of",
        "direction": "reverse",
        "role_filter": {"child_perspective": ["爸爸", "父亲"]},
    },
    {
        "suffix": "的奶奶",
        "relation": "grandmother_of",
        "direction": "reverse",
        "role_filter": {"child_perspective": ["奶奶", "外婆"]},
    },
    {
        "suffix": "的爷爷",
        "relation": "grandfather_of",
        "direction": "reverse",
        "role_filter": {"child_perspective": ["爷爷", "外公"]},
    },
    {
        "suffix": "的外婆",
        "relation": "grandmother_of",
        "direction": "reverse",
        "role_filter": {"child_perspective": ["外婆", "姥姥"]},
    },
    {
        "suffix": "的姥姥",
        "relation": "grandmother_of",
        "direction": "reverse",
        "role_filter": {"child_perspective": ["外婆", "姥姥"]},
    },
    {
        "suffix": "的外公",
        "relation": "grandfather_of",
        "direction": "reverse",
        "role_filter": {"child_perspective": ["外公", "姥爷"]},
    },
    {
        "suffix": "的姥爷",
        "relation": "grandfather_of",
        "direction": "reverse",
        "role_filter": {"child_perspective": ["外公", "姥爷"]},
    },
    {
        "suffix": "的女儿",
        "relation": "child_of",
        "direction": "reverse",
        "role_filter": {"parent_perspective": ["女儿"]},
    },
    {
        "suffix": "的儿子",
        "relation": "child_of",
        "direction": "reverse",
        "role_filter": {"parent_perspective": ["儿子"]},
    },
    {
        "suffix": "的孩子",
        "relation": "child_of",
        "direction": "reverse",
        "role_filter": {"parent_perspective": ["女儿", "儿子"]},
    },
    {
        "suffix": "的老家",
        "relation": "hometown",
        "direction": "symmetric",
        "role_filter": None,
    },
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
        "外婆",
        "外公",
        "姥姥",
        "姥爷",
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
    reverse_relationships: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    phrase_patterns: list[dict[str, Any]] = field(default_factory=list)


def _matches_role_filter(entity: dict[str, Any], role_filter: dict[str, list[str]] | None) -> bool:
    """Check whether an entity matches a family_role_labels filter.

    Backward-compatible: entities without family_role_labels are allowed
    to pass through. Only entities that *have* relevant labels but don't
    match are filtered out.
    """
    if not role_filter:
        return True

    family_role_labels = entity.get("attributes", {}).get("family_role_labels", {})
    if not family_role_labels:
        return True  # No labels to filter against; allow for backward compat.

    has_relevant_perspective = False
    for perspective, allowed in role_filter.items():
        label_data = family_role_labels.get(perspective)
        if not label_data:
            continue
        has_relevant_perspective = True
        primary = label_data.get("primary", "")
        aliases = label_data.get("aliases", [])
        all_labels = [primary] + aliases
        if any(label in allowed for label in all_labels if label):
            return True

    # Entity has family_role_labels but none of the relevant perspectives matched.
    return not has_relevant_perspective


def _expand_related_entities(
    *,
    source: dict[str, Any],
    relation: str,
    view: Any,
    direction: str = "symmetric",
    role_filter: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Find entities related to source by the given relation.

    Args:
        source: The source entity dict.
        relation: Canonical relation to match.
        view: The runtime view.
        direction: Traversal direction:
            "symmetric" — forward (source's own relationships) + reverse.
            "forward"   — only source's own relationships.
            "reverse"   — only reverse_relationships (who points to source).
        role_filter: Optional family_role_labels filter.

    Returns:
        List of matched entity dicts.
    """
    from tools.lib.entity_relations import normalize_relation

    related_entities: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def _match(actual: str) -> bool:
        return normalize_relation(actual) == normalize_relation(relation)

    def _add(target: dict[str, Any] | None) -> None:
        if target and target["id"] not in seen_ids and _matches_role_filter(target, role_filter):
            related_entities.append(target)
            seen_ids.add(target["id"])

    if direction in ("symmetric", "forward"):
        for rel in source.get("relationships", []):
            if _match(str(rel.get("relation", ""))):
                _add(resolve_via_runtime(rel["target"], view))

    if direction in ("symmetric", "reverse"):
        for source_id, reverse_relation in view.reverse_relationships.get(source["id"], []):
            if _match(reverse_relation):
                _add(resolve_via_runtime(source_id, view))

    return related_entities


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


# Backward-compat alias for code that imports _expand_related_entities
# from the old inline location in search_journals/core.py.
__all__ = [
    "EntityRuntimeView",
    "build_runtime_view",
    "load_runtime_view",
    "resolve_via_runtime",
    "_expand_related_entities",
    "_matches_role_filter",
    "RELATION_PHRASE_PATTERNS",
    "ROLE_LABELS",
]
