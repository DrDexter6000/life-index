#!/usr/bin/env python3

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from tools.lib.entity_schema import EntityGraphValidationError
from tools.lib.entity_schema import validate_entity_graph_payload

BUILD_FROM_JOURNALS_PREVIEW_COMMAND = "life-index entity build --from-journals --preview --json"

_GraphCacheKey = tuple[str, bool]
_GraphCacheEntry = tuple[tuple[int, int], list[dict[str, Any]]]
# Process-level memo: resolved path + allow_legacy flag -> ((mtime_ns, size), parse).
# The stat signature is re-checked on every load, so a long-lived host never
# serves a parse whose file changed or disappeared. Values are private copies;
# each load returns its own deep copy so callers may edit their result freely.
_GRAPH_CACHE: dict[_GraphCacheKey, _GraphCacheEntry] = {}


def _resolved_graph_path(path: Path) -> Path:
    try:
        return Path(path).resolve()
    except (OSError, RuntimeError):
        return Path(path).absolute()


def _drop_graph_cache_entries(resolved: Path) -> None:
    resolved_key = str(resolved)
    for key in [cached_key for cached_key in _GRAPH_CACHE if cached_key[0] == resolved_key]:
        del _GRAPH_CACHE[key]


def _cache_graph(path: Path, entities: list[dict[str, Any]]) -> None:
    """Record a parse of path for the default (schema-current) load mode."""
    resolved = _resolved_graph_path(path)
    try:
        info = resolved.stat()
    except OSError:
        _drop_graph_cache_entries(resolved)
        return
    # Writing a graph invalidates every cached parse of that path (including the
    # legacy-mode one), even if the new stat signature happens to look identical.
    _drop_graph_cache_entries(resolved)
    _GRAPH_CACHE[(str(resolved), False)] = (
        (info.st_mtime_ns, info.st_size),
        deepcopy(entities),
    )


def load_entity_graph(
    path: Path,
    *,
    allow_legacy_entity_types: bool = False,
) -> list[dict[str, Any]]:
    resolved = _resolved_graph_path(path)
    try:
        info = resolved.stat()
    except OSError:
        # The graph disappeared (or was never there): do not serve a stale parse.
        _drop_graph_cache_entries(resolved)
        return []

    signature = (info.st_mtime_ns, info.st_size)
    key = (str(resolved), allow_legacy_entity_types)
    cached = _GRAPH_CACHE.get(key)
    if cached is not None and cached[0] == signature:
        return deepcopy(cached[1])

    with resolved.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {"entities": []}

    entities = validate_entity_graph_payload(
        payload,
        allow_legacy_entity_types=allow_legacy_entity_types,
    )
    # Keep a private copy so a caller mutating the returned list (several write
    # paths edit entity dicts in place before saving) cannot corrupt the memo.
    _GRAPH_CACHE[key] = (signature, deepcopy(entities))
    return entities


def save_entity_graph(entities: list[dict[str, Any]], path: Path) -> None:
    validated = validate_entity_graph_payload({"entities": entities})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump({"entities": validated}, f, allow_unicode=True, sort_keys=False)
    _cache_graph(path, validated)


def resolve_entity(query: str, graph: list[dict[str, Any]]) -> dict[str, Any] | None:
    needle = query.strip()
    for entity in graph:
        if needle in {entity["id"], entity["primary_name"], *entity.get("aliases", [])}:
            return entity
    return None


def resolve_relationship(
    source_id: str, relation: str, graph: list[dict[str, Any]]
) -> dict[str, Any] | None:
    source = resolve_entity(source_id, graph)
    if source is None:
        return None

    for relationship in source.get("relationships", []):
        if relationship.get("relation") == relation:
            return resolve_entity(relationship["target"], graph)
    return None


def check_graph_status(graph_path: Path) -> dict[str, Any]:
    """
    Check entity graph initialization status.

    Returns:
        {
            "status": "initialized" | "not_initialized" | "empty",
            "entity_count": int,
            "suggested_action": dict | None,
        }
    """
    result: dict[str, Any] = {
        "status": "not_initialized",
        "entity_count": 0,
        "suggested_action": {
            "command": BUILD_FROM_JOURNALS_PREVIEW_COMMAND,
            "reason": (
                "entity graph not found; preview journal-derived candidates before any graph write"
            ),
        },
    }

    if not graph_path.exists():
        return result

    try:
        entities = load_entity_graph(graph_path)
    except EntityGraphValidationError as exc:
        result["status"] = "not_initialized"
        if exc.code == "ENTITY_SCHEMA_LEGACY":
            result["suggested_action"] = {
                "command": "life-index entity maintain --normalize --preview --json",
                "reason": (
                    "entity graph uses legacy entity types; preview maintain --normalize "
                    "before applying a schema cutover migration"
                ),
            }
            return result
        result["suggested_action"] = {
            "command": BUILD_FROM_JOURNALS_PREVIEW_COMMAND,
            "reason": (
                "entity graph is invalid or legacy; "
                "search will continue without graph expansion until it is repaired; "
                "use preview-only build output before choosing any write path"
            ),
        }
        return result

    result["entity_count"] = len(entities)

    if len(entities) == 0:
        result["status"] = "empty"
        return result

    result["status"] = "initialized"
    result["suggested_action"] = None
    return result
