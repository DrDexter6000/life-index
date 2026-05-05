#!/usr/bin/env python3
"""
Entity Candidate Extraction — Round 7 Phase 2 Task 6 + Round 10 T1.4.

Extracts structured entity candidates from frontmatter and content body.
Does NOT write to entity_graph.yaml — candidates are returned for review.

Candidate layer design:
- truth layer: entity_graph.yaml (confirmed entities)
- candidate layer: write/search/audit output (unconfirmed candidates, not persisted)

Round 10 T1.4: When graph is empty/missing, falls back to extracting candidates
directly from frontmatter fields (no EntityRuntimeView needed). Fallback candidates
include a suggested_command field for Agent one-click entity creation.
"""

from __future__ import annotations

import json
import re
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


# ── Type inference (shared with seed.py) ────────────────────────────────

_TOOL_PATTERN = re.compile(r"^[A-Z][a-zA-Z0-9 ]+$")


def _infer_type_from_source(source_field: str, value: str) -> str:
    """Infer entity type from the frontmatter field it came from.

    Rules:
    - people → person
    - location → place
    - tags + matches TOOL_PATTERN → concept (v1 schema has no "tool" type)
    - tags + doesn't match → concept
    - project → project
    """
    if source_field == "people":
        return "person"
    if source_field == "location":
        return "place"
    if source_field == "tags":
        if _TOOL_PATTERN.match(value):
            return "concept"
        return "concept"
    if source_field == "project":
        return "project"
    return "concept"


def _build_suggested_command(text: str, entity_type: str) -> str:
    """Build a valid `life-index entity --add` command for fallback candidates."""
    entity_data = json.dumps(
        {"primary_name": text, "type": entity_type},
        ensure_ascii=False,
    )
    return f"life-index entity --add '{entity_data}'"


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
        graph: Loaded entity graph list. When empty, falls back to
               extracting candidates directly from metadata fields.

    Returns:
        List of candidate dicts, each with:
            text, source, kind, matched_entity_id, suggested_action, risk_level
            When graph is empty (fallback mode), also includes suggested_command.
    """
    if not graph:
        return _extract_frontmatter_fallback(metadata)

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


def _extract_frontmatter_fallback(
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract candidates directly from metadata when no entity graph exists.

    This is the D5/D17 fallback: always return useful data so the Agent
    can present entity suggestions to the user even on first use.
    """
    field_to_source: dict[str, str] = {
        "people": "frontmatter_fallback",
        "location": "frontmatter_fallback",
        "tags": "frontmatter_fallback",
        "project": "frontmatter_fallback",
    }

    candidates: list[dict[str, Any]] = []
    seen_texts: set[str] = set()

    for field, source in field_to_source.items():
        value = metadata.get(field)
        items: list[str] = []
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
        elif isinstance(value, str) and value.strip():
            items = [value.strip()]

        for item in items:
            if item in seen_texts:
                continue
            seen_texts.add(item)

            kind = _infer_type_from_source(field, item)
            candidates.append(
                {
                    "text": item,
                    "source": source,
                    "kind": kind,
                    "matched_entity_id": None,
                    "suggested_action": "add_entity",
                    "risk_level": "medium",
                    "suggested_command": _build_suggested_command(item, kind),
                }
            )

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
