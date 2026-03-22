"""Write route."""

from __future__ import annotations

import json
import secrets
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from web.config import TEMPLATES_DIR
from web.services.llm_provider import get_provider
from web.services.write import (
    cleanup_staged_files,
    download_attachment_from_url,
    prepare_journal_data,
    write_journal_web,
)

router = APIRouter()

TEMPLATES_JSON_PATH = TEMPLATES_DIR / "writing_templates.json"


def load_writing_templates() -> list[dict[str, Any]]:
    return json.loads(TEMPLATES_JSON_PATH.read_text(encoding="utf-8"))


def _generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def _normalize_field_value(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _build_template_context(
    request: Request,
    *,
    csrf_token: str,
    templates: list[dict[str, Any]],
    llm_available: bool,
    form_data: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    values = form_data or {}
    return {
        "request": request,
        "csrf_token": csrf_token,
        "templates": templates,
        "templates_json": json.dumps(templates, ensure_ascii=False),
        "llm_available": llm_available,
        "error": error,
        "success": False,
        "journal_url": None,
        "title": _normalize_field_value(values.get("title")),
        "content": _normalize_field_value(values.get("content")),
        "date": _normalize_field_value(values.get("date"))
        or datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "topic": _normalize_field_value(values.get("topic")),
        "mood": ", ".join(values.get("mood", []))
        if isinstance(values.get("mood"), list)
        else _normalize_field_value(values.get("mood")),
        "tags": ", ".join(values.get("tags", []))
        if isinstance(values.get("tags"), list)
        else _normalize_field_value(values.get("tags")),
        "people": ", ".join(values.get("people", []))
        if isinstance(values.get("people"), list)
        else _normalize_field_value(values.get("people")),
        "location": _normalize_field_value(values.get("location")),
        "weather": _normalize_field_value(values.get("weather")),
        "project": _normalize_field_value(values.get("project")),
        "selected_template": _normalize_field_value(values.get("template")) or "blank",
    }


def _set_csrf_cookie(
    response: HTMLResponse | RedirectResponse, csrf_token: str
) -> None:
    response.set_cookie("csrf_token", csrf_token, samesite="lax")


def stage_uploaded_files(uploads: list[UploadFile]) -> list[dict[str, str]]:
    staged: list[dict[str, str]] = []
    for upload in uploads:
        filename = upload.filename or "attachment"
        suffix = Path(filename).suffix
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
            prefix="life-index-upload-",
        ) as temp_file:
            temp_file.write(upload.file.read())
            staged.append({"source_path": temp_file.name, "description": ""})
    return staged


def _normalize_uploads(uploads: Any) -> list[UploadFile]:
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


def _is_blocking_attachment_error(exc: Exception) -> bool:
    return "Content-Type" in str(exc)


@router.get("/write", response_class=HTMLResponse)
async def write_page(request: Request) -> HTMLResponse:
    templates = load_writing_templates()
    provider = await get_provider()
    csrf_token = _generate_csrf_token()
    response = request.app.state.templates.TemplateResponse(
        request,
        "write.html",
        _build_template_context(
            request,
            csrf_token=csrf_token,
            templates=templates,
            llm_available=provider is not None,
        ),
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.post("/write", response_class=HTMLResponse)
async def submit_write(
    request: Request,
    csrf_token: str = Form(...),
    title: str = Form(""),
    content: str = Form(""),
    date: str = Form(""),
    topic: str = Form(""),
    mood: str = Form(""),
    tags: str = Form(""),
    people: str = Form(""),
    location: str = Form(""),
    weather: str = Form(""),
    project: str = Form(""),
    template: str = Form("blank"),
    attachment_urls: list[str] | None = Form(None),
    attachments: list[UploadFile | str] | UploadFile | str | None = File(None),
) -> Response:
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or cookie_token != csrf_token:
        raise HTTPException(status_code=403, detail="CSRF 验证失败")

    templates = load_writing_templates()
    provider = await get_provider()
    normalized_urls = [
        item.strip() for item in (attachment_urls or []) if item and item.strip()
    ]
    staged_attachments = stage_uploaded_files(_normalize_uploads(attachments))

    downloaded_attachments: list[dict[str, str]] = []
    skipped_attachment_errors: list[str] = []
    try:
        for url in normalized_urls:
            try:
                downloaded_attachments.append(download_attachment_from_url(url))
            except Exception as exc:
                if _is_blocking_attachment_error(exc):
                    raise
                skipped_attachment_errors.append(f"{url}: {exc}")
    except ValueError as exc:
        cleanup_staged_files(staged_attachments)
        new_csrf_token = _generate_csrf_token()
        raw_form_data: dict[str, Any] = {
            "title": title,
            "content": content,
            "date": date,
            "topic": topic,
            "mood": mood,
            "tags": tags,
            "people": people,
            "location": location,
            "weather": weather,
            "project": project,
            "template": template,
            "attachment_urls": normalized_urls,
            "attachments": [],
        }
        response = request.app.state.templates.TemplateResponse(
            request,
            "write.html",
            _build_template_context(
                request,
                csrf_token=new_csrf_token,
                templates=templates,
                llm_available=provider is not None,
                form_data=raw_form_data,
                error=str(exc),
            ),
        )
        _set_csrf_cookie(response, new_csrf_token)
        return response

    raw_form_data: dict[str, Any] = {
        "title": title,
        "content": content,
        "date": date,
        "topic": topic,
        "mood": mood,
        "tags": tags,
        "people": people,
        "location": location,
        "weather": weather,
        "project": project,
        "template": template,
        "attachment_urls": normalized_urls,
        "attachments": [*staged_attachments, *downloaded_attachments],
    }

    try:
        prepared_data = await prepare_journal_data(raw_form_data, provider)
    except ValueError as exc:
        cleanup_staged_files(staged_attachments)
        new_csrf_token = _generate_csrf_token()
        response = request.app.state.templates.TemplateResponse(
            request,
            "write.html",
            _build_template_context(
                request,
                csrf_token=new_csrf_token,
                templates=templates,
                llm_available=provider is not None,
                form_data=raw_form_data,
                error=str(exc),
            ),
        )
        _set_csrf_cookie(response, new_csrf_token)
        return response

    result = await write_journal_web(prepared_data)
    if result.get("success") and result.get("journal_route_path"):
        cleanup_staged_files(staged_attachments)
        redirect_url = f"/journal/{result['journal_route_path']}"
        if skipped_attachment_errors:
            warning_message = "；".join(
                f"已跳过附件下载失败：{message}"
                for message in skipped_attachment_errors
            )
            redirect_url = f"{redirect_url}?warning={quote(warning_message)}"
        return RedirectResponse(
            url=redirect_url,
            status_code=303,
        )

    cleanup_staged_files(staged_attachments)
    new_csrf_token = _generate_csrf_token()
    error_message = str(result.get("error") or "写入失败")
    if skipped_attachment_errors:
        error_message = (
            error_message
            + "\n"
            + "\n".join(
                f"已跳过附件下载失败：{message}"
                for message in skipped_attachment_errors
            )
        )
    response = request.app.state.templates.TemplateResponse(
        request,
        "write.html",
        _build_template_context(
            request,
            csrf_token=new_csrf_token,
            templates=templates,
            llm_available=provider is not None,
            form_data=prepared_data,
            error=error_message,
        ),
    )
    _set_csrf_cookie(response, new_csrf_token)
    return response
