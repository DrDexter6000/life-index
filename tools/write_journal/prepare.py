#!/usr/bin/env python3
"""
Life Index - Journal Data Preparation Module
============================================
Prepare journal metadata from user input.

This module contains the core business logic for preparing journal data
before writing. It handles:
- LLM-based metadata extraction (title, abstract, topic, mood, tags, people, project)
- Rule-based fallbacks (title/abstract from content)
- Project inference from content keywords
- Weather query integration
- Location normalization

SSOT: This is the single source of truth for journal data preparation.
Web layer should call this module, not duplicate the logic.

Usage:
    from tools.write_journal.prepare import prepare_journal_metadata

    result = prepare_journal_metadata({
        "content": "今天看到乐乐以前的照片...",
        "date": "2026-03-29",
    })
"""

import logging
from typing import Any

from tools.lib.config import get_default_location
from tools.lib.text_normalize import normalize_text_list

logger = logging.getLogger(__name__)
from tools.lib.llm_extract import extract_metadata_sync, is_llm_available, VALID_TOPICS
from tools.write_journal.weather import normalize_location

from .weather import query_weather_for_location

# Project inference rules - SSOT for known project aliases
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


def _fallback_title(content: str) -> str:
    """Generate fallback title from content (rule-based).

    Uses first non-empty line, truncated to 50 chars.

    Args:
        content: Journal content

    Returns:
        Fallback title string
    """
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return "无标题日志"
    return lines[0][:50]


def _fallback_abstract(content: str) -> str:
    """Generate fallback abstract from content (rule-based).

    Uses first 100 chars of meaningful content (excluding headers).

    Args:
        content: Journal content

    Returns:
        Fallback abstract string (≤100 chars)
    """
    meaningful_lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if meaningful_lines:
        return " ".join(meaningful_lines)[:100]
    return content[:100].strip()


def _compact_location(value: str) -> str:
    """Compact location string to "City, Country" format.

    Args:
        value: Raw location string (may have multiple comma parts)

    Returns:
        Compact location (first and last comma parts)
    """
    parts = [part.strip() for part in str(value or "").split(",") if part.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}, {parts[-1]}"


def _infer_project(prepared: dict[str, Any], extracted: dict[str, Any]) -> str:
    """Infer project from content keywords.

    Checks both user-provided fields and extracted fields for known aliases.

    Args:
        prepared: User-provided data dict
        extracted: LLM-extracted metadata dict

    Returns:
        Inferred project name or empty string
    """
    explicit = str(prepared.get("project") or extracted.get("project") or "").strip()
    if explicit:
        return explicit

    # Build corpus for keyword search
    corpus_parts = [
        str(prepared.get("title") or ""),
        str(prepared.get("content") or ""),
        " ".join(normalize_text_list(prepared.get("tags"))),
        " ".join(normalize_text_list(extracted.get("tags"))),
    ]
    corpus = "\n".join(corpus_parts).lower()

    for needle, canonical in KNOWN_PROJECT_ALIASES:
        if needle in corpus:
            return canonical

    return ""


def _extract_weather_text(weather_result: dict[str, Any] | None) -> str:
    """Extract simple weather text from query result.

    Args:
        weather_result: Result from query_weather()

    Returns:
        Simple weather string or empty string
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


def _weather_query_date(date_value: Any) -> str:
    """Extract date string for weather query (YYYY-MM-DD format).

    Args:
        date_value: Date value (string or datetime)

    Returns:
        Date string (first 10 chars)
    """
    return str(date_value or "").strip()[:10]


def prepare_journal_metadata(
    form_data: dict[str, Any],
    *,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Prepare journal metadata from user input (CLI-friendly sync version).

    This is the core business logic for metadata preparation. It:
    1. Validates required fields (content)
    2. Calls LLM for metadata extraction (if available and enabled)
    3. Applies rule-based fallbacks for missing fields
    4. Infers project from content keywords
    5. Auto-fills location and weather if not provided
    6. Normalizes all text list fields

    Args:
        form_data: User-provided data dict with keys:
            - content (required): str
            - date: str (YYYY-MM-DD format)
            - title: str (optional, will be extracted/fallback)
            - abstract: str (optional, will be extracted/fallback)
            - topic: str or list (optional, will be extracted)
            - mood: str or list (optional)
            - tags: str or list (optional)
            - people: str or list (optional)
            - location: str (optional, will use default)
            - weather: str (optional, will query if location available)
            - project: str (optional, will be inferred)
            - attachments: list (optional)
            - attachment_urls: list (optional)

        use_llm: Whether to use LLM extraction (default True)
            Set False for rule-only mode (e.g., when LLM unavailable)

    Returns:
        Prepared data dict with additional keys:
            - field_sources: dict[str, str] tracking field origin
                ("user", "ai", "rule", "auto")
            - llm_status: dict with state and message
                state: "unavailable" | "idle" | "ready" | "fallback" | "failed"
            - All metadata fields normalized to proper types

    Raises:
        ValueError: If content is empty, or if topic missing when LLM unavailable

    Example:
        >>> result = prepare_journal_metadata({
        ...     "content": "今天看到乐乐以前的照片...",
        ...     "date": "2026-03-29",
        ... })
        >>> result["title"]
        '想念小英雄'
        >>> result["field_sources"]["title"]
        'ai'
    """
    content = str(form_data.get("content", "")).strip()
    if not content:
        raise ValueError("content 为必填字段")

    prepared = dict(form_data)
    prepared["content"] = content

    # Track field sources
    field_sources: dict[str, str] = {}

    # LLM status tracking
    llm_available = use_llm and is_llm_available()
    llm_status: dict[str, str | None] = {
        "state": "unavailable" if not llm_available else "idle",
        "message": "未配置 AI 服务，将使用规则补全或手动字段。"
        if not llm_available
        else None,
    }

    # Mark user-provided fields
    for field in (
        "title",
        "topic",
        "mood",
        "tags",
        "people",
        "links",
        "related_entries",
        "location",
        "weather",
        "project",
    ):
        if field == "topic":
            if normalize_text_list(prepared.get(field)):
                field_sources[field] = "user"
            continue
        if str(prepared.get(field, "")).strip():
            field_sources[field] = "user"

    if str(prepared.get("date", "")).strip():
        field_sources["date"] = "user"

    # LLM extraction
    extracted: dict[str, Any] = {}
    if llm_available:
        try:
            extracted = extract_metadata_sync(content)
        except Exception as exc:
            logger.warning("LLM enrichment failed, continuing without: %s", exc)
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

    # Apply extracted values for missing fields
    for field in ("title", "abstract"):
        if not prepared.get(field) and extracted.get(field):
            prepared[field] = extracted[field]
            field_sources[field] = "ai"

    for field in ("mood", "tags", "people", "topic"):
        if not normalize_text_list(prepared.get(field)):
            if field in extracted:
                normalized = normalize_text_list(extracted.get(field))
                prepared[field] = normalized
                field_sources[field] = "ai"

    # Project inference
    inferred_project = _infer_project(prepared, extracted)
    if inferred_project and not str(prepared.get("project", "")).strip():
        prepared["project"] = inferred_project
        field_sources["project"] = "ai"

    # Rule-based fallbacks
    if not prepared.get("title"):
        prepared["title"] = _fallback_title(content)
        field_sources["title"] = "rule"
    if not prepared.get("abstract"):
        prepared["abstract"] = _fallback_abstract(content)
        field_sources["abstract"] = "rule"

    # Attachments (pass through)
    prepared["attachments"] = list(form_data.get("attachments", []))
    prepared["attachment_urls"] = list(form_data.get("attachment_urls", []))

    # Location auto-fill
    location = str(prepared.get("location", "")).strip()
    weather = str(prepared.get("weather", "")).strip()

    if not location:
        location = get_default_location()
        field_sources["location"] = "auto"

    prepared["location"] = _compact_location(location)

    # Weather auto-fill
    if not weather and location:
        location_for_weather = normalize_location(location)
        weather_result = query_weather_for_location(
            location_for_weather,
            _weather_query_date(prepared.get("date", "")),
        )
        weather = str(weather_result or "").strip()

    if weather:
        prepared["weather"] = weather
        field_sources.setdefault("weather", "auto")
    else:
        prepared.pop("weather", None)

    # Normalize list fields
    prepared["topic"] = normalize_text_list(prepared.get("topic"))
    prepared["mood"] = normalize_text_list(prepared.get("mood"))
    prepared["tags"] = normalize_text_list(prepared.get("tags"))
    prepared["people"] = normalize_text_list(prepared.get("people"))
    prepared["links"] = normalize_text_list(prepared.get("links"))
    prepared["related_entries"] = normalize_text_list(prepared.get("related_entries"))

    # Default field sources
    field_sources.setdefault("title", "user")
    field_sources.setdefault("abstract", "rule")
    field_sources.setdefault("topic", "rule")
    field_sources.setdefault("mood", "rule")
    field_sources.setdefault("tags", "rule")
    field_sources.setdefault("people", "rule")
    field_sources.setdefault("links", "rule")
    field_sources.setdefault("related_entries", "rule")
    field_sources.setdefault("location", "user")
    field_sources.setdefault("date", "auto")
    if "weather" in prepared:
        field_sources.setdefault("weather", "user")

    # Validation: topic required when LLM unavailable
    if not llm_available and not prepared["topic"]:
        raise ValueError("LLM 不可用时，topic 为必填字段")

    prepared["field_sources"] = field_sources
    prepared["llm_status"] = llm_status

    return prepared


__all__ = [
    "prepare_journal_metadata",
    "KNOWN_PROJECT_ALIASES",
    "VALID_TOPICS",
]
