#!/usr/bin/env python3
"""
Entity Candidate Extraction — Round 7 Phase 2 Task 6.

Extracts structured entity candidates from frontmatter and content body.
Does NOT write to entity_graph.yaml — candidates are returned for review.

Candidate layer design:
- truth layer: entity_graph.yaml (confirmed entities)
- candidate layer: write/search/audit output (unconfirmed candidates, not persisted)
"""

from __future__ import annotations

from typing import Any

from tools.lib.entity_runtime import (
    EntityRuntimeView,
    build_runtime_view,
)

try:
    from tools.lib.logger import get_logger

    logger = get_logger("entity_candidates")
except ImportError:
    import logging

    logger = logging.getLogger("entity_candidates")


def extract_entity_candidates(
    *,
    metadata: dict[str, Any],
    content: str,
    graph: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract entity candidates from frontmatter metadata and content body.

    Args:
        metadata: Journal data dict with people/location/project fields.
        content: Journal body text.
        graph: Loaded entity graph list.

    Returns:
        List of candidate dicts, each with:
            text, source, kind, matched_entity_id, suggested_action, risk_level
    """
    if not graph:
        return []

    view = build_runtime_view(graph)
    candidates: list[dict[str, Any]] = []
    seen_keys: set[str] = set()  # Deduplicate by (text, source)

    def _add_candidate(
        text: str,
        source: str,
        kind: str,
        matched_entity_id: str | None,
    ) -> None:
        dedup_key = f"{text}|{source}"
        if dedup_key in seen_keys:
            return
        seen_keys.add(dedup_key)

        if matched_entity_id is not None:
            suggested_action = "confirm_match"
            risk_level = "low"
        else:
            suggested_action = "add_entity"
            risk_level = "medium"

        candidates.append(
            {
                "text": text,
                "source": source,
                "kind": kind,
                "matched_entity_id": matched_entity_id,
                "suggested_action": suggested_action,
                "risk_level": risk_level,
            }
        )

    # 1. Frontmatter sources: people, location, project
    _extract_from_frontmatter(metadata, view, _add_candidate)

    # 2. Content body: scan for entity alias/name mentions
    _extract_from_content(content, view, _add_candidate)

    return candidates


def _extract_from_frontmatter(
    metadata: dict[str, Any],
    view: EntityRuntimeView,
    add_fn: Any,  # Callable[[str, str, str, str | None], None]
) -> None:
    """Extract candidates from frontmatter people/location/project fields."""
    field_to_kind = {
        "people": "person",
        "location": "place",
        "project": "project",
    }

    for field, kind in field_to_kind.items():
        value = metadata.get(field)
        items: list[str] = []
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
        elif isinstance(value, str) and value.strip():
            items = [value.strip()]

        for item in items:
            entity = view.by_lookup.get(item)
            add_fn(
                text=item,
                source="frontmatter",
                kind=kind,
                matched_entity_id=entity["id"] if entity else None,
            )


def _extract_from_content(
    content: str,
    view: EntityRuntimeView,
    add_fn: Any,  # Callable[[str, str, str, str | None], None]
) -> None:
    """Extract candidates from content body using alias/name exact match.

    Strategy: scan content for all known entity names/aliases.
    This is a lightweight approach — no NLP, no fuzzy matching.
    """
    if not content or not view.by_lookup:
        return

    # Sort by length descending to match longer aliases first
    # (e.g., "乐乐妈" before "乐乐")
    lookup_keys = sorted(view.by_lookup.keys(), key=len, reverse=True)

    for key in lookup_keys:
        if key in content:
            entity = view.by_lookup[key]
            kind = entity.get("type", "concept")
            add_fn(
                text=key,
                source="content",
                kind=kind,
                matched_entity_id=entity["id"],
            )
