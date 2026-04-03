"""Write route."""

from __future__ import annotations

import json
import secrets
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import markdown

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from web.config import TEMPLATES_DIR
from web.services.journal import get_journal
from web.services.date_adapter import resolve_standard_date_value, to_gui_datetime_value
from web.services.llm_provider import get_provider
from web.services.write import (
    cleanup_staged_files,
    download_attachment_from_url,
    prepare_journal_data,
    write_journal_web,
)

router = APIRouter()

TEMPLATES_JSON_PATH = TEMPLATES_DIR / "writing_templates.json"


def _readonly_simulation_warning_message() -> str | None:
    from web.runtime import get_runtime_info

    runtime = get_runtime_info()
    if not runtime.get("readonly_simulation"):
        return None
    return "当前操作已写入临时副本，不会回写真实用户目录；如需保留结果，请先人工确认后再迁移。"


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
    llm_state = _normalize_field_value(values.get("llm_status_state"))
    llm_message_override = _normalize_field_value(values.get("llm_status_message"))

    if llm_state == "failed":
        llm_status_label = "AI 提炼失败"
        llm_status_message = (
            llm_message_override or "AI 提炼失败，当前已回退到规则补全，请检查后重试。"
        )
    elif llm_state == "fallback":
        llm_status_label = "AI 未提炼出结果"
        llm_status_message = (
            llm_message_override or "AI 未返回可用结果，当前使用规则补全或手动字段。"
        )
    elif llm_available:
        llm_status_label = "AI 辅助已就绪"
        llm_status_message = "留空的字段将由 AI 自动提炼。"
    else:
        llm_status_label = "AI 辅助不可用"
        llm_status_message = "未配置 AI 服务。请手动填写关键字段，或前往设置启用 AI。"

    return {
        "request": request,
        "current_page": "/write",
        "csrf_token": csrf_token,
        "templates": templates,
        "templates_json": json.dumps(templates, ensure_ascii=False),
        "llm_available": llm_available,
        "llm_status_label": llm_status_label,
        "llm_status_message": llm_status_message,
        "error": error,
        "success": False,
        "journal_url": None,
        "title": _normalize_field_value(values.get("title")),
        "content": _normalize_field_value(values.get("content")),
        "date": to_gui_datetime_value(_normalize_field_value(values.get("date")))
        or datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "topic": _normalize_field_value(values.get("topic")),
        "mood": (
            ", ".join(values.get("mood", []))
            if isinstance(values.get("mood"), list)
            else _normalize_field_value(values.get("mood"))
        ),
        "tags": (
            ", ".join(values.get("tags", []))
            if isinstance(values.get("tags"), list)
            else _normalize_field_value(values.get("tags"))
        ),
        "people": (
            ", ".join(values.get("people", []))
            if isinstance(values.get("people"), list)
            else _normalize_field_value(values.get("people"))
        ),
        "location": _normalize_field_value(values.get("location")),
        "weather": _normalize_field_value(values.get("weather")),
        "project": _normalize_field_value(values.get("project")),
        "selected_template": _normalize_field_value(values.get("template")) or "blank",
    }


def _source_label(source: str | None) -> str:
    return {
        "ai": "由 AI 自动提炼",
        "rule": "由规则自动生成",
        "user": "用户填写",
        "auto": "自动获取",
    }.get(str(source or ""), "")


def _build_write_confirm_context(
    request: Request,
    *,
    journal: dict[str, Any],
    field_sources: dict[str, str],
    llm_available: bool,
    warning_message: str | None = None,
    location_needs_confirm: bool = False,
    location_confirm_message: str | None = None,
    attachment_summary: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "request": request,
        "current_page": "/write",
        "journal": journal,
        "field_sources": field_sources,
        "field_source_labels": {
            field: _source_label(source) for field, source in field_sources.items()
        },
        "llm_available": llm_available,
        "warning": warning_message,
        "location_needs_confirm": location_needs_confirm,
        "location_confirm_message": location_confirm_message,
        "attachment_summary": attachment_summary or {"detected": 0, "processed": 0, "failed": 0},
    }


def _build_fallback_confirmation_journal(
    prepared_data: dict[str, Any], journal_route_path: str
) -> dict[str, Any]:
    metadata_fields = (
        "title",
        "date",
        "topic",
        "mood",
        "tags",
        "people",
        "location",
        "weather",
        "project",
        "abstract",
        "links",
    )
    metadata = {
        field: prepared_data.get(field)
        for field in metadata_fields
        if prepared_data.get(field) not in (None, "", [])
    }
    html_content = markdown.markdown(
        str(prepared_data.get("content", "")), extensions=["fenced_code", "tables"]
    )
    return {
        "metadata": metadata,
        "html_content": html_content,
        "raw_body": str(prepared_data.get("content", "")),
        "attachments": [],
        "links": [],
        "journal_route_path": journal_route_path,
    }


def _set_csrf_cookie(response: HTMLResponse | RedirectResponse, csrf_token: str) -> None:
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
    normalized_urls = [item.strip() for item in (attachment_urls or []) if item and item.strip()]
    staged_attachments = stage_uploaded_files(_normalize_uploads(attachments))

    downloaded_attachments: list[dict[str, str]] = []
    skipped_attachment_errors: list[str] = []
    try:
        for url in normalized_urls:
            try:
                downloaded_attachments.append(
                    download_attachment_from_url(url, date_str=date or None)
                )
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
            "date": resolve_standard_date_value(date),
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
        "date": resolve_standard_date_value(date),
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
        llm_error_text = str(exc)
        raw_form_data_with_status = dict(raw_form_data)
        if llm_error_text.startswith("AI 提炼失败："):
            raw_form_data_with_status["llm_status_state"] = "failed"
            raw_form_data_with_status["llm_status_message"] = llm_error_text
        elif "未返回可用结果" in llm_error_text:
            raw_form_data_with_status["llm_status_state"] = "fallback"
            raw_form_data_with_status["llm_status_message"] = llm_error_text
        response = request.app.state.templates.TemplateResponse(
            request,
            "write.html",
            _build_template_context(
                request,
                csrf_token=new_csrf_token,
                templates=templates,
                llm_available=provider is not None,
                form_data=raw_form_data_with_status,
                error=str(exc),
            ),
        )
        _set_csrf_cookie(response, new_csrf_token)
        return response

    field_sources = dict(prepared_data.get("field_sources", {}))
    llm_status = dict(prepared_data.get("llm_status", {}))
    data_to_write = dict(prepared_data)
    data_to_write.pop("field_sources", None)
    data_to_write.pop("llm_status", None)

    result = await write_journal_web(data_to_write)
    if result.get("success") and result.get("journal_route_path"):
        cleanup_staged_files(staged_attachments)
        warning_parts: list[str] = []
        readonly_warning = _readonly_simulation_warning_message()
        if readonly_warning:
            warning_parts.append(readonly_warning)
        if skipped_attachment_errors:
            warning_parts.extend(
                f"已跳过附件下载失败：{message}" for message in skipped_attachment_errors
            )
        journal = get_journal(str(result["journal_route_path"]))
        if journal.get("error"):
            journal = _build_fallback_confirmation_journal(
                data_to_write, str(result["journal_route_path"])
            )
        warning_message = "；".join(warning_parts) if warning_parts else None
        return request.app.state.templates.TemplateResponse(
            request,
            "write_confirm.html",
            _build_write_confirm_context(
                request,
                journal=journal,
                field_sources=field_sources,
                llm_available=llm_status.get("state") == "ready",
                warning_message=warning_message,
                location_needs_confirm=bool(result.get("needs_confirmation")),
                location_confirm_message=result.get("confirmation_message"),
                attachment_summary={
                    "detected": int(result.get("attachments_detected_count") or 0),
                    "processed": int(result.get("attachments_processed_count") or 0),
                    "failed": int(result.get("attachments_failed_count") or 0),
                },
            ),
        )

    cleanup_staged_files(staged_attachments)
    new_csrf_token = _generate_csrf_token()
    error_message = str(result.get("error") or "写入失败")
    if skipped_attachment_errors:
        error_message = (
            error_message
            + "\n"
            + "\n".join(f"已跳过附件下载失败：{message}" for message in skipped_attachment_errors)
        )
    response = request.app.state.templates.TemplateResponse(
        request,
        "write.html",
        _build_template_context(
            request,
            csrf_token=new_csrf_token,
            templates=templates,
            llm_available=provider is not None,
            form_data={
                **prepared_data,
                "llm_status_state": llm_status.get("state") or "idle",
                "llm_status_message": llm_status.get("message") or "",
            },
            error=error_message,
        ),
    )
    _set_csrf_cookie(response, new_csrf_token)
    return response
