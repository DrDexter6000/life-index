#!/usr/bin/env python3
"""Tests for Web GUI Write Service — Phase 4a provider foundation."""

from __future__ import annotations

import importlib
import json
import os
import asyncio
from pathlib import Path
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def _drain_asyncio_tasks() -> AsyncGenerator[None, None]:
    yield
    await asyncio.sleep(0)


class TestLLMProviderABC:
    def test_cannot_instantiate_abc(self) -> None:
        module = importlib.import_module("web.services.llm_provider")
        provider_cls = getattr(module, "LLMProvider")
        with pytest.raises(TypeError):
            provider_cls()

    def test_has_extract_metadata_method(self) -> None:
        from web.services.llm_provider import LLMProvider

        assert hasattr(LLMProvider, "extract_metadata")

    def test_has_is_available_method(self) -> None:
        from web.services.llm_provider import LLMProvider

        assert hasattr(LLMProvider, "is_available")


class TestHostAgentProvider:
    @pytest.mark.asyncio
    async def test_is_available_returns_false(self) -> None:
        from web.services.llm_provider import HostAgentProvider

        provider = HostAgentProvider()
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_extract_metadata_returns_empty(self) -> None:
        from web.services.llm_provider import HostAgentProvider

        provider = HostAgentProvider()
        assert await provider.extract_metadata("任意内容") == {}

    @pytest.mark.asyncio
    async def test_summarize_search_returns_empty(self) -> None:
        from web.services.llm_provider import HostAgentProvider

        provider = HostAgentProvider()
        assert await provider.summarize_search("乐乐", [{"title": "a"}]) == {}


class TestAPIKeyProvider:
    @pytest.mark.asyncio
    async def test_is_available_without_key(self) -> None:
        from web.services.llm_provider import APIKeyProvider

        with patch(
            "web.services.llm_provider.get_llm_config",
            return_value={
                "api_key": "",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
        ):
            provider = APIKeyProvider()
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_with_key(self) -> None:
        from web.services.llm_provider import APIKeyProvider

        with patch(
            "web.services.llm_provider.get_llm_config",
            return_value={
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
        ):
            provider = APIKeyProvider()
            assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_default_base_url_and_model(self) -> None:
        from web.services.llm_provider import APIKeyProvider

        with patch(
            "web.services.llm_provider.get_llm_config",
            return_value={
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
        ):
            provider = APIKeyProvider()

        assert provider.base_url == "https://api.openai.com/v1"
        assert provider.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_extract_metadata_success(self) -> None:
        from web.services.llm_provider import APIKeyProvider

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "title": "测试标题",
                                "mood": ["专注"],
                                "tags": ["测试"],
                                "topic": ["work", "invalid_topic"],
                                "abstract": "测试摘要",
                                "people": [],
                            }
                        )
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch(
            "web.services.llm_provider.get_llm_config",
            return_value={
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
        ):
            provider = APIKeyProvider()

        with patch("web.services.llm_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.extract_metadata("测试日志内容")

        assert result["title"] == "测试标题"
        assert result["topic"] == ["work"]
        assert result["abstract"] == "测试摘要"

    @pytest.mark.asyncio
    async def test_extract_metadata_invalid_json_returns_empty(self) -> None:
        from web.services.llm_provider import APIKeyProvider

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "not json"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch(
            "web.services.llm_provider.get_llm_config",
            return_value={
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
        ):
            provider = APIKeyProvider()

        with patch("web.services.llm_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.extract_metadata("测试内容")

        assert result == {}

    def test_extraction_prompt_includes_topic_table(self) -> None:
        """Regression: prompt must include Topic classification table so LLM knows valid values."""
        from web.services.llm_provider import EXTRACTION_SYSTEM_PROMPT

        prompt = str(EXTRACTION_SYSTEM_PROMPT)
        # Must mention the 7 valid topic values
        for topic in ("work", "learn", "health", "relation", "think", "create", "life"):
            assert topic in prompt, (
                f"Topic '{topic}' missing from EXTRACTION_SYSTEM_PROMPT"
            )
        # Must mention topic as array field
        assert "topic" in prompt
        # Must mention mood extraction limit
        assert "mood" in prompt
        # Must mention abstract length constraint
        assert "abstract" in prompt

    @pytest.mark.asyncio
    async def test_summarize_search_success(self) -> None:
        from web.services.llm_provider import APIKeyProvider

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "关于乐乐，你最近在回顾亲子时光。",
                                "key_entries": [
                                    {
                                        "title": "想念乐乐",
                                        "date": "2026-03-07",
                                        "reason": "翻看旧照片触发想念",
                                    }
                                ],
                                "time_span": "2026年3月",
                            }
                        )
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch(
            "web.services.llm_provider.get_llm_config",
            return_value={
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
        ):
            provider = APIKeyProvider()

        with patch("web.services.llm_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.summarize_search(
                "乐乐",
                [
                    {
                        "title": "想念乐乐",
                        "date": "2026-03-07",
                        "abstract": "翻看旧照片",
                        "highlight": "乐乐小时候照片",
                    }
                ],
            )

        assert result["summary"] == "关于乐乐，你最近在回顾亲子时光。"
        assert result["key_entries"][0]["title"] == "想念乐乐"
        assert result["time_span"] == "2026年3月"

    @pytest.mark.asyncio
    async def test_summarize_search_timeout_returns_empty(self) -> None:
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}, clear=True):
            provider = APIKeyProvider()

        with patch("web.services.llm_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
            mock_client_cls.return_value = mock_client

            result = await provider.summarize_search(
                "乐乐",
                [{"title": "想念乐乐", "date": "2026-03-07"}],
            )

        assert result == {}


class TestGetProvider:
    @pytest.mark.asyncio
    async def test_returns_none_when_all_unavailable(self) -> None:
        from web.services.llm_provider import get_provider

        with patch(
            "web.services.llm_provider.get_llm_config",
            return_value={
                "api_key": "",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
        ):
            assert await get_provider() is None

    @pytest.mark.asyncio
    async def test_returns_api_key_provider_when_configured(self) -> None:
        from web.services.llm_provider import APIKeyProvider, get_provider

        with patch(
            "web.services.llm_provider.get_llm_config",
            return_value={
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
        ):
            provider = await get_provider()

        assert isinstance(provider, APIKeyProvider)


class TestPrepareJournalData:
    @pytest.mark.asyncio
    async def test_requires_content(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        with pytest.raises(ValueError, match="content"):
            await prepare_journal_data({}, provider=None)

    @pytest.mark.asyncio
    async def test_user_input_wins_over_llm(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        provider = AsyncMock()
        provider.extract_metadata.return_value = {
            "title": "LLM标题",
            "topic": ["learn"],
            "abstract": "LLM摘要",
            "mood": ["专注"],
        }

        result = await prepare_journal_data(
            {
                "content": "这是正文内容",
                "title": "用户标题",
                "topic": ["work"],
                "date": "2026-03-22",
            },
            provider=provider,
        )

        assert result["title"] == "用户标题"
        assert result["topic"] == ["work"]
        assert result["abstract"] == "LLM摘要"
        assert result["mood"] == ["专注"]

    @pytest.mark.asyncio
    async def test_fallback_without_llm_requires_topic(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        with pytest.raises(ValueError, match="topic"):
            await prepare_journal_data(
                {"content": "今天写了一点东西", "date": "2026-03-22"}, provider=None
            )

    @pytest.mark.asyncio
    async def test_fallback_without_llm_generates_title_and_abstract(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        result = await prepare_journal_data(
            {
                "content": "今天写了一点东西，用来测试摘要和标题自动回填。",
                "topic": ["life"],
                "date": "2026-03-22",
            },
            provider=None,
        )

        assert result["title"]
        assert result["abstract"]
        assert result["topic"] == ["life"]

    @pytest.mark.asyncio
    async def test_fallback_title_uses_first_non_empty_line(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        result = await prepare_journal_data(
            {
                "content": "\n\n第一行标题\n第二行正文",
                "topic": ["life"],
                "date": "2026-03-22",
            },
            provider=None,
        )

        assert result["title"] == "第一行标题"

    @pytest.mark.asyncio
    async def test_fallback_title_uses_empty_title_default(self) -> None:
        module = importlib.import_module("web.services.write")
        fallback_title = getattr(module, "_fallback_title")

        assert fallback_title("") == "无标题日志"

    @pytest.mark.asyncio
    async def test_fallback_abstract_skips_markdown_heading_lines(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        result = await prepare_journal_data(
            {
                "content": "# 标题\n\n## 小标题\n\n正文第一段\n正文第二段",
                "topic": ["life"],
                "date": "2026-03-22",
            },
            provider=None,
        )

        assert result["abstract"].startswith("正文第一段 正文第二段")

    @pytest.mark.asyncio
    async def test_provider_failure_falls_back_to_required_metadata(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        provider = AsyncMock()
        provider.extract_metadata.side_effect = RuntimeError("provider failed")

        result = await prepare_journal_data(
            {
                "content": "第一行标题\n\n正文内容",
                "topic": ["life"],
                "date": "2026-03-22",
            },
            provider=provider,
        )

        assert result["title"] == "第一行标题"
        assert result["abstract"]
        assert result["mood"] == []
        assert result["tags"] == []
        assert result["people"] == []
        assert result["topic"] == ["life"]
        assert result["llm_status"]["state"] == "failed"
        assert "provider failed" in result["llm_status"]["message"]

    @pytest.mark.asyncio
    async def test_provider_unavailable_marks_llm_status_unavailable(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        result = await prepare_journal_data(
            {
                "content": "今天写了一点东西，用来测试摘要和标题自动回填。",
                "topic": ["life"],
                "date": "2026-03-22",
            },
            provider=None,
        )

        assert result["llm_status"]["state"] == "unavailable"
        assert "未配置" in result["llm_status"]["message"]

    @pytest.mark.asyncio
    async def test_provider_empty_extraction_marks_llm_status_fallback(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        provider = AsyncMock()
        provider.extract_metadata.return_value = {}

        result = await prepare_journal_data(
            {
                "content": "第一行标题\n\n正文内容",
                "topic": ["life"],
                "date": "2026-03-22",
            },
            provider=provider,
        )

        assert result["llm_status"]["state"] == "fallback"
        assert "未返回可用结果" in result["llm_status"]["message"]

    @pytest.mark.asyncio
    async def test_uses_default_location_when_missing(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        with patch(
            "web.services.write.get_default_location", return_value="Lagos, Nigeria"
        ):
            with patch("web.services.write.geocode_location") as mock_geocode:
                with patch("web.services.write.query_weather") as mock_weather:
                    mock_geocode.return_value = {
                        "latitude": 6.5244,
                        "longitude": 3.3792,
                    }
                    mock_weather.return_value = {
                        "success": True,
                        "weather": {"simple": "晴天"},
                    }

                    result = await prepare_journal_data(
                        {
                            "content": "今天状态不错",
                            "topic": ["life"],
                            "date": "2026-03-22",
                        },
                        provider=None,
                    )

        assert result["location"] == "Lagos, Nigeria"
        assert result["weather"] == "晴天"

    @pytest.mark.asyncio
    async def test_coordinate_location_is_reverse_geocoded_before_weather_lookup(
        self,
    ) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        with patch(
            "web.services.write.reverse_geocode_coordinates"
        ) as mock_reverse_geocode:
            with patch("web.services.write.geocode_location") as mock_geocode:
                with patch("web.services.write.query_weather") as mock_weather:
                    mock_reverse_geocode.return_value = {
                        "success": True,
                        "location": "Lagos, Nigeria",
                    }
                    mock_geocode.return_value = {
                        "latitude": 6.5244,
                        "longitude": 3.3792,
                    }
                    mock_weather.return_value = {
                        "success": True,
                        "weather": {"simple": "晴天"},
                    }

                    result = await prepare_journal_data(
                        {
                            "content": "今天状态不错",
                            "topic": ["life"],
                            "date": "2026-03-22",
                            "location": "6.5244, 3.3792",
                        },
                        provider=None,
                    )

        mock_reverse_geocode.assert_called_once_with(6.5244, 3.3792)
        mock_geocode.assert_called_once_with("Lagos, Nigeria")
        assert result["location"] == "Lagos, Nigeria"
        assert result["weather"] == "晴天"

    @pytest.mark.asyncio
    async def test_does_not_override_user_weather(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        with patch("web.services.write.geocode_location") as mock_geocode:
            result = await prepare_journal_data(
                {
                    "content": "今天状态不错",
                    "topic": ["life"],
                    "date": "2026-03-22",
                    "location": "Lagos, Nigeria",
                    "weather": "用户手填天气",
                },
                provider=None,
            )

        mock_geocode.assert_not_called()
        assert result["weather"] == "用户手填天气"

    @pytest.mark.asyncio
    async def test_weather_failure_is_non_blocking(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        with patch("web.services.write.geocode_location") as mock_geocode:
            with patch("web.services.write.query_weather") as mock_weather:
                mock_geocode.return_value = {
                    "latitude": 6.5244,
                    "longitude": 3.3792,
                }
                mock_weather.return_value = {
                    "success": False,
                    "error": "weather failed",
                }

                result = await prepare_journal_data(
                    {
                        "content": "今天状态不错",
                        "topic": ["life"],
                        "date": "2026-03-22",
                        "location": "Lagos, Nigeria",
                    },
                    provider=None,
                )

        assert result["location"] == "Lagos, Nigeria"
        assert "weather" not in result

    @pytest.mark.asyncio
    async def test_weather_lookup_uses_date_portion_for_datetime_input(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        with patch("web.services.write.geocode_location") as mock_geocode:
            with patch("web.services.write.query_weather") as mock_weather:
                mock_geocode.return_value = {
                    "latitude": 6.5244,
                    "longitude": 3.3792,
                }
                mock_weather.return_value = {
                    "success": True,
                    "weather": {"simple": "晴天"},
                }

                result = await prepare_journal_data(
                    {
                        "content": "今天状态不错",
                        "topic": ["life"],
                        "date": "2026-03-22T09:15:00",
                        "location": "Lagos, Nigeria",
                    },
                    provider=None,
                )

        mock_weather.assert_called_once_with(6.5244, 3.3792, "2026-03-22")
        assert result["weather"] == "晴天"

    @pytest.mark.asyncio
    async def test_preserves_attachment_fields(self) -> None:
        module = importlib.import_module("web.services.write")
        prepare_journal_data = getattr(module, "prepare_journal_data")

        result = await prepare_journal_data(
            {
                "content": "今天状态不错",
                "topic": ["life"],
                "date": "2026-03-22",
                "attachments": ["C:/temp/file1.png"],
                "attachment_urls": ["https://example.com/file2.png"],
            },
            provider=None,
        )

        assert result["attachments"] == [
            {"source_path": "C:/temp/file1.png", "description": ""}
        ]
        assert result["attachment_urls"] == ["https://example.com/file2.png"]


class TestWriteJournalWeb:
    @pytest.mark.asyncio
    async def test_write_journal_web_uses_to_thread_and_normalizes_path(self) -> None:
        module = importlib.import_module("web.services.write")
        write_journal_web = getattr(module, "write_journal_web")

        mock_result = {
            "success": True,
            "journal_path": "C:/Users/test/Documents/Life-Index/Journals/2026/03/test.md",
            "updated_indices": [],
            "index_status": "complete",
            "side_effects_status": "complete",
            "attachments_processed": [],
            "location_used": "Lagos, Nigeria",
            "weather_used": "晴天",
            "needs_confirmation": False,
            "confirmation_message": "",
            "metrics": {"total_ms": 12.5},
            "error": None,
        }

        with patch(
            "web.services.write.JOURNALS_DIR",
            Path("C:/Users/test/Documents/Life-Index/Journals"),
        ):
            with patch(
                "web.services.write.USER_DATA_DIR",
                Path("C:/Users/test/Documents/Life-Index"),
            ):
                with patch(
                    "web.services.write.asyncio.to_thread", new_callable=AsyncMock
                ) as mock_to_thread:
                    mock_to_thread.return_value = mock_result

                    result = await write_journal_web(
                        {"content": "正文", "topic": ["life"], "date": "2026-03-22"}
                    )

        mock_to_thread.assert_awaited_once()
        assert result["journal_route_path"] == "2026/03/test.md"
        assert result["path"] == mock_result["journal_path"]
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_write_journal_web_keeps_failure_shape(self) -> None:
        module = importlib.import_module("web.services.write")
        write_journal_web = getattr(module, "write_journal_web")

        failure = {
            "success": False,
            "journal_path": None,
            "error": "写入失败",
        }

        with patch(
            "web.services.write.asyncio.to_thread", new_callable=AsyncMock
        ) as mock_to_thread:
            mock_to_thread.return_value = failure

            result = await write_journal_web(
                {"content": "正文", "topic": ["life"], "date": "2026-03-22"}
            )

        assert result["success"] is False
        assert result["error"] == "写入失败"


class TestAttachmentBridgeHelpers:
    def test_build_attachment_records_from_local_paths(self) -> None:
        module = importlib.import_module("web.services.write")
        build_attachment_payloads = getattr(module, "build_attachment_payloads")

        result = build_attachment_payloads(
            [
                "C:/temp/a.png",
                {"source_path": "C:/temp/b.pdf", "description": "pdf"},
            ]
        )

        assert result == [
            {"source_path": "C:/temp/a.png", "description": ""},
            {"source_path": "C:/temp/b.pdf", "description": "pdf"},
        ]

    def test_build_attachment_records_skips_entries_without_source_path(self) -> None:
        module = importlib.import_module("web.services.write")
        build_attachment_payloads = getattr(module, "build_attachment_payloads")

        result = build_attachment_payloads(
            [
                {"filename": "file.txt"},
                {"source_path": "", "description": "empty"},
                {"source_path": "C:/temp/ok.txt", "description": "ok"},
            ]
        )

        assert result == [{"source_path": "C:/temp/ok.txt", "description": "ok"}]

    def test_build_attachment_records_preserves_source_url_entries(self) -> None:
        module = importlib.import_module("web.services.write")
        build_attachment_payloads = getattr(module, "build_attachment_payloads")

        result = build_attachment_payloads(
            [
                {
                    "source_url": "https://example.com/photo.jpg",
                    "description": "远程图片",
                    "content_type": "image/jpeg",
                    "size": 123,
                }
            ]
        )

        assert result == [
            {
                "source_url": "https://example.com/photo.jpg",
                "description": "远程图片",
                "content_type": "image/jpeg",
                "size": 123,
            }
        ]

    def test_download_attachment_from_url_returns_metadata_fields(self) -> None:
        module = importlib.import_module("web.services.write")
        download_attachment_from_url = getattr(module, "download_attachment_from_url")

        fake_result = {
            "success": True,
            "path": "C:/tmp/photo.jpg",
            "filename": "photo.jpg",
            "content_type": "image/jpeg",
            "size": 123,
        }

        with patch(
            "web.services.write.download_url", new=AsyncMock(return_value=fake_result)
        ):
            result = download_attachment_from_url(
                "https://example.com/photo.jpg", date_str="2026-03-10"
            )

        assert result == {
            "source_url": "https://example.com/photo.jpg",
            "source_path": "C:/tmp/photo.jpg",
            "description": "https://example.com/photo.jpg",
            "content_type": "image/jpeg",
            "size": 123,
        }

    def test_download_attachment_from_url_saves_temp_file(self, tmp_path: Path) -> None:
        module = importlib.import_module("web.services.write")
        download_attachment_from_url = getattr(module, "download_attachment_from_url")

        with patch("web.services.write.download_url") as mock_download:
            mock_download.return_value = {
                "success": True,
                "path": str(tmp_path / "image.png"),
                "filename": "image.png",
                "size": 9,
                "content_type": "image/png",
            }
            (tmp_path / "image.png").write_bytes(b"png-bytes")
            result = download_attachment_from_url(
                "https://example.com/image.png",
                temp_dir=tmp_path,
            )

        assert result["source_path"].endswith("image.png")
        assert Path(result["source_path"]).is_file()

    def test_download_attachment_rejects_non_file_content_type(
        self, tmp_path: Path
    ) -> None:
        module = importlib.import_module("web.services.write")
        download_attachment_from_url = getattr(module, "download_attachment_from_url")

        with patch("web.services.write.download_url") as mock_download:
            mock_download.return_value = {
                "success": False,
                "url": "https://example.com/index.html",
                "error": "Content-Type text/html rejected",
                "error_code": "E0702",
            }
            with pytest.raises(ValueError, match="Content-Type"):
                download_attachment_from_url(
                    "https://example.com/index.html",
                    temp_dir=tmp_path,
                )

    def test_cleanup_staged_files_deletes_existing_paths(self, tmp_path: Path) -> None:
        module = importlib.import_module("web.services.write")
        cleanup_staged_files = getattr(module, "cleanup_staged_files")

        staged_file = tmp_path / "staged.txt"
        staged_file.write_text("hello", encoding="utf-8")

        cleanup_staged_files([{"source_path": str(staged_file), "description": ""}])

        assert not staged_file.exists()


class TestWritingTemplates:
    def test_templates_file_exists(self) -> None:
        templates_path = Path("web/templates/writing_templates.json")
        assert templates_path.exists()

    def test_templates_have_expected_schema_and_count(self) -> None:
        templates_path = Path("web/templates/writing_templates.json")
        templates = json.loads(templates_path.read_text(encoding="utf-8"))

        assert len(templates) == 7
        expected_ids = {
            "blank",
            "letter_to_tuantuan",
            "daily_gratitude",
            "work_log",
            "study_notes",
            "book_review",
            "health_checkin",
        }
        assert {item["id"] for item in templates} == expected_ids

        for item in templates:
            assert set(item.keys()) == {"id", "name", "topic", "content", "tags"}
            assert isinstance(item["topic"], list)
            assert isinstance(item["tags"], list)
            assert isinstance(item["content"], str)

    def test_blank_template_is_default_empty_prefill(self) -> None:
        templates_path = Path("web/templates/writing_templates.json")
        templates = json.loads(templates_path.read_text(encoding="utf-8"))

        blank = next(item for item in templates if item["id"] == "blank")
        assert blank["name"] == "空白日志"
        assert blank["topic"] == []
        assert blank["content"] == ""
        assert blank["tags"] == []


class TestWriteRoutePhase3:
    @patch("web.routes.write.get_provider", new_callable=AsyncMock)
    def test_write_page_shows_llm_ready_status_when_provider_available(
        self, mock_get_provider: AsyncMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_get_provider.return_value = AsyncMock()

        client = TestClient(create_app())
        response = client.get("/write")

        assert response.status_code == 200
        # AI status is now detected client-side via JS /api/llm-status;
        # server-rendered HTML shows initial detection text
        assert "正在检测 AI 服务" in response.text
        assert "ai-status-text" in response.text

    @patch("web.routes.write.write_journal_web", new_callable=AsyncMock)
    @patch("web.routes.write.prepare_journal_data", new_callable=AsyncMock)
    @patch("web.routes.write.get_provider", new_callable=AsyncMock)
    def test_submit_write_returns_confirmation_page_instead_of_redirect(
        self,
        mock_get_provider: AsyncMock,
        mock_prepare_journal_data: AsyncMock,
        mock_write_journal_web: AsyncMock,
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_get_provider.return_value = AsyncMock()
        mock_prepare_journal_data.return_value = {
            "title": "测试标题",
            "content": "测试正文",
            "date": "2026-03-24T09:15:00",
            "topic": ["life"],
            "mood": ["平静"],
            "tags": ["测试"],
            "people": [],
            "location": "Lagos, Nigeria",
            "weather": "晴天",
            "project": "",
            "abstract": "测试摘要",
            "attachments": [],
            "attachment_urls": [],
        }
        mock_write_journal_web.return_value = {
            "success": True,
            "journal_route_path": "2026/03/test.md",
            "path": "C:/fake/Journals/2026/03/test.md",
            "journal_path": "C:/fake/Journals/2026/03/test.md",
            "needs_confirmation": False,
            "confirmation_message": "",
        }

        client = TestClient(create_app())
        get_response = client.get("/write")
        csrf_token = get_response.cookies.get("csrf_token")
        assert csrf_token

        response = client.post(
            "/write",
            data={
                "csrf_token": csrf_token,
                "title": "",
                "content": "测试正文",
                "date": "2026-03-24T09:15:00",
                "topic": "life",
                "mood": "",
                "tags": "",
                "people": "",
                "location": "",
                "weather": "",
                "project": "",
                "template": "blank",
            },
            follow_redirects=False,
        )

        assert response.status_code == 200
        assert "确认完成" in response.text
        assert "测试标题" in response.text
        assert "/journal/2026/03/test.md/edit" in response.text

    def test_write_confirm_template_exists(self) -> None:
        template_path = Path("web/templates/write_confirm.html")
        assert template_path.exists()

    def test_write_confirm_template_exposes_location_confirmation_and_project(
        self,
    ) -> None:
        source = Path("web/templates/write_confirm.html").read_text(encoding="utf-8")

        assert "location_needs_confirm" in source
        assert "location_confirm_message" in source
        assert "去修正地点" in source
        assert "'project': '项目'" in source
