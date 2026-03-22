#!/usr/bin/env python3
"""Tests for Web GUI Journal View + Search — Task 9 first."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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
        assert "min-h-[44px]" in source
        assert "divide-y divide-gray-100" in source
        assert "tracking-tight" in source


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

        search_journals_web(query="测试关键词", topic="work")
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

        result = search_journals_web(query="测试")
        assert result["success"] is True
        assert result["total_found"] == 1
        assert result["results"][0]["journal_route_path"] == "2026/03/a.md"
        assert result["time_ms"] == 42.5

    @patch("web.services.search.hierarchical_search")
    def test_search_empty_query_no_search(self, mock_search: MagicMock) -> None:
        from web.services.search import search_journals_web

        result = search_journals_web()
        mock_search.assert_not_called()
        assert result["results"] == []
        assert result["total_found"] == 0

    @patch("web.services.search.hierarchical_search")
    def test_search_error_handled_gracefully(self, mock_search: MagicMock) -> None:
        from web.services.search import search_journals_web

        mock_search.side_effect = Exception("Database error")
        result = search_journals_web(query="测试")
        assert result["success"] is False
        assert result["total_found"] == 0
        assert result["error"]


class TestSearchRoute:
    def test_search_page_returns_200(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        client = TestClient(create_app())
        response = client.get("/search")
        assert response.status_code == 200
        assert "搜索日志" in response.text

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
        assert "ring-1 ring-black/5" in source
