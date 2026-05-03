#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - Core
核心协调模块

双管道并行搜索架构:
  Pipeline A (关键词): L1 索引过滤 → L2 元数据过滤 → L3 FTS5 内容匹配
  Pipeline B (语义):   向量相似度搜索
  融合: RRF (Reciprocal Rank Fusion, k=RRF_K)
"""

import logging
import os
import re
import time
from datetime import date
from importlib import import_module
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..lib.entity_graph import load_entity_graph
from ..lib.entity_runtime import (
    build_runtime_view,
    resolve_via_runtime,
)
from ..lib.entity_relations import normalize_relation
from ..lib.entity_schema import EntityGraphValidationError
from ..lib.search_constants import (
    SEMANTIC_TOP_K_DEFAULT,
    SEMANTIC_MIN_SIMILARITY,
    FTS_MIN_RELEVANCE,
    RRF_MIN_SCORE,
    NON_RRF_MIN_SCORE,
    SEMANTIC_WEIGHT_DEFAULT,
    FTS_WEIGHT_DEFAULT,
    MAX_RESULTS_DEFAULT,
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


def _emit_search_metrics(result: Dict[str, Any]) -> None:
    metrics_module = import_module("tools.lib.search_metrics")
    metrics_module.emit_search_metrics(result)


def _compute_no_confident_match(results: list[dict[str, Any]]) -> bool:
    confidence_module = import_module("tools.search_journals.confidence")
    result: bool = confidence_module.compute_no_confident_match(results)
    return result


def _normalize_candidate_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _extract_candidate_path(link_target: str) -> Path | None:
    cleaned = link_target.strip()
    if not cleaned or cleaned.startswith(("http://", "https://", "#")):
        return None

    candidate = Path(cleaned)
    if not candidate.is_absolute():
        from ..lib.paths import get_user_data_dir

        candidate = get_user_data_dir() / cleaned

    return candidate.resolve()


def _topic_index_path(topic: str) -> Path:
    from ..lib.paths import get_user_data_dir

    return get_user_data_dir() / "by-topic" / f"主题_{topic}.md"


def _parse_journal_date(filename: str) -> str | None:
    """Extract the date portion (YYYY-MM-DD) from a journal filename.

    Filenames follow the pattern: life-index_YYYY-MM-DD_NNN.md
    Returns None if the filename doesn't match the expected pattern.
    """
    import re as _re

    m = _re.match(r"life-index_(\d{4}-\d{2}-\d{2})_\d+\.md", filename)
    return m.group(1) if m else None


def build_l0_candidate_set(
    *,
    year: int | None = None,
    month: int | None = None,
    topic: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> set[str] | None:
    from ..lib.paths import get_journals_dir

    _journals_dir = get_journals_dir()

    candidate_sets: list[set[str]] = []

    if year is not None:
        if month is not None:
            journal_paths = (_journals_dir / str(year) / f"{month:02d}").glob("life-index_*.md")
        else:
            journal_paths = (_journals_dir / str(year)).glob("**/life-index_*.md")
        candidate_sets.append({_normalize_candidate_path(path) for path in journal_paths})

    if topic:
        topic_index = _topic_index_path(topic)
        if topic_index.exists():
            topic_paths: set[str] = set()
            for link_target in _MARKDOWN_LINK_RE.findall(topic_index.read_text(encoding="utf-8")):
                candidate_path = _extract_candidate_path(link_target)
                if candidate_path and candidate_path.name.startswith("life-index_"):
                    topic_paths.add(_normalize_candidate_path(candidate_path))
            candidate_sets.append(topic_paths)

    # Phase 4 T4.1: date_from/date_to filtering via filename date extraction
    if date_from is not None or date_to is not None:
        date_filtered: set[str] = set()
        for journal_path in _journals_dir.glob("**/life-index_*.md"):
            journal_date = _parse_journal_date(journal_path.name)
            if journal_date is None:
                continue
            if date_from is not None and journal_date < date_from:
                continue
            if date_to is not None and journal_date > date_to:
                continue
            date_filtered.add(_normalize_candidate_path(journal_path))
        candidate_sets.append(date_filtered)

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
        path_value = item.get("path") or item.get("journal_route_path") or item.get("rel_path")
        if not path_value:
            continue
        normalized = _normalize_candidate_path(Path(str(path_value)))
        if normalized in candidate_paths:
            filtered_results.append(item)
    return filtered_results


def expand_query_with_entity_graph(query: str) -> str:
    """Expand a search query using entity graph aliases and relationship phrases.

    Uses the runtime view for O(1) lookup instead of linear scanning.
    Supports phrase patterns from the registry (e.g., X的老婆, X的奶奶, X的妈妈).
    Gracefully degrades if graph is missing or invalid.
    """
    # Read user data dir dynamically via lazy getter to support test isolation
    from ..lib.paths import get_user_data_dir

    graph_path = get_user_data_dir() / "entity_graph.yaml"
    try:
        graph = load_entity_graph(graph_path)
    except EntityGraphValidationError as exc:
        logger.warning("Skipping entity graph expansion due to invalid graph: %s", exc)
        return query
    if not graph:
        return query

    view = build_runtime_view(graph)

    def _expand_entity_names(entity: dict[str, Any]) -> str:
        names = [entity["primary_name"], *entity.get("aliases", [])]
        deduped: list[str] = []
        for name in names:
            if name not in deduped:
                deduped.append(name)
        return "(" + " OR ".join(deduped) + ")"

    def _iter_subject_candidates(token: str, suffix: str) -> list[str]:
        subjects: list[str] = []
        if token.endswith(suffix):
            subjects.append(token[: -len(suffix)].strip())

        if suffix.startswith("的"):
            bare_suffix = suffix[1:]
            if bare_suffix and token.endswith(bare_suffix):
                bare_subject = token[: -len(bare_suffix)].strip()
                if bare_subject and bare_subject not in subjects:
                    subjects.append(bare_subject)

        return [subject for subject in subjects if subject]

    def _match_relation(actual_relation: str, expected_relation: str) -> bool:
        return normalize_relation(actual_relation) == normalize_relation(expected_relation)

    def _expand_related_entities(
        *, source: dict[str, Any], relation: str, view: Any
    ) -> list[dict[str, Any]]:
        related_entities: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for rel in source.get("relationships", []):
            if not _match_relation(str(rel.get("relation", "")), relation):
                continue
            target = resolve_via_runtime(rel["target"], view)
            if target and target["id"] not in seen_ids:
                related_entities.append(target)
                seen_ids.add(target["id"])

        for source_id, reverse_relation in view.reverse_relationships.get(source["id"], []):
            if not _match_relation(reverse_relation, relation):
                continue
            target = resolve_via_runtime(source_id, view)
            if target and target["id"] not in seen_ids:
                related_entities.append(target)
                seen_ids.add(target["id"])

        return related_entities

    # 1. Whole-query exact match (unchanged behavior)
    whole_match = resolve_via_runtime(query, view)
    if whole_match:
        return _expand_entity_names(whole_match)

    # 2. Token-level expansion
    tokens = [token for token in query.split() if token.strip()]
    expanded_tokens: list[str] = []

    def _expand_phrase_pattern(token: str) -> str | None:
        """Try to match a relationship phrase pattern like X的老婆, X的奶奶."""
        for pattern in view.phrase_patterns:
            suffix = pattern["suffix"]
            relation = pattern["relation"]
            related_entities: list[dict[str, Any]] = []
            for subject in _iter_subject_candidates(token, suffix):
                source = resolve_via_runtime(subject, view)
                if source is None:
                    continue
                related_entities.extend(
                    _expand_related_entities(source=source, relation=relation, view=view)
                )

            if related_entities:
                deduped_names: list[str] = []
                for entity in related_entities:
                    for name in [entity["primary_name"], *entity.get("aliases", [])]:
                        if name not in deduped_names:
                            deduped_names.append(name)
                return "(" + " OR ".join(deduped_names) + ")"
        return None

    for token in tokens:
        # Try phrase pattern expansion first (e.g., 乐乐的奶奶)
        phrase_expansion = _expand_phrase_pattern(token)
        if phrase_expansion:
            expanded_tokens.append(phrase_expansion)
            continue

        # Try direct entity match (e.g., 老婆 as alias)
        matched_entity = resolve_via_runtime(token, view)
        if matched_entity:
            expanded_tokens.append(_expand_entity_names(matched_entity))
        else:
            # Substring replacement: replace any entity alias/name within the token
            replacements = token
            for entity in graph:
                for name in [entity["primary_name"], *entity.get("aliases", [])]:
                    if len(str(name).strip()) < 2:
                        continue
                    if name in replacements:
                        replacements = replacements.replace(name, _expand_entity_names(entity))
            expanded_tokens.append(replacements)

    expanded = " ".join(expanded_tokens).strip()
    return expanded or query


def resolve_query_entities(query: str) -> list[dict[str, Any]]:
    """Resolve entity hints from a query string.

    Returns structured entity hint objects for CLI/Agent consumption.
    Does NOT modify the query — only observes what entities were matched.

    Each hint contains:
        - matched_term: the token that matched
        - entity_id: the resolved entity's id
        - entity_type: person/place/project/event/concept
        - expansion_terms: all names/aliases for the entity
        - reason: how the match happened (alias_match / primary_name_match / phrase_match)
    """
    if not query or not query.strip():
        return []

    from ..lib.paths import get_user_data_dir

    graph_path = get_user_data_dir() / "entity_graph.yaml"
    try:
        graph = load_entity_graph(graph_path)
    except EntityGraphValidationError:
        return []
    if not graph:
        return []

    view = build_runtime_view(graph)
    hints: list[dict[str, Any]] = []
    seen_entity_ids: set[str] = set()

    def _add_hint(entity: dict[str, Any], matched_term: str, reason: str) -> None:
        if entity["id"] in seen_entity_ids:
            return
        seen_entity_ids.add(entity["id"])
        expansion_terms = [entity["primary_name"], *entity.get("aliases", [])]
        # Deduplicate while preserving order
        deduped_terms: list[str] = []
        for term in expansion_terms:
            if term not in deduped_terms:
                deduped_terms.append(term)
        hints.append(
            {
                "matched_term": matched_term,
                "entity_id": entity["id"],
                "entity_type": entity["type"],
                "expansion_terms": deduped_terms,
                "reason": reason,
            }
        )

    def _iter_subject_candidates(token: str, suffix: str) -> list[str]:
        subjects: list[str] = []
        if token.endswith(suffix):
            subjects.append(token[: -len(suffix)].strip())

        if suffix.startswith("的"):
            bare_suffix = suffix[1:]
            if bare_suffix and token.endswith(bare_suffix):
                bare_subject = token[: -len(bare_suffix)].strip()
                if bare_subject and bare_subject not in subjects:
                    subjects.append(bare_subject)

        return [subject for subject in subjects if subject]

    def _match_relation(actual_relation: str, expected_relation: str) -> bool:
        return normalize_relation(actual_relation) == normalize_relation(expected_relation)

    # Check whole-query match first
    whole_match = resolve_via_runtime(query.strip(), view)
    if whole_match:
        reason = (
            "primary_name_match" if query.strip() == whole_match["primary_name"] else "alias_match"
        )
        _add_hint(whole_match, query.strip(), reason)
        return hints

    # Token-level matching
    tokens = [t for t in query.split() if t.strip()]

    for token in tokens:
        # Try phrase patterns
        for pattern in view.phrase_patterns:
            suffix = pattern["suffix"]
            relation = pattern["relation"]
            matched_any = False
            for subject in _iter_subject_candidates(token, suffix):
                source = resolve_via_runtime(subject, view)
                if source is None:
                    continue

                for rel in source.get("relationships", []):
                    if _match_relation(str(rel.get("relation", "")), relation):
                        target = resolve_via_runtime(rel["target"], view)
                        if target:
                            _add_hint(target, token, "phrase_match")
                            matched_any = True

                for source_id, reverse_relation in view.reverse_relationships.get(source["id"], []):
                    if _match_relation(reverse_relation, relation):
                        target = resolve_via_runtime(source_id, view)
                        if target:
                            _add_hint(target, token, "phrase_match")
                            matched_any = True

            if matched_any:
                break

        # Direct entity match
        matched = resolve_via_runtime(token, view)
        if matched:
            reason = "primary_name_match" if token == matched["primary_name"] else "alias_match"
            _add_hint(matched, token, reason)

    return hints


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


def _eval_anchor() -> date | None:
    """Return the eval anchor date from the environment, or None."""
    env = os.environ.get("LIFE_INDEX_TIME_ANCHOR")
    if env:
        return date.fromisoformat(env)
    return None


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
        "entity_hints": [],  # Round 7 Phase 1: structured entity suggestion hints
        # Round 11 Phase 0: query understanding output placeholders
        "search_plan": None,  # Phase 1 implementation: structured query understanding
        "ambiguity": {"has_ambiguity": False, "items": []},  # Phase 2 implementation
        "hints": [],  # Phase 2 implementation: invocation-time hints
    }

    # Round 10 T1.2: Expose entity graph status
    from ..lib.entity_graph import check_graph_status
    from ..lib.paths import get_user_data_dir

    graph_status = check_graph_status(get_user_data_dir() / "entity_graph.yaml")
    result["entity_graph_status"] = graph_status

    if not semantic:
        result["semantic_note"] = "语义搜索已通过 --no-semantic 禁用。"
        result["warnings"].append("semantic_disabled: 用户通过 --no-semantic 禁用语义搜索")

    # F1: Eval anchor deterministic injection
    # Resolve a single anchor date for all time-dependent subsystems.
    _now = _eval_anchor() or date.today()

    # Round 7 Phase 1: Resolve entity hints before expansion
    entity_hints = resolve_query_entities(query) if query else []
    result["entity_hints"] = entity_hints

    # Round 11 Phase 0→1: Query understanding via preprocessor
    _plan = None
    if query:
        from .query_preprocessor import build_search_plan as _build_plan

        _plan = _build_plan(query, reference_date=_now)
        result["search_plan"] = _plan.to_dict()

    # Round 11 Phase 2: Ambiguity detection + hints
    if _plan is not None:
        from .ambiguity_detector import detect_ambiguity as _detect_amb
        from .hints_builder import build_hints as _build_hints

        _ambiguity = _detect_amb(_plan, query or "", entity_hints)
        result["ambiguity"] = _ambiguity.to_dict()
        _hints = _build_hints(_plan, _ambiguity)
        result["hints"] = [h.to_dict() for h in _hints]

    expanded_query = expand_query_with_entity_graph(query) if query else query
    if expanded_query != query:
        result["query_params"]["expanded_query"] = expanded_query
    query = expanded_query

    # Phase 2-B: Use preprocessor expanded_query for cleaner keyword search
    # when entity expansion did not modify the query.
    # Only use when it's a single token (no spaces) to avoid breaking
    # _segment_query_for_fts was_segmented detection.
    if (
        _plan
        and _plan.expanded_query
        and expanded_query == _plan.raw_query
        and " " not in _plan.expanded_query
    ):
        query = _plan.expanded_query

    start_time = time.time()

    # Round 12 Phase 3: Unified freshness guard + pending consumption
    from ..lib.pending_writes import has_pending as _has_pending, clear_pending as _clear_pending
    from ..lib.index_freshness import check_full_freshness as _check_full_freshness
    from ..lib.paths import get_user_data_dir as _get_user_data_dir

    _index_dir = _get_user_data_dir() / ".index"

    # Step 1: If pending writes, trigger build and consume
    if _has_pending():
        try:
            from ..build_index import build_all as _build_all

            logger.info("Pending writes detected, triggering incremental index update")
            _build_all(incremental=True)
            _clear_pending()
            result.setdefault("pending_consumed", True)
        except Exception as exc:
            logger.warning("Pending index update failed, continuing with stale index: %s", exc)
            result.setdefault("pending_consumed", False)
    else:
        # Step 2: Check full freshness (FTS + vector + manifest)
        _freshness = _check_full_freshness(_index_dir)
        result["index_status"] = {
            "freshness": _freshness.to_dict(),
        }
        if not _freshness.overall_fresh:
            for issue in _freshness.issues:
                result["warnings"].append(f"index_stale: {issue}")
            # Trigger incremental build to fix staleness
            try:
                from ..build_index import build_all as _build_all

                logger.info(
                    "Index stale, triggering incremental update: %s", ", ".join(_freshness.issues)
                )
                _build_all(incremental=True)
                result.setdefault("index_status", {})["auto_updated"] = True
            except Exception as exc:
                logger.warning("Auto index update failed: %s", exc)
                result.setdefault("index_status", {})["auto_updated"] = False

    # Round 19 Phase 1-C Track B: Time expression parsing
    _time_filter = None
    if query and not date_from and not date_to:
        from ..lib.time_parser import parse_time_expression

        _time_filter = parse_time_expression(query, now=_now)
        if _time_filter:
            date_from = _time_filter.date_range.start.isoformat()
            date_to = _time_filter.date_range.end.isoformat()
            result["time_parsed"] = {
                "matched_span": _time_filter.matched_span,
                "date_from": date_from,
                "date_to": date_to,
            }
            # NOTE: Topic inference from cleaned query was attempted but
            # reverted because keyword-based topic matching is unreliable
            # (e.g. "开发" maps to "create" but user intent may be "work").
            # GQ53 remains a failure due to ranking, not time parsing.

    # Phase 4 T4.1: Consume search_plan.date_range when no explicit date params
    if _plan and _plan.date_range and not date_from and not date_to:
        if _plan.date_range.since:
            date_from = _plan.date_range.since
        if _plan.date_range.until:
            date_to = _plan.date_range.until

    candidate_paths = build_l0_candidate_set(
        year=year, month=month, topic=topic, date_from=date_from, date_to=date_to
    )

    # ── Level 1: 索引层（向后兼容，提前返回） ──
    if level == 1:
        level_1_result = _search_level_1(
            result=result,
            topic=topic,
            project=project,
            tags=tags,
            start_time=start_time,
        )
        _emit_search_metrics(level_1_result)
        return level_1_result

    # ── Level 2: 索引 + 元数据（向后兼容，提前返回） ──
    if level == 2:
        level_2_result = _search_level_2(
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
        _emit_search_metrics(level_2_result)
        return level_2_result

    # ── Level 3: 双管道并行搜索 ──
    # Round 18 Phase 3: Noise gate — skip semantic pipeline for noise queries
    # Round 19 Phase 1 B2: For OOD/noise queries, bypass both pipelines entirely
    # to prevent keyword-pipeline leakage (e.g. GQ77 "区块链技术投资" matching
    # on "投资" alone after semantic bypass).
    _noise_blocked = False
    _noise_reason = None
    if semantic and query:
        from .noise_gate import is_noise_query

        _noise_blocked, _noise_reason = is_noise_query(query)
        if _noise_blocked:
            semantic = False
            result["semantic_note"] = f"语义搜索被 noise gate 拦截（{_noise_reason}）"
            result["warnings"].append(
                f"noise_gate: semantic bypassed for '{query}' ({_noise_reason})"
            )

    # Phase 1 B2: Full pipeline bypass for OOD/negation-intent queries only.
    # Conservative: too_short and other original rules only bypass semantic
    # pipeline to avoid keyword-regression on legitimate short queries
    # (GQ10 '吃饭', GQ85 'AI', GQ126 '投资', etc.).
    if _noise_blocked and _noise_reason in ("ood_topic", "negation_intent"):
        result["performance"]["total_time_ms"] = round((time.time() - start_time) * 1000, 2)
        _emit_search_metrics(result)
        logger.info(
            f"[SearchPerf] Total: {result['performance']['total_time_ms']}ms "
            f"(L1:0.0 L2:0.0 L3:0.0 Semantic:0.0) "
            f"| Results: 0 (noise_gate full bypass)"
        )
        return result

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
            entity_hints=entity_hints,
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
        semantic_results, sem_perf, semantic_available, semantic_note = future_semantic.result()

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
        # Skip if user explicitly disabled semantic (line 589 already added semantic_disabled)
        if not semantic_available and semantic:
            result["warnings"].append(f"semantic_unavailable: {semantic_note}")
    if l2_truncated:
        result["l2_truncated"] = True
        result["l2_total_available"] = l2_total_available
    result["performance"].update(kw_perf)
    if sem_perf:
        result["performance"].update(sem_perf)

    # ── RRF 融合 ──
    # Phase 4 T4.2: Extract topic_hints from search_plan for ranking boost
    _topic_hints = _plan.topic_hints if _plan else None

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
            entity_hints=entity_hints,
            topic_hints=_topic_hints,
        )
    else:
        # 语义搜索无结果时退化为纯关键词排序
        result["merged_results"] = merge_and_rank_results(
            l1_results,
            l2_results,
            l3_results,
            query,
            entity_hints=entity_hints,
            explain=explain,  # T3.4: forward explain to non-hybrid path
            topic_hints=_topic_hints,
        )

    result["total_found"] = len(result["merged_results"])
    result["total_available"] = len(result["merged_results"])

    # Phase 2 (Task 3): Presentation-layer truncation for backward compat.
    # ranking now returns ALL results; we truncate here to MAX_RESULTS_DEFAULT
    # so that existing callers (tests, GUI) are not affected.
    if len(result["merged_results"]) > MAX_RESULTS_DEFAULT:
        result["has_more"] = True
        result["merged_results"] = result["merged_results"][:MAX_RESULTS_DEFAULT]
    else:
        result["has_more"] = False

    result["total_found"] = len(result["merged_results"])
    result["no_confident_match"] = _compute_no_confident_match(result["merged_results"])

    # T4.4: Title hard promotion (post-rank, post-confidence)
    from .title_promotion import apply_title_promotion

    result["merged_results"] = apply_title_promotion(result["merged_results"], query or "")

    # T4.5: ranking_reason natural language explanation (--explain mode only)
    if explain:
        from .ranking_reason import compose as compose_reason

        for r in result["merged_results"]:
            r["query"] = query or ""
            r["ranking_reason"] = compose_reason(r)
            # Clean up transient field
            del r["query"]

    result["performance"]["total_time_ms"] = round((time.time() - start_time) * 1000, 2)

    _emit_search_metrics(result)

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
