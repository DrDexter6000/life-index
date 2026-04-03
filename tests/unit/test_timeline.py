#!/usr/bin/env python3
"""Runtime behavior tests for timeline command."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.timeline.core import run_timeline


def _write_journal(
    base_dir: Path,
    *,
    date: str,
    title: str,
    topic: str,
    abstract: str,
    mood: str,
    filename: str,
) -> None:
    year, month, _ = date.split("-")
    journal_dir = base_dir / year / month
    journal_dir.mkdir(parents=True, exist_ok=True)
    (journal_dir / filename).write_text(
        (
            "---\n"
            f'title: "{title}"\n'
            f"date: {date}T10:00:00\n"
            f'topic: ["{topic}"]\n'
            f'mood: ["{mood}"]\n'
            f'abstract: "{abstract}"\n'
            "---\n\n"
            f"# {title}\n\nBody for {title}\n"
        ),
        encoding="utf-8",
    )


class TestTimeline:
    def test_range_filter(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        journals_dir = tmp_path / "Journals"
        _write_journal(
            journals_dir,
            date="2026-01-05",
            title="Jan",
            topic="work",
            abstract="A",
            mood="focused",
            filename="life-index_2026-01-05_001.md",
        )
        _write_journal(
            journals_dir,
            date="2026-02-10",
            title="Feb",
            topic="work",
            abstract="B",
            mood="calm",
            filename="life-index_2026-02-10_001.md",
        )
        _write_journal(
            journals_dir,
            date="2026-03-10",
            title="Mar",
            topic="life",
            abstract="C",
            mood="happy",
            filename="life-index_2026-03-10_001.md",
        )
        monkeypatch.setattr("tools.timeline.core.JOURNALS_DIR", journals_dir)

        result = run_timeline(range_start="2026-01", range_end="2026-02")

        assert len(result["entries"]) == 2
        assert all(entry["date"] <= "2026-02-28" for entry in result["entries"])

    def test_chronological_order(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        journals_dir = tmp_path / "Journals"
        _write_journal(
            journals_dir,
            date="2026-03-10",
            title="Mar",
            topic="life",
            abstract="C",
            mood="happy",
            filename="life-index_2026-03-10_001.md",
        )
        _write_journal(
            journals_dir,
            date="2026-01-05",
            title="Jan",
            topic="work",
            abstract="A",
            mood="focused",
            filename="life-index_2026-01-05_001.md",
        )
        _write_journal(
            journals_dir,
            date="2026-02-10",
            title="Feb",
            topic="work",
            abstract="B",
            mood="calm",
            filename="life-index_2026-02-10_001.md",
        )
        monkeypatch.setattr("tools.timeline.core.JOURNALS_DIR", journals_dir)

        result = run_timeline(range_start="2026-01", range_end="2026-03")

        dates = [entry["date"] for entry in result["entries"]]
        assert dates == sorted(dates)

    def test_includes_abstract_and_mood(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        journals_dir = tmp_path / "Journals"
        _write_journal(
            journals_dir,
            date="2026-01-05",
            title="Jan",
            topic="work",
            abstract="Important abstract",
            mood="focused",
            filename="life-index_2026-01-05_001.md",
        )
        monkeypatch.setattr("tools.timeline.core.JOURNALS_DIR", journals_dir)

        result = run_timeline(range_start="2026-01", range_end="2026-01")

        assert result["entries"][0]["abstract"] == "Important abstract"
        assert result["entries"][0]["mood"] == ["focused"]

    def test_empty_range_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("tools.timeline.core.JOURNALS_DIR", journals_dir)

        result = run_timeline(range_start="2099-01", range_end="2099-12")

        assert result["entries"] == []

    def test_topic_filter(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        journals_dir = tmp_path / "Journals"
        _write_journal(
            journals_dir,
            date="2026-01-05",
            title="Work entry",
            topic="work",
            abstract="Important abstract",
            mood="focused",
            filename="life-index_2026-01-05_001.md",
        )
        _write_journal(
            journals_dir,
            date="2026-01-06",
            title="Life entry",
            topic="life",
            abstract="Another abstract",
            mood="calm",
            filename="life-index_2026-01-06_001.md",
        )
        monkeypatch.setattr("tools.timeline.core.JOURNALS_DIR", journals_dir)

        result = run_timeline(range_start="2026-01", range_end="2026-01", topic="work")

        assert len(result["entries"]) == 1
        assert result["entries"][0]["title"] == "Work entry"
