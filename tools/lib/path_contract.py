#!/usr/bin/env python3
"""Shared journal path normalization helpers."""

from pathlib import Path
from typing import Any, Dict


def _normalize_slashes(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def safe_relative_path(path: Path | str, base: Path | str) -> str:
    """Return a normalized relative path when possible, else normalized absolute path."""
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
