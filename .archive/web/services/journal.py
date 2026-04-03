"""Journal view service."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
from typing import Any
import re

import markdown
import re

from tools.lib.config import JOURNALS_DIR
from tools.lib.frontmatter import normalize_attachment_entries, parse_journal_file


def _extract_links_from_body(body: str) -> list[dict[str, str]]:
    """Extract Markdown links from body text."""
    links = []
    # Match Markdown links: [text](url)
    pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    for match in re.finditer(pattern, body):
        title = match.group(1).strip()
        url = match.group(2).strip()
        # Skip attachment links (relative paths)
        if url.startswith("http://") or url.startswith("https://"):
            links.append(
                {
                    "title": title,
                    "url": url,
                }
            )
    return links


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi"}


def _classify_attachment_kind(name: str) -> tuple[str, bool]:
    suffix = Path(name).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image", True
    if suffix in VIDEO_EXTENSIONS:
        return "video", True
    return "file", False


def _safe_journal_path(relative_path: str) -> Path:
    resolved = (JOURNALS_DIR / relative_path).resolve()
    journals_root = JOURNALS_DIR.resolve()
    if journals_root not in (resolved, *resolved.parents):
        raise ValueError("Path traversal detected")
    return resolved


def _rewrite_attachment_urls(body: str) -> str:
    rewritten = body.replace("../../../attachments/", "/attachments/")

    def _rewrite_markdown_url(match: re.Match[str]) -> str:
        prefix, url, suffix = match.groups()
        if not url.startswith("/attachments/"):
            return match.group(0)
        return f"{prefix}{quote(url, safe='/:')}{suffix}"

    return re.sub(r"(!?\[[^\]]*\]\()([^)]+)(\))", _rewrite_markdown_url, rewritten)


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

    attachment_links: list[dict[str, str]] = []
    for attachment in normalize_attachment_entries(
        metadata.get("attachments", []), mode="stored_metadata"
    ):
        kind, is_previewable = _classify_attachment_kind(attachment["name"])
        attachment_links.append(
            {
                "raw_path": attachment["raw_path"],
                "href": _rewrite_attachment_urls(attachment["path"]),
                "name": attachment["name"],
                "kind": kind,
                "is_previewable": is_previewable,
                "source_url": attachment.get("source_url"),
                "content_type": attachment.get("content_type"),
                "size": attachment.get("size"),
            }
        )

    metadata["links"] = metadata.get("links", []) or []

    # Extract links from body content
    body_links = _extract_links_from_body(str(parsed.get("_body", "")))

    # Data sovereignty visualization - full file path (DESIGN-DIRECTION §4.4, P0)
    full_file_path = str(file_path)
    # Convert to user-friendly path format
    try:
        from tools.lib.config import USER_DATA_DIR

        user_data_path = str(USER_DATA_DIR)
        if full_file_path.startswith(user_data_path):
            display_path = (
                "~/Documents/Life-Index" + full_file_path[len(user_data_path) :]
            )
        else:
            display_path = full_file_path
    except Exception:
        display_path = full_file_path

    return {
        "metadata": metadata,
        "html_content": html_content,
        "raw_body": str(parsed.get("_body", "")),
        "attachments": attachment_links,
        "links": body_links,
        "journal_route_path": relative_path,
        "file_path": display_path,  # P0: Data sovereignty visualization
        "file_path_full": full_file_path,
    }
