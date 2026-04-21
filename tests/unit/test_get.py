"""
Unit tests for the get command (Phase 1.9 CLI Followup).
"""

import json
import os
from pathlib import Path

import pytest

from tools.get.core import get_journal


@pytest.fixture
def _seed_journals(isolated_data_dir: Path) -> Path:
    """Create sample journal files in the isolated data directory."""
    journals_dir = isolated_data_dir / "Journals"
    d = journals_dir / "2026" / "04"
    d.mkdir(parents=True, exist_ok=True)

    fm = (
        "---\n"
        "title: Test Entry\n"
        "date: '2026-04-19'\n"
        "location: Beijing\n"
        "weather: Sunny\n"
        "mood: [happy]\n"
        "tags: [work, thinking]\n"
        "entities: [someone]\n"
        "sentiment_score: 0.5\n"
        "themes: [growth]\n"
        "links: []\n"
        "attachments: []\n"
        "---\n\n"
        "# Test Entry\n\n"
        "This is the body content.\n"
    )
    (d / "life-index_2026-04-19_001.md").write_text(fm, encoding="utf-8")

    return journals_dir


class TestGetJournal:
    def test_existing_journal(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = get_journal("life-index_2026-04-19_001")
        assert result is not None
        assert result["id"] == "life-index_2026-04-19_001"
        assert result["title"] == "Test Entry"
        assert result["date"] == "2026-04-19"
        assert result["location"] == "Beijing"
        assert result["mood"] == ["happy"]
        assert result["tags"] == ["work", "thinking"]

    def test_nonexistent_journal(self, isolated_data_dir: Path) -> None:
        result = get_journal("nonexistent_2026-01-01_999")
        assert result is None

    def test_contract_keys(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = get_journal("life-index_2026-04-19_001")
        assert result is not None
        expected_keys = {
            "id",
            "title",
            "content",
            "date",
            "location",
            "mood",
            "weather",
            "tags",
            "entities",
            "sentiment_score",
            "themes",
            "links",
            "attachments",
            "word_count",
        }
        assert set(result.keys()) == expected_keys

    def test_content_has_body(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = get_journal("life-index_2026-04-19_001")
        assert result is not None
        assert "This is the body content" in result["content"]
        # Title line should NOT be in content
        assert "# Test Entry" not in result["content"]

    def test_word_count_positive(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        result = get_journal("life-index_2026-04-19_001")
        assert result is not None
        assert result["word_count"] > 0

    def test_empty_data_dir(self, isolated_data_dir: Path) -> None:
        result = get_journal("life-index_2026-04-19_001")
        assert result is None


class TestGetCLI:
    def test_json_output(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        import subprocess

        result = subprocess.run(
            ["python", "-m", "tools.get", "life-index_2026-04-19_001", "--format", "json"],
            capture_output=True,
            text=True,
            env={**os.environ, "LIFE_INDEX_DATA_DIR": str(isolated_data_dir)},
            cwd=str(Path(__file__).parent.parent.parent),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == "life-index_2026-04-19_001"

    def test_nonexistent_exit_code(self, isolated_data_dir: Path) -> None:
        import subprocess

        result = subprocess.run(
            ["python", "-m", "tools.get", "nonexistent_id", "--format", "json"],
            capture_output=True,
            text=True,
            env={**os.environ, "LIFE_INDEX_DATA_DIR": str(isolated_data_dir)},
            cwd=str(Path(__file__).parent.parent.parent),
        )
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "not found" in result.stdout.lower()

    def test_human_readable_output(self, isolated_data_dir: Path, _seed_journals: Path) -> None:
        import subprocess

        result = subprocess.run(
            ["python", "-m", "tools.get", "life-index_2026-04-19_001"],
            capture_output=True,
            text=True,
            env={**os.environ, "LIFE_INDEX_DATA_DIR": str(isolated_data_dir)},
            cwd=str(Path(__file__).parent.parent.parent),
        )
        assert result.returncode == 0
        assert "Title:" in result.stdout
        assert "Test Entry" in result.stdout
