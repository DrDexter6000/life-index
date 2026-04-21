"""
Unit tests for the stats command (Phase 1.9 CLI Followup).
"""

import json
import os
from pathlib import Path

import pytest

from tools.stats.core import compute_stats, _compute_streak


@pytest.fixture
def _seed_journals(isolated_data_dir: Path) -> Path:
    """Create sample journal files in the isolated data directory."""
    journals_dir = isolated_data_dir / "Journals"

    entries = [
        (
            "2026",
            "04",
            "life-index_2026-04-18_001.md",
            "title: Day 1\ndate: '2026-04-18'\ntopic: [work]\nmood: [calm]\n",
        ),
        (
            "2026",
            "04",
            "life-index_2026-04-19_001.md",
            "title: Day 2\ndate: '2026-04-19'\ntopic: [work, learn]\nmood: [happy]\n",
        ),
        (
            "2026",
            "04",
            "life-index_2026-04-19_002.md",
            "title: Day 2b\ndate: '2026-04-19'\ntopic: [health]\nmood: [calm, happy]\n",
        ),
        (
            "2026",
            "04",
            "life-index_2026-04-20_001.md",
            "title: Day 3\ndate: '2026-04-20'\ntopic: [life]\nmood: [calm]\n",
        ),
    ]

    for year, month, fname, fm_content in entries:
        d = journals_dir / year / month
        d.mkdir(parents=True, exist_ok=True)
        body = "Word " * 50  # 50 words
        content = f"---\n{fm_content}---\n\n# Entry\n\n{body}\n"
        (d / fname).write_text(content, encoding="utf-8")

    return journals_dir


class TestComputeStats:
    def test_empty_directory(self, isolated_data_dir: Path) -> None:
        result = compute_stats()
        assert result["totalJournals"] == 0
        assert result["totalWords"] == 0
        assert result["activeDays"] == 0
        assert result["streakDays"] == 0
        assert result["avgWordsPerDay"] == 0
        assert result["topics"] == []
        assert result["moods"] == []
        assert result["heatmap"] == []

    def test_with_journals(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        assert result["totalJournals"] == 4
        assert result["totalWords"] > 0
        assert result["activeDays"] == 3
        assert result["avgWordsPerDay"] > 0

    def test_original_fields_unchanged(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        assert isinstance(result["totalJournals"], int)
        assert isinstance(result["totalWords"], int)
        assert isinstance(result["activeDays"], int)
        assert isinstance(result["streakDays"], int)
        assert isinstance(result["avgWordsPerDay"], int)

    def test_contract_keys(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        expected_keys = {
            "totalJournals",
            "totalWords",
            "activeDays",
            "streakDays",
            "avgWordsPerDay",
            "topics",
            "moods",
            "heatmap",
        }
        assert set(result.keys()) == expected_keys


class TestTopics:
    def test_topics_aggregated(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        topics = result["topics"]
        topic_map = {t["name"]: t for t in topics}
        assert topic_map["work"]["count"] == 2
        assert topic_map["learn"]["count"] == 1
        assert topic_map["health"]["count"] == 1
        assert topic_map["life"]["count"] == 1

    def test_topics_have_color(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        for t in result["topics"]:
            assert "name" in t
            assert "count" in t
            assert "color" in t
            assert t["color"].startswith("#")

    def test_topics_celestial_colors(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        topic_map = {t["name"]: t for t in result["topics"]}
        assert topic_map["work"]["color"] == "#FFE792"
        assert topic_map["health"]["color"] == "#92FFB6"
        assert topic_map["life"]["color"] == "#CBD5E1"

    def test_topics_sorted_by_count(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        counts = [t["count"] for t in result["topics"]]
        assert counts == sorted(counts, reverse=True)

    def test_empty_topics(self, isolated_data_dir: Path) -> None:
        result = compute_stats()
        assert result["topics"] == []


class TestMoods:
    def test_moods_aggregated(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        moods = result["moods"]
        mood_map = {m["name"]: m for m in moods}
        assert mood_map["calm"]["count"] == 3
        assert mood_map["happy"]["count"] == 2

    def test_moods_no_color_field(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        for m in result["moods"]:
            assert set(m.keys()) == {"name", "count"}

    def test_moods_sorted_by_count(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        counts = [m["count"] for m in result["moods"]]
        assert counts == sorted(counts, reverse=True)

    def test_empty_moods(self, isolated_data_dir: Path) -> None:
        result = compute_stats()
        assert result["moods"] == []


class TestHeatmap:
    def test_heatmap_dates(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        heatmap = result["heatmap"]
        heatmap_map = {h["date"]: h["count"] for h in heatmap}
        assert heatmap_map["2026-04-18"] == 1
        assert heatmap_map["2026-04-19"] == 2
        assert heatmap_map["2026-04-20"] == 1

    def test_heatmap_sorted_by_date(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        dates = [h["date"] for h in result["heatmap"]]
        assert dates == sorted(dates)

    def test_heatmap_entry_format(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = compute_stats()
        for h in result["heatmap"]:
            assert "date" in h
            assert "count" in h
            assert isinstance(h["count"], int)

    def test_empty_heatmap(self, isolated_data_dir: Path) -> None:
        result = compute_stats()
        assert result["heatmap"] == []


class TestComputeStreak:
    def test_empty_dates(self) -> None:
        assert _compute_streak(set()) == 0

    def test_streak_ending_today(self) -> None:
        from datetime import date, timedelta

        today = date.today()
        dates = {(today - timedelta(days=i)).isoformat() for i in range(3)}
        assert _compute_streak(dates) == 3

    def test_streak_ending_yesterday(self) -> None:
        from datetime import date, timedelta

        yesterday = date.today() - timedelta(days=1)
        dates = {(yesterday - timedelta(days=i)).isoformat() for i in range(2)}
        assert _compute_streak(dates) == 2

    def test_no_recent_streak(self) -> None:
        dates = {"2020-01-01", "2020-01-02", "2020-01-03"}
        assert _compute_streak(dates) == 0


class TestStatsCLI:
    def test_json_output(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        """Simulate CLI invocation with --format json."""
        import subprocess

        result = subprocess.run(
            ["python", "-m", "tools.stats", "--format", "json"],
            capture_output=True,
            text=True,
            env={**os.environ, "LIFE_INDEX_DATA_DIR": str(isolated_data_dir)},
            cwd=str(Path(__file__).parent.parent.parent),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "totalJournals" in data
        assert "topics" in data
        assert "moods" in data
        assert "heatmap" in data

    def test_human_readable_output(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        import subprocess

        result = subprocess.run(
            ["python", "-m", "tools.stats"],
            capture_output=True,
            text=True,
            env={**os.environ, "LIFE_INDEX_DATA_DIR": str(isolated_data_dir)},
            cwd=str(Path(__file__).parent.parent.parent),
        )
        assert result.returncode == 0
        assert "Total Journals" in result.stdout
