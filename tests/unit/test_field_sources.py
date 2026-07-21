"""Test field_sources tracking in prepare.py."""

from unittest.mock import patch

import pytest

from tools.write_journal.prepare import prepare_journal_metadata


def test_field_sources_user_provided_fields():
    """用户提供的字段应标记为 'user'"""
    raw = {
        "title": "我的标题",
        "abstract": "我的摘要",
        "content": "正文",
        "tags": "tag1, tag2",
        "topic": "work",
    }
    result = prepare_journal_metadata(raw)
    assert result["field_sources"]["title"] == "user"
    assert result["field_sources"]["abstract"] == "user"
    assert result["field_sources"]["tags"] == "user"
    assert result["field_sources"]["topic"] == "user"


def test_missing_date_defaults_to_today_with_auto_source(monkeypatch):
    """Missing date is filled from local today and marked as auto."""
    monkeypatch.setattr("tools.write_journal.prepare.current_local_date_iso", lambda: "2026-06-29")
    raw = {"title": "Test", "content": "内容", "topic": "life"}

    result = prepare_journal_metadata(raw)

    assert result["date"] == "2026-06-29"
    assert result["field_sources"]["date"] == "auto"


def test_user_date_is_preserved_with_user_source(monkeypatch):
    monkeypatch.setattr("tools.write_journal.prepare.current_local_date_iso", lambda: "2026-06-29")
    raw = {
        "title": "Test",
        "content": "内容",
        "topic": "life",
        "date": "2026-03-14",
    }

    result = prepare_journal_metadata(raw)

    assert result["date"] == "2026-03-14"
    assert result["field_sources"]["date"] == "user"


def test_field_sources_default_location():
    """默认填充的字段应标记为 'auto'"""
    raw = {"title": "Test", "content": "内容", "topic": "life"}
    result = prepare_journal_metadata(raw)
    assert "location" in result["field_sources"]


def test_field_sources_completeness():
    """field_sources 应覆盖主要输出字段"""
    raw = {"title": "Test", "content": "内容", "tags": "a, b", "topic": "work"}
    result = prepare_journal_metadata(raw)

    source_keys = set(result.get("field_sources", {}).keys())
    assert "title" in source_keys
    assert "abstract" in source_keys


def test_field_sources_mixed_sources():
    """测试混合来源：部分用户、部分规则、部分自动"""
    raw = {
        "title": "User Title",
        "content": "Content for testing",
        "topic": "think",
    }
    result = prepare_journal_metadata(raw)

    assert result["field_sources"]["title"] == "user"
    assert result["field_sources"]["abstract"] == "rule"
    assert result["field_sources"]["mood"] == "rule"


def test_default_path_does_not_infer_project_from_keywords():
    """Default no-LLM path leaves semantic project facet to the host Agent."""
    raw = {
        "content": "今天复盘 Life Index facet 进料闭环，也看了 life-index runbook。",
        "topic": "work",
    }

    result = prepare_journal_metadata(raw)

    assert result.get("project", "") == ""
    assert "project" not in result["field_sources"]
    assert result["llm_status"]["state"] == "disabled"


def test_user_project_is_preserved_without_inference():
    """Explicit project supplied by the Agent/caller is preserved."""
    raw = {
        "content": "今天复盘 facet 进料闭环。",
        "topic": "work",
        "project": "Index Pipeline",
    }

    result = prepare_journal_metadata(raw)

    assert result["project"] == "Index Pipeline"
    assert result["field_sources"]["project"] == "user"


@pytest.mark.parametrize(
    (
        "structured_fields",
        "expected_location",
        "expected_weather",
        "default_expected",
        "query_expected",
        "location_source",
        "weather_source",
    ),
    (
        (
            {"location": "  Lagos, Nigeria  ", "weather": "  Structured sun  "},
            "Lagos, Nigeria",
            "Structured sun",
            False,
            False,
            "user",
            "user",
        ),
        (
            {"location": "  Lagos, Nigeria  "},
            "Lagos, Nigeria",
            "Auto weather",
            False,
            True,
            "user",
            "auto",
        ),
        (
            {"weather": "  Structured rain  "},
            "Default City, Country",
            "Structured rain",
            True,
            False,
            "auto",
            "user",
        ),
        (
            {},
            "Default City, Country",
            "Auto weather",
            True,
            True,
            "auto",
            "auto",
        ),
        (
            {"location": "   ", "weather": "\t"},
            "Default City, Country",
            "Auto weather",
            True,
            True,
            "auto",
            "auto",
        ),
    ),
    ids=(
        "structured-location-and-weather",
        "structured-location-missing-weather",
        "missing-location-structured-weather",
        "both-absent",
        "both-whitespace",
    ),
)
def test_enrich_treats_structured_location_weather_as_authoritative(
    structured_fields,
    expected_location,
    expected_weather,
    default_expected,
    query_expected,
    location_source,
    weather_source,
):
    """Prepare uses structured fields only; body marker lines stay ordinary text."""
    body = "地点：Body City\n天气：Body Weather\n今天复盘 facet 进料闭环。"
    raw = {
        "content": body,
        "date": "2026-03-14",
        "topic": "work",
        **structured_fields,
    }

    with (
        patch(
            "tools.write_journal.prepare.get_default_location",
            return_value="Default City, Country",
        ) as mock_default,
        patch(
            "tools.write_journal.prepare.query_weather_for_location",
            return_value="Auto weather",
        ) as mock_weather,
    ):
        result = prepare_journal_metadata(raw)

    assert result["content"] == body
    assert result["location"] == expected_location
    assert result["weather"] == expected_weather
    assert result["field_sources"]["location"] == location_source
    assert result["field_sources"]["weather"] == weather_source
    if default_expected:
        mock_default.assert_called_once_with()
    else:
        mock_default.assert_not_called()
    if query_expected:
        mock_weather.assert_called_once_with(expected_location, "2026-03-14")
    else:
        mock_weather.assert_not_called()


def test_prepare_preserves_multi_component_structured_location_for_output():
    """Lookup normalization must not rewrite the authoritative stored value."""
    body = "地点：Body City\n天气：Body Weather\nNarrative."
    raw = {
        "content": body,
        "date": "2026-03-14",
        "topic": "work",
        "location": "  Lagos, Ikeja, Nigeria  ",
    }

    with (
        patch(
            "tools.write_journal.prepare.normalize_location",
            return_value="Lookup City, Country",
        ) as mock_normalize,
        patch(
            "tools.write_journal.prepare.query_weather_for_location",
            return_value="Auto weather",
        ) as mock_weather,
    ):
        result = prepare_journal_metadata(raw)

    assert result["content"] == body
    assert result["location"] == "Lagos, Ikeja, Nigeria"
    assert result["weather"] == "Auto weather"
    mock_normalize.assert_called_once_with("Lagos, Ikeja, Nigeria")
    mock_weather.assert_called_once_with("Lookup City, Country", "2026-03-14")


def test_prepare_preserves_body_boundary_whitespace_verbatim():
    """Content validation and fallbacks must not mutate durable journal prose."""
    body = " \n地点：Body City\n天气：Body Weather\nNarrative.\n \t"
    raw = {
        "content": body,
        "date": "2026-03-14",
        "topic": "work",
        "location": "Lagos, Nigeria",
        "weather": "Structured sun",
    }

    result = prepare_journal_metadata(raw)

    assert result["content"] == body
    assert result["title"] == "地点：Body City"
    assert result["abstract"] == "地点：Body City 天气：Body Weather Narrative."


def test_legacy_use_llm_parameter_is_ignored():
    """Legacy internal parameter must not re-enable in-tool AI extraction."""
    result = prepare_journal_metadata(
        {"content": "今天复盘 facet 进料闭环。", "topic": "work"},
        use_llm=True,
    )

    assert result.get("project", "") == ""
    assert result["field_sources"]["title"] == "rule"
    assert result["llm_status"]["state"] == "disabled"
