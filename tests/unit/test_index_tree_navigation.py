#!/usr/bin/env python3
"""Unit tests for tools.generate_index.navigation - Index Tree enumeration prototype."""

import os
import time
from pathlib import Path

import pytest

from tools.generate_index.navigation import (
    IndexNode,
    build_month_node_ref,
    check_index_tree_freshness,
    enumerate_index_nodes,
    index_node_ref_for_date,
    index_node_refs_for_range,
)


def _write_journal(
    path: Path,
    *,
    title: str = "Test",
    date: str = "2026-03-01",
    topic: str = "work",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{title}"\ndate: {date}\ntopic: [{topic}]\n---\n\n{title} body\n',
        encoding="utf-8",
    )


def _write_index(path: Path, frontmatter_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n# Index\n",
        encoding="utf-8",
    )


def _patch_nav_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import tools.generate_index.navigation as nav_mod

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        nav_mod,
        "get_journals_dir",
        lambda _j=tmp_path / "Journals": _j,
        raising=False,
    )
    monkeypatch.setattr(
        nav_mod,
        "get_user_data_dir",
        lambda _t=tmp_path: _t,
        raising=False,
    )


class TestIndexNodeContract:
    def test_index_node_has_required_fields(self) -> None:
        node = IndexNode(
            node_id="root",
            level="root",
            path=Path("/tmp/INDEX.md"),
            relative_path="INDEX.md",
            year=None,
            month=None,
            entry_count=0,
            topics={},
            date_range="",
            has_index=False,
            freshness="empty",
        )
        assert node.node_id == "root"
        assert node.level == "root"
        assert node.entry_count == 0
        assert node.freshness == "empty"

    def test_index_node_month_has_year_and_month(self) -> None:
        node = IndexNode(
            node_id="month:2026-03",
            level="month",
            path=Path("/tmp/Journals/2026/03/index_2026-03.md"),
            relative_path="Journals/2026/03/index_2026-03.md",
            year=2026,
            month=3,
            entry_count=5,
            topics={"work": 3, "life": 2},
            date_range="2026-03",
            has_index=True,
            freshness="fresh",
        )
        assert node.year == 2026
        assert node.month == 3

    def test_index_node_to_dict(self) -> None:
        node = IndexNode(
            node_id="year:2026",
            level="year",
            path=Path("/tmp/Journals/2026/index_2026.md"),
            relative_path="Journals/2026/index_2026.md",
            year=2026,
            month=None,
            entry_count=10,
            topics={"work": 7, "life": 3},
            date_range="2026",
            has_index=True,
            freshness="fresh",
        )
        d = node.to_dict()
        assert d["node_id"] == "year:2026"
        assert d["level"] == "year"
        assert d["entry_count"] == 10
        assert d["path"] == str(node.path)
        assert d["relative_path"] == "Journals/2026/index_2026.md"


class TestEnumerateRoot:
    def test_empty_data_dir_returns_root_node_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        nodes = enumerate_index_nodes(level="root")
        assert len(nodes) == 1
        assert nodes[0].node_id == "root"
        assert nodes[0].level == "root"
        assert nodes[0].entry_count == 0
        assert nodes[0].freshness == "empty"
        assert nodes[0].has_index is False

    def test_root_with_index_file_and_journals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            title="A",
            date="2026-03-01",
        )
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-02_001.md",
            title="B",
            date="2026-03-02",
        )
        _write_index(
            tmp_path / "INDEX.md",
            ["total_entries: 2", 'date_range: "2026-01 - 2026-03"'],
        )
        nodes = enumerate_index_nodes(level="root")
        assert len(nodes) == 1
        root = nodes[0]
        assert root.entry_count == 2
        assert root.has_index is True
        assert root.freshness == "fresh"

    def test_root_stale_when_index_older_than_journals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_index(
            tmp_path / "INDEX.md",
            ["total_entries: 1", 'date_range: "2026-01 - 2026-03"'],
        )
        idx_path = tmp_path / "INDEX.md"
        old_mtime = time.time() - 3600
        os.utime(idx_path, (old_mtime, old_mtime))

        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            title="A",
            date="2026-03-01",
        )

        nodes = enumerate_index_nodes(level="root")
        assert len(nodes) == 1
        assert nodes[0].freshness == "stale"


class TestEnumerateYear:
    def test_single_year_with_journals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "01" / "life-index_2026-01-15_001.md",
            title="Jan",
            date="2026-01-15",
        )
        _write_journal(
            j_dir / "2026" / "02" / "life-index_2026-02-15_001.md",
            title="Feb",
            date="2026-02-15",
        )
        nodes = enumerate_index_nodes(level="year")
        assert len(nodes) == 1
        y = nodes[0]
        assert y.node_id == "year:2026"
        assert y.year == 2026
        assert y.month is None
        assert y.entry_count == 2
        assert y.level == "year"

    def test_multiple_years(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2025" / "12" / "life-index_2025-12-01_001.md",
            title="Dec25",
            date="2025-12-01",
        )
        _write_journal(
            j_dir / "2026" / "01" / "life-index_2026-01-15_001.md",
            title="Jan26",
            date="2026-01-15",
        )
        nodes = enumerate_index_nodes(level="year")
        ids = [n.node_id for n in nodes]
        assert "year:2025" in ids
        assert "year:2026" in ids
        assert len(nodes) == 2

    def test_year_freshness_missing_index(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            title="A",
            date="2026-03-01",
        )
        nodes = enumerate_index_nodes(level="year")
        assert len(nodes) == 1
        assert nodes[0].has_index is False
        assert nodes[0].freshness == "missing_index"


class TestEnumerateMonth:
    def test_month_nodes_with_entry_counts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            title="A",
            date="2026-03-01",
        )
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-02_001.md",
            title="B",
            date="2026-03-02",
            topic="life",
        )
        _write_journal(
            j_dir / "2026" / "04" / "life-index_2026-04-01_001.md",
            title="C",
            date="2026-04-01",
        )
        nodes = enumerate_index_nodes(level="month")
        by_id = {n.node_id: n for n in nodes}
        assert "month:2026-03" in by_id
        assert "month:2026-04" in by_id
        assert by_id["month:2026-03"].entry_count == 2
        assert by_id["month:2026-03"].topics == {"work": 1, "life": 1}
        assert by_id["month:2026-04"].entry_count == 1

    def test_month_freshness_fresh(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            title="A",
            date="2026-03-01",
        )
        _write_index(
            j_dir / "2026" / "03" / "index_2026-03.md",
            [
                "year: 2026",
                "month: 3",
                "entries: 1",
                "topics: {work: 1}",
                'date_range: "2026-03"',
            ],
        )
        nodes = enumerate_index_nodes(level="month")
        assert len(nodes) == 1
        assert nodes[0].freshness == "fresh"
        assert nodes[0].has_index is True

    def test_month_stale_when_index_older_than_journals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            title="A",
            date="2026-03-01",
        )
        idx_path = j_dir / "2026" / "03" / "index_2026-03.md"
        _write_index(
            idx_path,
            [
                "year: 2026",
                "month: 3",
                "entries: 1",
                'date_range: "2026-03"',
            ],
        )
        old_mtime = time.time() - 3600
        os.utime(idx_path, (old_mtime, old_mtime))

        nodes = enumerate_index_nodes(level="month")
        assert len(nodes) == 1
        assert nodes[0].freshness == "stale"

    def test_month_empty_when_no_journals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        (tmp_path / "Journals" / "2026" / "03").mkdir(parents=True)
        nodes = enumerate_index_nodes(level="month")
        month_03 = [n for n in nodes if n.node_id == "month:2026-03"]
        assert len(month_03) == 0

    def test_month_node_date_range(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "01" / "life-index_2026-01-10_001.md",
            title="A",
            date="2026-01-10",
        )
        nodes = enumerate_index_nodes(level="month")
        assert len(nodes) == 1
        assert nodes[0].date_range == "2026-01"


class TestEnumerateAll:
    def test_all_returns_root_year_and_month_nodes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            title="A",
            date="2026-03-01",
        )
        _write_journal(
            j_dir / "2026" / "04" / "life-index_2026-04-01_001.md",
            title="B",
            date="2026-04-01",
        )
        nodes = enumerate_index_nodes(level="all")
        levels = [n.level for n in nodes]
        assert "root" in levels
        assert "year" in levels
        assert "month" in levels

    def test_all_empty_data_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        nodes = enumerate_index_nodes(level="all")
        assert len(nodes) == 1
        assert nodes[0].level == "root"
        assert nodes[0].freshness == "empty"


class TestNodeIds:
    def test_node_ids_are_stable_and_logical(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2025" / "12" / "life-index_2025-12-01_001.md",
            title="Dec25",
            date="2025-12-01",
        )
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            title="Mar26",
            date="2026-03-01",
        )
        nodes = enumerate_index_nodes(level="all")
        ids = {n.node_id for n in nodes}
        assert "root" in ids
        assert "year:2025" in ids
        assert "year:2026" in ids
        assert "month:2025-12" in ids
        assert "month:2026-03" in ids


class TestTopicsAggregation:
    def test_month_topics_are_aggregated_from_journals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            title="A",
            date="2026-03-01",
            topic="work",
        )
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-02_001.md",
            title="B",
            date="2026-03-02",
            topic="life",
        )
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-03_001.md",
            title="C",
            date="2026-03-03",
            topic="work",
        )
        nodes = enumerate_index_nodes(level="month")
        m = nodes[0]
        assert m.topics == {"work": 2, "life": 1}

    def test_year_topics_roll_up_from_months(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "01" / "life-index_2026-01-01_001.md",
            title="Jan",
            date="2026-01-01",
            topic="work",
        )
        _write_journal(
            j_dir / "2026" / "02" / "life-index_2026-02-01_001.md",
            title="Feb",
            date="2026-02-01",
            topic="life",
        )
        nodes = enumerate_index_nodes(level="year")
        y = nodes[0]
        assert y.topics == {"work": 1, "life": 1}
        assert y.entry_count == 2


class TestInvalidLevel:
    def test_invalid_level_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="level must be"):
            enumerate_index_nodes(level="invalid")


class TestMonthNodeRef:
    def test_build_month_node_ref_pads_month(self) -> None:
        ref = build_month_node_ref("2026", "3")
        assert ref == {
            "type": "month",
            "node_id": "month:2026-03",
            "id": "Journals/2026/03",
            "path": "Journals/2026/03/index_2026-03.md",
        }

    def test_build_month_node_ref_rejects_invalid_month(self) -> None:
        assert build_month_node_ref("2026", "13") is None


class TestCheckIndexTreeFreshness:
    """T1: check_index_tree_freshness gate using enumerate_index_nodes."""

    def test_all_fresh_no_issues(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            date="2026-03-01",
        )
        _write_index(
            j_dir / "2026" / "03" / "index_2026-03.md",
            [
                "entries: 1",
                "topics: {work: 1}",
                'date_range: "2026-03"',
            ],
        )
        result = check_index_tree_freshness(level="month")
        assert result["status"] == "all_fresh"
        assert result["issues"] == []
        assert result["total_nodes"] >= 1

    def test_stale_node_reported(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        idx_path = j_dir / "2026" / "03" / "index_2026-03.md"
        _write_index(
            idx_path,
            ["entries: 1", 'date_range: "2026-03"'],
        )
        old_mtime = time.time() - 3600
        os.utime(idx_path, (old_mtime, old_mtime))
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            date="2026-03-01",
        )
        result = check_index_tree_freshness(level="month")
        assert result["status"] == "has_issues"
        assert len(result["issues"]) >= 1
        stale_ids = [i["node_id"] for i in result["issues"]]
        assert "month:2026-03" in stale_ids
        assert any(i["freshness"] == "stale" for i in result["issues"])

    def test_missing_index_reported(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            date="2026-03-01",
        )
        result = check_index_tree_freshness(level="month")
        assert result["status"] == "has_issues"
        assert len(result["issues"]) >= 1
        assert any(i["freshness"] == "missing_index" for i in result["issues"])

    def test_empty_tree_status(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        result = check_index_tree_freshness(level="all")
        assert result["status"] == "empty_tree"
        assert result["issues"] == []
        assert result["total_nodes"] >= 1

    def test_issue_structure_has_required_fields(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            date="2026-03-01",
        )
        result = check_index_tree_freshness(level="month")
        assert result["status"] == "has_issues"
        for issue in result["issues"]:
            assert "node_id" in issue
            assert "level" in issue
            assert "freshness" in issue
            assert "relative_path" in issue

    def test_empty_nodes_not_reported_as_issues(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_nav_roots(monkeypatch, tmp_path)
        j_dir = tmp_path / "Journals"
        _write_journal(
            j_dir / "2026" / "03" / "life-index_2026-03-01_001.md",
            date="2026-03-01",
        )
        _write_index(
            j_dir / "2026" / "03" / "index_2026-03.md",
            [
                "entries: 1",
                "topics: {work: 1}",
                'date_range: "2026-03"',
            ],
        )
        (j_dir / "2026" / "04").mkdir(parents=True)
        result = check_index_tree_freshness(level="month")
        assert result["status"] == "all_fresh"
        assert result["issues"] == []


class TestMonthNodeRefDualIdentity:
    """RED step 1: month refs must have stable dual identity — id (physical) + node_id (logical)."""

    def test_build_month_node_ref_has_node_id(self) -> None:
        ref = build_month_node_ref("2026", "3")
        assert ref is not None
        assert "node_id" in ref
        assert ref["node_id"] == "month:2026-03"

    def test_build_month_node_ref_preserves_id_as_physical_path(self) -> None:
        ref = build_month_node_ref("2026", "3")
        assert ref is not None
        assert ref["id"] == "Journals/2026/03"

    def test_build_month_node_ref_path_points_at_index_file(self) -> None:
        ref = build_month_node_ref("2026", "3")
        assert ref is not None
        assert ref["path"] == "Journals/2026/03/index_2026-03.md"

    def test_build_month_node_ref_type_is_month(self) -> None:
        ref = build_month_node_ref("2026", "12")
        assert ref is not None
        assert ref["type"] == "month"
        assert ref["node_id"] == "month:2026-12"

    def test_index_node_ref_for_date_has_node_id(self) -> None:
        ref = index_node_ref_for_date("2026-03-14")
        assert ref is not None
        assert "node_id" in ref
        assert ref["node_id"] == "month:2026-03"

    def test_index_node_ref_for_date_preserves_existing_fields(self) -> None:
        ref = index_node_ref_for_date("2025-11-20")
        assert ref is not None
        assert ref["type"] == "month"
        assert ref["id"] == "Journals/2025/11"
        assert ref["path"] == "Journals/2025/11/index_2025-11.md"
        assert ref["node_id"] == "month:2025-11"

    def test_existing_test_compatibility_with_node_id(self) -> None:
        ref = build_month_node_ref("2026", "3")
        assert ref is not None
        assert ref["type"] == "month"
        assert ref["id"] == "Journals/2026/03"
        assert ref["path"] == "Journals/2026/03/index_2026-03.md"
        assert ref["node_id"] == "month:2026-03"


class TestIndexNodeRefsForRange:
    """RED step 3: index_node_refs_for_range returns inclusive month refs for a date range."""

    def test_same_month_single_ref(self) -> None:
        refs = index_node_refs_for_range("2026-03-01", "2026-03-31")
        assert len(refs) == 1
        assert refs[0]["node_id"] == "month:2026-03"

    def test_cross_month_range(self) -> None:
        refs = index_node_refs_for_range("2026-01-15", "2026-04-10")
        node_ids = [r["node_id"] for r in refs]
        assert "month:2026-01" in node_ids
        assert "month:2026-02" in node_ids
        assert "month:2026-03" in node_ids
        assert "month:2026-04" in node_ids
        assert len(refs) == 4

    def test_cross_year_range(self) -> None:
        refs = index_node_refs_for_range("2025-11-01", "2026-02-28")
        node_ids = [r["node_id"] for r in refs]
        assert "month:2025-11" in node_ids
        assert "month:2025-12" in node_ids
        assert "month:2026-01" in node_ids
        assert "month:2026-02" in node_ids
        assert len(refs) == 4

    def test_deterministic_chronological_ordering(self) -> None:
        refs = index_node_refs_for_range("2025-10-01", "2026-03-31")
        node_ids = [r["node_id"] for r in refs]
        assert node_ids == [
            "month:2025-10",
            "month:2025-11",
            "month:2025-12",
            "month:2026-01",
            "month:2026-02",
            "month:2026-03",
        ]

    def test_reversed_range_returns_empty(self) -> None:
        refs = index_node_refs_for_range("2026-03-31", "2026-01-01")
        assert refs == []

    def test_invalid_date_returns_empty(self) -> None:
        refs = index_node_refs_for_range("not-a-date", "2026-03-01")
        assert refs == []

    def test_none_inputs_return_empty(self) -> None:
        refs = index_node_refs_for_range(None, "2026-03-01")
        assert refs == []
        refs2 = index_node_refs_for_range("2026-03-01", None)
        assert refs2 == []

    def test_each_ref_has_full_shape(self) -> None:
        refs = index_node_refs_for_range("2026-01-01", "2026-01-31")
        assert len(refs) == 1
        ref = refs[0]
        assert ref["type"] == "month"
        assert "id" in ref
        assert "node_id" in ref
        assert "path" in ref
        assert ref["id"] == "Journals/2026/01"
        assert ref["node_id"] == "month:2026-01"
        assert ref["path"] == "Journals/2026/01/index_2026-01.md"

    def test_accepts_date_objects(self) -> None:
        import datetime

        refs = index_node_refs_for_range(
            datetime.date(2026, 1, 15),
            datetime.date(2026, 3, 20),
        )
        node_ids = [r["node_id"] for r in refs]
        assert node_ids == ["month:2026-01", "month:2026-02", "month:2026-03"]
