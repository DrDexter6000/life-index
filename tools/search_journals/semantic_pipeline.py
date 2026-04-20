#!/usr/bin/env python3
"""
Life Index - Semantic Search Pipeline
语义搜索管道

从 core.py 提取的 pipeline_semantic() 函数。
"""

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from ..lib.search_constants import (
    SEMANTIC_ABSOLUTE_FLOOR,
    SEMANTIC_BASELINE_OFFSET,
    SEMANTIC_MIN_SIMILARITY,
    SEMANTIC_TOP_K_DEFAULT,
)
from ..lib.search_index import get_fts_db_path

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


def _load_semantic_baseline() -> float | None:
    """Load semantic_baseline_p25 from index_meta SQLite table."""
    if not get_fts_db_path().exists():
        return None

    try:
        conn = sqlite3.connect(str(get_fts_db_path()))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM index_meta WHERE key = 'semantic_baseline_p25'")
            row = cursor.fetchone()
        finally:
            conn.close()
    except (sqlite3.Error, ValueError):
        return None

    if row is None:
        return None

    try:
        return float(row[0])
    except (TypeError, ValueError):
        return None


def get_effective_semantic_threshold(
    absolute_floor: float = SEMANTIC_MIN_SIMILARITY,
) -> float:
    """Compute effective semantic threshold: max(floor, baseline_p25 + offset)."""
    baseline_p25 = _load_semantic_baseline()
    if baseline_p25 is None:
        return absolute_floor
    return max(absolute_floor, baseline_p25 + SEMANTIC_BASELINE_OFFSET)


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


def _build_entity_augmented_query(query: str, entity_hints: list[dict[str, Any]] | None) -> str:
    """Augment a semantic query with entity expansion terms.

    Appends unique expansion terms from entity hints so the embedding model
    captures entity context (e.g., "我女儿" → "我女儿 乐乐 小豆丁 小英雄").
    Does NOT duplicate the keyword pipeline's OR-expression logic.
    """
    if not entity_hints:
        return query

    expansion_terms: list[str] = []
    seen: set[str] = set()
    for hint in entity_hints:
        for term in hint.get("expansion_terms", []):
            term_str = str(term)
            # Skip terms already in the original query to avoid redundancy
            if term_str not in seen and term_str not in query:
                expansion_terms.append(term_str)
                seen.add(term_str)

    if not expansion_terms:
        return query

    return f"{query} {' '.join(expansion_terms)}"


def run_semantic_pipeline(
    *,
    query: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    semantic: bool = True,
    semantic_top_k: int = SEMANTIC_TOP_K_DEFAULT,
    semantic_min_similarity: float | None = None,
    candidate_paths: set[str] | None = None,
    entity_hints: list[dict[str, Any]] | None = None,
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
        entity_hints: Entity expansion hints from resolve_query_entities().
            Used to augment the semantic query with entity names so vector
            similarity captures relationship context.

    Returns:
        (sem_results, perf, semantic_available, semantic_note)
    """
    sem_start = time.time()

    if not semantic:
        return [], {}, False, "语义搜索已通过 --no-semantic 禁用。"
    if not query:
        return [], {}, True, None
    if semantic_min_similarity is None:
        semantic_min_similarity = get_effective_semantic_threshold(
            absolute_floor=SEMANTIC_ABSOLUTE_FLOOR
        )

    # Augment query with entity expansion terms for richer semantic embedding
    semantic_query = _build_entity_augmented_query(query, entity_hints)
    if semantic_query != query:
        logger.debug(f"Semantic query augmented: '{query}' → '{semantic_query}'")

    runtime_status = get_semantic_runtime_status()
    if not runtime_status["available"]:
        reason = str(runtime_status["reason"])
        note = str(runtime_status["note"])
        logger.info(f"语义搜索不可用，降级为纯关键词搜索: {reason}")
        return [], {"semantic_degraded": reason}, False, note

    sem_results, perf = search_semantic(
        semantic_query,
        date_from or "",
        date_to or "",
        top_k=semantic_top_k,
        min_similarity=semantic_min_similarity,
    )
    if candidate_paths is not None:
        sem_results = [
            item
            for item in sem_results
            if item.get("path")
            and str(Path(str(item["path"])).resolve()).replace("\\", "/") in candidate_paths
        ]
    perf["semantic_time_ms"] = round((time.time() - sem_start) * 1000, 2)
    logger.info(f"[SearchPerf] Semantic: {len(sem_results)} results, {perf['semantic_time_ms']}ms")
    status_perf, semantic_available, semantic_note = _build_semantic_status(
        runtime_status, sem_results
    )
    perf.update(status_perf)

    return sem_results, perf, semantic_available, semantic_note
