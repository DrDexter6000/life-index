#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - Ranking
结果排序算法模块
"""

from typing import Any, Dict, List, Optional

from .semantic import enrich_semantic_result


def reciprocal_rank_fusion(
    ranked_lists: List[List[str]], k: int = 60
) -> Dict[str, float]:
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
        base_score = r.get("relevance", 50)
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
            query_lower = query.lower()
            title = r.get("title", "").lower()
            metadata = r.get("metadata", {})
            abstract = (
                metadata.get("abstract", "").lower()
                if isinstance(metadata.get("abstract"), str)
                else ""
            )
            tags = metadata.get("tags", [])
            tags_str = (
                " ".join(tags).lower() if isinstance(tags, list) else str(tags).lower()
            )

            # title 匹配 +8 分（限制上限，确保不超过 L3 内容匹配）
            if query_lower in title:
                score += 8
            # abstract 匹配 +5 分
            if query_lower in abstract:
                score += 5
            # tags 匹配 +2 分
            if query_lower in tags_str:
                score += 2

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
    sorted_results = sorted(
        scored.values(), key=lambda x: (x["score"], x["tier"]), reverse=True
    )

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
) -> List[Dict]:
    """
    混合排序：结合 FTS (BM25) 和语义搜索结果（RRF）

    Args:
        l1_results: L1 索引层结果
        l2_results: L2 元数据层结果
        l3_results: L3 内容层结果（FTS）
        semantic_results: 语义搜索结果
        query: 查询词
        fts_weight: 已弃用（为向后兼容保留）
        semantic_weight: 已弃用（为向后兼容保留）
    """
    # 保留参数以兼容旧调用方（RRF 不再使用权重融合）
    _ = fts_weight, semantic_weight

    scored: Dict[
        str, Dict[str, Any]
    ] = {}  # path -> {data, fts_score, semantic_score, final_score, tier, has_rrf}

    # 先构建 FTS 排名（按 relevance + title_match bonus）
    fts_ranked_paths: List[str] = []
    fts_ordered = sorted(
        l3_results,
        key=lambda r: (
            r.get("relevance", 50) + (10 if r.get("title_match") else 0),
            r.get("path", ""),
        ),
        reverse=True,
    )

    # 处理 L3/FTS 结果（记录分项分数用于输出）
    for r in l3_results:
        path = r["path"]
        fts_score = r.get("relevance", 50)
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

    # RRF 融合分数（只融合 FTS + 语义两个排序列表）
    rrf_scores = reciprocal_rank_fusion([fts_ranked_paths, semantic_ranked_paths], k=60)
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
            query_lower = query.lower()
            title = r.get("title", "").lower()
            metadata = r.get("metadata", {})
            abstract = (
                metadata.get("abstract", "").lower()
                if isinstance(metadata.get("abstract"), str)
                else ""
            )
            tags = metadata.get("tags", [])
            tags_str = (
                " ".join(tags).lower() if isinstance(tags, list) else str(tags).lower()
            )

            if query_lower in title:
                score += 8
            if query_lower in abstract:
                score += 5
            if query_lower in tags_str:
                score += 2

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

    # 按最终得分排序：有 RRF 融合分数的结果优先，其次按分数，再按 tier
    sorted_results = sorted(
        scored.values(),
        key=lambda x: (x["has_rrf"], x["final_score"], x["tier"]),
        reverse=True,
    )

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
