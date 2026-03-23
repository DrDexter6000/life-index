#!/usr/bin/env python3
"""Tests for Web GUI edit flow foundation — Phase 4c."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestEditService:
    def test_compute_edit_diff_omits_unchanged_fields(self) -> None:
        module = importlib.import_module("web.services.edit")
        compute_edit_diff = getattr(module, "compute_edit_diff")

        result = compute_edit_diff(
            original={
                "title": "原标题",
                "topic": ["life"],
                "weather": "晴",
                "_body": "原正文",
            },
            submitted={
                "title": "原标题",
                "topic": ["life"],
                "weather": "多云",
                "content": "新正文",
            },
        )

        assert result["frontmatter_updates"] == {"weather": "多云"}
        assert result["replace_content"] == "新正文"

    def test_compute_edit_diff_requires_weather_when_location_changes(self) -> None:
        module = importlib.import_module("web.services.edit")
        compute_edit_diff = getattr(module, "compute_edit_diff")

        result = compute_edit_diff(
            original={"location": "Lagos", "weather": "晴", "_body": "原正文"},
            submitted={"location": "Abuja", "weather": "", "content": "原正文"},
        )

        assert result["frontmatter_updates"] == {"location": "Abuja"}
        assert result["location_weather_required"] is True


class TestEditRoute:
    @patch("web.routes.edit.get_journal")
    @patch("web.routes.edit.get_provider", new_callable=AsyncMock)
    def test_get_edit_page_prefills_form(
        self,
        mock_provider: AsyncMock,
        mock_get_journal: MagicMock,
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_provider.return_value = None
        mock_get_journal.return_value = {
            "metadata": {
                "title": "测试日志",
                "date": "2026-03-07T14:30:00",
                "mood": ["专注"],
                "tags": ["python"],
                "topic": ["work"],
                "people": ["团团"],
                "location": "Lagos, Nigeria",
                "weather": "Sunny 28°C",
                "project": "Life Index",
            },
            "raw_body": "原正文内容",
            "attachments": [],
            "journal_route_path": "2026/03/test.md",
        }

        client = TestClient(create_app())
        response = client.get("/journal/2026/03/test.md/edit")

        assert response.status_code == 200
        assert "编辑日志" in response.text
        assert "测试日志" in response.text
        assert "原正文内容" in response.text
        assert "csrf_token" in response.cookies

    def test_post_edit_rejects_csrf_mismatch(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch("web.routes.edit.get_journal") as mock_get_journal:
            with patch(
                "web.routes.edit.get_provider", new_callable=AsyncMock
            ) as mock_provider:
                mock_provider.return_value = None
                mock_get_journal.return_value = {
                    "metadata": {},
                    "raw_body": "原正文",
                    "attachments": [],
                    "journal_route_path": "2026/03/test.md",
                }

                client = TestClient(create_app())
                client.get("/journal/2026/03/test.md/edit")
                response = client.post(
                    "/journal/2026/03/test.md/edit",
                    data={
                        "csrf_token": "wrong-token",
                        "title": "新标题",
                        "content": "新正文",
                    },
                )

        assert response.status_code == 403

    def test_post_edit_success_redirects_to_journal(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch("web.routes.edit.get_journal") as mock_get_journal:
            with patch(
                "web.routes.edit.get_provider", new_callable=AsyncMock
            ) as mock_provider:
                with patch("web.routes.edit.compute_edit_diff") as mock_diff:
                    with patch(
                        "web.routes.edit.edit_journal_web", new_callable=AsyncMock
                    ) as mock_edit:
                        mock_provider.return_value = None
                        mock_get_journal.return_value = {
                            "metadata": {"title": "原标题", "topic": ["life"]},
                            "raw_body": "原正文",
                            "attachments": [],
                            "journal_route_path": "2026/03/test.md",
                        }
                        mock_diff.return_value = {
                            "frontmatter_updates": {"title": "新标题"},
                            "replace_content": "新正文",
                            "location_weather_required": False,
                        }
                        mock_edit.return_value = {"success": True}

                        client = TestClient(create_app())
                        get_response = client.get("/journal/2026/03/test.md/edit")
                        csrf_token = get_response.cookies.get("csrf_token")
                        assert csrf_token is not None

                        response = client.post(
                            "/journal/2026/03/test.md/edit",
                            data={
                                "csrf_token": csrf_token,
                                "title": "新标题",
                                "content": "新正文",
                                "topic": "life",
                            },
                            follow_redirects=False,
                        )

        assert response.status_code == 303
        assert "saved=1" in response.headers["location"]

    def test_post_edit_failure_preserves_edit_state(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch("web.routes.edit.get_journal") as mock_get_journal:
            with patch(
                "web.routes.edit.get_provider", new_callable=AsyncMock
            ) as mock_provider:
                with patch("web.routes.edit.compute_edit_diff") as mock_diff:
                    with patch(
                        "web.routes.edit.edit_journal_web", new_callable=AsyncMock
                    ) as mock_edit:
                        mock_provider.return_value = None
                        mock_get_journal.return_value = {
                            "metadata": {"title": "原标题", "topic": ["life"]},
                            "raw_body": "原正文",
                            "attachments": [],
                            "journal_route_path": "2026/03/test.md",
                        }
                        mock_diff.return_value = {
                            "frontmatter_updates": {"title": "新标题"},
                            "replace_content": "失败后保留的正文",
                            "location_weather_required": False,
                        }
                        mock_edit.return_value = {
                            "success": False,
                            "error": "编辑失败",
                        }

                        client = TestClient(create_app())
                        get_response = client.get("/journal/2026/03/test.md/edit")
                        csrf_token = get_response.cookies.get("csrf_token")
                        assert csrf_token is not None

                        response = client.post(
                            "/journal/2026/03/test.md/edit",
                            data={
                                "csrf_token": csrf_token,
                                "title": "新标题",
                                "content": "失败后保留的正文",
                                "topic": "life",
                            },
                        )

        assert response.status_code == 200
        assert "编辑失败" in response.text
        assert "失败后保留的正文" in response.text
        assert "新标题" in response.text

    @patch("web.routes.journal.get_journal")
    def test_journal_route_renders_edit_success_banner(
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
        response = client.get("/journal/2026/03/test.md?saved=1")

        assert response.status_code == 200
        assert "修改已保存" in response.text

    @patch("web.routes.edit.query_weather_for_location")
    def test_weather_api_returns_simple_weather(self, mock_weather: MagicMock) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_weather.return_value = {
            "success": True,
            "weather": "晴天 28°C",
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/api/weather?location=Lagos,Nigeria&date=2026-03-22")

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["weather"] == "晴天 28°C"
        assert response.json()["error"] is None

    @patch("web.routes.edit.query_weather")
    @patch("web.routes.edit.geocode_location")
    def test_weather_api_treats_empty_date_as_missing(
        self,
        mock_geocode: MagicMock,
        mock_query_weather: MagicMock,
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_geocode.return_value = {
            "latitude": 6.5244,
            "longitude": 3.3792,
        }
        mock_query_weather.return_value = {
            "success": True,
            "weather": {
                "simple": "晴",
                "description": "Sunny",
            },
        }

        client = TestClient(create_app())
        response = client.get("/api/weather?location=Lagos,Nigeria&date=")

        assert response.status_code == 200
        assert response.json()["success"] is True
        called_args = mock_query_weather.call_args.args
        assert called_args[0] == 6.5244
        assert called_args[1] == 3.3792
        assert isinstance(called_args[2], str)
        assert len(called_args[2]) == 10

    @patch("web.routes.edit.query_weather")
    @patch("web.routes.edit.geocode_location")
    def test_weather_api_normalizes_datetime_local_value(
        self,
        mock_geocode: MagicMock,
        mock_query_weather: MagicMock,
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_geocode.return_value = {
            "latitude": 6.5244,
            "longitude": 3.3792,
        }
        mock_query_weather.return_value = {
            "success": True,
            "weather": {
                "simple": "晴",
                "description": "Sunny",
            },
        }

        client = TestClient(create_app())
        response = client.get(
            "/api/weather?location=Lagos,Nigeria&date=2026-03-23T19:31"
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_query_weather.assert_called_once_with(6.5244, 3.3792, "2026-03-23")

    @patch("web.routes.edit.reverse_geocode_for_coordinates")
    def test_reverse_geocode_api_returns_location_payload(
        self, mock_reverse_geocode: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_reverse_geocode.return_value = {
            "success": True,
            "location": "Lagos, Lagos State, Nigeria",
            "error": None,
        }

        client = TestClient(create_app())
        response = client.get("/api/reverse-geocode?lat=6.5244&lon=3.3792")

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["location"] == "Lagos, Lagos State, Nigeria"
        assert response.json()["error"] is None

    @patch("web.routes.edit.query_weather_for_location")
    def test_weather_api_requires_location(self, mock_weather: MagicMock) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        client = TestClient(create_app())
        response = client.get("/api/weather")

        assert response.status_code == 400
        mock_weather.assert_not_called()

    @patch("web.routes.edit.query_weather_for_location")
    def test_weather_api_returns_structured_error_payload(
        self, mock_weather: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        mock_weather.return_value = {
            "success": False,
            "weather": None,
            "error": "地点解析失败",
            "error_code": "E0402",
        }

        client = TestClient(create_app())
        response = client.get("/api/weather?location=BadPlace")

        assert response.status_code == 200
        assert response.json()["success"] is False
        assert response.json()["error"] == "地点解析失败"
        assert response.json()["error_code"] == "E0402"


class TestEditTemplate:
    def test_edit_template_exists(self) -> None:
        from web.config import TEMPLATES_DIR

        assert (TEMPLATES_DIR / "edit.html").is_file()

    def test_edit_template_extends_base(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "edit.html").read_text(encoding="utf-8")
        assert '{% extends "base.html" %}' in source
        assert "编辑日志" in source
        assert "csrf_token" in source
        assert "/api/weather" in source
        assert "weather-btn" in source
        assert "geolocation-btn" in source
        assert "fetch(" in source
        assert "/api/reverse-geocode" in source
        assert "setButtonBusy" in source
        assert "fetchWeatherForLocation" in source
        assert "weather-status" in source
        assert "original-location" in source
        assert "weather-warning" in source
        assert 'id="submit-btn"' in source
        assert 'data-idle-text="保存修改"' in source
        assert 'id="form-status"' in source
        assert "正在保存..." in source
        assert "formStatus" in source
        assert "submitBtn" in source
        assert "sm:text-4xl" in source
        assert "sm:p-6" in source
        assert "sm:flex-row" in source
        assert "min-h-[44px]" in source
        assert "tracking-tight" in source
        assert "保存前请先查询天气" in source
        assert "submit" in source
        assert "weatherField.value = ''" in source
        assert "locationDirty" in source
        assert "正在定位" in source
        assert "正在查询天气" in source
        assert "bg-red-50" in source


class TestEditRouteRegistration:
    def test_edit_route_exists(self) -> None:
        from web.app import create_app

        app = create_app()
        paths = [
            getattr(route, "path") for route in app.routes if hasattr(route, "path")
        ]
        assert "/journal/{journal_path:path}/edit" in paths
        assert "/api/reverse-geocode" in paths
