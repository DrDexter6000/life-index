#!/usr/bin/env python3
"""Integration smoke tests for the Web GUI main journey."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch


class TestWebE2ESmoke:
    def test_write_view_edit_search_smoke(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.write.get_provider", new_callable=AsyncMock
        ) as mock_write_provider:
            with patch(
                "web.routes.write.prepare_journal_data", new_callable=AsyncMock
            ) as mock_prepare:
                with patch(
                    "web.routes.write.write_journal_web", new_callable=AsyncMock
                ) as mock_write:
                    with patch("web.routes.journal.get_journal") as mock_get_journal:
                        with patch(
                            "web.routes.edit.get_provider", new_callable=AsyncMock
                        ) as mock_edit_provider:
                            with patch(
                                "web.routes.edit.compute_edit_diff"
                            ) as mock_diff:
                                with patch(
                                    "web.routes.edit.edit_journal_web",
                                    new_callable=AsyncMock,
                                ) as mock_edit:
                                    with patch(
                                        "web.routes.search.search_journals_web"
                                    ) as mock_search:
                                        mock_write_provider.return_value = None
                                        mock_edit_provider.return_value = None
                                        mock_prepare.return_value = {
                                            "content": "新的正文",
                                            "topic": ["life"],
                                            "date": "2026-03-22",
                                        }
                                        mock_write.return_value = {
                                            "success": True,
                                            "journal_route_path": "2026/03/test.md",
                                        }
                                        mock_get_journal.return_value = {
                                            "metadata": {
                                                "title": "测试日志",
                                                "date": "2026-03-22T10:00:00",
                                                "topic": ["life"],
                                                "mood": [],
                                                "tags": [],
                                                "people": [],
                                            },
                                            "html_content": "<p>新的正文</p>",
                                            "raw_body": "新的正文",
                                            "attachments": [],
                                            "journal_route_path": "2026/03/test.md",
                                        }
                                        mock_diff.return_value = {
                                            "frontmatter_updates": {
                                                "title": "改后的标题"
                                            },
                                            "replace_content": "改后的正文",
                                            "location_weather_required": False,
                                        }
                                        mock_edit.return_value = {"success": True}
                                        mock_search.return_value = {
                                            "success": True,
                                            "results": [
                                                {
                                                    "title": "测试日志",
                                                    "journal_route_path": "2026/03/test.md",
                                                    "highlight": "新的正文",
                                                }
                                            ],
                                            "total_found": 1,
                                            "time_ms": 5.0,
                                            "error": None,
                                            "query": "测试",
                                            "topic": "",
                                            "date_from": "",
                                            "date_to": "",
                                        }

                                        client = TestClient(create_app())

                                        write_get = client.get("/write")
                                        assert write_get.status_code == 200
                                        csrf_token = write_get.cookies.get("csrf_token")
                                        assert csrf_token is not None

                                        write_post = client.post(
                                            "/write",
                                            data={
                                                "csrf_token": csrf_token,
                                                "content": "新的正文",
                                                "topic": "life",
                                                "date": "2026-03-22",
                                            },
                                            follow_redirects=False,
                                        )
                                        assert write_post.status_code == 303
                                        assert (
                                            write_post.headers["location"]
                                            == "/journal/2026/03/test.md"
                                        )

                                        journal_get = client.get(
                                            "/journal/2026/03/test.md"
                                        )
                                        assert journal_get.status_code == 200
                                        assert "测试日志" in journal_get.text

                                        edit_get = client.get(
                                            "/journal/2026/03/test.md/edit"
                                        )
                                        assert edit_get.status_code == 200
                                        edit_csrf = edit_get.cookies.get("csrf_token")
                                        assert edit_csrf is not None

                                        edit_post = client.post(
                                            "/journal/2026/03/test.md/edit",
                                            data={
                                                "csrf_token": edit_csrf,
                                                "title": "改后的标题",
                                                "content": "改后的正文",
                                                "topic": "life",
                                            },
                                            follow_redirects=False,
                                        )
                                        assert edit_post.status_code == 303
                                        assert (
                                            "saved=1" in edit_post.headers["location"]
                                        )

                                        search_get = client.get("/search?q=测试")
                                        assert search_get.status_code == 200
                                        assert "测试日志" in search_get.text
