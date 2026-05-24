#!/usr/bin/env python3
"""B-C narrow rework: focused test for pure temporal → date-only branch.

Tests that when a query consists solely of a temporal expression (e.g.
"四月份", "3月4号"), hierarchical_search returns all journal entries
within the parsed date range, sorted by freshness (date descending).
"""

from pathlib import Path

import pytest


def _write_journal(path: Path, *, title: str, date: str, body: str, topic: str = "work") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{title}"\ndate: {date}\ntopic: [{topic}]\n---\n\n{body}\n',
        encoding="utf-8",
    )


# ── Test: Chinese month name returns in-range journals ─────────────────


def test_chinese_month_name_returns_date_range_entries(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """'四月份' should return all April 2026 journals, not zero results."""
    tmp_path = isolated_data_dir
    journals_dir = tmp_path / "Journals"

    # Create journals in different months
    _write_journal(
        journals_dir / "2026" / "02" / "life-index_2026-02-15_001.md",
        title="February entry",
        date="2026-02-15",
        body="feb content",
    )
    _write_journal(
        journals_dir / "2026" / "04" / "life-index_2026-04-05_001.md",
        title="April entry A",
        date="2026-04-05",
        body="apr content A",
    )
    _write_journal(
        journals_dir / "2026" / "04" / "life-index_2026-04-20_001.md",
        title="April entry B",
        date="2026-04-20",
        body="apr content B",
    )
    _write_journal(
        journals_dir / "2026" / "05" / "life-index_2026-05-01_001.md",
        title="May entry",
        date="2026-05-01",
        body="may content",
    )

    from tools.search_journals.core import hierarchical_search

    # Pin anchor so "四月份" resolves to 2026-04
    monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", "2026-05-24")

    result = hierarchical_search(query="四月份", level=3, semantic=False, use_index=False)

    assert result["success"] is True
    assert result["total_found"] >= 2, f"Expected >=2 results, got {result['total_found']}"

    result_paths = [Path(r["path"]).name for r in result["merged_results"]]
    assert "life-index_2026-04-05_001.md" in result_paths
    assert "life-index_2026-04-20_001.md" in result_paths
    # February and May should NOT appear
    assert "life-index_2026-02-15_001.md" not in result_paths
    assert "life-index_2026-05-01_001.md" not in result_paths


# ── Test: Chinese month-day returns single-day journals ─────────────────


def test_chinese_month_day_returns_single_day_entries(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """'3月4号' should return journals on 2026-03-04."""
    tmp_path = isolated_data_dir
    journals_dir = tmp_path / "Journals"

    _write_journal(
        journals_dir / "2026" / "03" / "life-index_2026-03-04_001.md",
        title="March 4 entry",
        date="2026-03-04",
        body="mar4 content",
    )
    _write_journal(
        journals_dir / "2026" / "03" / "life-index_2026-03-05_001.md",
        title="March 5 entry",
        date="2026-03-05",
        body="mar5 content",
    )

    from tools.search_journals.core import hierarchical_search

    monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", "2026-05-24")

    result = hierarchical_search(query="3月4号", level=3, semantic=False, use_index=False)

    assert result["total_found"] >= 1, f"Expected >=1 results, got {result['total_found']}"
    result_paths = [Path(r["path"]).name for r in result["merged_results"]]
    assert "life-index_2026-03-04_001.md" in result_paths
    assert "life-index_2026-03-05_001.md" not in result_paths


# ── Test: ISO date still works ──────────────────────────────────────────


def test_iso_date_still_returns_results(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """'2026-02-20' should continue to return the matching journal."""
    tmp_path = isolated_data_dir
    journals_dir = tmp_path / "Journals"

    _write_journal(
        journals_dir / "2026" / "02" / "life-index_2026-02-20_001.md",
        title="Feb 20 entry",
        date="2026-02-20",
        body="feb20 content",
    )

    from tools.search_journals.core import hierarchical_search

    result = hierarchical_search(query="2026-02-20", level=3, semantic=False, use_index=False)

    assert result["total_found"] >= 1, f"Expected >=1 results, got {result['total_found']}"
    result_paths = [Path(r["path"]).name for r in result["merged_results"]]
    assert "life-index_2026-02-20_001.md" in result_paths
