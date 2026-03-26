"""Web write service wrappers."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from tools.lib.config import JOURNALS_DIR, USER_DATA_DIR, get_default_location
from tools.lib.frontmatter import normalize_attachment_entries
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
    """Normalize a value to a list of strings.

    Handles:
    - None → []
    - Already a list → strip each item
    - Comma-separated string → split and strip each item
    - Single string → wrap in list

    This ensures "tag1, tag2" becomes ["tag1", "tag2"] not ["tag1, tag2"].
    """
    if value is None:
        return []
    if isinstance(value, list):
        # Already a list - but items might be comma-separated strings
        result: list[str] = []
        for item in value:
            item_str = str(item).strip()
            if not item_str:
                continue
            # If the item contains commas, split it
            if "," in item_str:
                result.extend(
                    [part.strip() for part in item_str.split(",") if part.strip()]
                )
            else:
                result.append(item_str)
        return result
    if isinstance(value, str) and value.strip():
        # Split on commas for form input like "tag1, tag2, tag3"
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _fallback_title(content: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return "无标题日志"
    return lines[0][:50]


def _fallback_abstract(content: str) -> str:
    meaningful_lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if meaningful_lines:
        return " ".join(meaningful_lines)[:100]
    return content[:100].strip()


def build_attachment_payloads(
    attachments: list[dict[str, Any] | str],
) -> list[dict[str, Any]]:
    return normalize_attachment_entries(attachments, mode="write_input")


def download_attachment_from_url(
    url: str,
    *,
    date_str: str | None = None,
    temp_dir: Path | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
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


def _weather_query_date(date_value: Any) -> str:
    return str(date_value or "").strip()[:10]


def _compact_location(value: str) -> str:
    parts = [part.strip() for part in str(value or "").split(",") if part.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}, {parts[-1]}"


KNOWN_PROJECT_ALIASES: list[tuple[str, str]] = [
    ("life index", "Life Index"),
    ("life-index", "Life Index"),
    ("lifeindex", "Life Index"),
    ("web gui", "Life Index"),
    ("digital-self", "Digital-self"),
    ("digital self", "Digital-self"),
    ("skyvision africa", "SkyVision Africa"),
    ("lobsterai", "LobsterAI"),
    ("carloha", "Carloha"),
]


def _infer_project(prepared: dict[str, Any], extracted: dict[str, Any]) -> str:
    explicit = str(prepared.get("project") or extracted.get("project") or "").strip()
    if explicit:
        return explicit

    corpus_parts = [
        str(prepared.get("title") or ""),
        str(prepared.get("content") or ""),
        " ".join(_normalize_text_list(prepared.get("tags"))),
        " ".join(_normalize_text_list(extracted.get("tags"))),
    ]
    corpus = "\n".join(corpus_parts).lower()
    for needle, canonical in KNOWN_PROJECT_ALIASES:
        if needle in corpus:
            return canonical
    return ""


async def prepare_journal_data(
    form_data: dict[str, Any], provider: LLMProvider | None
) -> dict[str, Any]:
    content = str(form_data.get("content", "")).strip()
    if not content:
        raise ValueError("content 为必填字段")

    prepared = dict(form_data)
    prepared["content"] = content
    field_sources: dict[str, str] = {}
    llm_status: dict[str, str | None] = {
        "state": "unavailable" if provider is None else "idle",
        "message": "未配置 AI 服务，将使用规则补全或手动字段。"
        if provider is None
        else None,
    }

    for field in (
        "title",
        "topic",
        "mood",
        "tags",
        "people",
        "location",
        "weather",
        "project",
    ):
        if field == "topic":
            if _normalize_text_list(prepared.get(field)):
                field_sources[field] = "user"
            continue
        if str(prepared.get(field, "")).strip():
            field_sources[field] = "user"

    if str(prepared.get("date", "")).strip():
        field_sources["date"] = "user"

    extracted: dict[str, Any] = {}
    if provider is not None:
        try:
            extracted = await provider.extract_metadata(content)
        except Exception as exc:
            extracted = {}
            llm_status = {
                "state": "failed",
                "message": f"AI 提炼失败：{exc}；已回退到规则补全，请检查后重试。",
            }
        else:
            if extracted:
                llm_status = {
                    "state": "ready",
                    "message": "AI 已成功提炼可用元数据。",
                }
            else:
                llm_status = {
                    "state": "fallback",
                    "message": "AI 未返回可用结果，已回退到规则补全或手动字段。",
                }

    for field in ("title", "abstract"):
        if not prepared.get(field) and extracted.get(field):
            prepared[field] = extracted[field]
            field_sources[field] = "ai"

    for field in ("mood", "tags", "people", "topic"):
        if not _normalize_text_list(prepared.get(field)):
            # Apply extracted values; only override if LLM returned something
            # (empty array = "LLM found nothing" vs missing key = "didn't try")
            if field in extracted:
                normalized = _normalize_text_list(extracted.get(field))
                prepared[field] = normalized
                field_sources[field] = "ai"

    inferred_project = _infer_project(prepared, extracted)
    if inferred_project and not str(prepared.get("project", "")).strip():
        prepared["project"] = inferred_project
        field_sources["project"] = "ai"

    if not prepared.get("title"):
        prepared["title"] = _fallback_title(content)
        field_sources["title"] = "rule"
    if not prepared.get("abstract"):
        prepared["abstract"] = _fallback_abstract(content)
        field_sources["abstract"] = "rule"

    prepared["attachments"] = build_attachment_payloads(
        list(form_data.get("attachments", []))
    )
    prepared["attachment_urls"] = list(form_data.get("attachment_urls", []))

    location = str(prepared.get("location", "")).strip()
    weather = str(prepared.get("weather", "")).strip()
    if not location:
        location = get_default_location()
        field_sources["location"] = "auto"

    coordinate_pair = parse_coordinate_location(location)
    if coordinate_pair is not None:
        reverse_result = reverse_geocode_coordinates(*coordinate_pair)
        resolved_location = str(reverse_result.get("location") or "").strip()
        if reverse_result.get("success") and resolved_location:
            location = resolved_location
            field_sources["location"] = "auto"

    prepared["location"] = _compact_location(location)

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
                _weather_query_date(prepared.get("date", "")),
            )
            weather = _extract_weather_text(weather_result)
    if weather:
        prepared["weather"] = weather
        field_sources.setdefault("weather", "auto")
    else:
        prepared.pop("weather", None)

    prepared["topic"] = _normalize_text_list(prepared.get("topic"))
    prepared["mood"] = _normalize_text_list(prepared.get("mood"))
    prepared["tags"] = _normalize_text_list(prepared.get("tags"))
    prepared["people"] = _normalize_text_list(prepared.get("people"))

    field_sources.setdefault("title", "user")
    field_sources.setdefault("abstract", "rule")
    field_sources.setdefault("topic", "rule")
    field_sources.setdefault("mood", "rule")
    field_sources.setdefault("tags", "rule")
    field_sources.setdefault("people", "rule")
    field_sources.setdefault("location", "user")
    field_sources.setdefault("date", "auto")
    if "weather" in prepared:
        field_sources.setdefault("weather", "user")

    if not provider and not prepared["topic"]:
        raise ValueError("LLM 不可用时，topic 为必填字段")

    prepared["field_sources"] = field_sources
    prepared["llm_status"] = llm_status

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
