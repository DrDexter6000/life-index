#!/usr/bin/env python3
"""
Life Index - FTS Search Module
FTS5 全文搜索功能

从 search_index.py 提取的搜索逻辑。
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .search_constants import (
    FTS_LIMIT,
    FTS_MIN_RELEVANCE,
    FTS_SNIPPET_TOKENS,
    BM25_RELEVANCE_BASE,
    BM25_RELEVANCE_MULTIPLIER,
)


def _parse_json_field(value: Any) -> List[str]:
    """解析 JSON 字段（可能是 JSON 字符串或已经是列表）"""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith("["):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def search_fts(
    fts_db_path: Path,
    query: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = FTS_LIMIT,
    min_relevance: int = FTS_MIN_RELEVANCE,
) -> List[Dict[str, Any]]:
    """
    使用 FTS5 搜索日志（带 BM25 相关性排序）

    Args:
        fts_db_path: FTS 数据库路径
        query: 搜索关键词（支持 FTS5 语法：AND, OR, NOT, * 通配符）
        date_from: 起始日期 YYYY-MM-DD
        date_to: 结束日期 YYYY-MM-DD
        limit: 最大返回结果数
        min_relevance: 最低相关性阈值（0-100）

    Returns:
        搜索结果列表（按 BM25 相关性排序，分数越高越相关）
    """
    results: List[Dict[str, Any]] = []

    try:
        if not fts_db_path.exists():
            # 索引不存在，返回空结果（调用方应回退到文件系统扫描）
            return results

        conn = sqlite3.connect(str(fts_db_path))
        cursor = conn.cursor()

        # 尝试使用新版本的完整查询（包含 mood/people 列）
        # 如果旧索引缺少这些列，会抛出 sqlite3.OperationalError
        try:
            sql = """
                SELECT path, title, date, location, weather, topic, project, tags, mood, people,
                       snippet(journals, 2, '<mark>', '</mark>', '...', ?) as snippet,
                       bm25(journals, 1.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5) as rank
                FROM journals
                WHERE journals MATCH ?
            """
            params = [FTS_SNIPPET_TOKENS, query]

            # 添加日期过滤
            if date_from:
                sql += " AND date >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND date <= ?"
                params.append(date_to)

            # 按 BM25 分数排序（分数越低表示越相关）
            sql += " ORDER BY rank ASC"
            sql += f" LIMIT {limit}"

            cursor.execute(sql, params)

            for row in cursor.fetchall():
                # BM25 分数转换为匹配度百分比（分数越低越相关）
                # 典型 BM25 分数范围：-10 到 10，负数表示高度相关
                bm25_score = row[11] if row[11] is not None else 0
                # 转换公式：将 BM25 分数映射到 0-100 的匹配度
                # 见 search_constants.py ADR-009
                relevance = max(
                    0,
                    min(
                        100,
                        int(
                            BM25_RELEVANCE_BASE - bm25_score * BM25_RELEVANCE_MULTIPLIER
                        ),
                    ),
                )
                if relevance < min_relevance:
                    continue

                results.append(
                    {
                        "path": row[0],
                        "title": row[1],
                        "date": row[2],
                        "location": row[3] or "",
                        "weather": row[4] or "",
                        "topic": _parse_json_field(row[5]) if row[5] else [],
                        "project": row[6] or "",
                        "tags": _parse_json_field(row[7]) if row[7] else [],
                        "mood": _parse_json_field(row[8]) if row[8] else [],
                        "people": _parse_json_field(row[9]) if row[9] else [],
                        "snippet": row[10],
                        "bm25_score": bm25_score,
                        "relevance": relevance,
                        "source": "fts",
                    }
                )

        except sqlite3.OperationalError:
            # 旧索引缺少 mood/people 列，使用简化查询
            sql = """
                SELECT path, title, date, location, weather, topic, project, tags,
                       snippet(journals, 2, '<mark>', '</mark>', '...', ?) as snippet,
                       bm25(journals, 1.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.5, 0.5) as rank
                FROM journals
                WHERE journals MATCH ?
            """
            params = [FTS_SNIPPET_TOKENS, query]

            if date_from:
                sql += " AND date >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND date <= ?"
                params.append(date_to)

            sql += " ORDER BY rank ASC"
            sql += f" LIMIT {limit}"

            cursor.execute(sql, params)

            for row in cursor.fetchall():
                bm25_score = row[9] if row[9] is not None else 0
                relevance = max(
                    0,
                    min(
                        100,
                        int(
                            BM25_RELEVANCE_BASE - bm25_score * BM25_RELEVANCE_MULTIPLIER
                        ),
                    ),
                )
                if relevance < min_relevance:
                    continue

                results.append(
                    {
                        "path": row[0],
                        "title": row[1],
                        "date": row[2],
                        "location": row[3] or "",
                        "weather": row[4] or "",
                        "topic": _parse_json_field(row[5]) if row[5] else [],
                        "project": row[6] or "",
                        "tags": _parse_json_field(row[7]) if row[7] else [],
                        "mood": [],
                        "people": [],
                        "snippet": row[8],
                        "bm25_score": bm25_score,
                        "relevance": relevance,
                        "source": "fts",
                    }
                )

        conn.close()

    except (sqlite3.Error, OSError) as e:
        print(f"FTS search error: {e}")

    return results
