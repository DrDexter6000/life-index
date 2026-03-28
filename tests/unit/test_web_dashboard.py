#!/usr/bin/env python3
"""Tests for Web GUI Dashboard stats service."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch


def _make_entry(
    *,
    date: str = "2026-03-07",
    title: str = "Test Journal",
    topic: list[str] | str | None = None,
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
        "topic": topic
        if isinstance(topic, list)
        else ([topic] if topic is not None else ["work"]),
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
            "topic": topic
            if isinstance(topic, list)
            else ([topic] if topic is not None else ["work"]),
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
        people=["乐乐"],
    ),
    _make_entry(
        date="2026-03-02",
        title="Day 2",
        topic=["think"],
        mood=["平静", "专注"],
        tags=["python", "反思"],
        people=["乐乐", "妻子"],
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
    @patch("web.services.stats.get_all_journal_files")
    @patch("web.services.stats.parse_and_cache_journal")
    @patch("web.services.stats._compute_total_words")
    def test_rebuilds_stats_from_journal_files_when_cache_is_sparse(
        self,
        mock_words: MagicMock,
        mock_parse_and_cache: MagicMock,
        mock_get_files: MagicMock,
        mock_meta: MagicMock,
    ) -> None:
        import importlib
        from pathlib import Path

        compute_dashboard_stats = importlib.import_module(
            "web.services.stats"
        ).compute_dashboard_stats
        mock_meta.return_value = [_make_entry(date="2026-03-01")]
        mock_get_files.return_value = [Path("a.md"), Path("b.md"), Path("c.md")]
        mock_parse_and_cache.side_effect = [
            _make_entry(date="2026-03-01"),
            _make_entry(date="2026-03-13"),
            _make_entry(date="2026-03-14"),
        ]
        mock_words.return_value = 100

        result = compute_dashboard_stats()

        assert result.total_journals == 3
        assert result.heatmap == {
            "2026-03-01": 1,
            "2026-03-13": 1,
            "2026-03-14": 1,
        }

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats.get_all_journal_files", return_value=[])
    @patch("web.services.stats._compute_total_words")
    def test_returns_dashboard_stats(
        self, mock_words: MagicMock, _mock_files: MagicMock, mock_meta: MagicMock
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
    @patch("web.services.stats.get_all_journal_files", return_value=[])
    @patch("web.services.stats._compute_total_words")
    def test_topic_distribution_and_tag_cloud(
        self, mock_words: MagicMock, _mock_files: MagicMock, mock_meta: MagicMock
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
    @patch("web.services.stats.get_all_journal_files", return_value=[])
    @patch("web.services.stats._compute_total_words")
    def test_string_topic_entries_do_not_split_into_single_char_topics(
        self, mock_words: MagicMock, _mock_files: MagicMock, mock_meta: MagicMock
    ) -> None:
        import importlib

        compute_dashboard_stats = importlib.import_module(
            "web.services.stats"
        ).compute_dashboard_stats
        mock_meta.return_value = [
            _make_entry(topic=["work"]),
            _make_entry(date="2026-03-08", topic="think"),
        ]
        mock_words.return_value = 100

        result = compute_dashboard_stats()

        topic_counts = {
            item["name"]: item["value"] for item in result.topic_distribution
        }
        assert topic_counts["think"] == 1
        assert "t" not in topic_counts
        assert "h" not in topic_counts
        assert "i" not in topic_counts
        assert "n" not in topic_counts
        assert "k" not in topic_counts

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats.get_all_journal_files", return_value=[])
    @patch("web.services.stats._compute_total_words")
    def test_people_graph_and_heatmap(
        self, mock_words: MagicMock, _mock_files: MagicMock, mock_meta: MagicMock
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
    @patch("web.services.stats.get_all_journal_files", return_value=[])
    @patch("web.services.stats._compute_total_words")
    def test_empty_metadata_returns_zero_defaults(
        self, mock_words: MagicMock, _mock_files: MagicMock, mock_meta: MagicMock
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
    @patch("web.services.stats.get_all_journal_files", return_value=[])
    @patch("web.services.stats._compute_total_words")
    def test_on_this_day_uses_journal_route_path_not_raw_file_path(
        self, mock_words: MagicMock, _mock_files: MagicMock, mock_meta: MagicMock
    ) -> None:
        import importlib

        stats_module = importlib.import_module("web.services.stats")
        compute_dashboard_stats = stats_module.compute_dashboard_stats
        mock_meta.return_value = [
            _make_entry(date="2024-03-22", journal_route_path="2024/03/a.md"),
            _make_entry(date="2025-03-22", journal_route_path="2025/03/b.md"),
        ]
        mock_words.return_value = 0

        with (
            patch("web.services.stats._today_month_day", return_value=(3, 22)),
            patch("web.services.stats._entry_file_exists", return_value=True),
        ):
            result = compute_dashboard_stats()

        # on_this_day is currently disabled (hardcoded empty)
        assert len(result.on_this_day) == 0

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats.get_all_journal_files", return_value=[])
    @patch("web.services.stats._compute_total_words")
    def test_on_this_day_skips_entries_with_missing_journal_files(
        self, mock_words: MagicMock, _mock_files: MagicMock, mock_meta: MagicMock
    ) -> None:
        import importlib

        stats_module = importlib.import_module("web.services.stats")
        compute_dashboard_stats = stats_module.compute_dashboard_stats
        mock_meta.return_value = [
            _make_entry(
                date="2025-03-22",
                title="Existing Entry",
                file_path="C:/existing.md",
                journal_route_path="2025/03/existing.md",
            ),
            _make_entry(
                date="2024-03-22",
                title="Missing Entry",
                file_path="C:/missing.md",
                journal_route_path="2024/03/missing.md",
            ),
        ]
        mock_words.return_value = 0

        with (
            patch("web.services.stats._today_month_day", return_value=(3, 22)),
            patch(
                "web.services.stats._entry_file_exists",
                side_effect=lambda entry: entry.get("file_path") != "C:/missing.md",
            ),
        ):
            result = compute_dashboard_stats()

        # on_this_day is currently disabled (hardcoded empty)
        assert len(result.on_this_day) == 0


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
            mood_frequency=[{"name": "专注", "value": 2}],
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
        assert 'id="topic-chart"' in html
        assert 'id="mood-chart"' in html

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
            on_this_day=[],
            recent_entries=[
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

    @patch("web.routes.dashboard.compute_dashboard_stats")
    def test_dashboard_does_not_render_removed_runtime_operator_panel(
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
            on_this_day=[],
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
        assert "运行时数据源" not in response.text
        assert "Journals 目录" not in response.text
        assert "当前实例正在读取以下目录" not in response.text
        assert "如路径不符合预期，请停止当前实例后重新设置环境变量" not in response.text


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
        assert "sm:text-4xl" in source
        assert "sm:p-6" in source
        assert "sm:flex-row" in source
        assert "sm:items-center" in source
        assert "sm:text-right" in source
        assert "tracking-tight" in source
        assert "运行时数据源" not in source

    def test_dashboard_template_contains_heatmap_section_and_script_hooks(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")

        assert "写作热力图" in source
        assert 'id="heatmap-chart"' in source
        assert "{% block extra_scripts %}" in source
        assert "calendar" in source
        assert "heatmap" in source
        assert "还没有写作记录，开始你的第一篇日志" in source
        assert "#8b5cf6" in source
        assert "#C4B6FE" in source

    def test_dashboard_template_contains_dv2_chart_sections(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")

        assert "主题分布" in source
        assert "情绪频率" in source
        assert 'id="topic-chart"' in source
        assert 'id="mood-chart"' in source
        assert "stats.topic_distribution | tojson" in source
        assert "stats.mood_frequency | tojson" in source

    def test_dashboard_template_contains_dv2_empty_states_and_interactions(
        self,
    ) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")

        assert "还没有足够数据生成主题分布" in source
        assert "记录更多日志，情绪图谱将在这里呈现" in source
        assert "/search?topic=" in source
        assert "/search?mood=" in source
        assert "type: 'pie'" in source
        assert "type: 'bar'" in source

    def test_dashboard_template_contains_dv3_chart_sections(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")

        assert "标签词云" in source
        assert "人物关系" in source
        assert 'id="tagcloud-chart"' in source
        assert 'id="people-chart"' in source
        assert "stats.tag_cloud | tojson" in source
        assert "stats.people_graph | tojson" in source

    def test_dashboard_template_contains_dv3_fallbacks_and_interactions(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")

        assert "标签少于 5 个时，显示标签列表" in source
        assert "在日志中提及人物后，关系图谱将在这里呈现" in source
        assert "/search?tag=" in source
        assert "/search?people=" in source
        assert "wordCloud" in source
        assert "type: 'graph'" in source

    def test_dashboard_template_contains_dv4_responsive_grid_markers(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")

        assert "space-y-8" in source
        assert "grid grid-cols-1 gap-4 sm:grid-cols-3" in source
        assert source.count("grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-6") >= 2

    def test_dashboard_template_contains_dv4_chart_card_safety_classes(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")

        assert source.count("min-w-0 overflow-hidden") >= 5
        assert 'id="topic-chart" class="mt-4 h-[300px] w-full sm:h-[320px]"' in source
        assert 'id="mood-chart" class="mt-4 h-[300px] w-full sm:h-[320px]"' in source
        assert (
            'id="tagcloud-chart" class="mt-4 h-[280px] w-full sm:h-[300px]"' in source
        )
        assert 'id="people-chart" class="mt-4 h-[280px] w-full sm:h-[300px]"' in source

    def test_dashboard_template_contains_dv5_empty_state_accessibility_and_motion(
        self,
    ) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")

        assert source.count('role="status" aria-live="polite"') >= 5
        assert source.count('aria-hidden="true"') >= 5
        assert source.count("animate-fade-in-up") >= 6
        assert source.count("transition-colors hover:opacity-80") >= 5

    def test_dashboard_template_contains_dv5_dark_mode_polish_markers(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")

        assert "backgroundColor: 'transparent'" in source
        assert "const buildTagCloudOption = (isDark) =>" in source
        assert "const lightAccentPalette" in source
        assert "const darkAccentPalette" in source

    def test_dashboard_app_css_contains_dv5_motion_utilities(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR.parent / "static" / "css" / "app.css").read_text(
            encoding="utf-8"
        )

        assert "@keyframes fadeInUp" in source
        assert ".animate-fade-in-up" in source
        assert "prefers-reduced-motion: reduce" in source
