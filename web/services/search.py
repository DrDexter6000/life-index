"""Web search service wrapper."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.search_journals.core import hierarchical_search

from tools.lib.config import get_search_mode, get_search_weights
from web.services.llm_provider import LLMProvider


def _is_valid_journal_route_path(path: str | None) -> bool:
    if not path:
        return False
    normalized = str(path).replace("\\", "/")
    filename = normalized.rsplit("/", 1)[-1].lower()
    return not (
        normalized.startswith("/")
        or ":/" in normalized
        or normalized.startswith("Journals/")
        or "pytest-" in normalized
        or "/Temp/" in normalized
        or normalized.startswith("Temp/")
        or filename.startswith("monthly_report_")
        or filename.startswith("yearly_report_")
        or filename == "monthly_abstract.md"
        or filename == "yearly_abstract.md"
    )


def _file_exists(item: dict[str, Any]) -> bool:
    file_path = item.get("file_path") or item.get("path")
    if not file_path:
        return False
    return Path(str(file_path)).exists()


def _sanitize_snippet(text: str | None) -> str | None:
    """Clean markdown residue from search snippets while preserving highlight tags."""
    if not text:
        return text

    lines = text.split("\n")
    cleaned_lines: list[str] = []
    skip_attachments = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## Attachment"):
            skip_attachments = True
            continue
        if skip_attachments and stripped.startswith("- ["):
            continue
        if skip_attachments and not stripped.startswith("- ["):
            skip_attachments = False

        cleaned_lines.append(re.sub(r"^#{1,6}\s+", "", line))

    return "\n".join(cleaned_lines).strip()


def _normalize_list_param(value: str | list[str] | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        normalized = [item.strip() for item in value if item and item.strip()]
        return normalized or None

    # Support both full-width and half-width commas
    normalized_value = value.replace("，", ",")
    normalized = [item.strip() for item in normalized_value.split(",") if item.strip()]
    return normalized or None


def _has_filters(params: dict[str, Any]) -> bool:
    return any(
        value not in (None, "", [])
        for value in (
            params.get("query"),
            params.get("topic"),
            params.get("date_from"),
            params.get("date_to"),
            params.get("mood"),
            params.get("tags"),
            params.get("people"),
            params.get("project"),
            params.get("location"),
            params.get("weather"),
        )
    )


async def search_journals_web(
    query: str | None = None,
    topic: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    mood: str | list[str] | None = None,
    tags: str | list[str] | None = None,
    people: str | list[str] | None = None,
    project: str | None = None,
    location: str | None = None,
    weather: str | None = None,
    level: int = 3,
    semantic: bool = True,
    limit: int = 20,
    provider: LLMProvider | None = None,
    enable_ai_summary: bool = True,
    # Web-only recall overrides (CLI uses hardcoded defaults)
    semantic_top_k: int = 50,
    semantic_min_similarity: float = 0.15,
    fts_min_relevance: int = 25,
    rrf_min_score: float = 0.008,
    non_rrf_min_score: float = 10,
) -> dict[str, Any]:
    """Return a web-friendly search payload for templates and routes."""

    normalized_params = {
        "query": query or None,
        "topic": topic or None,
        "date_from": date_from or None,
        "date_to": date_to or None,
        "mood": _normalize_list_param(mood),
        "tags": _normalize_list_param(tags),
        "people": _normalize_list_param(people),
        "project": project or None,
        "location": location or None,
        "weather": weather or None,
    }

    base_result = {
        "success": True,
        "results": [],
        "total_found": 0,
        "time_ms": 0.0,
        "error": None,
        "query": normalized_params["query"] or "",
        "topic": normalized_params["topic"] or "",
        "date_from": normalized_params["date_from"] or "",
        "date_to": normalized_params["date_to"] or "",
        "project": normalized_params["project"] or "",
        "location": normalized_params["location"] or "",
        "weather": normalized_params["weather"] or "",
        "ai_summary": {
            "state": "idle",
            "summary": None,
            "key_entries": [],
            "time_span": None,
            "message": None,
        },
    }

    if not _has_filters(normalized_params):
        return base_result

    # 获取搜索权重和模式
    fts_weight, semantic_weight = get_search_weights()
    search_mode = get_search_mode()

    # 根据搜索模式调整参数
    mode_params = {
        "strict": {
            "semantic_top_k": 20,
            "semantic_min_similarity": 0.25,
            "fts_min_relevance": 35,
            "rrf_min_score": 0.016,
            "non_rrf_min_score": 20,
        },
        "balanced": {
            "semantic_top_k": 50,
            "semantic_min_similarity": 0.15,
            "fts_min_relevance": 25,
            "rrf_min_score": 0.008,
            "non_rrf_min_score": 10,
        },
        "loose": {
            "semantic_top_k": 100,
            "semantic_min_similarity": 0.10,
            "fts_min_relevance": 15,
            "rrf_min_score": 0.004,
            "non_rrf_min_score": 5,
        },
    }
    params = mode_params.get(search_mode, mode_params["balanced"])

    try:
        raw_result = hierarchical_search(
            query=normalized_params["query"],
            topic=normalized_params["topic"],
            date_from=normalized_params["date_from"],
            date_to=normalized_params["date_to"],
            mood=normalized_params["mood"],
            tags=normalized_params["tags"],
            people=normalized_params["people"],
            project=normalized_params["project"],
            location=normalized_params["location"],
            weather=normalized_params["weather"],
            level=level,
            semantic=semantic,
            fts_weight=fts_weight,
            semantic_weight=semantic_weight,
            semantic_top_k=params["semantic_top_k"],
            semantic_min_similarity=params["semantic_min_similarity"],
            fts_min_relevance=params["fts_min_relevance"],
            rrf_min_score=params["rrf_min_score"],
            non_rrf_min_score=params["non_rrf_min_score"],
        )
    except Exception as exc:
        return {
            **base_result,
            "success": False,
            "error": str(exc),
        }

    results: list[dict[str, Any]] = []
    # Use merged_results if available, otherwise fall back to l2_results
    source_results = raw_result.get("merged_results", []) or raw_result.get(
        "l2_results", []
    )
    merged_results = source_results[:limit]
    for item in merged_results:
        route_path = item.get("journal_route_path", "")
        if not _is_valid_journal_route_path(route_path):
            continue
        if not _file_exists(item):
            continue
        results.append(
            {
                **item,
                "journal_route_path": route_path,
                "score": item.get("score", item.get("rrf_score")),
                "highlight": _sanitize_snippet(
                    item.get("highlight") or item.get("snippet")
                ),
            }
        )

    result = {
        **base_result,
        "success": bool(raw_result.get("success", True)),
        "results": results,
        "total_found": len(results),
        "time_ms": float(raw_result.get("performance", {}).get("total_time_ms", 0.0)),
    }

    if not enable_ai_summary:
        # AI summary disabled for this search (keyword search mode)
        result["ai_summary"] = {
            "state": "disabled",
            "summary": None,
            "key_entries": [],
            "time_span": None,
            "message": None,
        }
    elif provider is None:
        result["ai_summary"] = {
            "state": "unavailable",
            "summary": None,
            "key_entries": [],
            "time_span": None,
            "message": "启用 AI 可获得智能搜索摘要",
        }
    elif results and normalized_params["query"]:
        try:
            ai_summary = await provider.summarize_search(
                normalized_params["query"], results
            )
        except Exception as exc:
            result["ai_summary"] = {
                "state": "failed",
                "summary": None,
                "key_entries": [],
                "time_span": None,
                "message": str(exc),
            }
        else:
            if ai_summary.get("summary"):
                result["ai_summary"] = {
                    "state": "ready",
                    "summary": ai_summary.get("summary"),
                    "key_entries": list(ai_summary.get("key_entries") or []),
                    "time_span": ai_summary.get("time_span"),
                    "message": None,
                }
            else:
                result["ai_summary"] = {
                    "state": "failed",
                    "summary": None,
                    "key_entries": [],
                    "time_span": None,
                    "message": "AI 归纳暂时不可用",
                }
    else:
        result["ai_summary"] = {
            "state": "idle",
            "summary": None,
            "key_entries": [],
            "time_span": None,
            "message": None,
        }

    return result


def _dedupe_query_hints(user_query: str, derived_queries: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in [user_query, *derived_queries]:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(normalized)
    return ordered


async def search_ai_journals_web(
    *,
    user_query: str,
    derived_queries: list[str] | None,
    date_from: str | None,
    date_to: str | None,
    provider: LLMProvider | None,
    limit: int = 15,
) -> dict[str, Any]:
    query_hints = _dedupe_query_hints(user_query, list(derived_queries or []))
    combined_query = " ".join(query_hints)
    result = await search_journals_web(
        query=combined_query,
        date_from=date_from,
        date_to=date_to,
        level=3,
        semantic=True,
        limit=limit,
        provider=provider,
    )
    result["effective_query"] = combined_query
    result["derived_queries"] = query_hints[1:]
    result["display_query"] = user_query
    return result
