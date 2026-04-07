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
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..lib.entity_graph import load_entity_graph, resolve_entity
from ..lib.entity_schema import EntityGraphValidationError
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


_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _normalize_candidate_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _extract_candidate_path(link_target: str) -> Path | None:
    cleaned = link_target.strip()
    if not cleaned or cleaned.startswith(("http://", "https://", "#")):
        return None

    candidate = Path(cleaned)
    if not candidate.is_absolute():
        from ..lib.config import USER_DATA_DIR

        candidate = USER_DATA_DIR / cleaned

    return candidate.resolve()


def _topic_index_path(topic: str) -> Path:
    from ..lib.config import USER_DATA_DIR

    return USER_DATA_DIR / "by-topic" / f"主题_{topic}.md"


def build_l0_candidate_set(
    *, year: int | None = None, month: int | None = None, topic: str | None = None
) -> set[str] | None:
    from ..lib.config import JOURNALS_DIR

    candidate_sets: list[set[str]] = []

    if year is not None:
        if month is not None:
            journal_paths = (JOURNALS_DIR / str(year) / f"{month:02d}").glob(
                "life-index_*.md"
            )
        else:
            journal_paths = (JOURNALS_DIR / str(year)).glob("**/life-index_*.md")
        candidate_sets.append(
            {_normalize_candidate_path(path) for path in journal_paths}
        )

    if topic:
        topic_index = _topic_index_path(topic)
        if topic_index.exists():
            topic_paths: set[str] = set()
            for link_target in _MARKDOWN_LINK_RE.findall(
                topic_index.read_text(encoding="utf-8")
            ):
                candidate_path = _extract_candidate_path(link_target)
                if candidate_path and candidate_path.name.startswith("life-index_"):
                    topic_paths.add(_normalize_candidate_path(candidate_path))
            candidate_sets.append(topic_paths)

    if not candidate_sets:
        return None

    intersection = set(candidate_sets[0])
    for candidate_set in candidate_sets[1:]:
        intersection &= candidate_set
    return intersection


def _filter_results_by_candidates(
    results: list[dict[str, Any]], candidate_paths: set[str] | None
) -> list[dict[str, Any]]:
    if candidate_paths is None:
        return results

    filtered_results: list[dict[str, Any]] = []
    for item in results:
        path_value = (
            item.get("path") or item.get("journal_route_path") or item.get("rel_path")
        )
        if not path_value:
            continue
        normalized = _normalize_candidate_path(Path(str(path_value)))
        if normalized in candidate_paths:
            filtered_results.append(item)
    return filtered_results


def expand_query_with_entity_graph(query: str) -> str:
    # Read USER_DATA_DIR dynamically to support test isolation (fixture reloads paths module)
    from ..lib.paths import USER_DATA_DIR as _current_data_dir

    graph_path = _current_data_dir / "entity_graph.yaml"
    try:
        graph = load_entity_graph(graph_path)
    except EntityGraphValidationError as exc:
        logger.warning("Skipping entity graph expansion due to invalid graph: %s", exc)
        return query
    if not graph:
        return query

    whole_match = resolve_entity(query, graph)
    if whole_match:
        names = [whole_match["primary_name"], *whole_match.get("aliases", [])]
        deduped: list[str] = []
        for name in names:
            if name not in deduped:
                deduped.append(name)
        return "(" + " OR ".join(deduped) + ")"

    tokens = [token for token in query.split() if token.strip()]
    expanded_tokens: list[str] = []

    def expand_from_entity(entity: dict[str, Any]) -> str:
        names = [entity["primary_name"], *entity.get("aliases", [])]
        deduped: list[str] = []
        for name in names:
            if name not in deduped:
                deduped.append(name)
        return "(" + " OR ".join(deduped) + ")"

    def expand_relationship_phrase(token: str) -> str | None:
        if not token.endswith("的奶奶"):
            return None

        subject = token[: -len("的奶奶")].strip()
        if not subject:
            return None

        source = resolve_entity(subject, graph)
        if source is None:
            return None

        for relationship in source.get("relationships", []):
            if relationship.get("relation") != "granddaughter_of":
                continue
            target = resolve_entity(relationship["target"], graph)
            if target:
                return expand_from_entity(target)
        return None

    for token in tokens:
        relationship_expansion = expand_relationship_phrase(token)
        if relationship_expansion:
            expanded_tokens.append(relationship_expansion)
            continue

        matched_entity = resolve_entity(token, graph)
        if matched_entity:
            expanded_tokens.append(expand_from_entity(matched_entity))
        else:
            replacements = token
            for entity in graph:
                for alias in [entity["primary_name"], *entity.get("aliases", [])]:
                    if alias in replacements:
                        replacements = replacements.replace(
                            alias, expand_from_entity(entity)
                        )
            expanded_tokens.append(replacements)

    expanded = " ".join(expanded_tokens).strip()
    return expanded or query


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
    year: Optional[int] = None,
    month: Optional[int] = None,
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
    explain: bool = False,  # Task 2.1: explain mode
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
            "year": year,
            "month": month,
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

    expanded_query = expand_query_with_entity_graph(query) if query else query
    if expanded_query != query:
        result["query_params"]["expanded_query"] = expanded_query
    query = expanded_query

    start_time = time.time()
    candidate_paths = build_l0_candidate_set(year=year, month=month, topic=topic)

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
            candidate_paths=candidate_paths,
        )
        future_semantic = executor.submit(
            run_semantic_pipeline,
            query=query,
            date_from=date_from,
            date_to=date_to,
            semantic=semantic,
            semantic_top_k=semantic_top_k,
            semantic_min_similarity=semantic_min_similarity,
            candidate_paths=candidate_paths,
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

    l1_results = _filter_results_by_candidates(l1_results, candidate_paths)
    l2_results = _filter_results_by_candidates(l2_results, candidate_paths)
    l3_results = _filter_results_by_candidates(l3_results, candidate_paths)
    semantic_results = _filter_results_by_candidates(semantic_results, candidate_paths)

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
            explain=explain,  # Task 2.1
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
        f"[SearchPerf] Total: {total_time}ms "
        f"(L1:{l1_time} L2:{l2_time} L3:{l3_time} Semantic:{sem_time}) "
        f"| Results: {result['total_found']}"
    )

    return result
