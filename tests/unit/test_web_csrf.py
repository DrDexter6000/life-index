#!/usr/bin/env python3
"""Focused CSRF contract tests for Web GUI routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch


class TestWriteCsrfContract:
    def test_get_write_sets_cookie_and_form_token(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            mock_provider.return_value = None

            client = TestClient(create_app())
            response = client.get("/write")

        assert response.status_code == 200
        csrf_cookie = response.cookies.get("csrf_token")
        assert csrf_cookie is not None
        assert f'value="{csrf_cookie}"' in response.text

    def test_post_write_missing_cookie_returns_403(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        client = TestClient(create_app())
        response = client.post(
            "/write",
            data={
                "csrf_token": "orphan-token",
                "content": "正文",
                "topic": "life",
                "date": "2026-03-22",
            },
        )

        assert response.status_code == 403


class TestEditCsrfContract:
    def test_get_edit_sets_cookie_and_form_token(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.edit.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            with patch("web.routes.edit.get_journal") as mock_get_journal:
                mock_provider.return_value = None
                mock_get_journal.return_value = {
                    "metadata": {},
                    "raw_body": "原正文",
                    "attachments": [],
                    "journal_route_path": "2026/03/test.md",
                }

                client = TestClient(create_app())
                response = client.get("/journal/2026/03/test.md/edit")

        assert response.status_code == 200
        csrf_cookie = response.cookies.get("csrf_token")
        assert csrf_cookie is not None
        assert f'value="{csrf_cookie}"' in response.text

    def test_post_edit_missing_cookie_returns_403(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        client = TestClient(create_app())
        response = client.post(
            "/journal/2026/03/test.md/edit",
            data={
                "csrf_token": "orphan-token",
                "title": "标题",
                "content": "正文",
            },
        )

        assert response.status_code == 403
