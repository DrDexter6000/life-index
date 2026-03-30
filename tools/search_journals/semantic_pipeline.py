#!/usr/bin/env python3
"""
Life Index - Semantic Search Pipeline
语义搜索管道

从 core.py 提取的 pipeline_semantic() 函数。
"""

import logging
import time
from typing import Any

from ..lib.search_constants import SEMANTIC_TOP_K_DEFAULT, SEMANTIC_MIN_SIMILARITY

from .semantic import get_semantic_runtime_status, search_semantic

# 导入 logger
try:
    from ..lib.logger import get_logger

    logger = get_logger("search_journals")
except ImportError:
    logger = logging.getLogger("search_journals")


SemanticPipelineResult = tuple[
    list[dict[str, Any]],  # sem_results
    dict[str, Any],  # perf
    bool,  # semantic_available
    str | None,  # semantic_note
]


def _build_semantic_status(
    runtime_status: dict[str, Any], sem_results: list[dict[str, Any]]
) -> tuple[dict[str, Any], bool, str | None]:
    """Build semantic pipeline status details without inflating main flow complexity."""
    perf: dict[str, Any] = {}
    semantic_available = bool(runtime_status["available"])
    semantic_note: str | None = None

    if not semantic_available:
        reason = str(runtime_status["reason"])
        semantic_note = str(runtime_status["note"])
        perf["semantic_degraded"] = reason
        logger.info(f"语义搜索不可用，降级为纯关键词搜索: {reason}")

    if sem_results:
        logger.debug(f"Semantic found {len(sem_results)} results")
        semantic_available = True

    return perf, semantic_available, semantic_note


def run_semantic_pipeline(
    *,
    query: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    semantic: bool = True,
    semantic_top_k: int = SEMANTIC_TOP_K_DEFAULT,
    semantic_min_similarity: float = SEMANTIC_MIN_SIMILARITY,
) -> SemanticPipelineResult:
    """
    语义搜索管道

    Args:
        query: 搜索关键词
        date_from: 起始日期
        date_to: 结束日期
        semantic: 是否启用语义搜索
        semantic_top_k: 语义搜索返回数量
        semantic_min_similarity: 语义搜索最低相似度

    Returns:
        (sem_results, perf, semantic_available, semantic_note)
    """
    sem_start = time.time()

    if not semantic:
        return [], {}, False, "语义搜索已通过 --no-semantic 禁用。"
    if not query:
        return [], {}, True, None

    runtime_status = get_semantic_runtime_status()
    if not runtime_status["available"]:
        reason = str(runtime_status["reason"])
        note = str(runtime_status["note"])
        logger.info(f"语义搜索不可用，降级为纯关键词搜索: {reason}")
        return [], {"semantic_degraded": reason}, False, note

    sem_results, perf = search_semantic(
        query,
        date_from or "",
        date_to or "",
        top_k=semantic_top_k,
        min_similarity=semantic_min_similarity,
    )
    perf["semantic_time_ms"] = round((time.time() - sem_start) * 1000, 2)
    logger.info(f"[SearchPerf] Semantic: {len(sem_results)} results, {perf['semantic_time_ms']}ms")
    status_perf, semantic_available, semantic_note = _build_semantic_status(
        runtime_status, sem_results
    )
    perf.update(status_perf)

    return sem_results, perf, semantic_available, semantic_note
