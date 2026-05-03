#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - L2 Metadata
二级元数据搜索模块（frontmatter扫描）

性能优化：使用SQLite元数据缓存避免重复解析
"""

import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# 导入配置 (relative imports from tools/lib)
from ..lib.paths import get_user_data_dir, get_journals_dir
from ..lib.metadata_cache import (
    get_or_update_metadata,
    get_all_cached_metadata,
    update_cache_for_all_journals,
    get_cache_stats,
)
from ..lib.path_contract import build_journal_path_fields

# Deprecated aliases — kept for monkeypatch compatibility (Round 13 lesson)
USER_DATA_DIR = get_user_data_dir()
JOURNALS_DIR = get_journals_dir()

# 是否启用缓存（可通过环境变量控制）
ENABLE_CACHE = os.environ.get("LIFE_INDEX_L2_CACHE", "1") == "1"

_ASCII_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[\u3400-\u9fff]")


def _query_matches_text(text: str, query: str) -> bool:
    normalized_query = query.strip().lower()
    normalized_text = text.strip().lower()
    if not normalized_query or not normalized_text:
        return False

    if _CJK_RE.search(normalized_query):
        return normalized_query in normalized_text

    if _ASCII_TOKEN_RE.fullmatch(normalized_query):
        pattern = re.compile(
            rf"(?<![a-z0-9]){re.escape(normalized_query)}(?![a-z0-9])",
            re.IGNORECASE,
        )
        return bool(pattern.search(normalized_text))

    return normalized_query in normalized_text


def _query_matches_tags(tags: Any, query: str) -> bool:
    if isinstance(tags, list):
        return any(_query_matches_text(str(tag), query) for tag in tags)
    return _query_matches_text(str(tags), query)


def _matches_filters(
    metadata: Dict[str, Any],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    location: Optional[str] = None,
    weather: Optional[str] = None,
    topic: Optional[str] = None,
    project: Optional[str] = None,
    tags: Optional[List[str]] = None,
    mood: Optional[List[str]] = None,
    people: Optional[List[str]] = None,
    query: Optional[str] = None,
) -> bool:
    """检查元数据是否匹配过滤条件"""
    # 日期过滤 - 只比较日期部分（前10个字符：YYYY-MM-DD）
    file_date = metadata.get("date", "")
    # 提取日期部分（处理 ISO 8601 格式如 2026-03-04T19:43:02+01:00）
    file_date_part = file_date[:10] if len(file_date) >= 10 else file_date
    if date_from and file_date_part < date_from[:10]:
        return False
    if date_to and file_date_part > date_to[:10]:
        return False

    # 地点过滤
    if location and location.lower() not in metadata.get("location", "").lower():
        return False

    # 天气过滤
    if weather and weather.lower() not in metadata.get("weather", "").lower():
        return False

    # Topic过滤（支持数组或字符串）
    if topic:
        file_topics = metadata.get("topic", [])
        if isinstance(file_topics, str):
            file_topics = [file_topics]
        if topic not in file_topics:
            return False

    # Project过滤（支持数组或字符串）
    if project:
        file_projects = metadata.get("project", [])
        if isinstance(file_projects, str):
            file_projects = [file_projects]
        if project not in file_projects:
            return False

    # Tags过滤
    if tags:
        file_tags = metadata.get("tags", [])
        if not isinstance(file_tags, list):
            file_tags = [file_tags]
        if not any(tag in file_tags for tag in tags):
            return False

    # Mood过滤
    if mood:
        file_moods = metadata.get("mood", [])
        if isinstance(file_moods, str):
            file_moods = [file_moods]
        if not isinstance(file_moods, list):
            file_moods = []
        if not any(m in file_moods for m in mood):
            return False

    # People过滤
    if people:
        file_people = metadata.get("people", [])
        if isinstance(file_people, str):
            file_people = [file_people]
        if not isinstance(file_people, list):
            file_people = []
        if not any(p in file_people for p in people):
            return False

    # Query 过滤：当指定 query 时，要求元数据包含该关键词
    if query:
        title = metadata.get("title", "")
        abstract = metadata.get("abstract", "") if isinstance(metadata.get("abstract"), str) else ""
        file_tags = metadata.get("tags", [])

        # Multi-token query: OR semantics for metadata matching (C1-b alias support)
        query_tokens = query.split()
        if len(query_tokens) > 1:
            matched = any(
                _query_matches_text(title, token)
                or _query_matches_text(abstract, token)
                or _query_matches_tags(file_tags, token)
                for token in query_tokens
            )
        else:
            matched = (
                _query_matches_text(title, query)
                or _query_matches_text(abstract, query)
                or _query_matches_tags(file_tags, query)
            )
        if not matched:
            return False

    return True


def _search_with_cache(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    location: Optional[str] = None,
    weather: Optional[str] = None,
    topic: Optional[str] = None,
    project: Optional[str] = None,
    tags: Optional[List[str]] = None,
    mood: Optional[List[str]] = None,
    people: Optional[List[str]] = None,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """使用缓存的元数据进行搜索（高性能路径）"""
    results: List[Dict[str, Any]] = []

    # 获取所有缓存的元数据
    cached_entries = get_all_cached_metadata()

    for entry in cached_entries:
        # 使用通用过滤函数
        if not _matches_filters(
            entry,
            date_from=date_from,
            date_to=date_to,
            location=location,
            weather=weather,
            topic=topic,
            project=project,
            tags=tags,
            mood=mood,
            people=people,
            query=query,
        ):
            continue

        # 匹配成功
        file_path = Path(entry["file_path"])
        path_fields = build_journal_path_fields(
            file_path, journals_dir=get_journals_dir(), user_data_dir=get_user_data_dir()
        )

        results.append(
            {
                "date": entry["date"],
                "title": entry.get("title", "无标题"),
                **path_fields,
                "metadata": entry["metadata"],
                "source": "metadata_cache",
            }
        )

    return results


def _search_filesystem(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    location: Optional[str] = None,
    weather: Optional[str] = None,
    topic: Optional[str] = None,
    project: Optional[str] = None,
    tags: Optional[List[str]] = None,
    mood: Optional[List[str]] = None,
    people: Optional[List[str]] = None,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """使用文件系统扫描搜索（Fallback路径）"""
    results: List[Dict[str, Any]] = []

    _journals_dir = get_journals_dir()
    if not _journals_dir.exists():
        return results

    # 遍历所有日志文件
    for year_dir in _journals_dir.iterdir():
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue

        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue

            for journal_file in month_dir.glob("*.md"):
                try:
                    # 获取元数据（使用缓存）
                    entry = get_or_update_metadata(journal_file)
                    if not entry:
                        continue

                    # 使用通用过滤函数
                    if not _matches_filters(
                        entry,
                        date_from=date_from,
                        date_to=date_to,
                        location=location,
                        weather=weather,
                        topic=topic,
                        project=project,
                        tags=tags,
                        mood=mood,
                        people=people,
                        query=query,
                    ):
                        continue

                    # 匹配成功
                    path_fields = build_journal_path_fields(
                        journal_file,
                        journals_dir=get_journals_dir(),
                        user_data_dir=get_user_data_dir(),
                    )

                    results.append(
                        {
                            "date": entry["date"],
                            "title": entry.get("title", "无标题"),
                            **path_fields,
                            "metadata": entry["metadata"],
                            "source": "filesystem_scan",
                        }
                    )

                except (IOError, OSError, ValueError):
                    continue

    return results


def search_l2_metadata(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    location: Optional[str] = None,
    weather: Optional[str] = None,
    topic: Optional[str] = None,
    project: Optional[str] = None,
    tags: Optional[List[str]] = None,
    mood: Optional[List[str]] = None,
    people: Optional[List[str]] = None,
    query: Optional[str] = None,
    use_cache: bool = True,
    max_results: Optional[int] = 100,
) -> Dict[str, Any]:
    """
    L2: 元数据层搜索

    性能优化：使用SQLite元数据缓存避免重复解析
    缓存策略：
    1. 优先使用缓存表中的数据
    2. 缓存未命中时解析文件并更新缓存
    3. 文件变更检测：通过mtime+size判断缓存是否有效

    Args:
        query: 当指定 query 时，额外过滤 title/abstract/tags 包含该关键词的日志
        use_cache: 是否使用缓存（默认True）
        max_results: 无过滤条件时的最大返回数量（默认100，None表示无限制）
                     有过滤条件时不受此限制

    Returns:
        {
            "results": [...],      # 匹配结果列表
            "truncated": bool,     # 是否被截断
            "total_available": int # 总可用数量
        }
    """
    # 如果不使用缓存，直接扫描文件系统
    if not use_cache or not ENABLE_CACHE:
        results = _search_filesystem(
            date_from=date_from,
            date_to=date_to,
            location=location,
            weather=weather,
            topic=topic,
            project=project,
            tags=tags,
            mood=mood,
            people=people,
            query=query,
        )
    else:
        # 尝试使用缓存搜索
        try:
            # 检查缓存是否存在且有数据
            stats = get_cache_stats()
            if stats["total_entries"] > 0:
                # 使用缓存搜索
                results = _search_with_cache(
                    date_from=date_from,
                    date_to=date_to,
                    location=location,
                    weather=weather,
                    topic=topic,
                    project=project,
                    tags=tags,
                    mood=mood,
                    people=people,
                    query=query,
                )
            else:
                # 缓存为空，回退到文件系统扫描
                results = _search_filesystem(
                    date_from=date_from,
                    date_to=date_to,
                    location=location,
                    weather=weather,
                    topic=topic,
                    project=project,
                    tags=tags,
                    mood=mood,
                    people=people,
                    query=query,
                )
        except (IOError, OSError):
            # 缓存不可用，回退到文件系统扫描
            results = _search_filesystem(
                date_from=date_from,
                date_to=date_to,
                location=location,
                weather=weather,
                topic=topic,
                project=project,
                tags=tags,
                mood=mood,
                people=people,
                query=query,
            )

    # 检查是否有过滤条件
    has_filters = any(
        [
            date_from,
            date_to,
            location,
            weather,
            topic,
            project,
            tags,
            mood,
            people,
            query,
        ]
    )

    total_available = len(results)
    truncated = False

    # 只有在无过滤条件时才应用 max_results 限制
    if not has_filters and max_results is not None and total_available > max_results:
        results = results[:max_results]
        truncated = True

    return {
        "results": results,
        "truncated": truncated,
        "total_available": total_available,
    }


def warm_cache(progress_callback: Optional[Callable] = None) -> Dict[str, int]:
    """
    预热缓存：扫描所有日志文件并更新缓存

    建议在以下场景调用：
    - 首次启用缓存
    - 定期维护（如每周）
    - 批量导入日志后

    Returns:
        {"updated": 更新数, "skipped": 跳过数, "errors": 错误数}
    """
    return update_cache_for_all_journals(progress_callback)


def get_l2_cache_stats() -> Dict[str, Any]:
    """获取L2缓存统计信息"""
    return get_cache_stats()
