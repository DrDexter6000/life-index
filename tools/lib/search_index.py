#!/usr/bin/env python3
"""
Life Index - Search Index Module
SQLite FTS5 全文索引管理

特性:
- 增量更新：仅处理新增/修改的日志
- 自动初始化：首次使用时自动创建索引
- 降级路径：索引损坏时自动重建

架构说明:
- fts_search.py: 搜索功能
- fts_update.py: 索引构建/更新
- 本模块: 常量定义、初始化、统计、向后兼容包装器
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .paths import get_index_dir, get_fts_db_path, get_journals_dir, get_user_data_dir
from .chinese_tokenizer import get_dict_hash
from .search_constants import FTS_LIMIT, FTS_MIN_RELEVANCE, TOKENIZER_VERSION

# Bump this whenever the FTS table schema changes (columns added/removed).
# Ensures incremental updates auto-trigger a full rebuild when needed.
FTS_SCHEMA_VERSION: int = (
    2  # v2: title split into raw (UNINDEXED) + title_segmented (indexed)
)

# 索引存储目录 (deprecated: use get_index_dir() / get_fts_db_path())
INDEX_DIR = get_index_dir()  # deprecated: use get_index_dir()
FTS_DB_PATH = get_fts_db_path()  # deprecated: use get_fts_db_path()
USER_DATA_DIR = get_user_data_dir()  # deprecated: use get_user_data_dir()
JOURNALS_DIR = get_journals_dir()  # deprecated: use get_journals_dir()


def init_fts_db(*, force_recreate: bool = False) -> sqlite3.Connection:
    """Initialize FTS5 database.

    Args:
        force_recreate: If True, DROP the existing journals table before
            recreating it.  Needed when the schema has changed (e.g. new
            columns like mood/people) because ``CREATE VIRTUAL TABLE IF NOT
            EXISTS`` silently keeps the old schema.
    """
    get_index_dir().mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(get_fts_db_path()))
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    if force_recreate:
        try:
            cursor.execute("DROP TABLE IF EXISTS journals")
            conn.commit()
        except sqlite3.Error:
            pass

    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS journals USING fts5(
            path,
            title UNINDEXED,
            title_segmented,
            content,
            date,
            location,
            weather,
            topic,
            project,
            tags,
            mood,
            people,
            file_hash UNINDEXED,
            modified_time UNINDEXED
        )
    """)

    # 创建元数据表（记录索引状态）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    return conn


def ensure_fts_schema() -> Dict[str, Any]:
    """Check FTS schema version and auto-migrate if needed (D13).

    Detects old schema (v1: no title_segmented column) and triggers
    a full rebuild to v2 schema. Called automatically when the CLI
    or search tools open the FTS database.

    Migration strategy:
    1. PRAGMA table_info to check for title_segmented column
    2. If missing → drop old table → init v2 schema → rebuild from files
    3. Record migration in index_meta.migration_log

    Returns:
        dict with 'migrated': True/False and optional migration details.
    """
    result: Dict[str, Any] = {"migrated": False}

    if not get_fts_db_path().exists():
        return result

    try:
        conn = sqlite3.connect(str(get_fts_db_path()))
        cursor = conn.cursor()

        # Check if title_segmented column exists
        cursor.execute("PRAGMA table_info(journals)")
        columns = {row[1] for row in cursor.fetchall()}

        if "title_segmented" in columns:
            # Already v2 schema, no migration needed
            conn.close()
            return result

        # v1 schema detected — need migration
        import logging
        from datetime import datetime, timezone

        logger = logging.getLogger(__name__)
        logger.info("[migration] FTS schema upgrade: title column split (v1 → v2)")

        # Record migration log before destructive operation
        migration_log = {
            "from": "v1_title_only",
            "to": "v2_title_split",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        cursor.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            ("migration_log", json.dumps(migration_log, ensure_ascii=False)),
        )
        conn.commit()

        # Drop old table and recreate with v2 schema
        cursor.execute("DROP TABLE IF EXISTS journals")
        conn.commit()
        conn.close()

        # Re-init with v2 schema + rebuild from files
        conn = init_fts_db(force_recreate=True)
        conn.close()

        # Rebuild index from journal files
        rebuild_result = update_index(incremental=False)
        logger.info(
            "[migration] FTS rebuild complete: added=%d, total=%d",
            rebuild_result.get("added", 0),
            rebuild_result.get("total", 0),
        )

        result["migrated"] = True
        result["migration_log"] = migration_log
        result["rebuild_result"] = rebuild_result

    except (sqlite3.Error, OSError) as e:
        import logging

        logging.getLogger(__name__).error(
            "[migration] FTS schema migration failed: %s", e
        )
        result["error"] = str(e)

    return result


def write_index_meta(
    conn: sqlite3.Connection, semantic_baseline_p25: float | None = None
) -> None:
    """Write tokenizer_version, dict_hash, schema_version, and last_updated.

    These values are written into the index_meta table.
    """
    from datetime import datetime, timezone

    cursor = conn.cursor()
    dict_hash = get_dict_hash()
    cursor.execute(
        "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
        ("tokenizer_version", str(TOKENIZER_VERSION)),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
        ("dict_hash", dict_hash),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
        ("schema_version", str(FTS_SCHEMA_VERSION)),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
        ("last_updated", datetime.now(timezone.utc).isoformat()),
    )
    if semantic_baseline_p25 is not None:
        cursor.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            ("semantic_baseline_p25", f"{semantic_baseline_p25:.6f}"),
        )
    conn.commit()


def check_index_freshness() -> Dict[str, Any]:
    """Check FTS index freshness without requiring an open connection.

    Returns a structured result:
        stale: bool — whether the index is stale
        reason: str | None — specific staleness reason
        fts_document_count: int — number of documents in FTS index
        last_updated: str | None — ISO timestamp of last index update
    """
    result: Dict[str, Any] = {
        "stale": False,
        "reason": None,
        "fts_document_count": 0,
        "last_updated": None,
    }

    if not get_fts_db_path().exists():
        result["stale"] = True
        result["reason"] = "no_fts_db"
        return result

    try:
        conn = sqlite3.connect(str(get_fts_db_path()))
        try:
            # Document count
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM journals")
            result["fts_document_count"] = cursor.fetchone()[0]

            # Last updated from index_meta
            cursor.execute("SELECT value FROM index_meta WHERE key = 'last_updated'")
            row = cursor.fetchone()
            if row:
                result["last_updated"] = row[0]

            # Check freshness using existing logic
            if check_needs_rebuild(conn):
                result["stale"] = True
                # Determine specific reason
                cursor.execute("SELECT value FROM index_meta WHERE key = 'tokenizer_version'")
                row = cursor.fetchone()
                if row is None:
                    result["reason"] = "no_meta"
                elif int(row[0]) != TOKENIZER_VERSION:
                    result["reason"] = "tokenizer_mismatch"
                else:
                    cursor.execute("SELECT value FROM index_meta WHERE key = 'schema_version'")
                    row = cursor.fetchone()
                    if row is None or int(row[0]) != FTS_SCHEMA_VERSION:
                        result["reason"] = "schema_mismatch"
                    else:
                        cursor.execute("SELECT value FROM index_meta WHERE key = 'dict_hash'")
                        row = cursor.fetchone()
                        current_hash = get_dict_hash()
                        if row is None or row[0] != current_hash:
                            result["reason"] = "dict_hash_mismatch"
                        else:
                            result["reason"] = "unknown"
        finally:
            conn.close()
    except sqlite3.Error:
        result["stale"] = True
        result["reason"] = "db_error"

    return result


def check_needs_rebuild(conn: sqlite3.Connection) -> bool:
    """Check if the FTS index needs rebuilding due to schema/tokenizer/dict changes.

    Returns True if:
    - No tokenizer_version in index_meta (pre-v2 index)
    - tokenizer_version doesn't match current TOKENIZER_VERSION
    - schema_version doesn't match current FTS_SCHEMA_VERSION
    - dict_hash doesn't match current entity dictionary hash
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM index_meta WHERE key = 'tokenizer_version'")
        row = cursor.fetchone()
        if row is None:
            return True  # Pre-v2 index, needs rebuild
        if int(row[0]) != TOKENIZER_VERSION:
            return True  # Tokenizer version changed

        cursor.execute("SELECT value FROM index_meta WHERE key = 'schema_version'")
        row = cursor.fetchone()
        if row is None or int(row[0]) != FTS_SCHEMA_VERSION:
            return True  # Schema changed (new/removed columns)

        cursor.execute("SELECT value FROM index_meta WHERE key = 'dict_hash'")
        row = cursor.fetchone()
        if row is None:
            return True  # No dict hash recorded

        current_hash = get_dict_hash()
        if row[0] != current_hash:
            return True  # Entity dictionary changed since last index

        return False
    except sqlite3.Error:
        return True  # Any DB error = rebuild safe default


def get_stats() -> Dict[str, Any]:
    """获取索引统计信息"""
    stats: Dict[str, Any] = {
        "exists": get_fts_db_path().exists(),
        "total_documents": 0,
        "db_size_mb": 0.0,
        "last_updated": None,
    }

    try:
        if get_fts_db_path().exists():
            stats["db_size_mb"] = round(get_fts_db_path().stat().st_size / (1024 * 1024), 2)

            conn = sqlite3.connect(str(get_fts_db_path()))
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM journals")
            stats["total_documents"] = cursor.fetchone()[0]

            cursor.execute("SELECT MAX(modified_time) FROM journals")
            last = cursor.fetchone()[0]
            if last:
                stats["last_updated"] = last

            conn.close()

    except (OSError, IOError, sqlite3.Error):
        pass

    return stats


# --- Backward-compatible wrappers (delegate to fts_* modules) ---


def get_file_hash(file_path: Path) -> str:
    """计算文件内容哈希，用于检测变更"""
    from .fts_update import get_file_hash as _get_file_hash

    return _get_file_hash(file_path)


def _normalize_to_str(value: Any) -> str:
    """将值规范化为字符串"""
    from .fts_update import _normalize_to_str as _norm

    return _norm(value)


def parse_journal(file_path: Path) -> Optional[Dict[str, Any]]:
    """解析日志文件，提取可索引内容"""
    from .fts_update import parse_journal as _parse_journal

    return _parse_journal(file_path, get_journals_dir(), get_user_data_dir())


def update_index(incremental: bool = True) -> Dict[str, Any]:
    """
    更新搜索索引

    Args:
        incremental: True=仅更新变更，False=全量重建

    Returns:
        {
            "success": bool,
            "added": int,
            "updated": int,
            "removed": int,
            "total": int,
            "needs_rebuild": bool (if version mismatch detected),
            "error": str (optional)
        }
    """
    from .fts_update import update_index as _update_index

    # Check if index needs rebuild due to tokenizer/dict changes (T1.4)
    if incremental and get_fts_db_path().exists():
        try:
            conn = sqlite3.connect(str(get_fts_db_path()))
            needs = check_needs_rebuild(conn)
            conn.close()
            if needs:
                incremental = False
        except sqlite3.Error:
            incremental = False

    # Non-incremental (full rebuild) must force-recreate the FTS table
    # so that schema changes (new columns like mood/people) take effect.
    # CREATE VIRTUAL TABLE IF NOT EXISTS silently preserves old schema.
    init_func = (  # type: ignore[misc]
        init_fts_db if incremental else lambda: init_fts_db(force_recreate=True)
    )

    result = _update_index(
        init_func, get_fts_db_path(), get_journals_dir(), get_user_data_dir(), incremental
    )

    # After successful update, write version metadata (T1.4)
    if result.get("success") and get_fts_db_path().exists():
        try:
            conn = sqlite3.connect(str(get_fts_db_path()))
            write_index_meta(conn)
            conn.close()
        except sqlite3.Error:
            pass  # Non-critical — index is still valid

    return result


def get_indexed_files(conn: sqlite3.Connection) -> Dict[str, Tuple[str, str]]:
    """获取已索引的文件列表（路径 -> (hash, modified_time)）"""
    from .fts_update import get_indexed_files as _get_indexed_files

    return _get_indexed_files(conn)


def search_fts(
    query: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = FTS_LIMIT,
    min_relevance: int = FTS_MIN_RELEVANCE,
) -> List[Dict[str, Any]]:
    """
    使用 FTS5 搜索日志（带 BM25 相关性排序）

    Args:
        query: 搜索关键词（支持 FTS5 语法：AND, OR, NOT, * 通配符）
        date_from: 起始日期 YYYY-MM-DD
        date_to: 结束日期 YYYY-MM-DD
        limit: 最大返回结果数
        min_relevance: 最低相关性阈值（0-100）

    Returns:
        搜索结果列表（按 BM25 相关性排序，分数越高越相关）
    """
    from .fts_search import search_fts as _search_fts

    return _search_fts(get_fts_db_path(), query, date_from, date_to, limit, min_relevance)


if __name__ == "__main__":
    # 测试代码
    print("Initializing FTS index...")
    result = update_index(incremental=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\nIndex stats:")
    print(json.dumps(get_stats(), indent=2, ensure_ascii=False))

    print("\nTesting search:")
    results = search_fts("重构")
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title']}")
