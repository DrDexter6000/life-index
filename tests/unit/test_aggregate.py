#!/usr/bin/env python3
"""Unit tests for tools.aggregate.core — TDD RED phase.

Required RED cases:
1. date-only journals + entry_time_after=22:00 → not_measurable, count=0, unknown_entries
2. explicit datetime metadata counts late entries deterministically
3. two late entries same day → unit=day counts once, unit=entry counts twice
4. journal_count grouped by unit=month returns deterministic buckets
5. term_presence=晚睡 returns matched paths with exactness=approximate + limitations
"""

import os
from pathlib import Path

import pytest

from tools.aggregate.core import run_aggregate


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch):
    """Create a temp data dir with Journals/ structure, set LIFE_INDEX_DATA_DIR."""
    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    return data_dir


def _write_journal(
    journals_dir: Path,
    date: str,
    content: str = "test content",
    *,
    filename_suffix: str = "001",
    extra_frontmatter: str = "",
) -> Path:
    """Helper: write a minimal journal file under Journals/YYYY/MM/."""
    year, month, _ = date.split("-")
    d = journals_dir / year / month
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"life-index_{date}_{filename_suffix}.md"
    fm = f"---\ndate: {date}\n{extra_frontmatter}---\n\n# Test\n\n{content}\n"
    path.write_text(fm, encoding="utf-8")
    return path


def _write_journal_with_time(
    journals_dir: Path,
    date: str,
    time_str: str,
    content: str = "test content",
    *,
    filename_suffix: str = "001",
) -> Path:
    """Write journal with ISO datetime in frontmatter."""
    year, month, _ = date.split("-")
    d = journals_dir / year / month
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"life-index_{date}_{filename_suffix}.md"
    fm = f"---\ndate: {date}T{time_str}\n---\n\n# Test\n\n{content}\n"
    path.write_text(fm, encoding="utf-8")
    return path


def _write_journal_with_separate_time(
    journals_dir: Path,
    date: str,
    time_str: str,
    content: str = "test content",
    *,
    filename_suffix: str = "001",
) -> Path:
    """Write journal with separate frontmatter time: field (not embedded in date)."""
    year, month, _ = date.split("-")
    d = journals_dir / year / month
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"life-index_{date}_{filename_suffix}.md"
    fm = f"---\ndate: {date}\ntime: {time_str}\n---\n" f"\n# Test\n\n{content}\n"
    path.write_text(fm, encoding="utf-8")
    return path


class TestRed1DateOnlyNotMeasurable:
    """RED case 1: date-only journals with entry_time_after=22:00 → not_measurable."""

    def test_date_only_returns_not_measurable(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal(journals_dir, "2026-03-14", "some entry")
        _write_journal(journals_dir, "2026-03-15", "another entry")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-15",
            unit="day",
            predicate="entry_time_after=22:00",
        )

        assert result["success"] is True
        assert result["result"]["exactness"] == "not_measurable"
        assert result["result"]["count"] == 0
        assert len(result["unknown_entries"]) == 2
        for entry in result["unknown_entries"]:
            assert "reason" in entry
            assert "no_time" in entry["reason"] or "no_time_field" in entry["reason"]


class TestRed2ExplicitDatetimeDeterministic:
    """RED case 2: explicit datetime metadata counts late entries deterministically."""

    def test_late_entry_counted(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal_with_time(journals_dir, "2026-03-14", "23:30:00", "late entry")
        _write_journal_with_time(journals_dir, "2026-03-15", "10:00:00", "early entry")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-15",
            unit="entry",
            predicate="entry_time_after=22:00",
        )

        assert result["success"] is True
        assert result["result"]["exactness"] == "exact"
        assert result["result"]["count"] == 1
        assert len(result["matched_entries"]) == 1
        assert "2026-03-14" in result["matched_entries"][0]


class TestRed2BSeparateTimeField:
    """Gate fix: separate frontmatter time: 23:30 must be counted as late."""

    def test_separate_time_field_counted(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal_with_separate_time(journals_dir, "2026-03-14", "23:30", "late entry")
        _write_journal_with_separate_time(journals_dir, "2026-03-15", "10:00", "early entry")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-15",
            unit="entry",
            predicate="entry_time_after=22:00",
        )

        assert result["success"] is True
        assert result["result"]["exactness"] == "exact"
        assert result["result"]["count"] == 1
        assert len(result["matched_entries"]) == 1
        assert "2026-03-14" in result["matched_entries"][0]
        assert len(result["unknown_entries"]) == 0

    def test_separate_time_hhmmss_format(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal_with_separate_time(journals_dir, "2026-03-14", "23:30:00", "late entry")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-14",
            unit="entry",
            predicate="entry_time_after=22:00",
        )

        assert result["success"] is True
        assert result["result"]["count"] == 1


class TestRed3DayVsEntryDeduplication:
    """RED case 3: two late entries same day → unit=day counts once, unit=entry counts twice."""

    def _setup_two_late_same_day(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal_with_time(
            journals_dir, "2026-03-14", "22:30:00", "late1", filename_suffix="001"
        )
        _write_journal_with_time(
            journals_dir, "2026-03-14", "23:00:00", "late2", filename_suffix="002"
        )
        return journals_dir

    def test_unit_day_deduplicates(self, sandbox: Path):
        self._setup_two_late_same_day(sandbox)
        result = run_aggregate(
            range_str="2026-03-14..2026-03-14",
            unit="day",
            predicate="entry_time_after=22:00",
        )
        assert result["success"] is True
        assert result["result"]["count"] == 1

    def test_unit_entry_counts_each(self, sandbox: Path):
        self._setup_two_late_same_day(sandbox)
        result = run_aggregate(
            range_str="2026-03-14..2026-03-14",
            unit="entry",
            predicate="entry_time_after=22:00",
        )
        assert result["success"] is True
        assert result["result"]["count"] == 2


class TestRed4JournalCountByMonth:
    """RED case 4: journal_count grouped by unit=month returns deterministic buckets."""

    def test_monthly_buckets(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal(journals_dir, "2026-01-05", "jan entry 1")
        _write_journal(journals_dir, "2026-01-20", "jan entry 2")
        _write_journal(journals_dir, "2026-02-03", "feb entry")
        _write_journal(journals_dir, "2026-03-10", "mar entry 1")
        _write_journal(journals_dir, "2026-03-15", "mar entry 2")
        _write_journal(journals_dir, "2026-03-28", "mar entry 3")

        result = run_aggregate(
            range_str="2026-01-01..2026-03-31",
            unit="month",
            predicate="journal_count",
        )

        assert result["success"] is True
        assert result["result"]["exactness"] == "exact"
        assert "buckets" in result
        buckets_by_key = {b["key"]: b for b in result["buckets"]}
        assert buckets_by_key["2026-01"]["count"] == 2
        assert buckets_by_key["2026-02"]["count"] == 1
        assert buckets_by_key["2026-03"]["count"] == 3
        for b in result["buckets"]:
            assert "evidence_paths" in b
            for p in b["evidence_paths"]:
                assert not os.path.isabs(p)


class TestRed5TermPresenceApproximate:
    """RED case 5: term_presence=晚睡 returns matched paths with exactness=approximate."""

    def test_term_presence_approximate(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal(journals_dir, "2026-03-14", "今天又晚睡了，得早点休息")
        _write_journal(journals_dir, "2026-03-15", "今天按时睡觉了")
        _write_journal(journals_dir, "2026-03-16", "加班到很晚，又是晚睡")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-16",
            unit="day",
            predicate="term_presence=晚睡",
        )

        assert result["success"] is True
        assert result["result"]["exactness"] == "approximate"
        assert result["result"]["count"] == 2
        assert len(result["matched_entries"]) == 2
        assert "limitations" in result
        assert any(
            "not behavior proof" in lim.lower() or "mention" in lim.lower()
            for lim in result["limitations"]
        )


class TestRedInvalidInputs:
    """Additional RED: invalid predicates/ranges return structured error JSON."""

    def test_invalid_predicate(self, sandbox: Path):
        result = run_aggregate(
            range_str="2026-01-01..2026-03-31",
            unit="day",
            predicate="nonexistent_predicate",
        )
        assert result["success"] is False

    def test_invalid_range_format(self, sandbox: Path):
        result = run_aggregate(
            range_str="invalid",
            unit="day",
            predicate="journal_count",
        )
        assert result["success"] is False

    def test_invalid_unit(self, sandbox: Path):
        result = run_aggregate(
            range_str="2026-01-01..2026-03-31",
            unit="decade",
            predicate="journal_count",
        )
        assert result["success"] is False


class TestOutputContract:
    """Verify JSON output contract fields per RFC-001 §8."""

    def test_output_has_all_required_fields(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal(journals_dir, "2026-03-14", "test")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-14",
            unit="day",
            predicate="journal_count",
        )

        required_fields = [
            "success",
            "query",
            "command",
            "metric",
            "unit",
            "range",
            "predicate",
            "result",
            "buckets",
            "matched_entries",
            "excluded_entries",
            "unknown_entries",
            "evidence_paths",
            "limitations",
            "performance",
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        assert result["command"] == "aggregate"
        assert result["unit"] == "day"
        assert "total_time_ms" in result["performance"]

    def test_no_absolute_paths_in_output(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal(journals_dir, "2026-03-14", "test")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-14",
            unit="day",
            predicate="journal_count",
        )

        def _check_paths(
            obj,
            path_fields=(
                "evidence_paths",
                "matched_entries",
                "excluded_entries",
            ),
        ):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in path_fields and isinstance(v, list):
                        for p in v:
                            if isinstance(p, str):
                                assert not os.path.isabs(p), f"Absolute path found: {p}"
                            elif isinstance(p, dict) and "path" in p:
                                assert not os.path.isabs(p["path"]), (
                                    f"Absolute path found: " f"{p['path']}"
                                )
                    elif isinstance(v, (dict, list)):
                        _check_paths(v, path_fields)
            elif isinstance(obj, list):
                for item in obj:
                    _check_paths(item, path_fields)

        _check_paths(result)

    def test_evidence_paths_use_forward_slashes(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal(journals_dir, "2026-03-14", "test")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-14",
            unit="day",
            predicate="journal_count",
        )

        for path in result.get("evidence_paths", []):
            assert "\\" not in path, f"Backslash in path: {path}"


class TestMixedTimeNotMeasurableCountZero:
    """Contract fix: mixed time data must return count=0 when not_measurable.

    When some entries have time and others don't, exactness is not_measurable.
    Per RFC §9.2.3 and API.md, not_measurable count is 0 by convention.
    matched_entries may still list known-late entries as evidence/lower-bound.
    """

    def test_mixed_time_count_is_zero_entry_unit(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal_with_time(journals_dir, "2026-03-14", "23:30:00", "late entry")
        _write_journal(journals_dir, "2026-03-15", "no time entry")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-15",
            unit="entry",
            predicate="entry_time_after=22:00",
        )

        assert result["success"] is True
        assert result["result"]["exactness"] == "not_measurable"
        assert result["result"]["count"] == 0
        assert len(result["matched_entries"]) >= 1
        assert "2026-03-14" in result["matched_entries"][0]
        assert len(result["unknown_entries"]) == 1
        assert "2026-03-15" in result["unknown_entries"][0]["path"]

    def test_mixed_time_count_is_zero_day_unit(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal_with_time(journals_dir, "2026-03-14", "23:30:00", "late entry")
        _write_journal(journals_dir, "2026-03-15", "no time entry")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-15",
            unit="day",
            predicate="entry_time_after=22:00",
        )

        assert result["success"] is True
        assert result["result"]["exactness"] == "not_measurable"
        assert result["result"]["count"] == 0
        assert len(result["matched_entries"]) >= 1
        assert len(result["unknown_entries"]) == 1


class TestTermPresenceCaseInsensitive:
    """Contract fix: term_presence uses case-insensitive substring matching."""

    def test_term_latin_case_insensitive(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal(journals_dir, "2026-03-14", "Late-Night coding session")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-14",
            unit="entry",
            predicate="term_presence=late-night",
        )

        assert result["success"] is True
        assert result["result"]["count"] == 1
        assert len(result["matched_entries"]) == 1


class TestEntityPresenceCaseInsensitive:
    """Contract fix: entity_presence matches aliases case-insensitively."""

    def test_entity_alias_case_insensitive(self, sandbox: Path):
        journals_dir = sandbox / "Journals"
        _write_journal(journals_dir, "2026-03-14", "LATE-NIGHT gaming session")

        graph_yaml = (
            "entities:\n"
            "  - id: sleep_habit\n"
            "    type: concept\n"
            "    primary_name: Sleep Habit\n"
            "    aliases:\n"
            "      - late-night\n"
        )
        (sandbox / "entity_graph.yaml").write_text(graph_yaml, encoding="utf-8")

        result = run_aggregate(
            range_str="2026-03-14..2026-03-14",
            unit="entry",
            predicate="entity_presence=sleep_habit",
        )

        assert result["success"] is True
        assert result["result"]["count"] == 1
        assert len(result["matched_entries"]) == 1
