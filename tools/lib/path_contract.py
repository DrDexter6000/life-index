#!/usr/bin/env python3
"""Shared journal path normalization helpers."""

import os
from pathlib import Path
from typing import Any, Dict


def _normalize_slashes(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def safe_relative_path(path: Path | str, base: Path | str) -> str:
    """Return a normalized relative path when possible, else normalized absolute path.

    The fast path is a string-prefix comparison. It may only be used when its
    result is guaranteed identical to the lexical ``Path.relative_to`` rule:
    both arguments must already be ``Path`` objects, whose string form is
    normalized (separators collapsed, ``.`` removed). A raw string such as
    ``"foo//bar"`` keeps doubled separators, and the prefix fast path would
    then return a different relative string. Anything else falls back.
    """
    if isinstance(path, Path) and isinstance(base, Path):
        path_str = str(path)
        base_str = str(base)
        if base_str:
            separator = os.sep
            normalized_path = path_str.replace("/", separator).replace("\\", separator)
            normalized_base = (
                base_str.replace("/", separator).replace("\\", separator).rstrip(separator)
            )
            prefix = normalized_base + separator
            if normalized_path.startswith(prefix):
                return normalized_path[len(prefix) :].replace(separator, "/")
    path_obj = Path(path)
    base_obj = Path(base)
    try:
        return _normalize_slashes(path_obj.relative_to(base_obj))
    except ValueError:
        return _normalize_slashes(path_obj)


def build_journal_path_fields(
    file_path: Path | str, *, journals_dir: Path, user_data_dir: Path
) -> Dict[str, str]:
    """Build consistent absolute/user-relative/route-relative path fields."""
    path_obj = Path(file_path)

    absolute_path = _normalize_slashes(path_obj)

    rel_path = safe_relative_path(path_obj, user_data_dir)

    try:
        journal_route_path = _normalize_slashes(path_obj.relative_to(journals_dir))
    except ValueError:
        if rel_path.startswith("Journals/"):
            journal_route_path = rel_path[len("Journals/") :]
        else:
            journal_route_path = rel_path

    return {
        "path": absolute_path,
        "rel_path": rel_path,
        "journal_route_path": journal_route_path,
    }


def merge_journal_path_fields(
    payload: Dict[str, Any],
    file_path: Path | str,
    *,
    journals_dir: Path,
    user_data_dir: Path,
) -> Dict[str, Any]:
    """Return payload merged with normalized path fields."""
    result = dict(payload)
    result.update(
        build_journal_path_fields(file_path, journals_dir=journals_dir, user_data_dir=user_data_dir)
    )
    return result
