#!/usr/bin/env python3

from __future__ import annotations

from typing import Any

from tools.lib.entity_graph import resolve_entity
from tools.lib.llm_extract import is_llm_available


def generate_sentiment_score(content: str) -> float | None:
    """Online-first placeholder.

    When no LLM is available, return None per TDD decision.
    """
    if not is_llm_available():
        return None
    return None


def extract_themes(content: str) -> list[str]:
    """Online-first placeholder.

    When no LLM is available, return [] per TDD decision.
    """
    if not is_llm_available():
        return []
    return []


def match_entities(
    people: Any,
    location: Any,
    project: Any,
    entity_graph: list[dict[str, Any]],
) -> list[str]:
    matches: list[str] = []

    def _iter_values(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    for candidate in [
        *_iter_values(people),
        *_iter_values(location),
        *_iter_values(project),
    ]:
        entity = resolve_entity(candidate, entity_graph)
        if entity and entity["id"] not in matches:
            matches.append(entity["id"])

    return matches
