#!/usr/bin/env python3
"""Tests for Web GUI write route — Phase 4b."""

from __future__ import annotations

import importlib
import json
from io import BytesIO
from unittest.mock import AsyncMock, patch


class TestWriteRoute:
    def test_get_write_page_returns_200_and_sets_csrf_cookie(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            mock_provider.return_value = None

            client = TestClient(create_app())
            response = client.get("/write")

        assert response.status_code == 200
        assert "写日志" in response.text
        assert "csrf_token" in response.cookies

    def test_get_write_page_includes_template_selector(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            mock_provider.return_value = None

            client = TestClient(create_app())
            response = client.get("/write")

        assert response.status_code == 200
        assert "选择模板" in response.text
        assert "letter_to_tuantuan" in response.text

    def test_get_write_page_includes_reverse_geocoding_hook(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            mock_provider.return_value = None

            client = TestClient(create_app())
            response = client.get("/write")

        assert response.status_code == 200
        assert "geolocation-btn" in response.text
        assert "/api/reverse-geocode" in response.text
        assert "navigator.geolocation.getCurrentPosition" in response.text

    def test_post_write_rejects_csrf_mismatch(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            mock_provider.return_value = None

            client = TestClient(create_app())
            client.get("/write")
            response = client.post(
                "/write",
                data={
                    "csrf_token": "wrong-token",
                    "content": "正文",
                    "topic": "life",
                    "date": "2026-03-22",
                },
            )

        assert response.status_code == 403

    def test_post_write_ignores_empty_attachments_field_from_browser(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            with patch(
                "web.routes.write.prepare_journal_data", new_callable=AsyncMock
            ) as mock_prepare:
                with patch(
                    "web.routes.write.write_journal_web", new_callable=AsyncMock
                ) as mock_write:
                    mock_provider.return_value = None
                    mock_prepare.return_value = {
                        "content": "正文",
                        "topic": ["life"],
                        "date": "2026-03-22",
                    }
                    mock_write.return_value = {
                        "success": True,
                        "journal_route_path": "2026/03/test.md",
                    }

                    client = TestClient(create_app())
                    get_response = client.get("/write")
                    csrf_token = get_response.cookies.get("csrf_token")
                    assert csrf_token is not None

                    response = client.post(
                        "/write",
                        data={
                            "csrf_token": csrf_token,
                            "content": "正文",
                            "topic": "life",
                            "date": "2026-03-22",
                            "attachments": "",
                        },
                        follow_redirects=False,
                    )

        assert response.status_code == 303
        assert response.headers["location"] == "/journal/2026/03/test.md"

    def test_post_write_success_redirects_to_journal(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            with patch(
                "web.routes.write.prepare_journal_data", new_callable=AsyncMock
            ) as mock_prepare:
                with patch(
                    "web.routes.write.write_journal_web", new_callable=AsyncMock
                ) as mock_write:
                    with patch(
                        "web.routes.write.download_attachment_from_url"
                    ) as mock_download:
                        mock_provider.return_value = None
                        mock_prepare.return_value = {
                            "content": "正文",
                            "topic": ["life"],
                            "date": "2026-03-22",
                        }
                        mock_write.return_value = {
                            "success": True,
                            "journal_route_path": "2026/03/test.md",
                        }
                        mock_download.return_value = {
                            "source_path": "C:/temp/downloaded-file.png",
                            "description": "https://example.com/file.png",
                        }

                        client = TestClient(create_app())
                        get_response = client.get("/write")
                        csrf_token = get_response.cookies.get("csrf_token")
                        assert csrf_token is not None
                        response = client.post(
                            "/write",
                            data={
                                "csrf_token": csrf_token,
                                "content": "正文",
                                "topic": "life",
                                "date": "2026-03-22",
                            },
                            follow_redirects=False,
                        )

        assert response.status_code == 303
        assert response.headers["location"] == "/journal/2026/03/test.md"

    def test_post_write_failure_preserves_user_input(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            with patch(
                "web.routes.write.prepare_journal_data", new_callable=AsyncMock
            ) as mock_prepare:
                with patch(
                    "web.routes.write.write_journal_web", new_callable=AsyncMock
                ) as mock_write:
                    mock_provider.return_value = None
                    mock_prepare.return_value = {
                        "content": "保留的正文",
                        "topic": ["life"],
                        "date": "2026-03-22",
                        "title": "保留标题",
                    }
                    mock_write.return_value = {
                        "success": False,
                        "error": "写入失败",
                    }

                    client = TestClient(create_app())
                    get_response = client.get("/write")
                    csrf_token = get_response.cookies.get("csrf_token")
                    assert csrf_token is not None
                    response = client.post(
                        "/write",
                        data={
                            "csrf_token": csrf_token,
                            "content": "保留的正文",
                            "topic": "life",
                            "date": "2026-03-22",
                            "title": "保留标题",
                        },
                    )

        assert response.status_code == 200
        assert "写入失败" in response.text
        assert "保留的正文" in response.text
        assert "保留标题" in response.text

    def test_post_write_passes_uploaded_files_and_urls(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            with patch(
                "web.routes.write.prepare_journal_data", new_callable=AsyncMock
            ) as mock_prepare:
                with patch(
                    "web.routes.write.write_journal_web", new_callable=AsyncMock
                ) as mock_write:
                    with patch(
                        "web.routes.write.download_attachment_from_url"
                    ) as mock_download:
                        mock_provider.return_value = None
                        mock_prepare.return_value = {
                            "content": "正文",
                            "topic": ["life"],
                            "date": "2026-03-22",
                        }
                        mock_write.return_value = {
                            "success": True,
                            "journal_route_path": "2026/03/test.md",
                        }
                        mock_download.return_value = {
                            "source_path": "C:/temp/downloaded-file.png",
                            "description": "https://example.com/file.png",
                        }

                        client = TestClient(create_app())
                        get_response = client.get("/write")
                        csrf_token = get_response.cookies.get("csrf_token")
                        assert csrf_token is not None

                        response = client.post(
                            "/write",
                            data={
                                "csrf_token": csrf_token,
                                "content": "正文",
                                "topic": "life",
                                "date": "2026-03-22",
                                "attachment_urls": "https://example.com/file.png",
                            },
                            files={
                                "attachments": (
                                    "note.txt",
                                    BytesIO(b"hello"),
                                    "text/plain",
                                ),
                            },
                            follow_redirects=False,
                        )

        assert response.status_code == 303
        assert mock_prepare.await_count == 1
        prepare_args = mock_prepare.await_args_list[0].args[0]
        assert prepare_args["attachment_urls"] == ["https://example.com/file.png"]
        assert len(prepare_args["attachments"]) == 2
        assert prepare_args["attachments"][0]["source_path"]
        assert prepare_args["attachments"][1] == {
            "source_path": "C:/temp/downloaded-file.png",
            "description": "https://example.com/file.png",
        }

    def test_post_write_converts_attachments_to_source_paths(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            with patch(
                "web.routes.write.prepare_journal_data", new_callable=AsyncMock
            ) as mock_prepare:
                with patch("web.routes.write.stage_uploaded_files") as mock_stage:
                    with patch(
                        "web.routes.write.download_attachment_from_url"
                    ) as mock_download:
                        with patch(
                            "web.routes.write.write_journal_web", new_callable=AsyncMock
                        ) as mock_write:
                            mock_provider.return_value = None
                            mock_prepare.return_value = {
                                "content": "正文",
                                "topic": ["life"],
                                "date": "2026-03-22",
                                "attachments": [
                                    {
                                        "source_path": "C:/temp/uploaded-note.txt",
                                        "description": "",
                                    },
                                    {
                                        "source_path": "C:/temp/downloaded-file.png",
                                        "description": "https://example.com/file.png",
                                    },
                                ],
                            }
                            mock_stage.return_value = [
                                {
                                    "source_path": "C:/temp/uploaded-note.txt",
                                    "description": "",
                                }
                            ]
                            mock_download.return_value = {
                                "source_path": "C:/temp/downloaded-file.png",
                                "description": "https://example.com/file.png",
                            }
                            mock_write.return_value = {
                                "success": True,
                                "journal_route_path": "2026/03/test.md",
                            }

                            client = TestClient(create_app())
                            get_response = client.get("/write")
                            csrf_token = get_response.cookies.get("csrf_token")
                            assert csrf_token is not None

                            response = client.post(
                                "/write",
                                data={
                                    "csrf_token": csrf_token,
                                    "content": "正文",
                                    "topic": "life",
                                    "date": "2026-03-22",
                                    "attachment_urls": "https://example.com/file.png",
                                },
                                files={
                                    "attachments": (
                                        "note.txt",
                                        BytesIO(b"hello"),
                                        "text/plain",
                                    ),
                                },
                                follow_redirects=False,
                            )

        assert response.status_code == 303
        mock_stage.assert_called_once()
        mock_download.assert_called_once_with("https://example.com/file.png")
        assert mock_prepare.await_count == 1
        prepare_args = mock_prepare.await_args_list[0].args[0]
        assert prepare_args["attachments"] == [
            {"source_path": "C:/temp/uploaded-note.txt", "description": ""},
            {
                "source_path": "C:/temp/downloaded-file.png",
                "description": "https://example.com/file.png",
            },
        ]

    def test_post_write_attachment_download_failure_renders_error(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            with patch(
                "web.routes.write.download_attachment_from_url"
            ) as mock_download:
                mock_provider.return_value = None
                mock_download.side_effect = ValueError("Content-Type 不支持")

                client = TestClient(create_app())
                get_response = client.get("/write")
                csrf_token = get_response.cookies.get("csrf_token")
                assert csrf_token is not None

                response = client.post(
                    "/write",
                    data={
                        "csrf_token": csrf_token,
                        "content": "正文",
                        "topic": "life",
                        "date": "2026-03-22",
                        "attachment_urls": "https://example.com/index.html",
                    },
                )

        assert response.status_code == 200
        assert "Content-Type 不支持" in response.text

    def test_post_write_cleans_up_staged_files_when_content_type_rejected(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            with patch("web.routes.write.stage_uploaded_files") as mock_stage:
                with patch("web.routes.write.cleanup_staged_files") as mock_cleanup:
                    with patch(
                        "web.routes.write.download_attachment_from_url"
                    ) as mock_download:
                        mock_provider.return_value = None
                        mock_stage.return_value = [
                            {
                                "source_path": "C:/temp/uploaded-note.txt",
                                "description": "",
                            }
                        ]
                        mock_download.side_effect = ValueError("Content-Type 不支持")

                        client = TestClient(create_app())
                        get_response = client.get("/write")
                        csrf_token = get_response.cookies.get("csrf_token")
                        assert csrf_token is not None

                        response = client.post(
                            "/write",
                            data={
                                "csrf_token": csrf_token,
                                "content": "正文",
                                "topic": "life",
                                "date": "2026-03-22",
                                "attachment_urls": "https://example.com/file.png",
                            },
                            files={
                                "attachments": (
                                    "note.txt",
                                    BytesIO(b"hello"),
                                    "text/plain",
                                ),
                            },
                        )

        assert response.status_code == 200
        mock_cleanup.assert_called_once_with(
            [{"source_path": "C:/temp/uploaded-note.txt", "description": ""}]
        )

    def test_post_write_download_failure_skips_optional_and_continues(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            with patch("web.routes.write.stage_uploaded_files") as mock_stage:
                with patch(
                    "web.routes.write.download_attachment_from_url"
                ) as mock_download:
                    with patch(
                        "web.routes.write.prepare_journal_data", new_callable=AsyncMock
                    ) as mock_prepare:
                        with patch(
                            "web.routes.write.write_journal_web", new_callable=AsyncMock
                        ) as mock_write:
                            mock_provider.return_value = None
                            mock_stage.return_value = [
                                {
                                    "source_path": "C:/temp/uploaded-note.txt",
                                    "description": "",
                                }
                            ]
                            mock_download.side_effect = RuntimeError("网络失败")
                            mock_prepare.return_value = {
                                "content": "正文",
                                "topic": ["life"],
                                "date": "2026-03-22",
                                "attachments": [
                                    {
                                        "source_path": "C:/temp/uploaded-note.txt",
                                        "description": "",
                                    }
                                ],
                            }
                            mock_write.return_value = {
                                "success": True,
                                "journal_route_path": "2026/03/test.md",
                            }

                            client = TestClient(create_app())
                            get_response = client.get("/write")
                            csrf_token = get_response.cookies.get("csrf_token")
                            assert csrf_token is not None

                            response = client.post(
                                "/write",
                                data={
                                    "csrf_token": csrf_token,
                                    "content": "正文",
                                    "topic": "life",
                                    "date": "2026-03-22",
                                    "attachment_urls": "https://example.com/file.png",
                                },
                                files={
                                    "attachments": (
                                        "note.txt",
                                        BytesIO(b"hello"),
                                        "text/plain",
                                    ),
                                },
                                follow_redirects=False,
                            )

        assert response.status_code == 303
        assert "warning=" in response.headers["location"]
        assert mock_prepare.await_count == 1
        prepare_args = mock_prepare.await_args_list[0].args[0]
        assert prepare_args["attachments"] == [
            {"source_path": "C:/temp/uploaded-note.txt", "description": ""}
        ]


class TestWriteRouteRegistration:
    def test_write_route_exists(self) -> None:
        from web.app import create_app

        app = create_app()
        paths = [
            getattr(route, "path") for route in app.routes if hasattr(route, "path")
        ]
        assert "/write" in paths


class TestWriteTemplate:
    def test_write_template_exists(self) -> None:
        from web.config import TEMPLATES_DIR

        assert (TEMPLATES_DIR / "write.html").is_file()

    def test_write_template_extends_base(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "write.html").read_text(encoding="utf-8")
        assert '{% extends "base.html" %}' in source
        assert "csrf_token" in source
        assert "选择模板" in source
        assert "日志内容" in source

    def test_write_template_has_safe_preset_prefill_script(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "write.html").read_text(encoding="utf-8")
        assert "data-templates" in source
        assert "template-selector" in source
        assert "confirm(" in source
        assert "existingContent" in source
        assert "existingTopic" in source

    def test_write_template_has_geolocation_hook(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "write.html").read_text(encoding="utf-8")
        assert "geolocation-btn" in source
        assert "weather-btn" in source
        assert "navigator.geolocation" in source
        assert "setButtonBusy" in source
        assert "fetchWeatherForLocation" in source
        assert "weather-status" in source
        assert "/api/weather" in source
        assert "weatherField.value = ''" in source
        assert "正在定位" in source
        assert "正在查询天气" in source
        assert "位置信息获取失败" in source

    def test_write_template_has_dynamic_url_inputs(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "write.html").read_text(encoding="utf-8")
        assert 'id="url-inputs"' in source
        assert 'id="add-url-btn"' in source
        assert 'id="local-file-input"' in source
        assert 'id="selected-files-status"' in source
        assert 'id="attachment-status"' in source
        assert 'id="submit-btn"' in source
        assert 'data-idle-text="保存日志"' in source
        assert "正在保存..." in source
        assert "remove-url-btn" in source
        assert "selectedFilesStatus" in source
        assert "attachmentStatus" in source
        assert "submitBtn" in source
        assert "sm:text-4xl" in source
        assert "sm:p-6" in source
        assert "sm:flex-row" in source
        assert "min-h-[44px]" in source
        assert "tracking-tight" in source
        assert "attachment_urls" in source
        assert "appendChild" in source


class TestWritingTemplatesData:
    def test_write_route_can_load_templates_json(self) -> None:
        route_module = importlib.import_module("web.routes.write")
        load_templates = getattr(route_module, "load_writing_templates")

        templates = load_templates()

        assert len(templates) == 7
        assert any(item["id"] == "blank" for item in templates)
        assert any(item["id"] == "work_log" for item in templates)
