#!/usr/bin/env python3
"""
Life Index - Attachment Utilities
附件归一化处理模块

从 frontmatter.py 提取的附件处理逻辑。
支持写入输入 (write_input) 和已存储元数据 (stored_metadata) 两种模式。
"""

import mimetypes
from pathlib import Path
from typing import Any, Literal


def normalize_attachment_entries(
    attachments: list[Any] | None,
    *,
    mode: Literal["write_input", "stored_metadata"],
) -> list[dict[str, Any]]:
    """Normalize attachment entries for shared write/read handling."""
    normalized: list[dict[str, Any]] = []

    for attachment in attachments or []:
        if mode == "write_input":
            entry = _normalize_attachment_write_input(attachment)
        else:
            entry = _normalize_attachment_stored_metadata(attachment)

        if entry is not None:
            normalized.append(entry)

    return normalized


def _normalize_attachment_write_input(attachment: Any) -> dict[str, Any] | None:
    if isinstance(attachment, str):
        source_path = attachment.strip()
        if not source_path:
            return None
        return {"source_path": source_path, "description": ""}

    if not isinstance(attachment, dict):
        return None

    source_path = str(attachment.get("source_path", "")).strip()
    source_url = str(attachment.get("source_url", "")).strip()
    if not source_path and not source_url:
        return None

    normalized: dict[str, Any] = {"description": str(attachment.get("description", ""))}
    if source_path:
        normalized["source_path"] = source_path
    if source_url:
        normalized["source_url"] = source_url
    if attachment.get("content_type") is not None:
        normalized["content_type"] = str(attachment.get("content_type"))
    size_value = attachment.get("size")
    if size_value is not None:
        normalized["size"] = int(size_value)
    return normalized


def _guess_attachment_content_type(path: str) -> str | None:
    content_type, _ = mimetypes.guess_type(path)
    return content_type


def _normalize_attachment_stored_metadata(attachment: Any) -> dict[str, Any] | None:
    if isinstance(attachment, dict):
        raw_path = str(
            attachment.get("rel_path")
            or attachment.get("path")
            or attachment.get("source_path")
            or ""
        ).strip()
        if not raw_path:
            return None

        return {
            "raw_path": raw_path,
            "path": raw_path,
            "name": str(attachment.get("filename") or Path(raw_path).name),
            "description": str(attachment.get("description", "")),
            "source_url": attachment.get("source_url"),
            "content_type": attachment.get("content_type")
            or _guess_attachment_content_type(raw_path),
            "size": attachment.get("size"),
        }

    raw_path = str(attachment).strip()
    if not raw_path:
        return None

    return {
        "raw_path": raw_path,
        "path": raw_path,
        "name": Path(raw_path).name,
        "description": "",
        "source_url": None,
        "content_type": _guess_attachment_content_type(raw_path),
        "size": None,
    }
