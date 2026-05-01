#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - Ranking
结果排序算法模块
"""

from importlib import import_module
from typing import Any, Dict, List, Optional

from ..lib.metadata_cache import get_backlinked_by, init_metadata_cache
from .l2_metadata import _query_matches_tags, _query_matches_text


def reciprocal_rank_fusion(ranked_lists: List[List[str]], k: int = 60) -> Dict[str, float]:
    """Compute RRF scores for items across multiple ranked lists.

    Each list is a sequence of document identifiers ordered by relevance.
    Returns a dict mapping each identifier to its fused RRF score.
    """
    scores: Dict[str, float] = {}
    for lst in ranked_lists:
        for rank_minus_one, doc_id in enumerate(lst):
            rank = rank_minus_one + 1
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


from .semantic import enrich_semantic_result
from ..lib.search_constants import (
    RRF_K,
    RRF_MIN_SCORE,
    SCORE_L1_BASE,
    SCORE_L2_BASE,
    SCORE_TITLE_MATCH_BONUS,
    SCORE_TITLE_MATCH_BONUS_L2,
    SCORE_ABSTRACT_MATCH_BONUS,
    SCORE_TAGS_MATCH_BONUS,
    SCORE_ENTITY_BONUS,
    TOPIC_HINT_BOOST,
    NON_RRF_MIN_SCORE,
    MAX_RESULTS_DEFAULT,
    FTS_WEIGHT_DEFAULT,
    SEMANTIC_WEIGHT_DEFAULT,
    FTS_MIN_RELEVANCE,
)


def _to_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def _entity_bonus(result: dict[str, Any], entity_hints: list[dict[str, Any]]) -> int:
    """Return entity bonus if any expansion term appears in result signals.

    B-9: Checks metadata (people|tags) AND lightweight text signals (title,
    snippet/abstract) so entity matching is not overly dependent on metadata
    completeness.
    """
    if not entity_hints:
        return 0

    expansion_terms: set[str] = set()
    for hint in entity_hints:
        expansion_terms.update(str(term) for term in hint.get("expansion_terms", []))

    if not expansion_terms:
        return 0

    # Check metadata signals (people, tags)
    metadata = result.get("metadata", {})
    if isinstance(metadata, dict):
        people = set(_to_string_list(metadata.get("people")))
        tags = set(_to_string_list(metadata.get("tags")))
        if (people | tags) & expansion_terms:
            return SCORE_ENTITY_BONUS

    # B-9: Also check lightweight text signals (title, snippet)
    title = str(result.get("title", ""))
    snippet = str(result.get("snippet", ""))
    # Also check abstract from metadata
    abstract = ""
    if isinstance(metadata, dict):
        abstract = str(metadata.get("abstract", ""))

    text_signals = f"{title} {snippet} {abstract}".lower()
    for term in expansion_terms:
        if term.lower() in text_signals:
            return SCORE_ENTITY_BONUS

    return 0


def _topic_boost_multiplier(result: dict[str, Any], topic_hints: list[str] | None) -> float:
    """Return TOPIC_HINT_BOOST if result's topic matches any topic_hints.

    Phase 4 T4.2: Conservative boost — only 1.1x, not enough to override
    large FTS/RRF score gaps.
    """
    if not topic_hints:
        return 1.0

    result_topics: set[str] = set()

    # Check top-level topic field
    topic = result.get("topic")
    if isinstance(topic, list):
        result_topics.update(str(t) for t in topic)
    elif isinstance(topic, str):
        result_topics.add(topic)

    # Check metadata.topic
    metadata = result.get("metadata", {})
    if isinstance(metadata, dict):
        meta_topic = metadata.get("topic")
        if isinstance(meta_topic, list):
            result_topics.update(str(t) for t in meta_topic)
        elif isinstance(meta_topic, str):
            result_topics.add(meta_topic)

    if result_topics & set(topic_hints):
        return TOPIC_HINT_BOOST
    return 1.0


def _dynamic_threshold_floor(base_threshold: float, dynamic_threshold: float) -> float:
    """Keep dynamic thresholds from becoming more permissive than baseline."""
    return max(base_threshold, dynamic_threshold)


def _tukey_fence_threshold(
    scores: list[float], *, base_threshold: float, k: float = 1.5
) -> float:  # Tukey standard k=1.5 (mild outliers)
    """Compute a robust threshold using Tukey's IQR fence method.

    More resistant to outliers than mean/stddev for small sample sizes.

    Args:
        scores: Non-zero score values from scored results.
        base_threshold: Minimum floor — dynamic threshold never goes below this.
        k: Tukey multiplier (1.5 = standard, 3.0 = far outliers).

    Returns:
        A threshold value ≥ base_threshold.
    """
    if len(scores) < 8:
        return base_threshold

    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    q1 = sorted_scores[n // 4]
    q3 = sorted_scores[3 * n // 4]
    iqr = q3 - q1

    if iqr <= 0:
        # All scores very similar — no meaningful spread to exploit
        return base_threshold

    lower_fence = q1 - k * iqr
    return _dynamic_threshold_floor(base_threshold, lower_fence)


def _compute_dynamic_fts_threshold(
    scored_results: list[dict[str, Any]],
    *,
    base_threshold: float,
) -> float:
    """Compute a stricter FTS threshold from score distribution using Tukey IQR."""
    scores = [float(item["score"]) for item in scored_results if float(item["score"]) > 0]
    return _tukey_fence_threshold(scores, base_threshold=base_threshold)


def _compute_dynamic_non_rrf_threshold(
    ranked_results: list[dict[str, Any]],
    *,
    base_threshold: float,
) -> float:
    """Compute a stricter non-RRF threshold from lexical score distribution using Tukey IQR."""
    scores = [float(item["fts_score"]) for item in ranked_results if float(item["fts_score"]) > 0]
    return _tukey_fence_threshold(scores, base_threshold=base_threshold)


def _compute_dynamic_rrf_threshold(
    ranked_results: list[dict[str, Any]],
    *,
    base_threshold: float,
) -> float:
    """Compute a stricter RRF threshold when enough fused results exist using Tukey IQR."""
    scores = [
        float(item["final_score"])
        for item in ranked_results
        if item.get("has_rrf") and float(item["final_score"]) > 0
    ]
    return _tukey_fence_threshold(scores, base_threshold=base_threshold)


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


def _attach_relation_context(
    data: Dict[str, Any], *, metadata_conn: Any | None = None
) -> Dict[str, Any]:
    """Attach related_entries and backlinked_by to final search result payload."""
    enriched = data.copy()
    metadata = enriched.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        enriched["metadata"] = metadata

    related_entries = metadata.get("related_entries", enriched.get("related_entries", []))
    if not isinstance(related_entries, list):
        related_entries = []

    rel_path = enriched.get("rel_path")
    backlinked_by: list[str] = []
    if isinstance(rel_path, str) and rel_path and metadata_conn is not None:
        backlinked_by = get_backlinked_by(metadata_conn, rel_path)

    enriched["related_entries"] = related_entries
    enriched["backlinked_by"] = backlinked_by
    metadata.setdefault("related_entries", related_entries)
    metadata["backlinked_by"] = backlinked_by
    return enriched


def _classify_confidence(**kwargs: Any) -> str:
    result: str = import_module("tools.search_journals.confidence").classify_confidence(**kwargs)
    return result


def merge_and_rank_results(
    l1_results: List[Dict],
    l2_results: List[Dict],
    l3_results: List[Dict],
    query: Optional[str] = None,
    min_score: float = FTS_MIN_RELEVANCE,
    max_results: int = MAX_RESULTS_DEFAULT,
    entity_hints: Optional[List[Dict[str, Any]]] = None,
    explain: bool = False,
    topic_hints: Optional[List[str]] = None,
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
            base_score += SCORE_TITLE_MATCH_BONUS
        scored[path] = {"data": r, "score": base_score, "tier": 3}

    # L2: 元数据匹配（仅当不在 L3 中时添加）
    for r in l2_results:
        path = r["path"]
        if path in scored:
            continue  # L3 已覆盖，跳过

        # L2 基础分必须低于 L3 最低分（L3 最低约 30-40）
        # 确保即使 L2 title 完全匹配，也不超过 L3 的 BM25 分数
        score = SCORE_L2_BASE  # L2 基础分（显著低于 L3 的最低分）

        if query:
            title = r.get("title", "")
            metadata = r.get("metadata", {})
            abstract = (
                metadata.get("abstract", "") if isinstance(metadata.get("abstract"), str) else ""
            )
            tags = metadata.get("tags", [])

            # title 匹配加分（限制上限，确保不超过 L3 内容匹配）
            if _query_matches_text(title, query):
                score += SCORE_TITLE_MATCH_BONUS_L2
            # abstract 匹配加分（abstract-only 命中不应越过默认门槛）
            if _query_matches_text(abstract, query):
                score += SCORE_ABSTRACT_MATCH_BONUS
            # tags 匹配加分（仅作弱辅助信号）
            if _query_matches_tags(tags, query):
                score += SCORE_TAGS_MATCH_BONUS

        score += _entity_bonus(r, entity_hints or [])

        scored[path] = {"data": r, "score": score, "tier": 2}

    # L1: 索引匹配（最低优先级）
    for r in l1_results:
        path = r["path"]
        if path in scored:
            continue
        scored[path] = {
            "data": r,
            "score": SCORE_L1_BASE,  # L1 基础分
            "tier": 1,
        }

    # Phase 4 T4.2: Apply topic hint boost (conservative multiplier)
    if topic_hints:
        for path, entry in scored.items():
            boost = _topic_boost_multiplier(entry["data"], topic_hints)
            if boost > 1.0:
                entry["score"] = entry["score"] * boost

    # 按分数降序排序，分数相同按 tier 排序（高 tier 优先）
    sorted_results = sorted(scored.values(), key=lambda x: (x["score"], x["tier"]), reverse=True)

    # 分层阈值：L3 (FTS) 使用 FTS_MIN_RELEVANCE，L2/L1 使用更宽松的 NON_RRF_MIN_SCORE
    effective_fts_threshold = _compute_dynamic_fts_threshold(
        sorted_results,
        base_threshold=min_score,
    )

    def _passes_threshold(item: Dict[str, Any]) -> bool:
        tier: int = int(item.get("tier", 0))
        score: float = float(item["score"])
        if tier >= 3:
            # L3 (FTS content match) uses FTS threshold
            return score >= effective_fts_threshold
        else:
            # L2/L1 (metadata/index) use more lenient threshold
            return score >= NON_RRF_MIN_SCORE

    sorted_results = [item for item in sorted_results if _passes_threshold(item)]
    # NOTE: Truncation removed per Phase 2 (Task 3) — ranking returns ALL results.
    # Truncation now happens in core.py (presentation concern, not ranking concern).

    # 提取数据并添加排名信息
    merged = []
    metadata_conn = init_metadata_cache()
    try:
        for rank, item in enumerate(sorted_results, 1):
            data = _attach_relation_context(item["data"], metadata_conn=metadata_conn)
            data["search_rank"] = rank
            # T4.2: Unified score fields (non-hybrid path)
            data["rrf_score"] = 0.0  # Non-hybrid has no RRF fusion
            data["final_score"] = round(float(item["score"]), 2)
            data["relevance_score"] = data["final_score"]  # backward-compat alias
            data["fts_score"] = round(float(item["score"]), 2)
            data["semantic_score"] = 0.0
            # T4.3: Source field (non-hybrid: all results are FTS-tier, no semantic)
            data["source"] = "fts" if item.get("tier", 0) >= 3 else "none"
            data["confidence"] = _classify_confidence(
                fts_score=float(item["score"]),
                semantic_score=0.0,
                rrf_score=0.0,
            )
            # T3.4: Explain support for non-hybrid path
            if explain:
                data["explain"] = {
                    "keyword_pipeline": {
                        "fts_score": round(float(item["score"]), 2),
                        "has_fts_match": item.get("tier", 0) >= 3,
                    },
                    "semantic_pipeline": {
                        "cosine_similarity": 0.0,
                        "has_semantic_match": False,
                    },
                    "fusion": {
                        "rrf_score": 0.0,
                        "has_rrf": False,
                    },
                }
            merged.append(data)
    finally:
        metadata_conn.close()

    return merged


def merge_and_rank_results_hybrid(
    l1_results: List[Dict],
    l2_results: List[Dict],
    l3_results: List[Dict],
    semantic_results: List[Dict],
    query: Optional[str] = None,
    fts_weight: float = FTS_WEIGHT_DEFAULT,
    semantic_weight: float = SEMANTIC_WEIGHT_DEFAULT,
    min_rrf_score: float = RRF_MIN_SCORE,
    min_non_rrf_score: float = NON_RRF_MIN_SCORE,
    max_results: int = MAX_RESULTS_DEFAULT,
    explain: bool = False,  # Task 2.1: explain mode
    entity_hints: Optional[List[Dict[str, Any]]] = None,
    topic_hints: Optional[List[str]] = None,
) -> List[Dict]:
    """
    混合排序：结合 FTS (BM25) 和语义搜索结果（RRF）

    Args:
        l1_results: L1 索引层结果
        l2_results: L2 元数据层结果
        l3_results: L3 内容层结果（FTS）
        semantic_results: 语义搜索结果
        query: 查询词
        fts_weight: FTS 排名权重（默认 FTS_WEIGHT_DEFAULT，影响关键词命中在最终结果中的占比）
        semantic_weight: 语义排名权重（默认 SEMANTIC_WEIGHT_DEFAULT，影响语义相似度在最终结果中的占比）
    """

    scored: Dict[str, Dict[str, Any]] = (
        {}
    )  # path -> {data, fts_score, semantic_score, final_score, rrf_score, tier, has_rrf}

    # 先构建 FTS 排名（按 relevance + title_match bonus）
    fts_ranked_paths: List[str] = []
    fts_ordered = sorted(
        l3_results,
        key=lambda r: (
            r.get("relevance", 0) + (SCORE_TITLE_MATCH_BONUS if r.get("title_match") else 0),
            r.get("path", ""),
        ),
        reverse=True,
    )

    # 处理 L3/FTS 结果（记录分项分数用于输出）
    # 同时补充元数据（abstract, tags, topic 等），与语义结果格式统一
    for r in l3_results:
        path = r["path"]
        fts_score = r.get("relevance", 0)
        if r.get("title_match"):
            fts_score += SCORE_TITLE_MATCH_BONUS

        # 为 FTS 结果补充元数据，统一格式
        enriched_data = enrich_semantic_result(r)

        scored[path] = {
            "data": enriched_data,
            "fts_score": float(fts_score),
            "semantic_score": 0.0,
            "final_score": 0.0,
            "rrf_score": 0.0,
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
                "rrf_score": 0.0,
                "tier": 4,  # 语义层
                "has_rrf": False,
            }

    for r in semantic_ordered:
        path = r.get("path")
        if path:
            semantic_ranked_paths.append(path)

    # RRF 融合分数（加权融合：FTS 管道 × fts_weight，语义管道 × semantic_weight）
    k = RRF_K
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
            scored[path]["rrf_score"] = score
            scored[path]["has_rrf"] = True

    # 处理 L2 结果（仅当不在 L3/语义中时）
    for r in l2_results:
        path = r["path"]
        if path in scored:
            continue

        score = SCORE_L2_BASE  # L2 基础分
        if query:
            title = r.get("title", "")
            metadata = r.get("metadata", {})
            abstract = (
                metadata.get("abstract", "") if isinstance(metadata.get("abstract"), str) else ""
            )
            tags = metadata.get("tags", [])

            if _query_matches_text(title, query):
                score += SCORE_TITLE_MATCH_BONUS_L2
            if _query_matches_text(abstract, query):
                score += SCORE_ABSTRACT_MATCH_BONUS
            if _query_matches_tags(tags, query):
                score += SCORE_TAGS_MATCH_BONUS

        score += _entity_bonus(r, entity_hints or [])

        scored[path] = {
            "data": r,
            "fts_score": 0.0,
            "semantic_score": 0.0,
            "final_score": float(score),
            "rrf_score": 0.0,
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
            "final_score": float(SCORE_L1_BASE),
            "rrf_score": 0.0,
            "tier": 1,
            "has_rrf": False,
        }

    # Phase 4 T4.2: Apply topic hint boost (conservative multiplier) to final_score
    if topic_hints:
        for path, entry in scored.items():
            boost = _topic_boost_multiplier(entry["data"], topic_hints)
            if boost > 1.0:
                entry["final_score"] = entry["final_score"] * boost

    # 按混合检索意图排序：
    # 1) 真正的关键词命中（尤其 FTS）优先
    # 2) 结构化关键词命中（L2/L1）次之
    # 3) 纯语义结果作为补漏回填
    #
    # T3.8 (ADR-014): Note on score dimensions.
    # _hybrid_priority() separates FTS (5), L2 (4), L1 (3), semantic (2) into
    # distinct priority buckets. Within each bucket, scores come from the same
    # source and are directly comparable. Cross-bucket ordering is handled by
    # the priority function, not by score comparison. This design avoids the
    # dimension mismatch problem by construction.
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
    # Dynamic threshold via Tukey IQR, floored by the base constant (ADR-004).
    # max() ensures the A/B-selected floor is never violated, even if the
    # dynamic calculation returns a lower value due to score distribution.
    _dynamic_rrf = _compute_dynamic_rrf_threshold(
        sorted_results,
        base_threshold=min_rrf_score,
    )
    effective_min_rrf_score = max(_dynamic_rrf, min_rrf_score)
    _dynamic_non_rrf = _compute_dynamic_non_rrf_threshold(
        sorted_results,
        base_threshold=min_non_rrf_score,
    )
    effective_min_non_rrf_score = max(_dynamic_non_rrf, min_non_rrf_score)
    thresholded_results = [
        item
        for item in sorted_results
        if (item["has_rrf"] and item["final_score"] >= effective_min_rrf_score)
        or (not item["has_rrf"] and item["final_score"] >= effective_min_non_rrf_score)
    ]

    # Low-recall backfill: if thresholding removes every retrieval hit,
    # preserve a small amount of the strongest lexical/semantic evidence
    # instead of returning an empty hybrid result set. Do not pad already
    # useful result sets with extra semantic neighbors.
    has_retrieval_signal = any(
        item["fts_score"] > 0 or item["semantic_score"] > 0 for item in sorted_results
    )
    target_count = min(3, len(sorted_results), max_results)
    if has_retrieval_signal and not thresholded_results:
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

    sorted_results = thresholded_results
    # NOTE: Truncation removed per Phase 2 (Task 3) — ranking returns ALL results.
    # Truncation now happens in core.py (presentation concern, not ranking concern).

    # 提取数据并添加排名
    merged = []
    metadata_conn = init_metadata_cache()
    try:
        for rank, item in enumerate(sorted_results, 1):
            data = _attach_relation_context(item["data"], metadata_conn=metadata_conn)
            data["search_rank"] = rank
            # T4.2: Unified score fields (hybrid path)
            data["rrf_score"] = round(float(item["rrf_score"]), 4)
            data["final_score"] = round(float(item["final_score"]), 4)
            data["relevance_score"] = data["rrf_score"] if item["has_rrf"] else data["final_score"]
            data["fts_score"] = round(item["fts_score"], 2)
            data["semantic_score"] = round(item["semantic_score"], 2)
            # T4.3: Source field reflecting actual pipeline hits
            _sources = []
            if item["fts_score"] > 0:
                _sources.append("fts")
            if item["semantic_score"] > 0:
                _sources.append("semantic")
            data["source"] = ",".join(_sources) if _sources else "none"

            data["confidence"] = _classify_confidence(
                fts_score=float(item["fts_score"]),
                semantic_score=float(item["semantic_score"]),
                rrf_score=float(item["rrf_score"]),
            )

            # Task 2.1: Add explain field
            if explain:
                data["explain"] = {
                    "keyword_pipeline": {
                        "fts_score": round(item["fts_score"], 2),
                        "has_fts_match": item["fts_score"] > 0,
                    },
                    "semantic_pipeline": {
                        "cosine_similarity": (
                            round(item["semantic_score"] / 100.0, 4)
                            if item["semantic_score"] > 0
                            else 0.0
                        ),
                        "has_semantic_match": item["semantic_score"] > 0,
                    },
                    "fusion": {
                        "rrf_score": round(item["rrf_score"], 4),
                        "has_rrf": item["has_rrf"],
                    },
                }

            merged.append(data)
    finally:
        metadata_conn.close()

    return merged
