"""Edit route."""

from __future__ import annotations

import importlib
import secrets
from typing import Any, cast
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from web.services.date_adapter import resolve_standard_date_value, to_gui_datetime_value
from web.services.edit import compute_edit_diff, edit_journal_web
from web.services.llm_provider import get_provider  # noqa: F401 - kept for test mocks
from web.services.write import cleanup_staged_files, download_attachment_from_url

router = APIRouter()
get_journal = importlib.import_module("web.services.journal").get_journal


def _readonly_simulation_warning_message() -> str | None:
    from web.runtime import get_runtime_info

    runtime = get_runtime_info()
    if not runtime.get("readonly_simulation"):
        return None
    return "当前操作已写入临时副本，不会回写真实用户目录；如需保留结果，请先人工确认后再迁移。"


def _generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def _set_csrf_cookie(response: HTMLResponse | RedirectResponse, csrf_token: str) -> None:
    response.set_cookie("csrf_token", csrf_token, samesite="lax")


def _stringify_field(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    return "" if value is None else str(value)


def _stringify_multiline_field(value: Any) -> str:
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            if isinstance(item, dict):
                import json

                lines.append(json.dumps(item, ensure_ascii=False))
            else:
                text = str(item).strip()
                if text:
                    lines.append(text)
        return "\n".join(lines)
    return "" if value is None else str(value)


def _normalize_uploads(uploads: Any) -> list[UploadFile]:
    """Normalize upload input to a list of UploadFile objects."""
    if uploads is None:
        return []
    if hasattr(uploads, "filename") and not isinstance(uploads, str):
        upload = cast(UploadFile, uploads)
        filename = getattr(upload, "filename", None)
        return [upload] if filename else []
    if isinstance(uploads, str):
        return []

    normalized: list[UploadFile] = []
    for upload in uploads:
        if hasattr(upload, "filename") and not isinstance(upload, str):
            filename = getattr(upload, "filename", None)
            if filename:
                normalized.append(cast(UploadFile, upload))
    return normalized


def _stage_uploaded_files(uploads: list[UploadFile]) -> list[dict[str, str]]:
    """Stage uploaded files to temp directory for processing."""
    import tempfile
    from pathlib import Path

    staged: list[dict[str, str]] = []
    for upload in uploads:
        filename = upload.filename or "attachment"
        suffix = Path(filename).suffix
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
            prefix="life-index-edit-upload-",
        ) as temp_file:
            temp_file.write(upload.file.read())
            staged.append({"source_path": temp_file.name, "description": ""})
    return staged


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
        "current_page": request.url.path,
        "csrf_token": csrf_token,
        "journal_route_path": journal_route_path,
        "error": error,
        "llm_available": llm_available,
        "title": _stringify_field(form_data.get("title")),
        "date": _stringify_field(form_data.get("date")),
        "original_date_raw": _stringify_field(form_data.get("original_date_raw")),
        "topic": _stringify_field(form_data.get("topic")),
        "mood": _stringify_field(form_data.get("mood")),
        "tags": _stringify_field(form_data.get("tags")),
        "people": _stringify_field(form_data.get("people")),
        "location": _stringify_field(form_data.get("location")),
        "weather": _stringify_field(form_data.get("weather")),
        "project": _stringify_field(form_data.get("project")),
        "abstract": _stringify_field(form_data.get("abstract")),
        "links": _stringify_multiline_field(form_data.get("links", [])),
        "attachments": _stringify_multiline_field(form_data.get("attachments", [])),
        "existing_attachments": _stringify_multiline_field(form_data.get("attachments", [])),
        "content": _stringify_field(form_data.get("content")),
    }


def _journal_to_form_data(journal: dict[str, Any]) -> dict[str, Any]:
    metadata = journal.get("metadata", {})
    return {
        "title": metadata.get("title", ""),
        "date": to_gui_datetime_value(metadata.get("date", "")),
        "original_date_raw": metadata.get("date", ""),
        "topic": metadata.get("topic", []),
        "mood": metadata.get("mood", []),
        "tags": metadata.get("tags", []),
        "people": metadata.get("people", []),
        "location": metadata.get("location", ""),
        "weather": metadata.get("weather", ""),
        "project": metadata.get("project", ""),
        "abstract": metadata.get("abstract", ""),
        "links": metadata.get("links", []),
        "attachments": metadata.get("attachments", []),
        "content": journal.get("raw_body", ""),
    }


@router.get("/journal/{journal_path:path}/edit", response_class=HTMLResponse)
async def edit_page(request: Request, journal_path: str) -> HTMLResponse:
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
            llm_available=False,
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
    original_date_raw: str = Form(""),
    topic: str = Form(""),
    mood: str = Form(""),
    tags: str = Form(""),
    people: str = Form(""),
    location: str = Form(""),
    weather: str = Form(""),
    project: str = Form(""),
    abstract: str = Form(""),
    links: str = Form(""),
    existing_attachments: str = Form(""),
    content: str = Form(""),
    attachment_urls: list[str] | None = Form(None),
    attachments: list[UploadFile | str] | UploadFile | str | None = File(None),
) -> Response:
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or cookie_token != csrf_token:
        raise HTTPException(status_code=403, detail="CSRF 验证失败")

    try:
        journal = get_journal(journal_path)
    except ValueError:
        raise HTTPException(status_code=404, detail="日志未找到")

    # Process uploaded files
    staged_attachments = _stage_uploaded_files(_normalize_uploads(attachments))

    # Process URL attachments
    normalized_urls = [item.strip() for item in (attachment_urls or []) if item and item.strip()]
    downloaded_attachments: list[dict[str, str]] = []
    for url in normalized_urls:
        try:
            downloaded_attachments.append(download_attachment_from_url(url, date_str=date or None))
        except Exception:
            pass  # Skip failed URL downloads on edit

    # Merge with existing attachments (from textarea)
    all_attachments: list[dict[str, str] | str] = []
    if existing_attachments.strip():
        from web.services.edit import _normalize_attachment_textarea

        all_attachments.extend(_normalize_attachment_textarea(existing_attachments))
    all_attachments.extend(staged_attachments)
    all_attachments.extend(downloaded_attachments)

    form_data = {
        "title": title,
        "date": resolve_standard_date_value(date, original_date_raw),
        "original_date_raw": original_date_raw,
        "topic": topic,
        "mood": mood,
        "tags": tags,
        "people": people,
        "location": location,
        "weather": weather,
        "project": project,
        "abstract": abstract,
        "links": links,
        "attachments": all_attachments,
        "content": content,
    }
    original = {**journal.get("metadata", {}), "_body": journal.get("raw_body", "")}
    diff = compute_edit_diff(original=original, submitted=form_data)

    if diff.get("location_weather_required"):
        cleanup_staged_files(staged_attachments)
        new_csrf_token = _generate_csrf_token()
        response = request.app.state.templates.TemplateResponse(
            request,
            "edit.html",
            _build_edit_context(
                request,
                csrf_token=new_csrf_token,
                journal_route_path=journal_path,
                form_data=form_data,
                llm_available=False,
                error="修改地点后，请先查询天气或手动填写天气。",
            ),
        )
        _set_csrf_cookie(response, new_csrf_token)
        return response

    result = await edit_journal_web(
        journal_path=journal_path,
        frontmatter_updates=diff["frontmatter_updates"],
        replace_content=diff["replace_content"],
    )
    if result.get("success"):
        cleanup_staged_files(staged_attachments)
        redirect_url = f"/journal/{journal_path}?saved=1"
        readonly_warning = _readonly_simulation_warning_message()
        if readonly_warning:
            redirect_url = f"{redirect_url}&warning={quote(readonly_warning)}"
        return RedirectResponse(url=redirect_url, status_code=303)

    cleanup_staged_files(staged_attachments)
    new_csrf_token = _generate_csrf_token()
    response = request.app.state.templates.TemplateResponse(
        request,
        "edit.html",
        _build_edit_context(
            request,
            csrf_token=new_csrf_token,
            journal_route_path=journal_path,
            form_data=form_data,
            llm_available=False,
            error=str(result.get("error") or "编辑失败"),
        ),
    )
    _set_csrf_cookie(response, new_csrf_token)
    return response
