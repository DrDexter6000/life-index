"""Web write service wrappers - thin layer over CLI tools.

This module provides async wrappers and web-specific utilities (temp file handling,
URL download) while delegating all business logic to the CLI tools layer.

SSOT: Business logic lives in tools/. This module only handles web-specific concerns.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from tools.lib.config import JOURNALS_DIR, USER_DATA_DIR
from tools.lib.frontmatter import normalize_attachment_entries
from tools.lib.path_contract import merge_journal_path_fields
from tools.lib.text_normalize import normalize_text_list
from tools.query_weather import (
    geocode_location,
    parse_coordinate_location,
    query_weather,
    reverse_geocode_location,
)
from tools.write_journal.core import write_journal
from tools.write_journal.prepare import prepare_journal_metadata

from web.services.url_download import download_url


# Re-exports for backward compatibility with tests
# These functions now live in CLI layer but tests patch them at web layer
_normalize_text_list = normalize_text_list

# Alias for backward compatibility with tests
reverse_geocode_coordinates = reverse_geocode_location


def _extract_weather_text(weather_result: dict[str, Any] | None) -> str:
    """Extract simple weather text from query result.

    Kept for backward compatibility with tests.
    """
    if not isinstance(weather_result, dict):
        return ""
    if not weather_result.get("success"):
        return ""
    weather = weather_result.get("weather")
    if not isinstance(weather, dict):
        return ""
    simple = weather.get("simple")
    return str(simple).strip() if simple else ""


def build_attachment_payloads(
    attachments: list[dict[str, Any] | str],
) -> list[dict[str, Any]]:
    """Build attachment payloads from web form data.

    Thin wrapper around CLI's normalize_attachment_entries.
    """
    return normalize_attachment_entries(attachments, mode="write_input")


def download_attachment_from_url(
    url: str,
    *,
    date_str: str | None = None,
    temp_dir: Path | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Download attachment from URL to temp directory.

    This is web-specific: handles temp file creation for staged uploads.
    """
    target_dir = temp_dir or Path(tempfile.mkdtemp(prefix="life-index-url-"))
    result = asyncio.run(
        download_url(url, target_dir, date_str=date_str, timeout=timeout)
    )
    if not result.get("success"):
        error_code = result.get("error_code")
        if error_code == "E0702":
            raise ValueError(str(result.get("error") or "Content-Type 不支持"))
        raise RuntimeError(str(result.get("error") or "下载失败"))
    return {
        "source_url": url,
        "source_path": str(result["path"]),
        "description": url,
        "content_type": result.get("content_type"),
        "size": result.get("size"),
    }


def cleanup_staged_files(staged_attachments: list[dict[str, str]]) -> None:
    """Clean up temporary staged attachment files.

    Web-specific: handles cleanup of files staged during form submission.
    """
    for item in staged_attachments:
        source_path = str(item.get("source_path", "")).strip()
        if not source_path:
            continue
        path = Path(source_path)
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            continue


async def prepare_journal_data(
    form_data: dict[str, Any], provider: Any = None
) -> dict[str, Any]:
    """Prepare journal metadata from form data.

    Delegates to CLI's prepare_journal_metadata for all business logic.
    Handles coordinate-based location resolution (web-specific).

    Args:
        form_data: Raw form data from web request
        provider: LLM provider instance (ignored - CLI handles LLM internally)

    Returns:
        Prepared metadata dict with field_sources and llm_status
    """
    # Run CLI's prepare_journal_metadata in thread pool
    prepared = await asyncio.to_thread(prepare_journal_metadata, form_data)

    # Web-specific: handle coordinate-based location from browser geolocation
    location = str(prepared.get("location", "")).strip()
    coordinate_pair = parse_coordinate_location(location)
    if coordinate_pair is not None:
        reverse_result = await asyncio.to_thread(
            reverse_geocode_location, *coordinate_pair
        )
        resolved_location = str(reverse_result.get("location") or "").strip()
        if reverse_result.get("success") and resolved_location:
            # Compact to "City, Country" format
            parts = [p.strip() for p in resolved_location.split(",") if p.strip()]
            if len(parts) >= 2:
                prepared["location"] = f"{parts[0]}, {parts[-1]}"
            else:
                prepared["location"] = resolved_location
            prepared["field_sources"]["location"] = "auto"

    # Build attachment payloads (web-specific handling)
    prepared["attachments"] = build_attachment_payloads(
        list(form_data.get("attachments", []))
    )
    prepared["attachment_urls"] = list(form_data.get("attachment_urls", []))

    return prepared


async def write_journal_web(
    data: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Write journal entry via CLI.

    Thin async wrapper around CLI's write_journal function.
    """
    result = await asyncio.to_thread(write_journal, data, dry_run)
    journal_path = result.get("journal_path")
    if not result.get("success") or not journal_path:
        return result

    return merge_journal_path_fields(
        result,
        journal_path,
        journals_dir=JOURNALS_DIR,
        user_data_dir=USER_DATA_DIR,
    )
