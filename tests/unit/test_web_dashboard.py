#!/usr/bin/env python3
"""Tests for Web GUI Dashboard stats service."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch


def _make_entry(
    *,
    date: str = "2026-03-07",
    title: str = "Test Journal",
    topic: list[str] | None = None,
    mood: list[str] | None = None,
    tags: list[str] | None = None,
    people: list[str] | None = None,
    abstract: str = "Test abstract",
    location: str | None = "Lagos, Nigeria",
    weather: str | None = "Sunny 28°C",
    project: str | None = None,
    file_path: str | None = None,
    journal_route_path: str | None = None,
) -> dict[str, Any]:
    if file_path is None:
        file_path = f"C:/Users/test/Documents/Life-Index/Journals/2026/03/life-index_{date}_001.md"
    if journal_route_path is None:
        journal_route_path = f"2026/03/life-index_{date}_001.md"
    return {
        "file_path": file_path,
        "path": file_path,
        "rel_path": f"Journals/{journal_route_path}",
        "journal_route_path": journal_route_path,
        "date": date,
        "title": title,
        "topic": topic or ["work"],
        "mood": mood or [],
        "tags": tags or [],
        "people": people or [],
        "abstract": abstract,
        "location": location,
        "weather": weather,
        "project": project,
        "metadata": {
            "date": date,
            "title": title,
            "topic": topic or ["work"],
            "mood": mood or [],
            "tags": tags or [],
            "people": people or [],
            "abstract": abstract,
            "location": location,
            "weather": weather,
            "project": project,
        },
    }


SAMPLE_ENTRIES: list[dict[str, Any]] = [
    _make_entry(
        date="2026-03-01",
        title="Day 1",
        topic=["work"],
        mood=["专注"],
        tags=["python"],
        people=["团团"],
    ),
    _make_entry(
        date="2026-03-02",
        title="Day 2",
        topic=["think"],
        mood=["平静", "专注"],
        tags=["python", "反思"],
        people=["团团", "妻子"],
    ),
    _make_entry(
        date="2026-03-03",
        title="Day 3",
        topic=["work", "create"],
        mood=["兴奋"],
        tags=["项目"],
        people=["妻子"],
    ),
]


class TestDashboardStatsDataclass:
    def test_dataclass_importable(self) -> None:
        import importlib
        import dataclasses

        DashboardStats = importlib.import_module("web.services.stats").DashboardStats
        assert dataclasses.is_dataclass(DashboardStats)

    def test_dataclass_has_all_fields(self) -> None:
        import importlib
        import dataclasses

        DashboardStats = importlib.import_module("web.services.stats").DashboardStats
        field_names = {f.name for f in dataclasses.fields(DashboardStats)}
        required = {
            "total_journals",
            "total_words",
            "longest_streak",
            "current_streak",
            "month_journals",
            "most_frequent_mood",
            "most_active_topic",
            "on_this_day",
            "milestone",
            "mood_frequency",
            "topic_distribution",
            "tag_cloud",
            "people_graph",
            "heatmap",
        }
        assert required.issubset(field_names)


class TestComputeDashboardStats:
    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_returns_dashboard_stats(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        import importlib

        stats_module = importlib.import_module("web.services.stats")
        DashboardStats = stats_module.DashboardStats
        compute_dashboard_stats = stats_module.compute_dashboard_stats
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 321

        result = compute_dashboard_stats()

        assert isinstance(result, DashboardStats)
        assert result.total_journals == 3
        assert result.total_words == 321

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_topic_distribution_and_tag_cloud(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        import importlib

        compute_dashboard_stats = importlib.import_module(
            "web.services.stats"
        ).compute_dashboard_stats
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 100

        result = compute_dashboard_stats()

        topic_names = {item["name"] for item in result.topic_distribution}
        tag_names = {item["name"] for item in result.tag_cloud}
        assert "work" in topic_names
        assert "python" in tag_names

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_people_graph_and_heatmap(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        import importlib

        compute_dashboard_stats = importlib.import_module(
            "web.services.stats"
        ).compute_dashboard_stats
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 100

        result = compute_dashboard_stats()

        assert result.people_graph["nodes"]
        assert result.people_graph["edges"]
        assert result.heatmap["2026-03-01"] == 1

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_empty_metadata_returns_zero_defaults(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        import importlib

        compute_dashboard_stats = importlib.import_module(
            "web.services.stats"
        ).compute_dashboard_stats
        mock_meta.return_value = []
        mock_words.return_value = 0

        result = compute_dashboard_stats()

        assert result.total_journals == 0
        assert result.total_words == 0
        assert result.on_this_day == []
        assert result.tag_cloud == []

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_on_this_day_uses_journal_route_path_not_raw_file_path(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        import importlib

        stats_module = importlib.import_module("web.services.stats")
        compute_dashboard_stats = stats_module.compute_dashboard_stats
        mock_meta.return_value = [
            _make_entry(date="2024-03-22", journal_route_path="2024/03/a.md"),
            _make_entry(date="2025-03-22", journal_route_path="2025/03/b.md"),
        ]
        mock_words.return_value = 0

        with patch("web.services.stats._today_month_day", return_value=(3, 22)):
            result = compute_dashboard_stats()

        assert len(result.on_this_day) == 2
        assert result.on_this_day[0]["journal_route_path"] == "2025/03/b.md"
        assert "file_path" not in result.on_this_day[0]


class TestDashboardRoute:
    @patch("web.routes.dashboard.compute_dashboard_stats")
    def test_dashboard_route_renders(self, mock_stats: MagicMock) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app
        from web.services.stats import DashboardStats

        mock_stats.return_value = DashboardStats(
            total_journals=3,
            total_words=321,
            longest_streak=3,
            current_streak=0,
            month_journals=3,
            most_frequent_mood="专注",
            most_active_topic="work",
            on_this_day=[],
            milestone=0,
            mood_frequency=[],
            topic_distribution=[{"name": "work", "value": 2}],
            tag_cloud=[{"name": "python", "value": 2}],
            people_graph={"nodes": [], "edges": []},
            heatmap={"2026-03-01": 1},
        )

        client = TestClient(create_app())
        response = client.get("/")

        assert response.status_code == 200
        html = response.text
        assert "仪表盘" in html
        assert "总日志数" in html
        assert "321" in html

    @patch("web.routes.dashboard.compute_dashboard_stats")
    def test_dashboard_template_uses_journal_route_path(
        self, mock_stats: MagicMock
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app
        from web.services.stats import DashboardStats

        mock_stats.return_value = DashboardStats(
            total_journals=1,
            total_words=10,
            longest_streak=1,
            current_streak=0,
            month_journals=1,
            most_frequent_mood="专注",
            most_active_topic="work",
            on_this_day=[
                {
                    "date": "2025-03-22",
                    "title": "Old Entry",
                    "abstract": "摘要",
                    "journal_route_path": "2025/03/old-entry.md",
                }
            ],
            milestone=0,
            mood_frequency=[],
            topic_distribution=[],
            tag_cloud=[],
            people_graph={"nodes": [], "edges": []},
            heatmap={},
        )

        client = TestClient(create_app())
        response = client.get("/")

        assert response.status_code == 200
        assert "/journal/2025/03/old-entry.md" in response.text
        assert "file_path" not in response.text


class TestDashboardTemplate:
    def test_dashboard_template_exists(self) -> None:
        from web.config import TEMPLATES_DIR

        assert (TEMPLATES_DIR / "dashboard.html").is_file()

    def test_dashboard_template_extends_base(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")
        assert '{% extends "base.html" %}' in source
        assert "{% block content %}" in source

    def test_dashboard_template_contains_key_sections(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")
        assert "总日志数" in source
        assert "那年今日" in source
        assert "连续记录" in source
        assert "sm:text-4xl" in source
        assert "sm:p-6" in source
        assert "sm:flex-row" in source
        assert "sm:items-center" in source
        assert "sm:text-right" in source
        assert "ring-1 ring-black/5" in source
        assert "tracking-tight" in source
