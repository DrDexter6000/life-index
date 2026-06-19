"""Test field_sources tracking in prepare.py."""

from unittest.mock import patch
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


def test_enrich_uses_explicit_body_location_weather_before_defaults():
    """Body-declared location/weather win during metadata preview."""
    raw = {
        "content": "地点：Lagos, Nigeria\n天气：Rain 24C\n今天复盘 facet 进料闭环。",
        "topic": "work",
        "location": "Chongqing, China",
        "weather": "Sunny 30C",
    }

    with (
        patch("tools.write_journal.prepare.get_default_location") as mock_default,
        patch("tools.write_journal.prepare.query_weather_for_location") as mock_weather,
    ):
        result = prepare_journal_metadata(raw)

    mock_default.assert_not_called()
    mock_weather.assert_not_called()
    assert result["location"] == "Lagos, Nigeria"
    assert result["weather"] == "Rain 24C"
    assert result["field_sources"]["location"] == "user"
    assert result["field_sources"]["weather"] == "user"


def test_legacy_use_llm_parameter_is_ignored():
    """Legacy internal parameter must not re-enable in-tool AI extraction."""
    result = prepare_journal_metadata(
        {"content": "今天复盘 facet 进料闭环。", "topic": "work"},
        use_llm=True,
    )

    assert result.get("project", "") == ""
    assert result["field_sources"]["title"] == "rule"
    assert result["llm_status"]["state"] == "disabled"
