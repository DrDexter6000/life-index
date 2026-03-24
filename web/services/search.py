"""Web search service wrapper."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from tools.search_journals.core import hierarchical_search

from web.services.llm_provider import LLMProvider

_SEARCH_CACHE: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}
_SEARCH_CACHE_TTL_SECONDS = 60
_SEARCH_CACHE_MAXSIZE = 32


def _is_valid_journal_route_path(path: str | None) -> bool:
    if not path:
        return False
    normalized = str(path).replace("\\", "/")
    return not (
        normalized.startswith("/")
        or ":/" in normalized
        or normalized.startswith("Journals/")
        or "pytest-" in normalized
        or "/Temp/" in normalized
        or normalized.startswith("Temp/")
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

    normalized = [item.strip() for item in value.split(",") if item.strip()]
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
        )
    )


def _build_cache_key(
    params: dict[str, Any],
    level: int,
    semantic: bool,
    limit: int,
    provider: LLMProvider | None,
) -> tuple[Any, ...]:
    return (
        params.get("query"),
        params.get("topic"),
        params.get("date_from"),
        params.get("date_to"),
        tuple(params.get("mood") or []),
        tuple(params.get("tags") or []),
        tuple(params.get("people") or []),
        level,
        semantic,
        limit,
        id(provider) if provider is not None else None,
    )


def _get_cached_result(cache_key: tuple[Any, ...]) -> dict[str, Any] | None:
    cached = _SEARCH_CACHE.get(cache_key)
    if not cached:
        return None

    cached_at, result = cached
    if time.time() - cached_at > _SEARCH_CACHE_TTL_SECONDS:
        _SEARCH_CACHE.pop(cache_key, None)
        return None

    return result.copy()


def _store_cached_result(cache_key: tuple[Any, ...], result: dict[str, Any]) -> None:
    if len(_SEARCH_CACHE) >= _SEARCH_CACHE_MAXSIZE:
        oldest_key = min(_SEARCH_CACHE.items(), key=lambda item: item[1][0])[0]
        _SEARCH_CACHE.pop(oldest_key, None)

    _SEARCH_CACHE[cache_key] = (time.time(), result.copy())


async def search_journals_web(
    query: str | None = None,
    topic: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    mood: str | list[str] | None = None,
    tags: str | list[str] | None = None,
    people: str | list[str] | None = None,
    level: int = 3,
    semantic: bool = True,
    limit: int = 20,
    provider: LLMProvider | None = None,
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

    cache_key = _build_cache_key(normalized_params, level, semantic, limit, provider)
    cached_result = _get_cached_result(cache_key)
    if cached_result is not None:
        return cached_result

    try:
        raw_result = hierarchical_search(
            query=normalized_params["query"],
            topic=normalized_params["topic"],
            date_from=normalized_params["date_from"],
            date_to=normalized_params["date_to"],
            mood=normalized_params["mood"],
            tags=normalized_params["tags"],
            people=normalized_params["people"],
            level=level,
            semantic=semantic,
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

    if provider is None:
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

    _store_cached_result(cache_key, result)
    return result
