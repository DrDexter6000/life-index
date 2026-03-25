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
                                        assert write_post.status_code == 200
                                        assert "确认写入结果" in write_post.text
                                        assert (
                                            "/journal/2026/03/test.md"
                                            in write_post.text
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

    def test_regular_search_forwards_canonical_contract(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.search.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            with patch(
                "web.routes.search.search_journals_web", new_callable=AsyncMock
            ) as mock_search:
                provider = AsyncMock()
                mock_provider.return_value = provider
                mock_search.return_value = {
                    "success": True,
                    "results": [],
                    "total_found": 0,
                    "time_ms": 0.0,
                    "error": None,
                }

                client = TestClient(create_app())
                response = client.get("/search?q=测试&people=乐乐")

        assert response.status_code == 200
        mock_search.assert_awaited_once_with(
            query="测试",
            topic=None,
            date_from=None,
            date_to=None,
            mood=None,
            tags=None,
            people="乐乐",
            project=None,
            location=None,
            weather=None,
            semantic=True,
            provider=provider,
        )

    def test_edit_blocks_location_change_without_weather_integration(self) -> None:
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
                        mock_provider.return_value = AsyncMock()
                        mock_get_journal.return_value = {
                            "metadata": {
                                "title": "原标题",
                                "topic": ["life"],
                                "location": "Lagos",
                                "weather": "晴",
                            },
                            "raw_body": "原正文",
                            "attachments": [],
                            "journal_route_path": "2026/03/test.md",
                        }
                        mock_diff.return_value = {
                            "frontmatter_updates": {"location": "Abuja"},
                            "replace_content": None,
                            "location_weather_required": True,
                        }

                        client = TestClient(create_app())
                        get_response = client.get("/journal/2026/03/test.md/edit")
                        csrf_token = get_response.cookies.get("csrf_token")
                        assert csrf_token is not None
                        response = client.post(
                            "/journal/2026/03/test.md/edit",
                            data={
                                "csrf_token": csrf_token,
                                "title": "原标题",
                                "content": "原正文",
                                "location": "Abuja",
                                "weather": "",
                            },
                        )

        assert response.status_code == 200
        assert "请先查询天气或手动填写天气" in response.text
        mock_edit.assert_not_awaited()

    def test_ai_search_route_uses_single_canonical_ai_service_integration(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch(
            "web.routes.search.get_provider", new_callable=AsyncMock
        ) as mock_provider:
            with patch(
                "web.routes.search._derive_search_queries", new_callable=AsyncMock
            ) as mock_derive_queries:
                with patch(
                    "web.routes.search.search_ai_journals_web", new_callable=AsyncMock
                ) as mock_ai_search:
                    provider = AsyncMock()
                    mock_provider.return_value = provider
                    mock_derive_queries.return_value = ["睡眠不足", "凌晨", "晚睡"]
                    mock_ai_search.return_value = {
                        "success": True,
                        "results": [
                            {
                                "title": "睡眠不足早起验收编码成果",
                                "date": "2026-03-14",
                                "journal_route_path": "2026/03/life-index_2026-03-14_002.md",
                            }
                        ],
                        "total_found": 1,
                        "time_ms": 12.0,
                        "error": None,
                        "derived_queries": ["睡眠不足", "凌晨", "晚睡"],
                        "ai_summary": {
                            "state": "ready",
                            "summary": "最近 30 天有多天晚睡。",
                            "key_entries": [],
                            "time_span": "过去30天",
                        },
                    }

                    client = TestClient(create_app())
                    response = client.post(
                        "/api/search/ai",
                        data={"query": "过去30天我有哪几天是晚于十点之后睡觉的"},
                    )

        assert response.status_code == 200
        assert "AI 回答" in response.text
        assert "基于搜索到的 1 篇相关日志" in response.text
        mock_ai_search.assert_awaited_once()
