#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - Utilities
通用工具函数模块
"""

from pathlib import Path
from typing import Any, Dict, Tuple

# SSOT: 使用 lib/frontmatter 进行 frontmatter 解析 (relative imports)
from ..lib.frontmatter import parse_frontmatter as _parse_frontmatter


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """解析 YAML frontmatter，返回 (metadata, body)

    此函数是 lib.frontmatter.parse_frontmatter 的包装，用于保持向后兼容。
    """
    return _parse_frontmatter(content)


def annotate_kind_and_display_label(items: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Attach ``kind`` and ``display_label`` to pointer-derived result items.

    A result that comes from a derived pointer (a by-topic index line, an FTS
    row) has no journal body in hand, so its label comes from the metadata
    cache by path; when there is no row the label is the file name without
    extension. The kind is the file-name kind. Items that already carry both
    fields are left untouched (idempotent), so producers that computed the
    label from the body keep theirs. Never opens a journal file.
    """
    from ..lib.journal_files import classify_journal_path
    from ..lib.metadata_cache import get_display_labels_for_keys
    from ..lib.path_contract import build_journal_path_fields
    from ..lib.paths import get_journals_dir, get_user_data_dir

    def _item_path(item: Dict[str, Any]) -> str:
        return str(item.get("path") or item.get("rel_path") or "")

    label_items: list[Dict[str, Any]] = []
    keys: list[str] = []
    for item in items:
        if "kind" not in item:
            item["kind"] = classify_journal_path(Path(_item_path(item))).value
        if not item.get("display_label"):
            label_items.append(item)
            keys.append(
                build_journal_path_fields(
                    Path(_item_path(item)),
                    journals_dir=get_journals_dir(),
                    user_data_dir=get_user_data_dir(),
                )["path"]
            )

    if keys:
        labels = get_display_labels_for_keys(keys)
        for item, key in zip(label_items, keys):
            item["display_label"] = labels.get(key) or Path(_item_path(item)).stem
    return items
