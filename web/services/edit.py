"""Web edit service wrappers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from tools.edit_journal import edit_journal
from tools.lib.config import JOURNALS_DIR, USER_DATA_DIR
from tools.lib.path_contract import merge_journal_path_fields
from web.services.write import _normalize_text_list


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
        normalized_original = (
            "" if original_value is None else str(original_value).strip()
        )
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
