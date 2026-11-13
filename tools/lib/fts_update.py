#!/usr/bin/env python3
"""
Life Index - FTS Update Module
FTS5 索引更新功能

从 search_index.py 提取的索引构建/更新逻辑。

增量扫描以文件 (mtime, size) 签名（fts_file_stats 侧表）判定"未变更"，
只读取新增/变更文件；insert_fts_doc 是 "file → FTS row" 的唯一插入路径，
全量重建与写入/编辑后的单行写穿共用它。
"""

import hashlib
import logging
import sqlite3
import time as _time_module
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_REBUILD_MARKER_NAME = ".rebuilding"
_STALE_MARKER_TIMEOUT_S = 300

from .chinese_tokenizer import segment_for_fts
from .frontmatter import parse_frontmatter
from .journal_files import iter_journal_files
from .path_contract import build_journal_path_fields, safe_relative_path


def get_file_hash(file_path: Path) -> str:
    """计算文件内容哈希，用于检测变更"""
    try:
        content = file_path.read_bytes()
        return hashlib.md5(content, usedforsecurity=False).hexdigest()[:16]
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

        # MD3: Only segment title + content for FTS; metadata columns stay raw.
        # file_hash is computed from original file content, NOT segmented text.
        # R11 fix: 'title' stores raw original text (for display),
        # 'title_segmented' stores jieba tokens (for FTS matching).
        raw_title = metadata.get("title", "")
        segmented_title = segment_for_fts(raw_title, mode="index")
        segmented_content = segment_for_fts(body, mode="index")

        doc = {
            "path": path_fields["rel_path"],
            "title": raw_title,
            "title_segmented": segmented_title,
            "content": segmented_content,
            "date": metadata.get("date", "")[:10],
            "location": metadata.get("location", ""),
            "weather": metadata.get("weather", ""),
            "topic": _normalize_to_str(metadata.get("topic")),
            "project": metadata.get("project", ""),
            "tags": _normalize_to_str(metadata.get("tags")),
            "mood": _normalize_to_str(metadata.get("mood")),
            "people": _normalize_to_str(metadata.get("people")),
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


def get_file_stats(conn: sqlite3.Connection) -> dict[str, tuple[float, int]]:
    """获取已记录的文件签名（路径 -> (mtime, size)，来自 fts_file_stats 侧表）。"""
    cursor = conn.cursor()
    cursor.execute("SELECT path, mtime, size FROM fts_file_stats")

    result = {}
    for row in cursor.fetchall():
        result[row[0]] = (row[1], row[2])

    return result


def record_file_stat(cursor: sqlite3.Cursor, file_path: Path, rel_path: str) -> None:
    """记录文件当前 (mtime, size) 签名，供下次增量扫描做 stat-only 判定。"""
    stat = file_path.stat()
    cursor.execute(
        "INSERT OR REPLACE INTO fts_file_stats (path, mtime, size) VALUES (?, ?, ?)",
        (rel_path, stat.st_mtime, stat.st_size),
    )


def insert_fts_doc(cursor: sqlite3.Cursor, doc: dict[str, Any]) -> None:
    """插入一条 FTS 行（"file → FTS row" 的唯一插入路径）。

    全量重建与写入/编辑后的单行写穿共用本函数，保证两条路径产出的行
    逐列一致（含真实 file_hash 与文件真实 mtime）。
    """
    cursor.execute(
        """
                    INSERT INTO journals (
                        path, title, title_segmented, content, date, location, weather,
                        topic, project, tags, mood, people,
                        file_hash, modified_time
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
        (
            doc["path"],
            doc["title"],
            doc["title_segmented"],
            doc["content"],
            doc["date"],
            doc["location"],
            doc["weather"],
            doc["topic"],
            doc["project"],
            doc["tags"],
            doc["mood"],
            doc["people"],
            doc["file_hash"],
            doc["modified_time"],
        ),
    )


def _check_rebuild_marker(fts_db_path: Path) -> Path:
    """Return marker path. Raise if active rebuild detected."""
    marker = fts_db_path.parent / _REBUILD_MARKER_NAME
    if marker.exists():
        try:
            mtime = marker.stat().st_mtime
            age = _time_module.time() - mtime
            if age >= _STALE_MARKER_TIMEOUT_S:
                logger.warning("Removing stale rebuild marker (age=%.0fs)", age)
                marker.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to inspect rebuild marker %s: %s", marker, exc)
    return marker


def _write_rebuild_marker(marker: Path) -> None:
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"{_time_module.time()}", encoding="utf-8")


def _remove_rebuild_marker(marker: Path) -> None:
    try:
        marker.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed to remove rebuild marker %s: %s", marker, exc)


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

    marker: Path | None = None
    marker_written = False

    try:
        if not incremental:
            marker = _check_rebuild_marker(fts_db_path)
            if marker.exists():
                result["error"] = "rebuild already in progress"
                result["rebuild_in_progress"] = True
                return result
            _write_rebuild_marker(marker)
            marker_written = True

        conn = init_fts_db_func()
        cursor = conn.cursor()

        # 获取当前已索引的文件与已记录的文件签名
        indexed_files = get_indexed_files(conn)
        indexed_stats = get_file_stats(conn)

        # 扫描所有日志文件（仅经 journal_files 枚举；以 (mtime, size) stat-only
        # 判定是否变更——未变更的文件不再被读取或哈希）。
        current_files = set()
        files_to_update = []

        if journals_dir.exists():
            for journal_file in iter_journal_files(journals_dir):
                rel_path = safe_relative_path(journal_file, user_data_dir)
                current_files.add(rel_path)

                stat = journal_file.stat()
                if indexed_stats.get(rel_path) == (stat.st_mtime, stat.st_size):
                    # 签名未变 → 视为未变更，不读文件内容
                    continue

                if rel_path not in indexed_files:
                    # 新文件
                    files_to_update.append(("add", journal_file, rel_path))
                else:
                    # 文件已修改（或签名记录缺失，保守起见重读）
                    files_to_update.append(("update", journal_file, rel_path))

        # 找出需要删除的索引（文件已不存在；含孤儿签名行）
        files_to_remove = (set(indexed_files.keys()) | set(indexed_stats)) - current_files

        # 如果不是增量模式，清空所有索引
        if not incremental:
            cursor.execute("DELETE FROM journals")
            cursor.execute("DELETE FROM fts_file_stats")
            files_to_remove = set()
            files_to_update = [("add", user_data_dir / p, p) for p in current_files]
            result["removed"] = len(indexed_files)

        # 执行删除
        for rel_path in files_to_remove:
            cursor.execute("DELETE FROM journals WHERE path = ?", (rel_path,))
            cursor.execute("DELETE FROM fts_file_stats WHERE path = ?", (rel_path,))
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

                # 插入新记录并记录签名
                insert_fts_doc(cursor, doc)
                try:
                    record_file_stat(cursor, file_path, rel_path)
                except OSError:
                    # 记录签名失败只影响下次扫描多读一次，不阻断本次构建
                    logger.warning("Failed to record file stat for %s", rel_path)

        conn.commit()
        conn.close()

        # 更新总数
        result["total"] = len(current_files)
        result["success"] = True

    except (OSError, IOError, sqlite3.Error) as e:
        result["error"] = str(e)
    finally:
        if marker is not None and marker_written:
            _remove_rebuild_marker(marker)

    return result
