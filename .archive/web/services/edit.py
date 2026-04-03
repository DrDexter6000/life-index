"""Web edit service wrappers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from tools.edit_journal import edit_journal
from tools.lib.config import JOURNALS_DIR, USER_DATA_DIR
from tools.lib.path_contract import merge_journal_path_fields
from web.services.write import _normalize_text_list


def _normalize_multiline_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    lines = str(value).splitlines()
    return [line.strip() for line in lines if line.strip()]


def _normalize_attachment_textarea(value: Any) -> list[dict[str, Any] | str]:
    """Normalize attachment input to a list of dicts or strings.

    Handles:
    - Already normalized lists (list of dicts with source_path)
    - JSON strings from textarea
    - Plain string paths (one per line)
    """
    if value is None:
        return []

    # If already a list, process each item
    if isinstance(value, list):
        normalized: list[dict[str, Any] | str] = []
        for item in value:
            if isinstance(item, dict):
                # Already a dict, keep as-is
                normalized.append(item)
            elif isinstance(item, str):
                # String might be JSON or plain path
                item = item.strip()
                if not item:
                    continue
                if item.startswith("{"):
                    try:
                        parsed = json.loads(item)
                        if isinstance(parsed, dict):
                            normalized.append(parsed)
                            continue
                    except json.JSONDecodeError:
                        pass
                normalized.append(item)
        return normalized

    # String input (from textarea)
    normalized = []
    for line in _normalize_multiline_text(value):
        if line.startswith("{"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                normalized.append(line)
                continue
            if isinstance(parsed, dict):
                normalized.append(parsed)
                continue
        normalized.append(line)
    return normalized


def compute_edit_diff(
    original: dict[str, Any],
    submitted: dict[str, Any],
) -> dict[str, Any]:
    frontmatter_updates: dict[str, Any] = {}

    list_fields = {"topic", "mood", "tags", "people"}
    scalar_fields = {"title", "date", "location", "weather", "project", "abstract"}

    for field in scalar_fields:
        original_value = original.get(field)
        submitted_value = str(submitted.get(field, "")).strip()
        normalized_original = "" if original_value is None else str(original_value).strip()
        if (
            field == "weather"
            and submitted_value == ""
            and str(submitted.get("location", "")).strip()
            != str(original.get("location", "")).strip()
        ):
            continue
        if submitted_value != normalized_original:
            frontmatter_updates[field] = submitted_value

    for field in list_fields:
        original_value = _normalize_text_list(original.get(field))
        submitted_value = _normalize_text_list(submitted.get(field))
        if submitted_value != original_value:
            frontmatter_updates[field] = submitted_value

    if "links" in submitted:
        original_links = _normalize_text_list(original.get("links"))
        submitted_links = _normalize_multiline_text(submitted.get("links"))
        if submitted_links != original_links:
            frontmatter_updates["links"] = submitted_links

    if "attachments" in submitted:
        original_attachments = original.get("attachments", []) or []
        submitted_attachments = _normalize_attachment_textarea(submitted.get("attachments"))
        if submitted_attachments != original_attachments:
            frontmatter_updates["attachments"] = submitted_attachments

    replace_content = None
    original_body = str(original.get("_body", ""))
    submitted_body = str(submitted.get("content", ""))
    if submitted_body != original_body:
        replace_content = submitted_body

    location_changed = "location" in frontmatter_updates
    weather_missing = not str(frontmatter_updates.get("weather", "")).strip()

    return {
        "frontmatter_updates": frontmatter_updates,
        "replace_content": replace_content,
        "location_weather_required": location_changed and weather_missing,
    }


async def edit_journal_web(
    journal_path: str,
    frontmatter_updates: dict[str, Any],
    replace_content: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    result = await asyncio.to_thread(
        edit_journal,
        Path(JOURNALS_DIR / journal_path),
        frontmatter_updates,
        None,
        replace_content,
        dry_run,
    )

    journal_result_path = result.get("journal_path") or str(JOURNALS_DIR / journal_path)
    return merge_journal_path_fields(
        result,
        journal_result_path,
        journals_dir=JOURNALS_DIR,
        user_data_dir=USER_DATA_DIR,
    )
