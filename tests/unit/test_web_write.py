#!/usr/bin/env python3
"""Tests for Web GUI Write Service — Phase 4a provider foundation."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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


class TestAPIKeyProvider:
    @pytest.mark.asyncio
    async def test_is_available_without_key(self) -> None:
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {}, clear=True):
            provider = APIKeyProvider()
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_with_key(self) -> None:
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}, clear=True):
            provider = APIKeyProvider()
            assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_default_base_url_and_model(self) -> None:
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}, clear=True):
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

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}, clear=True):
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

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}, clear=True):
            provider = APIKeyProvider()

        with patch("web.services.llm_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.extract_metadata("测试内容")

        assert result == {}


class TestGetProvider:
    @pytest.mark.asyncio
    async def test_returns_none_when_all_unavailable(self) -> None:
        from web.services.llm_provider import get_provider

        with patch.dict(os.environ, {}, clear=True):
            assert await get_provider() is None

    @pytest.mark.asyncio
    async def test_returns_api_key_provider_when_configured(self) -> None:
        from web.services.llm_provider import APIKeyProvider, get_provider

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}, clear=True):
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
                        "location": "Lagos, Lagos State, Nigeria",
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
        mock_geocode.assert_called_once_with("Lagos, Lagos State, Nigeria")
        assert result["location"] == "Lagos, Lagos State, Nigeria"
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
        assert result.get("weather", "") == ""

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
