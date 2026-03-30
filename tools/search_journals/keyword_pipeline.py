#!/usr/bin/env python3
"""
Life Index - Keyword Search Pipeline
关键词搜索管道: L1 → L2 → L3

从 core.py 提取的 pipeline_keyword() 函数。
"""

import logging
import time
from typing import Any

from ..lib.config import JOURNALS_DIR, USER_DATA_DIR
from ..lib.path_contract import merge_journal_path_fields
from ..lib.search_constants import FTS_LIMIT, FTS_FALLBACK_THRESHOLD

from .l1_index import search_l1_index
from .l2_metadata import search_l2_metadata
from .l3_content import search_l3_content

# 导入 logger
try:
    from ..lib.logger import get_logger

    logger = get_logger("search_journals")
except ImportError:
    logger = logging.getLogger("search_journals")


KeywordPipelineResult = tuple[
    list[dict[str, Any]],  # l1_results
    list[dict[str, Any]],  # l2_results
    list[dict[str, Any]],  # l3_results
    bool,  # l2_truncated
    int,  # l2_total_available
    dict[str, float],  # perf
]


def run_keyword_pipeline(
    *,
    query: str | None = None,
    topic: str | None = None,
    project: str | None = None,
    tags: list[str] | None = None,
    mood: list[str] | None = None,
    people: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
    weather: str | None = None,
    use_index: bool = True,
    fts_min_relevance: int = 50,
) -> KeywordPipelineResult:
    """
    关键词搜索管道: L1 索引 → L2 元数据 → L3 FTS5 内容

    Args:
        query: 搜索关键词
        topic: 按主题过滤
        project: 按项目过滤
        tags: 按标签过滤
        mood: 按心情过滤
        people: 按人物过滤
        date_from: 起始日期
        date_to: 结束日期
        location: 按地点过滤
        weather: 按天气过滤
        use_index: 是否使用 FTS 索引加速
        fts_min_relevance: FTS 最低相关性阈值

    Returns:
        (l1_results, l2_results, l3_results, l2_truncated, l2_total_available, perf)
    """
    perf: dict[str, float] = {}

    # L1: 索引过滤
    l1_start = time.time()
    l1_results: list[dict] = []
    if topic:
        l1_results.extend(search_l1_index("topic", topic))
    if project:
        l1_results.extend(search_l1_index("project", project))
    if tags:
        for tag in tags:
            l1_results.extend(search_l1_index("tag", tag))
    # 去重
    seen: set = set()
    l1_results = [
        r
        for r in l1_results
        if r["path"] not in seen and not seen.add(r["path"])  # type: ignore[func-returns-value]
    ]
    perf["l1_time_ms"] = round((time.time() - l1_start) * 1000, 2)
    logger.info(
        f"[SearchPerf] L1 index: {len(l1_results)} results, {perf['l1_time_ms']}ms"
    )

    # L2: 元数据过滤
    l2_start = time.time()
    l2_response = search_l2_metadata(
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
    l2_results = l2_response["results"]
    l2_truncated = l2_response.get("truncated", False)
    l2_total_available = l2_response.get("total_available", 0)
    perf["l2_time_ms"] = round((time.time() - l2_start) * 1000, 2)
    logger.info(
        f"[SearchPerf] L2 metadata: {len(l2_results)} results, {perf['l2_time_ms']}ms"
    )

    # L3: FTS5 内容搜索
    l3_start = time.time()
    l3_results: list[dict] = []

    if query:
        # 处理多关键词：将空格分隔转换为 FTS5 OR 语法
        if (
            query
            and " " in query
            and "OR" not in query.upper()
            and "AND" not in query.upper()
        ):
            keywords = [k.strip() for k in query.split() if k.strip()]
            if len(keywords) > 1:
                fts_query = " OR ".join(keywords)
            else:
                fts_query = query
        else:
            fts_query = query

        # 尝试使用 FTS 索引（如果可用且启用）
        if use_index:
            try:
                from ..lib.search_index import search_fts

                fts_results = search_fts(
                    fts_query,
                    date_from,
                    date_to,
                    limit=FTS_LIMIT,
                    min_relevance=fts_min_relevance,
                )
                if fts_results:
                    l3_results = [
                        {
                            "date": r["date"],
                            "title": r["title"],
                            "snippet": r.get("snippet", ""),
                            "match_count": 1,
                            "source": "fts_index",
                            "relevance": r.get("relevance", 50),
                            # 元数据字段
                            "location": r.get("location", ""),
                            "weather": r.get("weather", ""),
                            "topic": r.get("topic", []),
                            "project": r.get("project", ""),
                            "tags": r.get("tags", []),
                            "mood": r.get("mood", []),
                            "people": r.get("people", []),
                            **merge_journal_path_fields(
                                {},
                                USER_DATA_DIR / r["path"],
                                journals_dir=JOURNALS_DIR,
                                user_data_dir=USER_DATA_DIR,
                            ),
                        }
                        for r in fts_results
                    ]

                    # When FTS recall is suspiciously low, supplement with full-corpus
                    # content scan so body-only matches are not missed due to stale or
                    # incomplete index coverage.
                    if query and len(l3_results) < FTS_FALLBACK_THRESHOLD:
                        fallback_l3_results = search_l3_content(query, None)
                        seen_paths = {
                            str(
                                item.get("journal_route_path") or item.get("path") or ""
                            )
                            for item in l3_results
                        }
                        for item in fallback_l3_results:
                            key = str(
                                item.get("journal_route_path") or item.get("path") or ""
                            )
                            if key and key not in seen_paths:
                                l3_results.append(item)
                                seen_paths.add(key)
                    logger.debug(f"FTS found {len(l3_results)} results")
            except (ImportError, OSError) as e:
                logger.debug(f"FTS error: {e}")

        # 如果没有 FTS 结果，使用传统文件系统扫描
        if not l3_results:
            # IMPORTANT: when FTS is unavailable, fallback must search full corpus.
            # Restricting to L2-filtered candidates causes body-only keyword matches
            # (e.g. names appearing only in content) to be lost before L3 sees them.
            l3_results = search_l3_content(query, None)
            logger.debug(f"File scan found {len(l3_results)} results")

    perf["l3_time_ms"] = round((time.time() - l3_start) * 1000, 2)
    logger.info(
        f"[SearchPerf] L3 content: {len(l3_results)} results, {perf['l3_time_ms']}ms"
    )

    return (
        l1_results,
        l2_results,
        l3_results,
        l2_truncated,
        l2_total_available,
        perf,
    )
