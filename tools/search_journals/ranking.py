#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - Ranking
结果排序算法模块
"""

from typing import Any, Dict, List, Optional

from .l2_metadata import _query_matches_tags, _query_matches_text
from .semantic import enrich_semantic_result


def _hybrid_priority(item: Dict[str, Any]) -> int:
    """Priority bucket for hybrid result ordering.

    Prefer true lexical matches first, then keyword-only metadata hits,
    then semantic-only backfill.
    """
    fts_score = float(item.get("fts_score", 0.0))
    semantic_score = float(item.get("semantic_score", 0.0))
    tier = int(item.get("tier", 0))

    if fts_score > 0:
        return 5
    if tier == 2:
        return 4
    if tier == 1:
        return 3
    if semantic_score > 0:
        return 2
    return 0


def _hybrid_backfill_score(item: Dict[str, Any]) -> float:
    """Display score for low-recall hybrid backfill entries."""
    fts_score = float(item.get("fts_score", 0.0))
    semantic_score = float(item.get("semantic_score", 0.0))
    final_score = float(item.get("final_score", 0.0))

    if fts_score > 0:
        return max(final_score, fts_score)
    if semantic_score > 0:
        return max(final_score, semantic_score)
    return final_score


def reciprocal_rank_fusion(ranked_lists: List[List[str]], k: int = 60) -> Dict[str, float]:
    """
    Reciprocal Rank Fusion (RRF)

    论文：Cormack et al., SIGIR 2009
    score(d) = Σ 1 / (k + rank_d)

    Args:
        ranked_lists: 多个有序文档 ID 列表（rank 从 1 开始）
        k: 平滑常数，业界常用 60

    Returns:
        dict[path, rrf_score]
    """
    scores: Dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


def merge_and_rank_results(
    l1_results: List[Dict],
    l2_results: List[Dict],
    l3_results: List[Dict],
    query: Optional[str] = None,
    min_score: float = 25,
    max_results: int = 20,
) -> List[Dict]:
    """
    合并三层搜索结果并按相关性排序

    排序策略：
    1. L3 内容匹配（最高优先级）：使用 BM25 分数
    2. L2 元数据匹配：title/abstract 匹配加分
    3. L1 索引匹配：基础存在分
    """
    scored: Dict[str, Dict[str, Any]] = {}  # path -> {data, score, tier}

    # L3: 内容匹配（最高优先级，BM25 分数已计算）
    for r in l3_results:
        path = r["path"]
        # BM25 分数转换：relevance 已经是 0-100 的匹配度
        base_score = r.get("relevance", 0)
        # 标题匹配额外加分
        if r.get("title_match"):
            base_score += 10
        scored[path] = {"data": r, "score": base_score, "tier": 3}

    # L2: 元数据匹配（仅当不在 L3 中时添加）
    for r in l2_results:
        path = r["path"]
        if path in scored:
            continue  # L3 已覆盖，跳过

        # L2 基础分必须低于 L3 最低分（L3 最低约 30-40）
        # 确保即使 L2 title 完全匹配，也不超过 L3 的 BM25 分数
        score = 20  # L2 基础分（显著低于 L3 的最低分）

        if query:
            title = r.get("title", "")
            metadata = r.get("metadata", {})
            abstract = (
                metadata.get("abstract", "") if isinstance(metadata.get("abstract"), str) else ""
            )
            tags = metadata.get("tags", [])

            # title 匹配 +8 分（限制上限，确保不超过 L3 内容匹配）
            if _query_matches_text(title, query):
                score += 8
            # abstract 匹配 +4 分（abstract-only 命中不应越过默认门槛）
            if _query_matches_text(abstract, query):
                score += 4
            # tags 匹配 +1 分（仅作弱辅助信号）
            if _query_matches_tags(tags, query):
                score += 1

        scored[path] = {"data": r, "score": score, "tier": 2}

    # L1: 索引匹配（最低优先级）
    for r in l1_results:
        path = r["path"]
        if path in scored:
            continue
        scored[path] = {
            "data": r,
            "score": 10,  # L1 基础分
            "tier": 1,
        }

    # 按分数降序排序，分数相同按 tier 排序（高 tier 优先）
    sorted_results = sorted(scored.values(), key=lambda x: (x["score"], x["tier"]), reverse=True)
    effective_min_score = min_score
    if query and min_score == 25:
        effective_min_score = 26
    sorted_results = [item for item in sorted_results if item["score"] >= effective_min_score]
    sorted_results = sorted_results[:max_results]

    # 提取数据并添加排名信息
    merged = []
    for rank, item in enumerate(sorted_results, 1):
        data = item["data"].copy()
        data["search_rank"] = rank
        data["relevance_score"] = item["score"]
        merged.append(data)

    return merged


def merge_and_rank_results_hybrid(
    l1_results: List[Dict],
    l2_results: List[Dict],
    l3_results: List[Dict],
    semantic_results: List[Dict],
    query: Optional[str] = None,
    fts_weight: float = 0.6,
    semantic_weight: float = 0.4,
    min_rrf_score: float = 0.016,
    min_non_rrf_score: float = 25,
    max_results: int = 20,
) -> List[Dict]:
    """
    混合排序：结合 FTS (BM25) 和语义搜索结果（RRF）

    Args:
        l1_results: L1 索引层结果
        l2_results: L2 元数据层结果
        l3_results: L3 内容层结果（FTS）
        semantic_results: 语义搜索结果
        query: 查询词
        fts_weight: FTS 排名权重（默认 0.6，影响关键词命中在最终结果中的占比）
        semantic_weight: 语义排名权重（默认 0.4，影响语义相似度在最终结果中的占比）
    """

    scored: Dict[str, Dict[str, Any]] = (
        {}
    )  # path -> {data, fts_score, semantic_score, final_score, tier, has_rrf}

    # 先构建 FTS 排名（按 relevance + title_match bonus）
    fts_ranked_paths: List[str] = []
    fts_ordered = sorted(
        l3_results,
        key=lambda r: (
            r.get("relevance", 0) + (10 if r.get("title_match") else 0),
            r.get("path", ""),
        ),
        reverse=True,
    )

    # 处理 L3/FTS 结果（记录分项分数用于输出）
    for r in l3_results:
        path = r["path"]
        fts_score = r.get("relevance", 0)
        if r.get("title_match"):
            fts_score += 10

        scored[path] = {
            "data": r,
            "fts_score": float(fts_score),
            "semantic_score": 0.0,
            "final_score": 0.0,
            "tier": 3,
            "has_rrf": False,
        }

    for r in fts_ordered:
        path = r.get("path")
        if path:
            fts_ranked_paths.append(path)

    # 构建语义排名（按 similarity 降序）
    semantic_ranked_paths: List[str] = []
    semantic_ordered = sorted(
        semantic_results,
        key=lambda r: (r.get("similarity", 0), r.get("path", "")),
        reverse=True,
    )

    # 处理语义结果（记录分项分数用于输出）
    for r in semantic_results:
        path = r["path"]
        semantic_score = float(r.get("similarity", 0)) * 100.0

        if path in scored:
            scored[path]["semantic_score"] = semantic_score
        else:
            enriched_data = enrich_semantic_result(r)
            scored[path] = {
                "data": enriched_data,
                "fts_score": 0.0,
                "semantic_score": semantic_score,
                "final_score": 0.0,
                "tier": 4,  # 语义层
                "has_rrf": False,
            }

    for r in semantic_ordered:
        path = r.get("path")
        if path:
            semantic_ranked_paths.append(path)

    # RRF 融合分数（加权融合：FTS 管道 × fts_weight，语义管道 × semantic_weight）
    k = 60
    scores: Dict[str, float] = {}
    for rank, doc_id in enumerate(fts_ranked_paths, start=1):
        if doc_id:
            scores[doc_id] = scores.get(doc_id, 0.0) + fts_weight / (k + rank)
    for rank, doc_id in enumerate(semantic_ranked_paths, start=1):
        if doc_id:
            scores[doc_id] = scores.get(doc_id, 0.0) + semantic_weight / (k + rank)
    rrf_scores = scores
    for path, score in rrf_scores.items():
        if path in scored:
            scored[path]["final_score"] = score
            scored[path]["has_rrf"] = True

    # 处理 L2 结果（仅当不在 L3/语义中时）
    for r in l2_results:
        path = r["path"]
        if path in scored:
            continue

        score = 20  # L2 基础分
        if query:
            title = r.get("title", "")
            metadata = r.get("metadata", {})
            abstract = (
                metadata.get("abstract", "") if isinstance(metadata.get("abstract"), str) else ""
            )
            tags = metadata.get("tags", [])

            if _query_matches_text(title, query):
                score += 8
            if _query_matches_text(abstract, query):
                score += 4
            if _query_matches_tags(tags, query):
                score += 1

        scored[path] = {
            "data": r,
            "fts_score": 0.0,
            "semantic_score": 0.0,
            "final_score": float(score),
            "tier": 2,
            "has_rrf": False,
        }

    # 处理 L1 结果
    for r in l1_results:
        path = r["path"]
        if path in scored:
            continue
        scored[path] = {
            "data": r,
            "fts_score": 0.0,
            "semantic_score": 0.0,
            "final_score": 10.0,
            "tier": 1,
            "has_rrf": False,
        }

    # 按混合检索意图排序：
    # 1) 真正的关键词命中（尤其 FTS）优先
    # 2) 结构化关键词命中（L2/L1）次之
    # 3) 纯语义结果作为补漏回填
    sorted_results = sorted(
        scored.values(),
        key=lambda x: (
            _hybrid_priority(x),
            x["final_score"],
            x["fts_score"],
            x["semantic_score"],
        ),
        reverse=True,
    )
    effective_min_non_rrf_score = min_non_rrf_score
    if query and min_non_rrf_score == 25:
        effective_min_non_rrf_score = 26
    thresholded_results = [
        item
        for item in sorted_results
        if (item["has_rrf"] and item["final_score"] >= min_rrf_score)
        or (not item["has_rrf"] and item["final_score"] >= effective_min_non_rrf_score)
    ]

    # Low-recall backfill: if thresholding leaves too few real retrieval hits,
    # preserve a small amount of strong lexical/semantic evidence instead of
    # returning an empty (or near-empty) hybrid result set.
    has_retrieval_signal = any(
        item["fts_score"] > 0 or item["semantic_score"] > 0 for item in sorted_results
    )
    target_count = min(3, len(sorted_results), max_results)
    if has_retrieval_signal and len(thresholded_results) < target_count:
        seen_paths = {
            str(item["data"].get("path", ""))
            for item in thresholded_results
            if item["data"].get("path")
        }
        for item in sorted_results:
            path = str(item["data"].get("path", ""))
            if path in seen_paths:
                continue
            fallback_item = dict(item)
            fallback_item["final_score"] = _hybrid_backfill_score(item)
            thresholded_results.append(fallback_item)
            if path:
                seen_paths.add(path)
            if len(thresholded_results) >= target_count:
                break

    sorted_results = thresholded_results[:max_results]

    # 提取数据并添加排名
    merged = []
    for rank, item in enumerate(sorted_results, 1):
        data = item["data"].copy()
        data["search_rank"] = rank
        data["relevance_score"] = item["final_score"]
        data["fts_score"] = round(item["fts_score"], 2)
        data["semantic_score"] = round(item["semantic_score"], 2)
        merged.append(data)

    return merged
