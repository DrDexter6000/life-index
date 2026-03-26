"""API route."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from tools.query_weather import geocode_location, query_weather
from web.services.geolocation import reverse_geocode_coordinates
from web.services.llm_provider import get_provider
from web.services.search import search_journals_web

router = APIRouter(prefix="/api")


def _extract_weather_text(weather_result: dict[str, Any] | None) -> str:
    if not isinstance(weather_result, dict):
        return ""
    if not weather_result.get("success"):
        return ""
    weather = weather_result.get("weather")
    if not isinstance(weather, dict):
        return ""

    description = str(weather.get("description") or "").strip()
    temp_max = weather.get("temperature_max")
    temp_min = weather.get("temperature_min")

    if description and temp_max not in (None, "") and temp_min not in (None, ""):
        return f"{description} {temp_max}°C/{temp_min}°C"
    if description and temp_max not in (None, ""):
        return f"{description} {temp_max}°C"
    if description:
        return description

    simple = weather.get("simple")
    return str(simple).strip() if simple else ""


def query_weather_for_location(
    location: str, date: str | None = None
) -> dict[str, Any]:
    normalized_date = (
        date.strip()[:10]
        if date is not None and date.strip()
        else datetime.now().strftime("%Y-%m-%d")
    )
    geocode_result = geocode_location(location)
    if not isinstance(geocode_result, dict):
        return {"success": False, "weather": None, "error": "地点解析失败"}

    latitude = geocode_result.get("latitude")
    longitude = geocode_result.get("longitude")
    if latitude is None or longitude is None:
        return {"success": False, "weather": None, "error": "地点解析失败"}

    weather_result = query_weather(float(latitude), float(longitude), normalized_date)
    weather_text = _extract_weather_text(weather_result)
    if not weather_text:
        return {
            "success": False,
            "weather": None,
            "error": str(
                weather_result.get("error")
                if isinstance(weather_result, dict)
                else "天气查询失败"
            ),
        }

    return {"success": True, "weather": weather_text, "error": None}


def reverse_geocode_for_coordinates(
    latitude: float, longitude: float
) -> dict[str, Any]:
    return reverse_geocode_coordinates(latitude, longitude)


@router.get("/weather")
async def weather_api(
    location: str | None = Query(None),
    date: str | None = Query(None),
) -> JSONResponse:
    if not location or not location.strip():
        raise HTTPException(status_code=400, detail="location 为必填参数")

    result = query_weather_for_location(location.strip(), date)
    return JSONResponse(result)


@router.get("/reverse-geocode")
async def reverse_geocode_api(
    lat: float | None = Query(None),
    lon: float | None = Query(None),
) -> JSONResponse:
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="lat 和 lon 为必填参数")

    result = reverse_geocode_for_coordinates(lat, lon)
    return JSONResponse(result)


@router.get("/search/summarize", response_class=HTMLResponse)
async def search_summarize_api(
    request: Request,
    query: str = Query(...),
    topic: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    mood: str | None = Query(None),
    tags: str | None = Query(None),
    people: str | None = Query(None),
    project: str | None = Query(None),
    location: str | None = Query(None),
) -> HTMLResponse:
    provider = await get_provider()
    search_result = await search_journals_web(
        query=query,
        topic=topic,
        date_from=date_from,
        date_to=date_to,
        mood=mood,
        tags=tags,
        people=people,
        project=project,
        location=location,
        weather=None,
        semantic=True,
        provider=provider,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/search_summary.html",
        {
            "request": request,
            "query": query,
            "ai_summary": search_result.get("ai_summary", {}),
        },
    )


@router.get("/llm-status")
async def llm_status_api() -> JSONResponse:
    """Check if LLM provider is available for metadata extraction."""
    provider = await get_provider()
    available = provider is not None
    return JSONResponse(
        {
            "success": True,
            "available": available,
        }
    )
