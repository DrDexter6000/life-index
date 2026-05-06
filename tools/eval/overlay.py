#!/usr/bin/env python3
"""Private eval overlay loader for golden_queries.yaml.

Allows local production data to override public anonymized eval expectations
without modifying committed artifacts or leaking privacy into the repo.
"""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def get_default_overlay_path() -> Path:
    """Return the default private overlay path in the user's data directory."""
    return Path.home() / "Documents" / "Life-Index" / "eval" / "golden_queries.local.yaml"


def is_ci_environment() -> bool:
    """Return True if running in a CI environment."""
    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def load_overlay(path: Path | None = None) -> dict[str, Any] | None:
    """Load a private eval overlay from YAML.

    Returns None if the file does not exist.
    Raises ValueError on schema errors (fail-fast).
    """
    overlay_path = path or get_default_overlay_path()
    if not overlay_path.exists():
        return None

    raw = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"Overlay file must contain a YAML mapping, got {type(raw).__name__}")

    return raw


def _to_list(value: Any) -> list[Any]:
    """Normalize a scalar or list value to a list."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _validate_overlay_schema(overlay: dict[str, Any]) -> None:
    """Validate top-level overlay structure. Raises ValueError on errors."""
    if "queries" not in overlay:
        return
    queries_section = overlay["queries"]
    if not isinstance(queries_section, dict):
        raise ValueError("Overlay 'queries' must be a mapping of query_id -> fields")

    for qid, fields in queries_section.items():
        if not isinstance(fields, dict):
            raise ValueError(
                f"Overlay for query '{qid}' must be a mapping, got {type(fields).__name__}"
            )
        allowed_keys = {"must_contain_title_override", "expected_titles_add", "notes"}
        unknown = set(fields.keys()) - allowed_keys
        if unknown:
            raise ValueError(
                f"Overlay for query '{qid}' contains unknown keys: {sorted(unknown)}. "
                f"Allowed: {sorted(allowed_keys)}"
            )
        for key in ("must_contain_title_override", "expected_titles_add"):
            if key in fields:
                val = fields[key]
                if not isinstance(val, (str, list)):
                    raise ValueError(
                        f"Overlay '{key}' for query '{qid}' must be a string or list, "
                        f"got {type(val).__name__}"
                    )


def apply_overlay(
    queries: list[dict[str, Any]],
    overlay: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], int, list[str], set[str]]:
    """Apply a private overlay to a list of golden queries.

    Returns:
        (modified_queries, applied_count, warnings, applied_query_ids)
    """
    if overlay is None:
        return queries, 0, [], set()

    _validate_overlay_schema(overlay)

    queries_section = overlay.get("queries", {})
    if not queries_section:
        return queries, 0, [], set()

    applied_count = 0
    applied_query_ids: set[str] = set()
    warning_messages: list[str] = []

    # Deep-copy queries to avoid mutating the original list
    modified_queries = deepcopy(queries)
    modified_by_id = {str(q["id"]): q for q in modified_queries if "id" in q}

    for qid_str, fields in queries_section.items():
        if qid_str not in modified_by_id:
            warning_messages.append(f"Overlay references unknown query id: {qid_str}")
            continue

        query = modified_by_id[qid_str]
        expected = query.setdefault("expected", {})
        action_applied = False

        if "must_contain_title_override" in fields:
            expected["must_contain_title"] = [
                str(item) for item in _to_list(fields["must_contain_title_override"])
            ]
            applied_count += 1
            action_applied = True

        if "expected_titles_add" in fields:
            existing = expected.get("must_contain_title", [])
            if not isinstance(existing, list):
                existing = [str(existing)] if existing else []
            additions = [str(item) for item in _to_list(fields["expected_titles_add"])]
            merged = existing + [a for a in additions if a not in existing]
            expected["must_contain_title"] = merged
            applied_count += 1
            action_applied = True

        if "notes" in fields:
            query.setdefault("_local_notes", []).append(str(fields["notes"]))

        if action_applied:
            applied_query_ids.add(qid_str)

    return modified_queries, applied_count, warning_messages, applied_query_ids
