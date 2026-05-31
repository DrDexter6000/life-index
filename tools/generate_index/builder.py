#!/usr/bin/env python3
"""Shared deterministic Index Tree model builder.

This module builds machine-readable node data from journals and existing index
tree freshness metadata. It is read-only and does not define a public CLI
contract by itself.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from tools.generate_index.navigation import IndexNode, build_month_node_ref, enumerate_index_nodes
from tools.lib.frontmatter import parse_frontmatter
from tools.lib.paths import get_user_data_dir

NAVIGABLE_SIGNALS = ("topic", "people", "project")


def safe_relative_path(path: Path, data_dir: Path | None = None) -> str:
    """Return a POSIX relative path confined to the Life Index data dir."""
    root = data_dir or get_user_data_dir()
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return ""
    if not rel or any(part == ".." for part in PurePosixPath(rel).parts):
        return ""
    if rel.startswith("/") or rel.startswith("//") or re.match(r"^[A-Za-z]:/", rel):
        return ""
    return rel


def _parse_file_frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    if not text.startswith("---\n"):
        return {}
    try:
        metadata, _body = parse_frontmatter(text)
    except (TypeError, ValueError):
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _iter_field_values(value: Any) -> Iterable[str]:
    if isinstance(value, list):
        for item in value:
            text = str(item).strip()
            if text:
                yield text
        return
    text = str(value or "").strip()
    if text:
        yield text


def _journal_files_for_node(node: IndexNode, data_dir: Path) -> list[Path]:
    journals_dir = data_dir / "Journals"
    if node.level == "root":
        scope_dir = journals_dir
    elif node.level == "year" and node.year is not None:
        scope_dir = journals_dir / f"{node.year:04d}"
    elif node.level == "month" and node.year is not None and node.month is not None:
        scope_dir = journals_dir / f"{node.year:04d}" / f"{node.month:02d}"
    else:
        return []
    if not scope_dir.exists():
        return []
    return sorted(scope_dir.rglob("life-index_*.md"))


def _entry_node_ref(node: IndexNode) -> dict[str, str] | None:
    if node.year is None or node.month is None:
        return None
    return build_month_node_ref(f"{node.year:04d}", f"{node.month:02d}")


def _entry_ref(path: Path, node: IndexNode, data_dir: Path) -> dict[str, Any] | None:
    rel = safe_relative_path(path, data_dir)
    if not rel:
        return None
    metadata = _parse_file_frontmatter(path)
    signals = {field: list(_iter_field_values(metadata.get(field))) for field in NAVIGABLE_SIGNALS}
    payload: dict[str, Any] = {
        "relative_path": rel,
        "date": str(metadata.get("date", "")) if metadata.get("date") is not None else "",
        "title": str(metadata.get("title", "")) if metadata.get("title") is not None else "",
        "signals": {k: v for k, v in signals.items() if v},
    }
    node_ref = _entry_node_ref(node)
    if node_ref is not None:
        payload["node_ref"] = node_ref
    return payload


def _signal_counts(entries: list[dict[str, Any]], field: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for entry in entries:
        counter.update(entry.get("signals", {}).get(field, []))
    return dict(counter.most_common())


def _signal_coverage(entries: list[dict[str, Any]], field: str) -> dict[str, int]:
    present = 0
    parseable = 0
    for entry in entries:
        values = entry.get("signals", {}).get(field, [])
        if values:
            present += 1
            parseable += 1
    return {
        "entries_in_scope": len(entries),
        "present": present,
        "parseable": parseable,
    }


def _node_model(node: IndexNode, data_dir: Path) -> dict[str, Any]:
    entries = [
        entry
        for path in _journal_files_for_node(node, data_dir)
        for entry in [_entry_ref(path, node, data_dir)]
        if entry is not None
    ]
    return {
        "node_id": node.node_id,
        "level": node.level,
        "relative_path": safe_relative_path(node.path, data_dir),
        "year": node.year,
        "month": node.month,
        "entry_count": node.entry_count,
        "date_range": node.date_range,
        "has_index": node.has_index,
        "freshness": node.freshness,
        "topics": node.topics,
        "entry_refs": entries,
        "frontmatter_signals": {
            "topic_counts": _signal_counts(entries, "topic"),
            "people_counts": _signal_counts(entries, "people"),
            "project_counts": _signal_counts(entries, "project"),
        },
        "signal_coverage": {field: _signal_coverage(entries, field) for field in NAVIGABLE_SIGNALS},
    }


def build_index_tree_model(level: str = "all") -> dict[str, Any]:
    """Build a deterministic, journal-derived Index Tree model."""
    data_dir = get_user_data_dir()
    nodes = [_node_model(node, data_dir) for node in enumerate_index_nodes(level=level)]
    return {
        "source": {"truth_source": "journals", "builder": "deterministic"},
        "level": level,
        "nodes": nodes,
    }
