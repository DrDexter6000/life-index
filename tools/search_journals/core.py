#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - Core
核心协调模块

v1.2: 双管道并行搜索架构
  Pipeline A (关键词): L1 索引过滤 → L2 元数据过滤 → L3 FTS5 内容匹配
  Pipeline B (语义):   向量相似度搜索
  融合: RRF (Reciprocal Rank Fusion, k=RRF_K)
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from ..lib.search_constants import (
    SEMANTIC_TOP_K_DEFAULT,
    SEMANTIC_MIN_SIMILARITY,
    FTS_MIN_RELEVANCE,
    RRF_MIN_SCORE,
    NON_RRF_MIN_SCORE,
    SEMANTIC_WEIGHT_DEFAULT,
    FTS_WEIGHT_DEFAULT,
)

# 导入子模块
from .l1_index import scan_all_indices, search_l1_index
from .l2_metadata import search_l2_metadata
from .ranking import merge_and_rank_results, merge_and_rank_results_hybrid
from .keyword_pipeline import run_keyword_pipeline
from .semantic_pipeline import run_semantic_pipeline

# 导入 logger
try:
    from ..lib.logger import get_logger

    logger = get_logger("search_journals")
except ImportError:
    logger = logging.getLogger("search_journals")


def _search_level_1(
    *,
    result: Dict[str, Any],
    topic: Optional[str],
    project: Optional[str],
    tags: Optional[List[str]],
    start_time: float,
) -> Dict[str, Any]:
    """Level 1: 索引层搜索"""
    l1_start = time.time()

    if topic:
        result["l1_results"].extend(search_l1_index("topic", topic))
    if project:
        result["l1_results"].extend(search_l1_index("project", project))
    if tags:
        for tag in tags:
            result["l1_results"].extend(search_l1_index("tag", tag))

    if not topic and not project and not tags:
        result["l1_results"].extend(scan_all_indices())

    seen_paths: set = set()
    unique_l1: List[Dict] = []
    for item in result["l1_results"]:
        if item["path"] not in seen_paths:
            seen_paths.add(item["path"])
            unique_l1.append(item)
    result["l1_results"] = unique_l1

    result["performance"]["l1_time_ms"] = round((time.time() - l1_start) * 1000, 2)
    result["total_found"] = len(result["l1_results"])
    result["performance"]["total_time_ms"] = round((time.time() - start_time) * 1000, 2)
    return result


def _search_level_2(
    *,
    result: Dict[str, Any],
    query: Optional[str],
    topic: Optional[str],
    project: Optional[str],
    tags: Optional[List[str]],
    mood: Optional[List[str]],
    people: Optional[List[str]],
    date_from: Optional[str],
    date_to: Optional[str],
    location: Optional[str],
    weather: Optional[str],
    start_time: float,
) -> Dict[str, Any]:
    """Level 2: 索引 + 元数据搜索"""
    l1_start = time.time()

    if topic:
        result["l1_results"].extend(search_l1_index("topic", topic))
    if project:
        result["l1_results"].extend(search_l1_index("project", project))
    if tags:
        for tag in tags:
            result["l1_results"].extend(search_l1_index("tag", tag))

    seen_paths: set = set()
    unique_l1: List[Dict] = []
    for item in result["l1_results"]:
        if item["path"] not in seen_paths:
            seen_paths.add(item["path"])
            unique_l1.append(item)
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
    result["performance"]["total_time_ms"] = round((time.time() - start_time) * 1000, 2)
    return result


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
    semantic_weight: float = SEMANTIC_WEIGHT_DEFAULT,
    fts_weight: float = FTS_WEIGHT_DEFAULT,
    # Web-only recall overrides
    semantic_top_k: int = SEMANTIC_TOP_K_DEFAULT,
    semantic_min_similarity: float = SEMANTIC_MIN_SIMILARITY,
    fts_min_relevance: int = FTS_MIN_RELEVANCE,
    rrf_min_score: float = RRF_MIN_SCORE,
    non_rrf_min_score: float = NON_RRF_MIN_SCORE,
) -> Dict[str, Any]:
    """
    双管道并行搜索

    Pipeline A: L1 索引过滤 → L2 元数据过滤 → L3 FTS5 内容匹配
    Pipeline B: 语义向量搜索
    融合: RRF (Reciprocal Rank Fusion, k=RRF_K)

    当 level=1 或 level=2 时，按原逻辑提前返回（向后兼容）。
    仅 level=3（默认）时启动双管道并行。
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
        "semantic_available": semantic,
        "performance": {},
        "warnings": [],  # Phase 2C: 降级警告收集
    }

    if not semantic:
        result["semantic_note"] = "语义搜索已通过 --no-semantic 禁用。"
        result["warnings"].append(
            "semantic_disabled: 用户通过 --no-semantic 禁用语义搜索"
        )

    start_time = time.time()

    # ── Level 1: 索引层（向后兼容，提前返回） ──
    if level == 1:
        return _search_level_1(
            result=result,
            topic=topic,
            project=project,
            tags=tags,
            start_time=start_time,
        )

    # ── Level 2: 索引 + 元数据（向后兼容，提前返回） ──
    if level == 2:
        return _search_level_2(
            result=result,
            query=query,
            topic=topic,
            project=project,
            tags=tags,
            mood=mood,
            people=people,
            date_from=date_from,
            date_to=date_to,
            location=location,
            weather=weather,
            start_time=start_time,
        )

    # ── Level 3: 双管道并行搜索 ──
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_keyword = executor.submit(
            run_keyword_pipeline,
            query=query,
            topic=topic,
            project=project,
            tags=tags,
            mood=mood,
            people=people,
            date_from=date_from,
            date_to=date_to,
            location=location,
            weather=weather,
            use_index=use_index,
            fts_min_relevance=fts_min_relevance,
        )
        future_semantic = executor.submit(
            run_semantic_pipeline,
            query=query,
            date_from=date_from,
            date_to=date_to,
            semantic=semantic,
            semantic_top_k=semantic_top_k,
            semantic_min_similarity=semantic_min_similarity,
        )

        # 收集结果
        (
            l1_results,
            l2_results,
            l3_results,
            l2_truncated,
            l2_total_available,
            kw_perf,
        ) = future_keyword.result()
        semantic_results, sem_perf, semantic_available, semantic_note = (
            future_semantic.result()
        )

    # 填充结果
    result["l1_results"] = l1_results
    result["l2_results"] = l2_results
    result["l3_results"] = l3_results
    result["semantic_results"] = semantic_results
    result["semantic_available"] = semantic_available
    if semantic_note:
        result["semantic_note"] = semantic_note
        # Phase 2C: 语义搜索降级时添加警告
        if not semantic_available:
            result["warnings"].append(f"semantic_unavailable: {semantic_note}")
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
            min_rrf_score=rrf_min_score,
            min_non_rrf_score=non_rrf_min_score,
        )
    else:
        # 语义搜索无结果时退化为纯关键词排序
        result["merged_results"] = merge_and_rank_results(
            l1_results, l2_results, l3_results, query
        )

    result["total_found"] = len(result["merged_results"])
    result["performance"]["total_time_ms"] = round((time.time() - start_time) * 1000, 2)

    # Log summary
    total_time = result["performance"]["total_time_ms"]
    l1_time = result["performance"].get("l1_time_ms", 0)
    l2_time = result["performance"].get("l2_time_ms", 0)
    l3_time = result["performance"].get("l3_time_ms", 0)
    sem_time = result["performance"].get("semantic_time_ms", 0)
    logger.info(
        f"[SearchPerf] Total: {total_time}ms (L1:{l1_time} L2:{l2_time} L3:{l3_time} Semantic:{sem_time}) | Results: {result['total_found']}"
    )

    return result
