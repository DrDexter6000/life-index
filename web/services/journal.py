"""Journal view service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import markdown

from tools.lib.config import JOURNALS_DIR
from tools.lib.frontmatter import parse_journal_file


def _safe_journal_path(relative_path: str) -> Path:
    resolved = (JOURNALS_DIR / relative_path).resolve()
    journals_root = JOURNALS_DIR.resolve()
    if journals_root not in (resolved, *resolved.parents):
        raise ValueError("Path traversal detected")
    return resolved


def _rewrite_attachment_urls(body: str) -> str:
    return body.replace("../../../attachments/", "/attachments/")


def get_journal(relative_path: str) -> dict[str, Any]:
    file_path = _safe_journal_path(relative_path)
    if not file_path.exists():
        return {"error": "日志未找到", "journal_route_path": relative_path}

    parsed = parse_journal_file(file_path)
    if parsed.get("_error"):
        return {"error": "日志未找到", "journal_route_path": relative_path}

    body = _rewrite_attachment_urls(str(parsed.get("_body", "")))
    try:
        html_content = markdown.markdown(body, extensions=["fenced_code", "tables"])
    except Exception:
        html_content = body

    metadata = {key: value for key, value in parsed.items() if not key.startswith("_")}
    metadata["title"] = parsed.get("_title") or metadata.get("title") or file_path.stem

    return {
        "metadata": metadata,
        "html_content": html_content,
        "raw_body": str(parsed.get("_body", "")),
        "attachments": metadata.get("attachments", []),
        "journal_route_path": relative_path,
    }
