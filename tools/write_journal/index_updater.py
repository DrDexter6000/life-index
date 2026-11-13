#!/usr/bin/env python3
"""
Life Index - Write Journal Tool - Index Updater
索引更新模块
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..lib.config import get_index_prefixes
from ..lib.paths import get_by_topic_dir, get_user_data_dir
from ..lib.errors import ErrorCode, create_error_response
from ..lib.frontmatter import get_summary
from ..lib.journal_files import display_label
from ..lib.path_contract import safe_relative_path
from ..lib.text_normalize import normalize_text_list


def _build_entry(data: Dict[str, Any], journal_path: Path) -> str:
    """Build a by-topic entry line with optional summary.

    The bracket text is the one display label (title, else first body line,
    else file name); ``title`` itself is never invented here.
    """
    date_str = data.get("date", "")[:10]
    title = display_label(
        str(data.get("title") or ""), str(data.get("content") or ""), journal_path
    )
    rel_path = safe_relative_path(journal_path, get_user_data_dir())
    summary = get_summary(data) or ""
    if summary:
        return f"- [{date_str}] [{title}]({rel_path}) — {summary}"
    return f"- [{date_str}] [{title}]({rel_path})"


def _sanitize_index_name(value: str) -> str:
    text = str(value or "").strip()
    return text.replace("/", "_").replace("\\", "_")


def sanitize_index_name(value: str) -> str:
    """Public SSOT helper for index-safe topic/project/tag names."""
    return _sanitize_index_name(value)


def build_index_filename(kind: str, value: str) -> str:
    prefixes = get_index_prefixes()
    default_prefixes = {"topic": "主题_", "project": "项目_", "tag": "标签_"}
    prefix = prefixes.get(kind, default_prefixes[kind])
    safe_value = sanitize_index_name(value)
    return f"{prefix}{safe_value}.md"


def update_topic_index(topic: Any, journal_path: Path, data: Dict[str, Any]) -> List[Path]:
    """更新主题索引文件 - 支持单个主题或主题列表"""
    topics = normalize_text_list(topic)
    if not topics:
        return []

    entry = _build_entry(data, journal_path)

    updated = []
    for t in topics:
        if not t:
            continue
        get_by_topic_dir().mkdir(parents=True, exist_ok=True)
        index_file = get_by_topic_dir() / build_index_filename("topic", str(t))

        if index_file.exists():
            content = index_file.read_text(encoding="utf-8")
            if entry not in content:
                with open(index_file, "a", encoding="utf-8") as f:
                    f.write(entry + "\n")
        else:
            with open(index_file, "w", encoding="utf-8") as f:
                f.write(f"# 主题: {t}\n\n")
                f.write(entry + "\n")

        updated.append(index_file)

    return updated


def update_project_index(project: str, journal_path: Path, data: Dict[str, Any]) -> Optional[Path]:
    """更新项目索引文件"""
    if not project:
        return None

    # 获取可配置的前缀
    get_by_topic_dir().mkdir(parents=True, exist_ok=True)
    index_file = get_by_topic_dir() / build_index_filename("project", project)

    entry = _build_entry(data, journal_path)

    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        if entry not in content:
            with open(index_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
    else:
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(f"# 项目: {project}\n\n")
            f.write(entry + "\n")

    return index_file


def update_tag_indices(tags: Any, journal_path: Path, data: Dict[str, Any]) -> List[Path]:
    """更新标签索引文件"""
    updated = []

    # 获取可配置的前缀
    for tag in normalize_text_list(tags):
        if not tag:
            continue

        get_by_topic_dir().mkdir(parents=True, exist_ok=True)
        index_file = get_by_topic_dir() / build_index_filename("tag", str(tag))

        entry = _build_entry(data, journal_path)

        if index_file.exists():
            content = index_file.read_text(encoding="utf-8")
            if entry not in content:
                with open(index_file, "a", encoding="utf-8") as f:
                    f.write(entry + "\n")
        else:
            with open(index_file, "w", encoding="utf-8") as f:
                f.write(f"# 标签: {tag}\n\n")
                f.write(entry + "\n")

        updated.append(index_file)

    return updated


def update_index(year: int, month: int, dry_run: bool = False) -> Dict[str, Any]:
    """
    Update index tree after journal write.

    Touches 3 files:
    1. index_YYYY-MM.md — monthly index
    2. index_YYYY.md — yearly index
    3. INDEX.md — root anchor

    Args:
        year: Year
        month: Month
        dry_run: Preview mode

    Returns:
        {
            "success": bool,
            "monthly_index": dict,
            "yearly_index": dict,
            "root_index": dict,
        }
    """
    from ..generate_index import (
        generate_monthly_index,
        generate_yearly_index,
        generate_root_index,
    )

    result: Dict[str, Any] = {"success": True}

    try:
        # 1. Monthly index
        monthly = generate_monthly_index(year=year, month=month, dry_run=dry_run)
        result["monthly_index"] = monthly

        # 2. Yearly index
        yearly = generate_yearly_index(year=year, dry_run=dry_run)
        result["yearly_index"] = yearly

        # 3. Root index
        root = generate_root_index(dry_run=dry_run)
        result["root_index"] = root

        # Mark degraded if any layer failed
        if not all(r.get("success", False) for r in [monthly, yearly, root] if r is not None):
            result["success"] = False

    except Exception as e:
        result["success"] = False
        result.update(
            create_error_response(
                ErrorCode.INDEX_BUILD_FAILED,
                f"Index tree update failed: {e}",
                {"year": year, "month": month},
                "Index update is non-blocking; next write or rebuild will retry",
            )
        )

    return result


def refresh_index_b(dry_run: bool = False) -> Dict[str, Any]:
    """Refresh deterministic Index B navigation docs after journal changes.

    Index B is rebuildable derived data. Refresh failures must be visible but
    non-blocking for write/edit flows; consumers can still fall back to journal
    pointers through index-tree ensure.
    """

    try:
        from ..index_tree.materialize import build_materialize_payload

        payload = build_materialize_payload(dry_run=dry_run, incremental=True)
        return {
            "success": True,
            "updated": not dry_run,
            "artifact": "index-b",
            "payload": payload,
        }
    except Exception as exc:
        return {
            "success": False,
            "updated": False,
            "artifact": "index-b",
            **create_error_response(
                ErrorCode.INDEX_BUILD_FAILED,
                f"Index B refresh failed: {exc}",
                {},
                "Index B refresh is non-blocking; run life-index index-tree ensure to retry",
            ),
        }


# Backward-compatible alias
update_monthly_abstract = update_index


def update_vector_index(journal_path: Path, data: Dict[str, Any]) -> bool:
    """Deprecated compatibility no-op.

    Life Index no longer maintains an in-tool vector index.  The function
    remains importable for older callers, but it intentionally performs no
    embedding/model work and reports successful no-op completion.
    """
    _ = (journal_path, data)
    return True
