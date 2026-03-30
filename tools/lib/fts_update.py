#!/usr/bin/env python3
"""
Life Index - FTS Update Module
FTS5 索引更新功能

从 search_index.py 提取的索引构建/更新逻辑。
"""

import hashlib
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

from .frontmatter import parse_frontmatter
from .path_contract import build_journal_path_fields


def get_file_hash(file_path: Path) -> str:
    """计算文件内容哈希，用于检测变更"""
    try:
        content = file_path.read_bytes()
        return hashlib.md5(content).hexdigest()[:16]
    except (OSError, IOError):
        return ""


def _normalize_to_str(value: Any) -> str:
    """将值规范化为字符串"""
    if not value:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def parse_journal(
    file_path: Path, journals_dir: Path, user_data_dir: Path
) -> dict[str, Any] | None:
    """解析日志文件，提取可索引内容"""
    try:
        content = file_path.read_text(encoding="utf-8")

        if not content.startswith("---"):
            return None

        # 使用 SSOT frontmatter 解析
        metadata, body = parse_frontmatter(content)

        if not metadata:
            return None

        # 构建可索引文档
        path_fields = build_journal_path_fields(
            file_path, journals_dir=journals_dir, user_data_dir=user_data_dir
        )
        doc = {
            "path": path_fields["rel_path"],
            "title": metadata.get("title", ""),
            "content": body,
            "date": metadata.get("date", "")[:10],
            "location": metadata.get("location", ""),
            "weather": metadata.get("weather", ""),
            "topic": _normalize_to_str(metadata.get("topic")),
            "project": metadata.get("project", ""),
            "tags": _normalize_to_str(metadata.get("tags")),
            "file_hash": get_file_hash(file_path),
            "modified_time": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
        }

        return doc

    except (OSError, IOError, ValueError) as e:
        logger.warning("Failed to parse %s: %s", file_path, e)
        return None


def get_indexed_files(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """获取已索引的文件列表（路径 -> (hash, modified_time)）"""
    cursor = conn.cursor()
    cursor.execute("SELECT path, file_hash, modified_time FROM journals")

    result = {}
    for row in cursor.fetchall():
        result[row[0]] = (row[1], row[2])

    return result


def update_index(
    init_fts_db_func: Callable[[], sqlite3.Connection],
    fts_db_path: Path,
    journals_dir: Path,
    user_data_dir: Path,
    incremental: bool = True,
) -> dict[str, Any]:
    """
    更新搜索索引

    Args:
        init_fts_db_func: 初始化 FTS 数据库的函数（来自 search_index.init_fts_db）
        fts_db_path: FTS 数据库路径
        journals_dir: 日志目录
        user_data_dir: 用户数据目录
        incremental: True=仅更新变更，False=全量重建

    Returns:
        {
            "success": bool,
            "added": int,
            "updated": int,
            "removed": int,
            "total": int,
            "error": str (optional)
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "added": 0,
        "updated": 0,
        "removed": 0,
        "total": 0,
        "error": None,
    }

    try:
        conn = init_fts_db_func()
        cursor = conn.cursor()

        # 获取当前已索引的文件
        indexed_files = get_indexed_files(conn)

        # 扫描所有日志文件
        current_files = set()
        files_to_update = []

        if journals_dir.exists():
            for year_dir in journals_dir.iterdir():
                if not year_dir.is_dir() or not year_dir.name.isdigit():
                    continue

                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue

                    for journal_file in month_dir.glob("life-index_*.md"):
                        rel_path = str(journal_file.relative_to(user_data_dir)).replace("\\", "/")
                        current_files.add(rel_path)

                        # 检查是否需要更新
                        file_hash = get_file_hash(journal_file)

                        if rel_path not in indexed_files:
                            # 新文件
                            files_to_update.append(("add", journal_file, rel_path))
                        elif indexed_files[rel_path][0] != file_hash:
                            # 文件已修改
                            files_to_update.append(("update", journal_file, rel_path))

        # 找出需要删除的索引（文件已不存在）
        files_to_remove = set(indexed_files.keys()) - current_files

        # 如果不是增量模式，清空所有索引
        if not incremental:
            cursor.execute("DELETE FROM journals")
            files_to_remove = set()
            files_to_update = [("add", user_data_dir / p, p) for p in current_files]
            result["removed"] = len(indexed_files)

        # 执行删除
        for rel_path in files_to_remove:
            cursor.execute("DELETE FROM journals WHERE path = ?", (rel_path,))
            result["removed"] = (result["removed"] or 0) + 1

        # 执行添加/更新
        for action, file_path, rel_path in files_to_update:
            doc = parse_journal(file_path, journals_dir, user_data_dir)
            if doc:
                # 如果是更新，先删除旧记录
                if action == "update":
                    cursor.execute("DELETE FROM journals WHERE path = ?", (rel_path,))
                    result["updated"] = (result["updated"] or 0) + 1
                else:
                    result["added"] = (result["added"] or 0) + 1

                # 插入新记录
                cursor.execute(
                    """
                    INSERT INTO journals (path, title, content, date, location, weather,
                                        topic, project, tags, file_hash, modified_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        doc["path"],
                        doc["title"],
                        doc["content"],
                        doc["date"],
                        doc["location"],
                        doc["weather"],
                        doc["topic"],
                        doc["project"],
                        doc["tags"],
                        doc["file_hash"],
                        doc["modified_time"],
                    ),
                )

        conn.commit()
        conn.close()

        # 更新总数
        result["total"] = len(current_files)
        result["success"] = True

    except (OSError, IOError, sqlite3.Error) as e:
        result["error"] = str(e)

    return result
