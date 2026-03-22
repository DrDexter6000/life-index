"""Web write service wrappers."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from tools.lib.config import JOURNALS_DIR, USER_DATA_DIR, get_default_location
from tools.lib.path_contract import merge_journal_path_fields
from tools.query_weather import geocode_location, query_weather
from tools.write_journal.core import write_journal

from web.services.geolocation import (
    parse_coordinate_location,
    reverse_geocode_coordinates,
)
from web.services.url_download import download_url
from web.services.llm_provider import LLMProvider


def _normalize_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _fallback_title(content: str) -> str:
    return content[:20].strip() or "无标题"


def _fallback_abstract(content: str) -> str:
    return content[:100].strip()


def build_attachment_payloads(
    attachments: list[dict[str, Any] | str],
) -> list[dict[str, str]]:
    payloads: list[dict[str, str]] = []
    for item in attachments:
        if isinstance(item, str):
            payloads.append({"source_path": item, "description": ""})
            continue

        source_path = str(item.get("source_path", "")).strip()
        if not source_path:
            continue

        payloads.append(
            {
                "source_path": source_path,
                "description": str(item.get("description", "")),
            }
        )
    return payloads


def download_attachment_from_url(
    url: str,
    *,
    temp_dir: Path | None = None,
    timeout: float = 30.0,
) -> dict[str, str]:
    target_dir = temp_dir or Path(tempfile.mkdtemp(prefix="life-index-url-"))
    result = asyncio.run(download_url(url, target_dir, timeout=timeout))
    if not result.get("success"):
        error_code = result.get("error_code")
        if error_code == "E0702":
            raise ValueError(str(result.get("error") or "Content-Type 不支持"))
        raise RuntimeError(str(result.get("error") or "下载失败"))
    return {"source_path": str(result["path"]), "description": url}


def cleanup_staged_files(staged_attachments: list[dict[str, str]]) -> None:
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


def _extract_weather_text(weather_result: dict[str, Any] | None) -> str:
    if not isinstance(weather_result, dict):
        return ""
    if not weather_result.get("success"):
        return ""
    weather = weather_result.get("weather")
    if not isinstance(weather, dict):
        return ""
    simple = weather.get("simple")
    return str(simple).strip() if simple else ""


async def prepare_journal_data(
    form_data: dict[str, Any], provider: LLMProvider | None
) -> dict[str, Any]:
    content = str(form_data.get("content", "")).strip()
    if not content:
        raise ValueError("content 为必填字段")

    prepared = dict(form_data)
    prepared["content"] = content

    extracted: dict[str, Any] = {}
    if provider is not None:
        extracted = await provider.extract_metadata(content)

    for field in ("title", "abstract"):
        if not prepared.get(field) and extracted.get(field):
            prepared[field] = extracted[field]

    for field in ("mood", "tags", "people", "topic"):
        if not _normalize_text_list(prepared.get(field)):
            normalized = _normalize_text_list(extracted.get(field))
            if normalized:
                prepared[field] = normalized

    if not prepared.get("title"):
        prepared["title"] = _fallback_title(content)
    if not prepared.get("abstract"):
        prepared["abstract"] = _fallback_abstract(content)

    prepared["attachments"] = build_attachment_payloads(
        list(form_data.get("attachments", []))
    )
    prepared["attachment_urls"] = list(form_data.get("attachment_urls", []))

    location = str(prepared.get("location", "")).strip()
    weather = str(prepared.get("weather", "")).strip()
    if not location:
        location = get_default_location()

    coordinate_pair = parse_coordinate_location(location)
    if coordinate_pair is not None:
        reverse_result = reverse_geocode_coordinates(*coordinate_pair)
        resolved_location = str(reverse_result.get("location") or "").strip()
        if reverse_result.get("success") and resolved_location:
            location = resolved_location

    prepared["location"] = location

    if not weather and location:
        geocode_result = geocode_location(location)
        if (
            isinstance(geocode_result, dict)
            and "latitude" in geocode_result
            and "longitude" in geocode_result
        ):
            weather_result = query_weather(
                float(geocode_result["latitude"]),
                float(geocode_result["longitude"]),
                str(prepared.get("date", "")),
            )
            weather = _extract_weather_text(weather_result)
    prepared["weather"] = weather

    prepared["topic"] = _normalize_text_list(prepared.get("topic"))
    prepared["mood"] = _normalize_text_list(prepared.get("mood"))
    prepared["tags"] = _normalize_text_list(prepared.get("tags"))
    prepared["people"] = _normalize_text_list(prepared.get("people"))

    if not provider and not prepared["topic"]:
        raise ValueError("LLM 不可用时，topic 为必填字段")

    return prepared


async def write_journal_web(
    data: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
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
