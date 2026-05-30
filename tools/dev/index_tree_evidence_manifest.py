#!/usr/bin/env python3
"""Private read-only Index Tree Evidence Navigation manifest prototype."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from tools.generate_index.navigation import IndexNode, enumerate_index_nodes
from tools.lib.frontmatter import parse_frontmatter
from tools.lib.paths import get_user_data_dir

SCHEMA_VERSION = "index_tree_evidence_manifest.dev.v0"
COMMAND = "dev.index_tree_evidence_manifest"
VALID_LEVELS = {"root", "year", "month", "all"}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m tools.dev.index_tree_evidence_manifest",
        description="Private read-only Index Tree Evidence Navigation manifest prototype.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--level",
        choices=sorted(VALID_LEVELS),
        default="all",
        help="Index Tree level to inspect.",
    )
    return parser.parse_args(argv)


def _limitations() -> list[str]:
    return [
        "Private dev artifact; not a public CLI/API contract.",
        "Navigation signals are deterministic frontmatter counts, not narrative truth.",
        "No LLM interpretation, persona judgment, or relationship judgment was performed.",
    ]


def _error_payload(code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "source": {"builder": "prototype", "public_contract": False},
        "nodes": [],
        "limitations": _limitations(),
        "error": {"code": code, "message": message, "details": {}},
    }


def _safe_rel_path(path: Path, data_dir: Path) -> str:
    try:
        rel = path.resolve().relative_to(data_dir.resolve()).as_posix()
    except ValueError:
        return ""
    if not rel or any(part == ".." for part in PurePosixPath(rel).parts):
        return ""
    if rel.startswith("/") or rel.startswith("//") or re.match(r"^[A-Za-z]:/", rel):
        return ""
    return rel


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _parse_file_frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    if not text.startswith("---\n"):
        return {}
    try:
        metadata, _body = parse_frontmatter(text)
    except (ValueError, TypeError):
        return {}
    return metadata


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


def _count_field(entries: list[dict[str, Any]], field: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for entry in entries:
        counter.update(_iter_field_values(entry.get(field)))
    return dict(counter.most_common())


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


def _manifest_node(node: IndexNode, data_dir: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    entry_refs: list[str] = []
    entry_hashes: dict[str, str] = {}
    node_relative_path = _safe_rel_path(node.path, data_dir)
    for path in _journal_files_for_node(node, data_dir):
        rel = _safe_rel_path(path, data_dir)
        if not rel:
            continue
        entry_refs.append(rel)
        file_hash = _sha256_file(path)
        if file_hash is not None:
            entry_hashes[rel] = file_hash
        entries.append(_parse_file_frontmatter(path))

    return {
        "node_id": node.node_id,
        "level": node.level,
        "relative_path": node_relative_path,
        "year": node.year,
        "month": node.month,
        "entry_count": node.entry_count,
        "date_range": node.date_range,
        "has_index": node.has_index,
        "freshness": node.freshness,
        "entry_refs": entry_refs,
        "frontmatter_signals": {
            "topic_counts": _count_field(entries, "topic"),
            "people_counts": _count_field(entries, "people"),
            "project_counts": _count_field(entries, "project"),
        },
        "source_hashes": {
            "index": _sha256_file(node.path) if node_relative_path else None,
            "entries": entry_hashes,
        },
    }


def build_manifest(level: str = "all") -> dict[str, Any]:
    if level not in VALID_LEVELS:
        return _error_payload(
            "INDEX_TREE_MANIFEST_INVALID_LEVEL",
            f"level must be one of {sorted(VALID_LEVELS)}, got '{level}'",
        )
    data_dir = get_user_data_dir()
    nodes = [_manifest_node(node, data_dir) for node in enumerate_index_nodes(level=level)]
    return {
        "success": True,
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "source": {"builder": "prototype", "public_contract": False},
        "nodes": nodes,
        "limitations": _limitations(),
        "error": None,
    }


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    payload = build_manifest(level=str(args.level))
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for node in payload.get("nodes", []):
        if isinstance(node, dict):
            print(f"{node.get('node_id')} {node.get('freshness')} {node.get('relative_path')}")


if __name__ == "__main__":
    main(sys.argv[1:])
