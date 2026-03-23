"""Edit route."""

from __future__ import annotations

import importlib
import secrets
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from web.services.geolocation import reverse_geocode_coordinates
from web.services.edit import compute_edit_diff, edit_journal_web
from web.services.llm_provider import get_provider
from web.services.write import _extract_weather_text
from tools.query_weather import geocode_location, query_weather

router = APIRouter()
get_journal = importlib.import_module("web.services.journal").get_journal


def _generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def _set_csrf_cookie(
    response: HTMLResponse | RedirectResponse, csrf_token: str
) -> None:
    response.set_cookie("csrf_token", csrf_token, samesite="lax")


def _stringify_field(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    return "" if value is None else str(value)


def _build_edit_context(
    request: Request,
    *,
    csrf_token: str,
    journal_route_path: str,
    form_data: dict[str, Any],
    llm_available: bool,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "request": request,
        "csrf_token": csrf_token,
        "journal_route_path": journal_route_path,
        "error": error,
        "llm_available": llm_available,
        "title": _stringify_field(form_data.get("title")),
        "date": _stringify_field(form_data.get("date")),
        "topic": _stringify_field(form_data.get("topic")),
        "mood": _stringify_field(form_data.get("mood")),
        "tags": _stringify_field(form_data.get("tags")),
        "people": _stringify_field(form_data.get("people")),
        "location": _stringify_field(form_data.get("location")),
        "weather": _stringify_field(form_data.get("weather")),
        "project": _stringify_field(form_data.get("project")),
        "abstract": _stringify_field(form_data.get("abstract")),
        "content": _stringify_field(form_data.get("content")),
    }


def _journal_to_form_data(journal: dict[str, Any]) -> dict[str, Any]:
    metadata = journal.get("metadata", {})
    return {
        "title": metadata.get("title", ""),
        "date": metadata.get("date", ""),
        "topic": metadata.get("topic", []),
        "mood": metadata.get("mood", []),
        "tags": metadata.get("tags", []),
        "people": metadata.get("people", []),
        "location": metadata.get("location", ""),
        "weather": metadata.get("weather", ""),
        "project": metadata.get("project", ""),
        "abstract": metadata.get("abstract", ""),
        "content": journal.get("raw_body", ""),
    }


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


@router.get("/api/weather")
async def weather_api(
    location: str | None = Query(None),
    date: str | None = Query(None),
) -> JSONResponse:
    if not location or not location.strip():
        raise HTTPException(status_code=400, detail="location 为必填参数")

    result = query_weather_for_location(location.strip(), date)
    return JSONResponse(result)


@router.get("/api/reverse-geocode")
async def reverse_geocode_api(
    lat: float | None = Query(None),
    lon: float | None = Query(None),
) -> JSONResponse:
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="lat 和 lon 为必填参数")

    result = reverse_geocode_for_coordinates(lat, lon)
    return JSONResponse(result)


@router.get("/journal/{journal_path:path}/edit", response_class=HTMLResponse)
async def edit_page(request: Request, journal_path: str) -> HTMLResponse:
    provider = await get_provider()
    try:
        journal = get_journal(journal_path)
    except ValueError:
        raise HTTPException(status_code=404, detail="日志未找到")

    csrf_token = _generate_csrf_token()
    response = request.app.state.templates.TemplateResponse(
        request,
        "edit.html",
        _build_edit_context(
            request,
            csrf_token=csrf_token,
            journal_route_path=journal_path,
            form_data=_journal_to_form_data(journal),
            llm_available=provider is not None,
        ),
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.post("/journal/{journal_path:path}/edit", response_class=HTMLResponse)
async def submit_edit(
    request: Request,
    journal_path: str,
    csrf_token: str = Form(...),
    title: str = Form(""),
    date: str = Form(""),
    topic: str = Form(""),
    mood: str = Form(""),
    tags: str = Form(""),
    people: str = Form(""),
    location: str = Form(""),
    weather: str = Form(""),
    project: str = Form(""),
    abstract: str = Form(""),
    content: str = Form(""),
) -> Response:
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or cookie_token != csrf_token:
        raise HTTPException(status_code=403, detail="CSRF 验证失败")

    provider = await get_provider()
    try:
        journal = get_journal(journal_path)
    except ValueError:
        raise HTTPException(status_code=404, detail="日志未找到")

    form_data = {
        "title": title,
        "date": date,
        "topic": topic,
        "mood": mood,
        "tags": tags,
        "people": people,
        "location": location,
        "weather": weather,
        "project": project,
        "abstract": abstract,
        "content": content,
    }
    original = {**journal.get("metadata", {}), "_body": journal.get("raw_body", "")}
    diff = compute_edit_diff(original=original, submitted=form_data)

    result = await edit_journal_web(
        journal_path=journal_path,
        frontmatter_updates=diff["frontmatter_updates"],
        replace_content=diff["replace_content"],
    )
    if result.get("success"):
        return RedirectResponse(url=f"/journal/{journal_path}?saved=1", status_code=303)

    new_csrf_token = _generate_csrf_token()
    response = request.app.state.templates.TemplateResponse(
        request,
        "edit.html",
        _build_edit_context(
            request,
            csrf_token=new_csrf_token,
            journal_route_path=journal_path,
            form_data=form_data,
            llm_available=provider is not None,
            error=str(result.get("error") or "编辑失败"),
        ),
    )
    _set_csrf_cookie(response, new_csrf_token)
    return response
