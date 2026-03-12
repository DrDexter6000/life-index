#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - Ranking
结果排序算法模块
"""

from typing import Any, Dict, List, Optional

from .semantic import enrich_semantic_result


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
    scored = {}  # path -> {data, score, tier}

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
    混合排序：结合 FTS (BM25) 和语义搜索结果

    Args:
        l1_results: L1 索引层结果
        l2_results: L2 元数据层结果
        l3_results: L3 内容层结果（FTS）
        semantic_results: 语义搜索结果
        query: 查询词
        fts_weight: FTS 得分权重
        semantic_weight: 语义得分权重
    """
    scored = {}  # path -> {data, fts_score, semantic_score, final_score}

    # 处理 L3/FTS 结果
    max_fts_score = 0
    for r in l3_results:
        path = r["path"]
        # 使用 BM25 relevance 分数（0-100）
        fts_score = r.get("relevance", 50)
        if r.get("title_match"):
            fts_score += 10
        max_fts_score = max(max_fts_score, fts_score)

        scored[path] = {
            "data": r,
            "fts_score": fts_score / 100.0,  # 归一化到 0-1
            "semantic_score": 0,
            "tier": 3,
        }

    # 处理语义结果
    max_semantic_score = (
        max([r.get("similarity", 0) for r in semantic_results])
        if semantic_results
        else 1.0
    )
    if max_semantic_score == 0:
        max_semantic_score = 1.0

    for r in semantic_results:
        path = r["path"]
        semantic_score = r.get("similarity", 0) / max_semantic_score  # 归一化

        if path in scored:
            # 已存在，合并语义分数
            scored[path]["semantic_score"] = semantic_score
        else:
            # 新结果 - 需要补充读取文件元数据
            enriched_data = enrich_semantic_result(r)
            scored[path] = {
                "data": enriched_data,
                "fts_score": 0,
                "semantic_score": semantic_score,
                "tier": 4,  # 语义层
            }

    # 计算最终得分
    for path, item in scored.items():
        item["final_score"] = (
            item["fts_score"] * fts_weight + item["semantic_score"] * semantic_weight
        ) * 100  # 转换回 0-100 范围

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
            "fts_score": 0,
            "semantic_score": 0,
            "final_score": score,
            "tier": 2,
        }

    # 处理 L1 结果
    for r in l1_results:
        path = r["path"]
        if path in scored:
            continue
        scored[path] = {
            "data": r,
            "fts_score": 0,
            "semantic_score": 0,
            "final_score": 10,
            "tier": 1,
        }

    # 按最终得分排序
    sorted_results = sorted(
        scored.values(), key=lambda x: (x["final_score"], x["tier"]), reverse=True
    )

    # 提取数据并添加排名
    merged = []
    for rank, item in enumerate(sorted_results, 1):
        data = item["data"].copy()
        data["search_rank"] = rank
        data["relevance_score"] = round(item["final_score"], 2)
        data["fts_score"] = round(item["fts_score"] * 100, 2)
        data["semantic_score"] = round(item["semantic_score"] * 100, 2)
        merged.append(data)

    return merged
