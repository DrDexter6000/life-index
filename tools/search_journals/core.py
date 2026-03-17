#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - Core
核心协调模块

v1.2: 双管道并行搜索架构
  Pipeline A (关键词): L1 索引过滤 → L2 元数据过滤 → L3 FTS5 内容匹配
  Pipeline B (语义):   向量相似度搜索
  融合: RRF (Reciprocal Rank Fusion, k=60)
"""

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

# 导入子模块
from .l1_index import scan_all_indices, search_l1_index
from .l2_metadata import search_l2_metadata
from .l3_content import search_l3_content
from .semantic import search_semantic
from .ranking import merge_and_rank_results, merge_and_rank_results_hybrid

# 导入 logger
try:
    from ..lib.logger import get_logger

    logger = get_logger("search_journals")
except ImportError:
    import logging

    logger = logging.getLogger("search_journals")


def hierarchical_search(
    query: Optional[str] = None,
    topic: Optional[str] = None,
    project: Optional[str] = None,
    tags: Optional[List[str]] = None,
    mood: Optional[List[str]] = None,
    people: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    location: Optional[str] = None,
    weather: Optional[str] = None,
    level: int = 3,
    use_index: bool = True,
    semantic: bool = True,
    semantic_weight: float = 0.4,
    fts_weight: float = 0.6,
) -> Dict[str, Any]:
    """
    双管道并行搜索

    Pipeline A: L1 索引过滤 → L2 元数据过滤 → L3 FTS5 内容匹配
    Pipeline B: 语义向量搜索
    融合: RRF (Reciprocal Rank Fusion, k=60)

    当 level=1 或 level=2 时，按原逻辑提前返回（向后兼容）。
    仅 level=3（默认）时启动双管道并行。

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
        level: 1=仅索引, 2=索引+元数据, 3=完整双管道并行
        use_index: 是否使用 FTS 索引加速 L3 搜索（默认 True）
        semantic: 是否启用语义搜索（默认 True）
        semantic_weight: 语义搜索得分权重（默认 0.4）
        fts_weight: FTS 搜索得分权重（默认 0.6）
    """
    result: Dict[str, Any] = {
        "success": True,
        "query_params": {
            "query": query,
            "topic": topic,
            "project": project,
            "tags": tags,
            "mood": mood,
            "people": people,
            "date_from": date_from,
            "date_to": date_to,
            "level": level,
            "semantic": semantic,
        },
        "l1_results": [],
        "l2_results": [],
        "l3_results": [],
        "semantic_results": [],
        "merged_results": [],
        "total_found": 0,
        "performance": {},
    }

    start_time = time.time()

    # ── Level 1: 索引层（向后兼容，提前返回） ──
    if level == 1:
        l1_start = time.time()

        if topic:
            result["l1_results"].extend(search_l1_index("topic", topic))
        if project:
            result["l1_results"].extend(search_l1_index("project", project))
        if tags:
            for tag in tags:
                result["l1_results"].extend(search_l1_index("tag", tag))

        # 当无过滤条件但指定 level=1 时，扫描所有索引文件
        if not topic and not project and not tags:
            result["l1_results"].extend(scan_all_indices())

        # 去重
        seen_paths: set = set()
        unique_l1: List[Dict] = []
        for r in result["l1_results"]:
            if r["path"] not in seen_paths:
                seen_paths.add(r["path"])
                unique_l1.append(r)
        result["l1_results"] = unique_l1

        result["performance"]["l1_time_ms"] = round((time.time() - l1_start) * 1000, 2)
        result["total_found"] = len(result["l1_results"])
        result["performance"]["total_time_ms"] = round(
            (time.time() - start_time) * 1000, 2
        )
        return result

    # ── Level 2: 索引 + 元数据（向后兼容，提前返回） ──
    if level == 2:
        l1_start = time.time()

        if topic:
            result["l1_results"].extend(search_l1_index("topic", topic))
        if project:
            result["l1_results"].extend(search_l1_index("project", project))
        if tags:
            for tag in tags:
                result["l1_results"].extend(search_l1_index("tag", tag))

        # 去重
        seen_paths = set()
        unique_l1 = []
        for r in result["l1_results"]:
            if r["path"] not in seen_paths:
                seen_paths.add(r["path"])
                unique_l1.append(r)
        result["l1_results"] = unique_l1

        result["performance"]["l1_time_ms"] = round((time.time() - l1_start) * 1000, 2)

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
        result["l2_results"] = l2_response["results"]
        if l2_response.get("truncated"):
            result["l2_truncated"] = True
            result["l2_total_available"] = l2_response.get("total_available", 0)

        result["performance"]["l2_time_ms"] = round((time.time() - l2_start) * 1000, 2)
        result["total_found"] = len(result["l2_results"])
        result["performance"]["total_time_ms"] = round(
            (time.time() - start_time) * 1000, 2
        )
        return result

    # ── Level 3: 双管道并行搜索 ──

    def pipeline_keyword() -> tuple:
        """关键词搜索管道: L1 → L2 → L3"""
        perf: Dict[str, float] = {}

        # L1: 索引过滤
        l1_start = time.time()
        l1_results: List[Dict] = []
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

        # L3: FTS5 内容搜索
        l3_start = time.time()
        l3_results: List[Dict] = []

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
                    from ..lib.config import USER_DATA_DIR
                    from ..lib.search_index import search_fts

                    fts_results = search_fts(fts_query, date_from, date_to, limit=100)
                    if fts_results:
                        l3_results = [
                            {
                                "path": str(USER_DATA_DIR / r["path"]),
                                "rel_path": r["path"],
                                "date": r["date"],
                                "title": r["title"],
                                "snippet": r.get("snippet", ""),
                                "match_count": 1,
                                "source": "fts_index",
                                "relevance": r.get("relevance", 50),
                            }
                            for r in fts_results
                        ]
                        logger.debug(f"FTS found {len(l3_results)} results")
                except (ImportError, OSError) as e:
                    logger.debug(f"FTS error: {e}")

            # 如果没有 FTS 结果，使用传统文件系统扫描
            if not l3_results:
                candidate_paths = [r["path"] for r in l1_results + l2_results]
                l3_results = search_l3_content(
                    query, candidate_paths if candidate_paths else None
                )
                logger.debug(f"File scan found {len(l3_results)} results")

        perf["l3_time_ms"] = round((time.time() - l3_start) * 1000, 2)

        return (
            l1_results,
            l2_results,
            l3_results,
            l2_truncated,
            l2_total_available,
            perf,
        )

    def pipeline_semantic() -> tuple:
        """语义搜索管道"""
        if not (semantic and query):
            return [], {}
        sem_start = time.time()
        sem_results = search_semantic(query, date_from or "", date_to or "")
        perf = {"semantic_time_ms": round((time.time() - sem_start) * 1000, 2)}
        if sem_results:
            logger.debug(f"Semantic found {len(sem_results)} results")
        return sem_results, perf

    # ── 并行执行双管道 ──
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_keyword = executor.submit(pipeline_keyword)
        future_semantic = executor.submit(pipeline_semantic)

        # 收集结果
        (
            l1_results,
            l2_results,
            l3_results,
            l2_truncated,
            l2_total_available,
            kw_perf,
        ) = future_keyword.result()
        semantic_results, sem_perf = future_semantic.result()

    # 填充结果
    result["l1_results"] = l1_results
    result["l2_results"] = l2_results
    result["l3_results"] = l3_results
    result["semantic_results"] = semantic_results
    if l2_truncated:
        result["l2_truncated"] = True
        result["l2_total_available"] = l2_total_available
    result["performance"].update(kw_perf)
    if sem_perf:
        result["performance"].update(sem_perf)

    # ── RRF 融合 ──
    if semantic_results:
        result["merged_results"] = merge_and_rank_results_hybrid(
            l1_results,
            l2_results,
            l3_results,
            semantic_results,
            query,
            fts_weight=fts_weight,
            semantic_weight=semantic_weight,
        )
    else:
        # 语义搜索无结果时退化为纯关键词排序
        result["merged_results"] = merge_and_rank_results(
            l1_results, l2_results, l3_results, query
        )

    result["total_found"] = len(result["merged_results"])
    result["performance"]["total_time_ms"] = round((time.time() - start_time) * 1000, 2)

    return result
