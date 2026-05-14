#!/usr/bin/env python3
"""Unit tests for tools.generate_index Index Tree rebuild and generation."""

from pathlib import Path

import pytest

from tools.generate_index import generate_root_index, rebuild_index_tree


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    return data_dir


def _write_journal(journals_dir: Path, date: str, content: str = "test") -> Path:
    year, month, _ = date.split("-")
    d = journals_dir / year / month
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"life-index_{date}_001.md"
    fm = f"---\ndate: {date}\ntitle: Test\n---\n\n# Test\n\n{content}\n"
    path.write_text(fm, encoding="utf-8")
    return path


class TestRebuildIgnoresNonYearDirectories:
    """RED 1: rebuild_index_tree must skip non-numeric directories under Journals/.

    When a non-numeric directory exists alongside valid year directories,
    rebuild must silently ignore it rather than crash on int() conversion.
    The crash path is _count_topic_entries, which is triggered when by-topic/
    contains topic index files.
    """

    def test_rebuild_ignores_reports_directory(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal(journals_dir, "2026-03-14", "test entry")

        reports_dir = journals_dir / "reports"
        reports_dir.mkdir()
        (reports_dir / "summary.md").write_text("# Report\n", encoding="utf-8")

        by_topic = sandbox / "by-topic"
        by_topic.mkdir()
        (by_topic / "\u4e3b\u9898_work.md").write_text(
            "---\ntopic: work\n---\n\n# Work\n",
            encoding="utf-8",
        )

        result = rebuild_index_tree(dry_run=True)
        assert isinstance(result, dict)
        assert "errors" in result
        for error in result.get("errors", []):
            assert "reports" not in str(error).lower()
        assert result["monthly_indexes_rebuilt"] >= 0

    def test_root_generation_ignores_non_year_dir(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal(journals_dir, "2026-03-14", "test entry")

        (journals_dir / "archive").mkdir()

        by_topic = sandbox / "by-topic"
        by_topic.mkdir()
        (by_topic / "\u4e3b\u9898_life.md").write_text(
            "---\n---\n\n# Life\n",
            encoding="utf-8",
        )

        result = generate_root_index(dry_run=True)
        assert result["success"] is True
        assert result["journal_count"] >= 1
