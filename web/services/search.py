"""Web search service wrapper."""

from __future__ import annotations

from typing import Any

from tools.search_journals.core import hierarchical_search


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


def search_journals_web(
    query: str | None = None,
    topic: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    mood: str | list[str] | None = None,
    tags: str | list[str] | None = None,
    people: str | list[str] | None = None,
    level: int = 3,
    semantic: bool = True,
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
    }

    if not _has_filters(normalized_params):
        return base_result

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
    for item in raw_result.get("merged_results", []):
        results.append(
            {
                **item,
                "journal_route_path": item.get("journal_route_path", ""),
                "score": item.get("score", item.get("rrf_score")),
                "highlight": item.get("highlight") or item.get("snippet"),
            }
        )

    return {
        **base_result,
        "success": bool(raw_result.get("success", True)),
        "results": results,
        "total_found": int(raw_result.get("total_found", len(results))),
        "time_ms": float(raw_result.get("performance", {}).get("total_time_ms", 0.0)),
    }
