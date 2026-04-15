#!/usr/bin/env python3

from __future__ import annotations

from typing import Any

from tools.lib.entity_graph import resolve_entity


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
