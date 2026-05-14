"""Test field_sources tracking in prepare.py."""

from unittest.mock import patch
from tools.write_journal.prepare import prepare_journal_metadata


def test_field_sources_user_provided_fields():
    """用户提供的字段应标记为 'user'"""
    with (
        patch("tools._optional.llm_extract.is_llm_available", return_value=True),
        patch("tools._optional.llm_extract.extract_metadata_sync") as mock_extract,
    ):
        mock_extract.return_value = {}
        raw = {
            "title": "我的标题",
            "content": "正文",
            "tags": "tag1, tag2",
            "topic": "work",
        }
        result = prepare_journal_metadata(raw, use_llm=True)
        assert result["field_sources"]["title"] == "user"
        assert result["field_sources"]["tags"] == "user"
        assert result["field_sources"]["topic"] == "user"


def test_field_sources_ai_generated_title():
    """AI 生成的字段应标记为 'ai'"""
    with (
        patch("tools._optional.llm_extract.is_llm_available", return_value=True),
        patch("tools._optional.llm_extract.extract_metadata_sync") as mock_extract,
    ):
        mock_extract.return_value = {
            "title": "AI Generated Title",
            "abstract": "AI generated abstract",
        }
        raw = {"content": "这是一段测试内容"}
        result = prepare_journal_metadata(raw, use_llm=True)
        assert result["field_sources"]["title"] == "ai"
        assert result["field_sources"]["abstract"] == "ai"


def test_field_sources_default_location():
    """默认填充的字段应标记为 'auto'"""
    with (
        patch("tools._optional.llm_extract.is_llm_available", return_value=True),
        patch("tools._optional.llm_extract.extract_metadata_sync") as mock_extract,
    ):
        mock_extract.return_value = {}
        raw = {"title": "Test", "content": "内容", "topic": "life"}
        result = prepare_journal_metadata(raw, use_llm=True)
        assert "location" in result["field_sources"]


def test_field_sources_completeness():
    """field_sources 应覆盖主要输出字段"""
    with (
        patch("tools._optional.llm_extract.is_llm_available", return_value=True),
        patch("tools._optional.llm_extract.extract_metadata_sync") as mock_extract,
    ):
        mock_extract.return_value = {}
        raw = {"title": "Test", "content": "内容", "tags": "a, b", "topic": "work"}
        result = prepare_journal_metadata(raw, use_llm=True)

        source_keys = set(result.get("field_sources", {}).keys())
        assert "title" in source_keys
        assert "abstract" in source_keys


def test_field_sources_ai_extraction_with_mock():
    """使用 mock LLM 时，AI 提取的字段应标记为 'ai'"""
    with (
        patch("tools._optional.llm_extract.is_llm_available", return_value=True),
        patch("tools._optional.llm_extract.extract_metadata_sync") as mock_extract,
    ):
        mock_extract.return_value = {
            "title": "AI Generated Title",
            "abstract": "AI generated abstract",
            "mood": ["happy"],
            "tags": ["ai-tag"],
        }

        raw = {"content": "这是一段测试内容"}
        result = prepare_journal_metadata(raw, use_llm=True)

        assert result["field_sources"]["title"] == "ai"
        assert result["field_sources"]["abstract"] == "ai"
        assert result["field_sources"]["mood"] == "ai"
        assert result["field_sources"]["tags"] == "ai"


def test_field_sources_mixed_sources():
    """测试混合来源：部分用户、部分 AI、部分规则"""
    with (
        patch("tools._optional.llm_extract.is_llm_available", return_value=True),
        patch("tools._optional.llm_extract.extract_metadata_sync") as mock_extract,
    ):
        mock_extract.return_value = {
            "mood": ["calm"],
        }

        raw = {
            "title": "User Title",
            "content": "Content for testing",
            "topic": "think",
        }
        result = prepare_journal_metadata(raw, use_llm=True)

        assert result["field_sources"]["title"] == "user"
        assert result["field_sources"]["abstract"] == "rule"
        assert result["field_sources"]["mood"] == "ai"
