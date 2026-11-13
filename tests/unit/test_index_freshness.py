"""Tests for index_freshness module (Round 12 Phase 3 Task 3.1).

Freshness is now decided by per-fragment ``(mtime, size)`` signatures
(``fts_update.inspect_fts_index``), not by manifest row counts. These tests
pin the signature rule: a live fragment is fresh only with an FTS row and a
matching signature row, and any vanished row keeps the index stale.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from tools.lib.index_freshness import check_full_freshness
from tools.lib.index_manifest import IndexManifest, write_manifest
from tools.lib.pending_writes import mark_pending


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    """Isolate paths and pending queue to tmp_path."""
    import tools.lib.pending_writes as pw_mod

    idx = tmp_path / ".index"
    idx.mkdir(parents=True)
    (tmp_path / "Journals" / "2026" / "03").mkdir(parents=True)

    monkeypatch.setattr(pw_mod, "get_index_dir", lambda: idx)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))


def _write_journal(tmp_path: Path, name: str = "life-index_2026-03-04_001.md") -> Path:
    journal = tmp_path / "Journals" / "2026" / "03" / name
    journal.write_text(
        "---\ntitle: test\ndate: 2026-03-04\ntopic: work\n---\n\nbody\n",
        encoding="utf-8",
    )
    return journal


def _seed_index(tmp_path: Path, expected: int = 1) -> Path:
    from tools.lib.search_index import update_index

    result = update_index(incremental=False)
    assert result["success"] is True, result.get("error")
    assert result["total"] == expected
    return tmp_path / ".index"


def _write_manifest(index_dir: Path, *, partial: bool = False) -> None:
    write_manifest(
        IndexManifest(
            fts_count=1,
            vector_count=0,
            file_count=1,
            fts_checksum="",
            vector_checksum="",
            build_timestamp="2026-04-18T12:00:00",
            build_version="2.0.0",
            partial=partial,
        ),
        index_dir,
    )


def _db(index_dir: Path) -> sqlite3.Connection:
    return sqlite3.connect(str(index_dir / "journals_fts.db"))


class TestSignatureFreshness:
    def test_signature_current_index_is_fresh(self, tmp_path: Path):
        _write_journal(tmp_path)
        index_dir = _seed_index(tmp_path)
        _write_manifest(index_dir)

        report = check_full_freshness(index_dir)

        assert report.fts_fresh is True
        assert report.vector_fresh is True
        assert report.overall_fresh is True
        assert report.issues == []

    def test_missing_fts_row_marks_stale(self, tmp_path: Path):
        """A matching signature without an FTS row is not fresh (R1)."""
        _write_journal(tmp_path)
        index_dir = _seed_index(tmp_path)
        _write_manifest(index_dir)

        conn = _db(index_dir)
        try:
            conn.execute("DELETE FROM journals")
            conn.commit()
        finally:
            conn.close()

        report = check_full_freshness(index_dir)

        assert report.fts_fresh is False
        assert report.overall_fresh is False
        assert any("fts_signature_mismatch" in issue for issue in report.issues)

    def test_changed_signature_marks_stale(self, tmp_path: Path):
        """An outside edit (same archive row count) is still a change (R2)."""
        journal = _write_journal(tmp_path)
        index_dir = _seed_index(tmp_path)
        _write_manifest(index_dir)

        journal.write_text(
            journal.read_text(encoding="utf-8")
            + "\n\noutside edit that changes both mtime and size\n",
            encoding="utf-8",
        )

        report = check_full_freshness(index_dir)

        assert report.fts_fresh is False
        assert any("fts_signature_mismatch" in issue for issue in report.issues)

    def test_vanished_file_marks_stale(self, tmp_path: Path):
        """A row for a deleted file is stale even when counts happen to match."""
        journal = _write_journal(tmp_path)
        index_dir = _seed_index(tmp_path)
        _write_manifest(index_dir)

        journal.unlink()

        report = check_full_freshness(index_dir)

        assert report.fts_fresh is False
        assert any("fts_signature_mismatch" in issue for issue in report.issues)

    def test_missing_stats_row_marks_stale(self, tmp_path: Path):
        _write_journal(tmp_path)
        index_dir = _seed_index(tmp_path)
        _write_manifest(index_dir)

        conn = _db(index_dir)
        try:
            conn.execute("DELETE FROM fts_file_stats")
            conn.commit()
        finally:
            conn.close()

        report = check_full_freshness(index_dir)

        assert report.fts_fresh is False
        assert any("fts_signature_mismatch" in issue for issue in report.issues)

    def test_no_manifest_marks_overall_stale(self, tmp_path: Path):
        """No manifest → overall_fresh=False (first install scenario)."""
        _write_journal(tmp_path)
        index_dir = _seed_index(tmp_path)

        report = check_full_freshness(index_dir)

        assert report.overall_fresh is False
        assert any("no_manifest" in issue.lower() for issue in report.issues)

    def test_pending_non_empty_marks_stale(self, tmp_path: Path):
        """Pending queue non-empty → overall_fresh=False."""
        _write_journal(tmp_path)
        index_dir = _seed_index(tmp_path)
        _write_manifest(index_dir)

        mark_pending("Journals/2026/03/test.md")

        report = check_full_freshness(index_dir)

        assert report.overall_fresh is False
        assert any("pending" in str(issue).lower() for issue in report.issues)

    def test_partial_manifest_marks_stale(self, tmp_path: Path):
        """Partial manifest → overall_fresh=False."""
        _write_journal(tmp_path)
        index_dir = _seed_index(tmp_path)
        _write_manifest(index_dir, partial=True)

        report = check_full_freshness(index_dir)

        assert report.overall_fresh is False
        assert any("partial" in str(issue).lower() for issue in report.issues)

    def test_no_fts_db_marks_stale(self, tmp_path: Path):
        index_dir = tmp_path / ".index"
        _write_manifest(index_dir)

        report = check_full_freshness(index_dir)

        assert report.fts_fresh is False
        assert any("no_fts_db" in issue for issue in report.issues)

    def test_report_is_json_serializable(self, tmp_path: Path):
        _write_journal(tmp_path)
        index_dir = _seed_index(tmp_path)
        _write_manifest(index_dir)

        report = check_full_freshness(index_dir)

        json_str = json.dumps(report.to_dict())
        assert "fts_fresh" in json_str
        assert "vector_fresh" in json_str
        assert "overall_fresh" in json_str
