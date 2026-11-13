#!/usr/bin/env python3
"""Unit tests for tools.generate_index Index Tree rebuild and generation."""

from pathlib import Path
import json
import sys

import pytest

from tools.generate_index import (
    collect_year_journals,
    generate_root_index,
    generate_yearly_index,
    rebuild_index_tree,
)


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


class TestGenerateIndexCliAllMonths:
    def test_all_months_without_year_generates_every_month_with_journals(
        self, sandbox: Path, monkeypatch, capsys
    ) -> None:
        from tools.generate_index import __main__ as cli

        journals_dir = sandbox / "Journals"
        _write_journal(journals_dir, "2025-12-01", "december entry")
        _write_journal(journals_dir, "2026-03-14", "march entry")
        (journals_dir / "reports").mkdir(parents=True)

        calls: list[tuple[int, int, bool]] = []

        def fake_generate_monthly_abstract(year: int, month: int, dry_run: bool) -> dict:
            calls.append((year, month, dry_run))
            return {
                "type": "monthly",
                "year": year,
                "month": month,
                "updated": True,
                "journal_count": 1,
                "message": f"generated {year}-{month:02d}",
            }

        monkeypatch.setattr(cli, "generate_monthly_abstract", fake_generate_monthly_abstract)
        monkeypatch.setattr(
            sys,
            "argv",
            ["life-index generate-index", "--all-months", "--json"],
        )

        cli.main()

        payload = json.loads(capsys.readouterr().out)
        assert calls == [(2025, 12, False), (2026, 3, False)]
        monthly = [item for item in payload if item.get("type") == "monthly"]
        assert [(item["year"], item["month"]) for item in monthly] == [(2025, 12), (2026, 3)]
        assert payload[-1]["type"] == "index-b"
        assert payload[-1]["success"] is True


# The one date rule for the generated indexes: a fragment whose frontmatter
# date is missing or malformed still appears under the day the shared rule
# gives (here: the file-name day 2026-03-11), not under ``--``.
SHAPE_DAY = "2026-03-11"

# shape name -> (seq, exact file bytes)
DATE_SHAPES: dict[str, tuple[str, bytes]] = {
    "no_frontmatter": ("001", "no-frontmatter shape body\n".encode()),
    "date_digit_run_on": (
        "002",
        "---\ntitle: Digit Run On\ndate: 20260311\n---\n\nbody\n".encode(),
    ),
    "date_list": (
        "003",
        "---\ntitle: List Date\ndate: [2026]\n---\n\nbody\n".encode(),
    ),
    "date_tz_datetime": (
        "004",
        ("---\ntitle: Tz Datetime\ndate: 2026-03-11T19:43:02+08:00\n---\n\nbody\n").encode(),
    ),
}

# The row label each shape's entry shows in the month index table: the
# verbatim title, or the display label (first body line) when absent.
SHAPE_ROW_TITLES: dict[str, str] = {
    "no_frontmatter": "no-frontmatter shape body",
    "date_digit_run_on": "Digit Run On",
    "date_list": "List Date",
    "date_tz_datetime": "Tz Datetime",
}


def _write_shape_month(journals_dir: Path) -> None:
    """One month holding every shape on 2026-03-11 between two dated neighbours."""
    month_dir = journals_dir / "2026" / "03"
    month_dir.mkdir(parents=True, exist_ok=True)
    (month_dir / "life-index_2026-03-10_001.md").write_text(
        "---\ntitle: Neighbour Before\ndate: 2026-03-10\n---\n\nbody\n",
        encoding="utf-8",
    )
    (month_dir / "life-index_2026-03-12_001.md").write_text(
        "---\ntitle: Neighbour After\ndate: 2026-03-12\n---\n\nbody\n",
        encoding="utf-8",
    )
    for seq, payload in DATE_SHAPES.values():
        (month_dir / f"life-index_2026-03-11_{seq}.md").write_bytes(payload)


class TestGeneratedIndexDateRule:
    def test_month_index_dates_each_shape_by_the_shared_rule(self, sandbox: Path):
        from tools.generate_index import generate_monthly_index

        _write_shape_month(sandbox / "Journals")

        result = generate_monthly_index(year=2026, month=3)

        assert result["success"] is True
        content = (sandbox / "Journals" / "2026" / "03" / "index_2026-03.md").read_text(
            encoding="utf-8"
        )
        before = content.index("| 03-10 | [Neighbour Before]")
        after = content.index("| 03-12 | [Neighbour After]")
        for shape, title in SHAPE_ROW_TITLES.items():
            seq = DATE_SHAPES[shape][0]
            row = f"| 03-11 | [{title}](life-index_2026-03-11_{seq}.md) |"
            assert row in content, shape
            assert before < content.index(row) < after, shape
        assert "| -- |" not in content

    def test_year_index_collector_dates_each_shape_by_the_shared_rule(self, sandbox: Path):
        _write_shape_month(sandbox / "Journals")

        journals = collect_year_journals(2026)

        by_file = {journal["file"]: journal for journal in journals}
        assert len(by_file) == 6
        for shape, (seq, _payload) in DATE_SHAPES.items():
            assert by_file[f"life-index_2026-03-11_{seq}.md"]["date"] == SHAPE_DAY, shape
        assert by_file["life-index_2026-03-10_001.md"]["date"] == "2026-03-10"
        assert by_file["life-index_2026-03-12_001.md"]["date"] == "2026-03-12"

    def test_yearly_index_counts_every_shape_fragment(self, sandbox: Path):
        _write_shape_month(sandbox / "Journals")

        result = generate_yearly_index(2026)

        assert result["success"] is True
        # _read_month_summary's fallback scan (no month index exists yet) must
        # keep all four shape fragments, each dated by the shared rule.
        assert result["journal_count"] == 6
