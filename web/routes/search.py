"""Search route."""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web.services.llm_provider import get_provider
from web.services.search import search_journals_web

router = APIRouter()


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request) -> HTMLResponse:
    """Render search page (full page or HTMX partial based on request headers)."""
    query = request.query_params.get("q", "")
    topic = request.query_params.get("topic", "")
    mood = request.query_params.get("mood", "")
    tag = request.query_params.get("tag", "")
    tags = request.query_params.get("tags", "") or tag
    people = request.query_params.get("people", "")
    single_date = request.query_params.get("date", "")
    date_from = request.query_params.get("date_from", "") or single_date
    date_to = request.query_params.get("date_to", "") or single_date

    active_filters = {
        "query": query,
        "topic": topic,
        "date_from": date_from,
        "date_to": date_to,
        "mood": mood,
        "tags": tags,
        "people": people,
    }
    has_active_filters = any(active_filters.values())

    # Determine if this is an HTMX request
    is_htmx = request.headers.get("HX-Request") == "true"

    # Perform search if query or filters provided
    search_result: dict[str, Any] | None = None
    provider = await get_provider()
    if has_active_filters:
        search_result = await search_journals_web(
            query=query or None,
            topic=topic or None,
            date_from=date_from or None,
            date_to=date_to or None,
            mood=mood or None,
            tags=tags or None,
            people=people or None,
            provider=None,
        )

    if is_htmx:
        # Return partial for HTMX requests
        if search_result:
            return request.app.state.templates.TemplateResponse(
                request,
                "partials/search_results.html",
                {
                    "request": request,
                    "current_page": "/search",
                    "results": search_result.get("results", []),
                    "total_found": search_result.get("total_found", 0),
                    "time_ms": search_result.get("time_ms", 0.0),
                    "error": search_result.get("error"),
                    "query": query,
                    "topic": topic,
                    "date_from": date_from,
                    "date_to": date_to,
                    "mood": mood,
                    "tags": tags,
                    "people": people,
                    "has_active_filters": has_active_filters,
                    "llm_available": provider is not None,
                },
            )
        # Return empty results partial
        return request.app.state.templates.TemplateResponse(
            request,
            "partials/search_results.html",
            {
                "request": request,
                "current_page": "/search",
                "results": [],
                "total_found": 0,
                "time_ms": 0.0,
                "error": None,
                "query": query,
                "topic": topic,
                "date_from": date_from,
                "date_to": date_to,
                "mood": mood,
                "tags": tags,
                "people": people,
                "has_active_filters": has_active_filters,
                "llm_available": provider is not None,
            },
        )

    # Full page render
    return request.app.state.templates.TemplateResponse(
        request,
        "search.html",
        {
            "request": request,
            "current_page": "/search",
            "results": search_result.get("results", []) if search_result else [],
            "total_found": search_result.get("total_found", 0) if search_result else 0,
            "time_ms": search_result.get("time_ms", 0.0) if search_result else 0.0,
            "error": search_result.get("error") if search_result else None,
            "query": query,
            "topic": topic,
            "date_from": date_from,
            "date_to": date_to,
            "mood": mood,
            "tags": tags,
            "people": people,
            "has_active_filters": has_active_filters,
            "llm_available": provider is not None,
        },
    )
