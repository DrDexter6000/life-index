#!/usr/bin/env python3
"""Tests for Web GUI Journal View + Search — Task 9 first."""

from __future__ import annotations

from pathlib import Path
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestJournalServicePathSafety:
    def test_path_traversal_rejected(self) -> None:
        import importlib

        get_journal = importlib.import_module("web.services.journal").get_journal

        with pytest.raises(ValueError, match="[Pp]ath"):
            get_journal("../../etc/passwd")

    def test_dotdot_in_middle_rejected(self) -> None:
        import importlib

        get_journal = importlib.import_module("web.services.journal").get_journal

        with pytest.raises(ValueError, match="[Pp]ath"):
            get_journal("2026/03/../../../../../../etc/shadow")


class TestJournalServiceParsing:
    @patch("web.services.journal.parse_journal_file")
    def test_returns_metadata_and_html(self, mock_parse: MagicMock) -> None:
        mock_parse.return_value = {
            "title": "测试日志",
            "date": "2026-03-07T14:30:00",
            "mood": ["专注"],
            "tags": ["python"],
            "topic": ["work"],
            "people": [],
            "location": "Lagos, Nigeria",
            "weather": "Sunny 28°C",
            "abstract": "测试摘要",
            "_title": "测试日志",
            "_abstract": "测试摘要",
            "_body": "# 测试日志\n\n这是正文内容。\n\n```python\nprint('hello')\n```\n",
            "_file": "C:/fake/journals/2026/03/life-index_2026-03-07_001.md",
        }

        with patch("web.services.journal.JOURNALS_DIR", Path("C:/fake/journals")):
            with patch.object(Path, "exists", return_value=True):
                result = __import__(
                    "web.services.journal", fromlist=["get_journal"]
                ).get_journal("2026/03/life-index_2026-03-07_001.md")

        assert "metadata" in result
        assert "html_content" in result
        assert result["metadata"]["title"] == "测试日志"
        assert "<h1>" in result["html_content"] or "测试日志" in result["html_content"]
        assert "<code" in result["html_content"] or "print" in result["html_content"]

    @patch("web.services.journal.parse_journal_file")
    def test_attachment_rewriting(self, mock_parse: MagicMock) -> None:
        mock_parse.return_value = {
            "title": "附件测试",
            "_title": "附件测试",
            "_abstract": "附件摘要",
            "_body": "[查看附件](../../../attachments/image.png)",
            "_file": "C:/fake/journals/2026/03/a.md",
            "mood": [],
            "tags": [],
            "topic": ["work"],
            "people": [],
        }

        with patch("web.services.journal.JOURNALS_DIR", Path("C:/fake/journals")):
            with patch.object(Path, "exists", return_value=True):
                result = __import__(
                    "web.services.journal", fromlist=["get_journal"]
                ).get_journal("2026/03/a.md")

        assert "/attachments/" in result["html_content"]

    @patch("web.services.journal.parse_journal_file")
    def test_attachment_urls_encode_hash_characters(
        self, mock_parse: MagicMock
    ) -> None:
        mock_parse.return_value = {
            "title": "附件测试",
            "_title": "附件测试",
            "_abstract": "附件摘要",
            "_body": "[查看附件](../../../attachments/2026/02/file_#2.pptx)",
            "_file": "C:/fake/journals/2026/02/a.md",
            "mood": [],
            "tags": [],
            "topic": ["work"],
            "people": [],
            "attachments": ["../../../attachments/2026/02/file_#2.pptx"],
        }

        with patch("web.services.journal.JOURNALS_DIR", Path("C:/fake/journals")):
            with patch.object(Path, "exists", return_value=True):
                result = __import__(
                    "web.services.journal", fromlist=["get_journal"]
                ).get_journal("2026/02/a.md")

        assert "/attachments/2026/02/file_%232.pptx" in result["html_content"]

    @patch("web.services.journal.parse_journal_file")
    def test_attachment_url_rewriting_preserves_markdown_headings(
        self, mock_parse: MagicMock
    ) -> None:
        mock_parse.return_value = {
            "title": "附件标题保留测试",
            "_title": "附件标题保留测试",
            "_abstract": "附件摘要",
            "_body": "## Attachments\n\n[查看附件](../../../attachments/2026/02/file_#2.pptx)",
            "_file": "C:/fake/journals/2026/02/a.md",
            "mood": [],
            "tags": [],
            "topic": ["work"],
            "people": [],
        }

        with patch("web.services.journal.JOURNALS_DIR", Path("C:/fake/journals")):
            with patch.object(Path, "exists", return_value=True):
                result = __import__(
                    "web.services.journal", fromlist=["get_journal"]
                ).get_journal("2026/02/a.md")

        assert "<h2>Attachments</h2>" in result["html_content"]
        assert "%23%23 Attachments" not in result["html_content"]
        assert "/attachments/2026/02/file_%232.pptx" in result["html_content"]

    @patch("web.services.journal.parse_journal_file")
    def test_journal_service_exposes_links_and_attachment_metadata(
        self, mock_parse: MagicMock
    ) -> None:
        mock_parse.return_value = {
            "title": "链接附件测试",
            "_title": "链接附件测试",
            "_abstract": "摘要",
            "_body": "正文",
            "_file": "C:/fake/journals/2026/02/a.md",
            "mood": [],
            "tags": [],
            "topic": ["work"],
            "people": [],
            "links": ["https://example.com/a"],
            "attachments": ["../../../attachments/2026/02/file.pptx"],
        }

        with patch("web.services.journal.JOURNALS_DIR", Path("C:/fake/journals")):
            with patch.object(Path, "exists", return_value=True):
                result = __import__(
                    "web.services.journal", fromlist=["get_journal"]
                ).get_journal("2026/02/a.md")

        assert result["metadata"]["links"] == ["https://example.com/a"]
        assert result["attachments"]

    @patch("web.services.journal.parse_journal_file")
    def test_journal_service_supports_structured_attachment_objects(
        self, mock_parse: MagicMock
    ) -> None:
        mock_parse.return_value = {
            "title": "结构化附件测试",
            "_title": "结构化附件测试",
            "_abstract": "摘要",
            "_body": "正文",
            "_file": "C:/fake/journals/2026/03/a.md",
            "mood": [],
            "tags": [],
            "topic": ["work"],
            "people": [],
            "attachments": [
                {
                    "filename": "file.pptx",
                    "rel_path": "../../../attachments/2026/03/file.pptx",
                    "description": "演示文稿",
                    "source_url": "https://example.com/file.pptx",
                    "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    "size": 2048,
                }
            ],
        }

        with patch("web.services.journal.JOURNALS_DIR", Path("C:/fake/journals")):
            with patch.object(Path, "exists", return_value=True):
                result = __import__(
                    "web.services.journal", fromlist=["get_journal"]
                ).get_journal("2026/03/a.md")

        assert result["attachments"] == [
            {
                "raw_path": "../../../attachments/2026/03/file.pptx",
                "href": "/attachments/2026/03/file.pptx",
                "name": "file.pptx",
                "kind": "file",
                "is_previewable": False,
                "source_url": "https://example.com/file.pptx",
                "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "size": 2048,
            }
        ]

    @patch("web.services.journal.parse_journal_file")
    def test_journal_service_classifies_attachment_types(
        self, mock_parse: MagicMock
    ) -> None:
        mock_parse.return_value = {
            "title": "附件分类测试",
            "_title": "附件分类测试",
            "_abstract": "摘要",
            "_body": "正文",
            "_file": "C:/fake/journals/2026/03/a.md",
            "mood": [],
            "tags": [],
            "topic": ["work"],
            "people": [],
            "attachments": [
                "../../../attachments/2026/03/photo.jpg",
                "../../../attachments/2026/03/clip.mp4",
                "../../../attachments/2026/03/report.pdf",
            ],
        }

        with patch("web.services.journal.JOURNALS_DIR", Path("C:/fake/journals")):
            with patch.object(Path, "exists", return_value=True):
                result = __import__(
                    "web.services.journal", fromlist=["get_journal"]
                ).get_journal("2026/03/a.md")

        assert result["attachments"] == [
            {
                "raw_path": "../../../attachments/2026/03/photo.jpg",
                "href": "/attachments/2026/03/photo.jpg",
                "name": "photo.jpg",
                "kind": "image",
                "is_previewable": True,
                "source_url": None,
                "content_type": "image/jpeg",
                "size": None,
            },
            {
                "raw_path": "../../../attachments/2026/03/clip.mp4",
                "href": "/attachments/2026/03/clip.mp4",
                "name": "clip.mp4",
                "kind": "video",
                "is_previewable": True,
                "source_url": None,
                "content_type": "video/mp4",
                "size": None,
            },
            {
                "raw_path": "../../../attachments/2026/03/report.pdf",
                "href": "/attachments/2026/03/report.pdf",
                "name": "report.pdf",
                "kind": "file",
                "is_previewable": False,
                "source_url": None,
                "content_type": "application/pdf",
                "size": None,
            },
        ]


class TestJournalRoute:
    @patch("web.routes.journal.get_journal")
    def test_journal_route_renders(self, mock_get_journal: MagicMock) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_get_journal.return_value = {
            "metadata": {
                "title": "测试日志",
                "date": "2026-03-07T14:30:00",
                "mood": ["专注"],
                "tags": ["python"],
                "topic": ["work"],
                "people": [],
                "location": "Lagos, Nigeria",
                "weather": "Sunny 28°C",
            },
            "html_content": "<h1>测试日志</h1><p>正文</p>",
            "attachments": [],
            "journal_route_path": "2026/03/test.md",
        }

        client = TestClient(create_app())
        response = client.get("/journal/2026/03/test.md")

        assert response.status_code == 200
        assert "测试日志" in response.text
        assert "/journal/2026/03/test.md/edit" in response.text

    @patch("web.routes.journal.get_journal")
    def test_journal_route_does_not_render_removed_runtime_operator_panel(
        self, mock_get_journal: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_get_journal.return_value = {
            "metadata": {"title": "测试日志"},
            "html_content": "<p>正文</p>",
            "attachments": [],
            "journal_route_path": "2026/03/test.md",
        }

        client = TestClient(create_app())
        response = client.get("/journal/2026/03/test.md")

        assert response.status_code == 200
        assert "当前日志详情页正在读取以下目录" not in response.text
        assert "如内容或附件异常，先核对当前数据源与 Journals 目录" not in response.text

    @patch("web.routes.journal.get_journal")
    def test_journal_route_renders_warning_banner(
        self, mock_get_journal: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_get_journal.return_value = {
            "metadata": {
                "title": "测试日志",
                "date": "2026-03-07T14:30:00",
                "mood": [],
                "tags": [],
                "topic": ["work"],
                "people": [],
            },
            "html_content": "<p>正文</p>",
            "attachments": [],
            "journal_route_path": "2026/03/test.md",
        }

        client = TestClient(create_app())
        response = client.get(
            "/journal/2026/03/test.md?warning=%E9%99%84%E4%BB%B6%E4%B8%8B%E8%BD%BD%E5%A4%B1%E8%B4%A5"
        )

        assert response.status_code == 200
        assert "附件下载失败" in response.text

    @patch("web.routes.journal.get_journal")
    def test_journal_route_does_not_render_removed_readonly_simulation_notice(
        self, mock_get_journal: MagicMock, monkeypatch, tmp_path
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path / "sandbox"))
        monkeypatch.setenv("LIFE_INDEX_READONLY_SIMULATION", "1")
        mock_get_journal.return_value = {
            "metadata": {"title": "测试日志"},
            "html_content": "<p>正文</p>",
            "attachments": [],
            "journal_route_path": "2026/03/test.md",
        }

        client = TestClient(create_app())
        response = client.get("/journal/2026/03/test.md")

        assert response.status_code == 200
        assert "只读仿真" not in response.text
        assert "当前页面内容来自临时副本，可安全用于验收和排查" not in response.text

    @patch(
        "web.routes.journal.get_journal",
        side_effect=ValueError("Path traversal detected"),
    )
    def test_journal_route_traversal_returns_404(
        self, mock_get_journal: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        client = TestClient(create_app())
        response = client.get("/journal/../../etc/passwd")

        assert response.status_code == 404


class TestJournalTemplate:
    def test_journal_template_exists(self) -> None:
        from web.config import TEMPLATES_DIR

        assert (TEMPLATES_DIR / "journal.html").is_file()

    def test_journal_template_extends_base(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "journal.html").read_text(encoding="utf-8")
        assert '{% extends "base.html" %}' in source
        assert "{% block content %}" in source
        assert "warning" in source
        assert "sm:p-6" in source

    def test_journal_template_has_type_aware_attachment_sections(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "journal.html").read_text(encoding="utf-8")
        assert "图片附件" in source
        assert "视频附件" in source
        assert "文件附件" in source
        assert "attachment.kind == 'image'" in source
        assert "attachment.kind == 'video'" in source
        assert "min-h-[44px]" in source
        assert "divide-y divide-gray-100" in source
        assert "tracking-tight" in source

    def test_journal_template_renders_links_and_attachments_sections(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "journal.html").read_text(encoding="utf-8")
        assert "相关链接" in source
        assert "附件" in source
        assert "journal.metadata.links" in source
        assert "journal.attachments" in source


class TestEditRoute:
    def test_to_gui_datetime_value_accepts_offset_datetime(self) -> None:
        from web.services.date_adapter import to_gui_datetime_value

        assert (
            to_gui_datetime_value("2026-03-20T21:46:00+01:00") == "2026-03-20T21:46:00"
        )

    @patch("web.routes.edit.get_journal")
    @patch("web.routes.edit.get_provider")
    def test_edit_page_prefills_browser_compatible_datetime_local(
        self, mock_get_provider: MagicMock, mock_get_journal: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_get_provider.return_value = None
        mock_get_journal.return_value = {
            "metadata": {
                "title": "测试日志",
                "date": "2026-03-20T21:46:00+01:00",
                "topic": ["work"],
                "mood": ["专注"],
                "tags": ["python"],
                "people": [],
                "location": "Lagos, Nigeria",
                "weather": "Sunny 28°C",
            },
            "raw_body": "正文",
        }

        client = TestClient(create_app())
        response = client.get("/journal/2026/03/test.md/edit")

        assert response.status_code == 200
        assert 'type="datetime-local" value="2026-03-20T21:46:00"' in response.text
        assert 'id="original-date-raw"' in response.text
        assert 'name="original_date_raw"' in response.text
        assert 'value="2026-03-20T21:46:00+01:00"' in response.text

    def test_resolve_standard_date_value_preserves_original_offset_when_unchanged(
        self,
    ) -> None:
        from web.services.date_adapter import resolve_standard_date_value

        assert (
            resolve_standard_date_value(
                gui_value="2026-03-20T21:46:00",
                original_raw_value="2026-03-20T21:46:00+01:00",
            )
            == "2026-03-20T21:46:00+01:00"
        )

    def test_resolve_standard_date_value_returns_gui_value_for_new_write(self) -> None:
        from web.services.date_adapter import resolve_standard_date_value

        assert (
            resolve_standard_date_value("2026-03-24T09:15:00", "")
            == "2026-03-24T09:15:00"
        )

    @patch("web.routes.edit.edit_journal_web")
    @patch("web.routes.edit.get_journal")
    @patch("web.routes.edit.get_provider")
    def test_submit_edit_preserves_original_raw_date_when_display_value_unchanged(
        self,
        mock_get_provider: MagicMock,
        mock_get_journal: MagicMock,
        mock_edit_journal_web: MagicMock,
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_get_provider.return_value = None
        mock_get_journal.return_value = {
            "metadata": {
                "title": "测试日志",
                "date": "2026-03-20T21:46:00+01:00",
                "topic": ["work"],
                "mood": ["专注"],
                "tags": ["python"],
                "people": [],
                "location": "Lagos, Nigeria",
                "weather": "Sunny 28°C",
            },
            "raw_body": "正文",
        }
        mock_edit_journal_web.return_value = {
            "success": True,
            "journal_path": "C:/fake/journals/2026/03/test.md",
        }

        client = TestClient(create_app())
        get_response = client.get("/journal/2026/03/test.md/edit")

        assert get_response.status_code == 200
        csrf_token = get_response.cookies.get("csrf_token")
        assert csrf_token

        post_response = client.post(
            "/journal/2026/03/test.md/edit",
            data={
                "csrf_token": csrf_token,
                "title": "测试日志",
                "date": "2026-03-20T21:46:00",
                "original_date_raw": "2026-03-20T21:46:00+01:00",
                "topic": "work",
                "mood": "专注",
                "tags": "python",
                "people": "",
                "location": "Lagos, Nigeria",
                "weather": "Sunny 28°C",
                "project": "",
                "abstract": "",
                "links": "",
                "attachments": "",
                "content": "正文",
            },
            follow_redirects=False,
        )

        assert post_response.status_code == 303
        submitted_form_data = mock_edit_journal_web.call_args.kwargs[
            "frontmatter_updates"
        ]
        assert "date" not in submitted_form_data


class TestEditTemplate:
    def test_edit_template_places_weather_button_with_weather_input(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "edit.html").read_text(encoding="utf-8")

        location_idx = source.index('<label for="location"')
        weather_idx = source.index('<label for="weather"')
        geo_btn_idx = source.index('id="geolocation-btn"')
        weather_btn_idx = source.index('id="weather-btn"')

        assert location_idx < geo_btn_idx < weather_idx
        assert weather_idx < weather_btn_idx
        assert weather_btn_idx > source.index('id="weather"')

    def test_edit_template_preserves_original_raw_date_hidden_field(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "edit.html").read_text(encoding="utf-8")

        assert 'id="original-date-raw"' in source


class TestWriteRoute:
    def test_write_template_context_uses_gui_datetime_value(self) -> None:
        from web.routes.write import _build_template_context

        context = _build_template_context(
            request=MagicMock(url=MagicMock(path="/write")),
            csrf_token="token",
            templates=[],
            llm_available=False,
            form_data={"date": "2026-03-20T21:46:00+01:00"},
        )

        assert context["date"] == "2026-03-20T21:46:00"


class TestWriteTemplate:
    def test_write_template_title_input_has_single_style_attribute(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "write.html").read_text(encoding="utf-8")

        title_input_start = source.index('id="title"')
        title_input_end = source.index('autocomplete="off"', title_input_start)
        title_input_markup = source[title_input_start:title_input_end]

        assert title_input_markup.count("style=") == 1


class TestLLMProviderConfig:
    def test_api_key_provider_reads_shared_llm_config(self, monkeypatch) -> None:
        from web.services.llm_provider import APIKeyProvider

        monkeypatch.setattr(
            "web.services.llm_provider.get_llm_config",
            lambda: {
                "api_key": "config-key",
                "base_url": "https://openrouter.ai/api/v1",
                "model": "openai/gpt-4o-mini",
            },
        )

        provider = APIKeyProvider()

        assert provider.api_key == "config-key"
        assert provider.base_url == "https://openrouter.ai/api/v1"
        assert provider.model == "openai/gpt-4o-mini"


class TestSettingsRoute:
    @patch("web.routes.settings.get_llm_config")
    def test_settings_page_renders_existing_config(
        self, mock_get_llm_config: MagicMock
    ):
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_get_llm_config.return_value = {
            "api_key": "sk-test-1234",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
        }

        client = TestClient(create_app())
        response = client.get("/settings")

        assert response.status_code == 200
        assert "LLM 设置" in response.text
        assert "gpt-4o-mini" in response.text
        assert "OpenAI" in response.text
        assert "••••1234" in response.text

    @patch("web.routes.settings._check_llm_connectivity")
    @patch("web.routes.settings.save_llm_config")
    def test_settings_page_saves_config_and_reports_connectivity(
        self,
        mock_save_llm_config: MagicMock,
        mock_check_llm_connectivity: MagicMock,
    ):
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_check_llm_connectivity.return_value = (True, "连接成功")

        client = TestClient(create_app())
        response = client.post(
            "/settings",
            data={
                "api_key": "sk-live-key",
                "base_url": "https://openrouter.ai/api/v1",
                "base_url_preset": "https://openrouter.ai/api/v1",
                "model": "openai/gpt-4o-mini",
                "default_location": "Lagos, Nigeria",
            },
        )

        assert response.status_code == 200
        mock_save_llm_config.assert_called_once_with(
            api_key="sk-live-key",
            base_url="https://openrouter.ai/api/v1",
            model="openai/gpt-4o-mini",
        )
        assert "连接成功" in response.text
        assert "配置已保存" in response.text


class TestSearchService:
    @patch("web.services.search.hierarchical_search")
    def test_search_calls_hierarchical_search(self, mock_search: MagicMock) -> None:
        from web.services.search import search_journals_web

        mock_search.return_value = {
            "success": True,
            "merged_results": [],
            "total_found": 0,
            "performance": {"total_time_ms": 10.0},
            "semantic_available": True,
        }

        asyncio.run(search_journals_web(query="测试关键词", topic="work"))
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["query"] == "测试关键词"
        assert call_kwargs["topic"] == "work"
        assert call_kwargs["level"] == 3
        assert call_kwargs["semantic"] is True

    @patch("web.services.search.hierarchical_search")
    def test_search_returns_web_friendly_result(self, mock_search: MagicMock) -> None:
        from web.services.search import search_journals_web

        mock_search.return_value = {
            "success": True,
            "merged_results": [
                {
                    "path": "C:/Users/.../Documents/Life-Index/Journals/2026/03/a.md",
                    "journal_route_path": "2026/03/a.md",
                    "title": "测试日志",
                    "date": "2026-03-07",
                    "rrf_score": 0.031,
                    "snippet": "这是匹配的片段...",
                }
            ],
            "total_found": 1,
            "performance": {"total_time_ms": 42.5},
            "semantic_available": True,
        }

        with patch("web.services.search._file_exists", return_value=True):
            result = asyncio.run(search_journals_web(query="测试"))
        assert result["success"] is True
        assert result["total_found"] == 1
        assert result["results"][0]["journal_route_path"] == "2026/03/a.md"
        assert result["time_ms"] == 42.5

    @patch("web.services.search.hierarchical_search")
    def test_search_filters_invalid_temp_route_paths(
        self, mock_search: MagicMock
    ) -> None:
        from web.services.search import search_journals_web

        mock_search.return_value = {
            "success": True,
            "merged_results": [
                {
                    "journal_route_path": "2026/03/real.md",
                    "title": "真实日志",
                    "date": "2026-03-13",
                },
                {
                    "journal_route_path": "C:/Users/17865/AppData/Local/Temp/pytest-of-17865/test.md",
                    "title": "Test",
                    "date": "2026-03-14",
                },
            ],
            "total_found": 2,
            "performance": {"total_time_ms": 10.0},
        }

        with patch("web.services.search._file_exists", return_value=True):
            result = asyncio.run(
                search_journals_web(date_from="2026-03-13", date_to="2026-03-13")
            )

        assert len(result["results"]) == 1
        assert result["results"][0]["journal_route_path"] == "2026/03/real.md"

    @patch("web.services.search.hierarchical_search")
    def test_search_empty_query_no_search(self, mock_search: MagicMock) -> None:
        from web.services.search import search_journals_web

        result = asyncio.run(search_journals_web())
        mock_search.assert_not_called()
        assert result["results"] == []
        assert result["total_found"] == 0

    @patch("web.services.search.hierarchical_search")
    def test_search_error_handled_gracefully(self, mock_search: MagicMock) -> None:
        from web.services import search as search_module

        search_module._SEARCH_CACHE.clear()
        mock_search.side_effect = Exception("Database error")
        result = asyncio.run(search_module.search_journals_web(query="测试"))
        assert result["success"] is False
        assert result["total_found"] == 0
        assert result["error"]

    @patch("web.services.search.hierarchical_search")
    def test_search_reuses_cached_result_for_identical_params(
        self, mock_search: MagicMock
    ) -> None:
        from web.services import search as search_module

        search_module._SEARCH_CACHE.clear()
        mock_search.return_value = {
            "success": True,
            "merged_results": [],
            "total_found": 0,
            "performance": {"total_time_ms": 10.0},
        }

        asyncio.run(search_module.search_journals_web(query="测试", topic="work"))
        asyncio.run(search_module.search_journals_web(query="测试", topic="work"))

        assert mock_search.call_count == 1

    @patch("web.services.search.hierarchical_search")
    def test_search_cache_key_differs_for_different_params(
        self, mock_search: MagicMock
    ) -> None:
        from web.services import search as search_module

        search_module._SEARCH_CACHE.clear()
        mock_search.return_value = {
            "success": True,
            "merged_results": [],
            "total_found": 0,
            "performance": {"total_time_ms": 10.0},
        }

        asyncio.run(search_module.search_journals_web(query="测试", topic="work"))
        asyncio.run(search_module.search_journals_web(query="测试", topic="life"))

        assert mock_search.call_count == 2

    @patch("web.services.search.hierarchical_search")
    @patch("web.services.search.time.time")
    def test_search_cache_expires_after_ttl(
        self, mock_time: MagicMock, mock_search: MagicMock
    ) -> None:
        from web.services import search as search_module

        search_module._SEARCH_CACHE.clear()
        mock_search.return_value = {
            "success": True,
            "merged_results": [],
            "total_found": 0,
            "performance": {"total_time_ms": 10.0},
        }
        mock_time.side_effect = [1000.0, 1061.0, 1061.0]

        asyncio.run(search_module.search_journals_web(query="测试", topic="work"))
        asyncio.run(search_module.search_journals_web(query="测试", topic="work"))

        assert mock_search.call_count == 2

    def test_sanitize_snippet_removes_attachments_block(self) -> None:
        from web.services.search import _sanitize_snippet

        snippet = "命中内容\n## Attachments\n- [file.png](../../../attachments/2026/03/file.png)"

        assert _sanitize_snippet(snippet) == "命中内容"

    def test_sanitize_snippet_preserves_mark_tags(self) -> None:
        from web.services.search import _sanitize_snippet

        snippet = "这是 <mark>关键词</mark> 命中内容"

        assert _sanitize_snippet(snippet) == snippet

    def test_sanitize_snippet_removes_markdown_heading_prefix(self) -> None:
        from web.services.search import _sanitize_snippet

        snippet = "## 标题\n正文"

        assert _sanitize_snippet(snippet) == "标题\n正文"

    @patch("web.services.search.hierarchical_search")
    def test_search_filters_results_with_missing_journal_files(
        self, mock_search: MagicMock
    ) -> None:
        from web.services.search import search_journals_web

        mock_search.return_value = {
            "success": True,
            "merged_results": [
                {
                    "journal_route_path": "2026/03/existing.md",
                    "file_path": "C:/existing.md",
                    "title": "Existing",
                    "date": "2026-03-13",
                },
                {
                    "journal_route_path": "2026/03/missing.md",
                    "file_path": "C:/missing.md",
                    "title": "Missing",
                    "date": "2026-03-14",
                },
            ],
            "total_found": 2,
            "performance": {"total_time_ms": 10.0},
        }

        with patch(
            "web.services.search._file_exists",
            side_effect=lambda item: item.get("file_path") != "C:/missing.md",
        ):
            result = asyncio.run(search_journals_web(query="测试"))

        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Existing"


class TestSearchRoute:
    @patch("web.routes.search.search_journals_web")
    def test_search_date_param_prefills_date_filters_and_runs_search(
        self, mock_search: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "日期命中",
                    "date": "2026-03-13",
                    "journal_route_path": "2026/03/test.md",
                    "mood": [],
                    "snippet": None,
                }
            ],
            "total_found": 1,
            "time_ms": 12.0,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?date=2026-03-13")

        assert response.status_code == 200
        assert 'value="2026-03-13"' in response.text
        assert "日期命中" in response.text
        mock_search.assert_called_once_with(
            query=None,
            topic=None,
            date_from="2026-03-13",
            date_to="2026-03-13",
            mood=None,
            tags=None,
            people=None,
            provider=None,
        )

    @patch("web.routes.search.search_journals_web")
    def test_search_mood_param_runs_filter_only_search(
        self, mock_search: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "心情命中",
                    "date": "2026-03-07",
                    "journal_route_path": "2026/03/test.md",
                    "mood": ["兴奋"],
                    "snippet": None,
                }
            ],
            "total_found": 1,
            "time_ms": 7.0,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?mood=%E5%85%B4%E5%A5%8B")

        assert response.status_code == 200
        assert "心情命中" in response.text
        mock_search.assert_called_once_with(
            query=None,
            topic=None,
            date_from=None,
            date_to=None,
            mood="兴奋",
            tags=None,
            people=None,
            provider=None,
        )

    @patch("web.routes.search.search_journals_web")
    def test_search_tag_param_alias_runs_filter_only_search(
        self, mock_search: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "标签命中",
                    "date": "2026-03-07",
                    "journal_route_path": "2026/03/test.md",
                    "tags": ["OpenClaw"],
                    "snippet": None,
                }
            ],
            "total_found": 1,
            "time_ms": 8.0,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?tag=OpenClaw")

        assert response.status_code == 200
        assert "标签命中" in response.text
        mock_search.assert_called_once_with(
            query=None,
            topic=None,
            date_from=None,
            date_to=None,
            mood=None,
            tags="OpenClaw",
            people=None,
            provider=None,
        )

    @patch("web.routes.search.search_journals_web")
    def test_search_people_param_runs_filter_only_search(
        self, mock_search: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "人物命中",
                    "date": "2026-03-07",
                    "journal_route_path": "2026/03/test.md",
                    "people": ["乐乐"],
                    "snippet": None,
                }
            ],
            "total_found": 1,
            "time_ms": 9.0,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?people=%E5%9B%A2%E5%9B%A2")

        assert response.status_code == 200
        assert "人物命中" in response.text
        mock_search.assert_called_once_with(
            query=None,
            topic=None,
            date_from=None,
            date_to=None,
            mood=None,
            tags=None,
            people="乐乐",
            provider=None,
        )

    @patch("web.routes.search.search_journals_web")
    def test_search_filter_only_empty_state_shows_active_filter_context(
        self, mock_search: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_search.return_value = {
            "success": True,
            "results": [],
            "total_found": 0,
            "time_ms": 5.0,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?mood=%E5%85%B4%E5%A5%8B")

        assert response.status_code == 200
        assert "兴奋" in response.text
        assert "未找到相关日志" in response.text
        assert "开始搜索日志" not in response.text

    def test_search_page_returns_200(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        client = TestClient(create_app())
        response = client.get("/search")
        assert response.status_code == 200
        assert "搜索日志" in response.text

    def test_search_page_does_not_render_removed_runtime_operator_context(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        client = TestClient(create_app())
        response = client.get("/search")

        assert response.status_code == 200
        assert "当前搜索实例正在读取以下目录" not in response.text
        assert "如搜索结果异常，先核对当前数据源与 Journals 目录" not in response.text

    def test_search_page_does_not_render_removed_readonly_simulation_context(
        self, monkeypatch, tmp_path
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path / "sandbox"))
        monkeypatch.setenv("LIFE_INDEX_READONLY_SIMULATION", "1")

        client = TestClient(create_app())
        response = client.get("/search")

        assert response.status_code == 200
        assert "只读仿真" not in response.text
        assert "当前结果来自临时副本，可安全用于验收和排查" not in response.text

    @patch("web.routes.search.search_journals_web")
    def test_search_with_query_returns_results(self, mock_search: MagicMock) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "匹配的日志",
                    "date": "2026-03-07",
                    "journal_route_path": "2026/03/test.md",
                    "mood": ["专注"],
                    "snippet": "这里有关键词...",
                }
            ],
            "total_found": 1,
            "time_ms": 42.5,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?q=关键词")
        assert response.status_code == 200
        assert "匹配的日志" in response.text
        assert "2026-03-07" in response.text

    @patch("web.routes.search.search_journals_web")
    def test_search_htmx_returns_partial(self, mock_search: MagicMock) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "HTMX结果",
                    "date": "2026-03-07",
                    "journal_route_path": "2026/03/test.md",
                    "mood": [],
                    "snippet": None,
                }
            ],
            "total_found": 1,
            "time_ms": 10.0,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?q=测试", headers={"HX-Request": "true"})
        assert response.status_code == 200
        assert "HTMX结果" in response.text
        assert "<!DOCTYPE" not in response.text

    @patch("web.routes.search.search_journals_web")
    def test_search_empty_results_message(self, mock_search: MagicMock) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_search.return_value = {
            "success": True,
            "results": [],
            "total_found": 0,
            "time_ms": 15.0,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?q=不存在的关键词")
        assert response.status_code == 200
        assert "未找到" in response.text

    @patch("web.routes.search.search_journals_web")
    def test_search_results_link_to_journal(self, mock_search: MagicMock) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "链接测试",
                    "date": "2026-03-07",
                    "journal_route_path": "2026/03/life-index_2026-03-07_001.md",
                    "mood": [],
                    "snippet": None,
                }
            ],
            "total_found": 1,
            "time_ms": 5.0,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?q=链接")
        assert "/journal/2026/03/life-index_2026-03-07_001.md" in response.text

    @patch("web.routes.search.search_journals_web")
    def test_search_with_none_score_does_not_crash(
        self, mock_search: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "无分数结果",
                    "date": "2026-03-07",
                    "journal_route_path": "2026/03/test.md",
                    "mood": [],
                    "snippet": None,
                    "score": None,
                }
            ],
            "total_found": 1,
            "time_ms": 5.0,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?q=无分数")
        assert response.status_code == 200
        assert "无分数结果" in response.text


class TestSearchRouterRegistration:
    def test_search_route_exists(self) -> None:
        from web.app import create_app

        app = create_app()
        paths = [getattr(r, "path") for r in app.routes if hasattr(r, "path")]
        assert "/search" in paths


class TestSearchPhase4:
    @patch("web.routes.search.get_provider", new_callable=AsyncMock)
    @patch("web.routes.search.search_journals_web", new_callable=AsyncMock)
    def test_search_page_renders_htmx_ai_summary_loader_when_available(
        self,
        mock_search: AsyncMock,
        mock_get_provider: AsyncMock,
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_get_provider.return_value = AsyncMock()
        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "匹配的日志",
                    "date": "2026-03-07",
                    "journal_route_path": "2026/03/test.md",
                    "mood": ["专注"],
                    "snippet": "这里有关键词...",
                }
            ],
            "total_found": 1,
            "time_ms": 42.5,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?q=关键词")

        assert response.status_code == 200
        assert "AI 智能归纳" in response.text
        assert (
            "/api/search/summarize?query=%E5%85%B3%E9%94%AE%E8%AF%8D" in response.text
        )
        assert "AI 正在奋力归纳总结中" in response.text

    @patch("web.routes.search.get_provider", new_callable=AsyncMock)
    @patch("web.routes.search.search_journals_web", new_callable=AsyncMock)
    def test_search_page_shows_ai_settings_prompt_when_unavailable(
        self,
        mock_search: AsyncMock,
        mock_get_provider: AsyncMock,
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_get_provider.return_value = None
        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "匹配的日志",
                    "date": "2026-03-07",
                    "journal_route_path": "2026/03/test.md",
                    "mood": [],
                    "snippet": None,
                }
            ],
            "total_found": 1,
            "time_ms": 42.5,
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/search?q=关键词")

        assert response.status_code == 200
        assert "启用 AI 可获得智能搜索摘要" in response.text
        assert "/settings" in response.text

    @patch("web.routes.api.get_provider", new_callable=AsyncMock)
    @patch("web.routes.api.search_journals_web", new_callable=AsyncMock)
    def test_search_summarize_api_returns_partial_when_llm_available(
        self,
        mock_search: AsyncMock,
        mock_get_provider: AsyncMock,
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_get_provider.return_value = AsyncMock()
        mock_search.return_value = {
            "success": True,
            "results": [
                {"title": "匹配的日志", "journal_route_path": "2026/03/test.md"}
            ],
            "total_found": 1,
            "time_ms": 12.0,
            "error": None,
            "ai_summary": {
                "state": "ready",
                "summary": "关于关键词，你最近主要在记录高质量工作片段。",
                "highlights": ["2026-03-07《匹配的日志》"],
                "message": None,
            },
        }

        client = TestClient(create_app())
        response = client.get("/api/search/summarize?query=关键词")

        assert response.status_code == 200
        assert "AI 智能归纳" in response.text
        assert "关于关键词，你最近主要在记录高质量工作片段。" in response.text
        assert "<!DOCTYPE" not in response.text

    def test_search_page_contains_htmx_summary_container_and_timeout_markers(
        self,
    ) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "partials/search_results.html").read_text(
            encoding="utf-8"
        )

        assert 'hx-get="/api/search/summarize' in source
        assert "data-timeout-15-message" in source
        assert "data-timeout-30-message" in source
        assert "重试" in source


class TestSearchTemplate:
    def test_search_template_contains_responsive_layout_classes(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "search.html").read_text(encoding="utf-8")
        assert "sm:text-4xl" in source
        assert "sm:p-6" in source
        assert "sm:flex-row" in source
        assert "sm:items-center" in source
        assert "sm:w-48" in source

    def test_search_results_template_contains_responsive_result_layout(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "partials/search_results.html").read_text(
            encoding="utf-8"
        )
        assert "sm:p-6" in source
        assert "sm:flex-row" in source
        assert "sm:items-center" in source
        assert "sm:text-right" in source
        assert "min-h-[44px]" in source
        assert (
            "box-shadow: 0 20px 40px rgba(0, 0, 0, 0.28), 0 0 0 1px rgba(255, 255, 255, 0.05);"
            in source
        )
