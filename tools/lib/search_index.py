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

from .config import JOURNALS_DIR, USER_DATA_DIR
from .search_constants import FTS_LIMIT, FTS_MIN_RELEVANCE

# 索引存储目录
INDEX_DIR = USER_DATA_DIR / ".index"
FTS_DB_PATH = INDEX_DIR / "journals_fts.db"


def init_fts_db() -> sqlite3.Connection:
    """初始化 FTS5 数据库"""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(FTS_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")  # 启用 WAL 模式提升并发性能
    cursor = conn.cursor()

    # 创建 FTS5 虚拟表（如果不存在）
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS journals USING fts5(
            path,
            title,
            content,
            date,
            location,
            weather,
            topic,
            project,
            tags,
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


def get_stats() -> Dict[str, Any]:
    """获取索引统计信息"""
    stats: Dict[str, Any] = {
        "exists": FTS_DB_PATH.exists(),
        "total_documents": 0,
        "db_size_mb": 0.0,
        "last_updated": None,
    }

    try:
        if FTS_DB_PATH.exists():
            stats["db_size_mb"] = round(FTS_DB_PATH.stat().st_size / (1024 * 1024), 2)

            conn = sqlite3.connect(str(FTS_DB_PATH))
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

    return _parse_journal(file_path, JOURNALS_DIR, USER_DATA_DIR)


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
            "error": str (optional)
        }
    """
    from .fts_update import update_index as _update_index

    return _update_index(init_fts_db, FTS_DB_PATH, JOURNALS_DIR, USER_DATA_DIR, incremental)


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

    return _search_fts(FTS_DB_PATH, query, date_from, date_to, limit, min_relevance)


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
