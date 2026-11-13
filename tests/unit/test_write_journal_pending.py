"""Tests for write_journal pending queue integration (Round 12 Phase 1 Task 1.2).

Since the FTS write-through landed, a successful write no longer queues the
journal: its FTS row is already current (``fts_row=complete``) and
``mark_pending`` is recorded as ``skipped``. The pending queue is the
failure-repair path — it is used exactly when the FTS row write-through
failed, so the next search preflight can repair the index.
"""

import pytest
from pathlib import Path

from tools.lib.pending_writes import get_pending, clear_pending, has_pending


@pytest.fixture(autouse=True)
def _isolate_index(tmp_path: Path, monkeypatch):
    """Isolate pending_writes to tmp_path."""
    import tools.lib.pending_writes as pw_mod

    idx = tmp_path / ".index"
    idx.mkdir()
    monkeypatch.setattr(pw_mod, "get_index_dir", lambda: idx)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a data directory with Journals structure."""
    d = tmp_path / "Life-Index"
    (d / "Journals" / "2026" / "03").mkdir(parents=True)
    return d


@pytest.fixture(autouse=True)
def _override_data_dir(data_dir: Path, monkeypatch):
    """Override data dir for write tests via env var."""
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    import tools.lib.config as cfg
    import tools.lib.paths as paths

    monkeypatch.setattr(cfg, "get_user_data_dir", lambda _d=data_dir: _d, raising=False)
    monkeypatch.setattr(cfg, "get_journals_dir", lambda _j=data_dir / "Journals": _j, raising=False)
    monkeypatch.setattr(paths, "get_user_data_dir", lambda _d=data_dir: _d, raising=False)
    monkeypatch.setattr(
        paths, "get_journals_dir", lambda _j=data_dir / "Journals": _j, raising=False
    )


def _write_journal(data_dir: Path, date: str = "2026-03-15T10:00:00") -> dict:
    """Call write_journal core with minimal data."""
    from tools.write_journal.core import write_journal

    return write_journal(
        {
            "title": "Test R12 Write",
            "content": "Content for round 12 pending test.",
            "date": date,
            "topic": ["life"],
        }
    )


class TestWritePendingIntegration:
    def test_write_through_leaves_queue_empty(self, data_dir: Path):
        """A successful FTS write-through queues nothing and reports complete."""
        clear_pending()
        result = _write_journal(data_dir)
        assert result.get("success") or result.get("write_outcome") in (
            "success",
            "success_pending_confirmation",
        )
        fts_records = [r for r in result["side_effects"] if r["name"] == "fts_row"]
        assert [r["status"] for r in fts_records] == ["complete"]
        pending_records = [r for r in result["side_effects"] if r["name"] == "mark_pending"]
        assert [r["status"] for r in pending_records] == ["skipped"]
        assert result["index_status"] == "complete"
        assert not has_pending()
        assert get_pending() == []

    def test_fts_write_through_failure_queues_the_path(
        self,
        data_dir: Path,
        monkeypatch,
    ):
        """A failed write-through falls back to the durable pending queue."""
        import tools.write_journal.core as write_core

        clear_pending()
        monkeypatch.setattr(
            write_core,
            "upsert_fts_row",
            lambda *_args: (_ for _ in ()).throw(OSError("synthetic FTS persistence failure")),
        )

        result = _write_journal(data_dir)

        assert result["success"] is True
        assert result["write_outcome"] == "success_degraded"
        assert result["index_status"] == "degraded"
        assert has_pending()
        pending = get_pending()
        assert len(pending) >= 1
        assert any("life-index_2026-03-15" in p for p in pending)
        fts_records = [r for r in result["side_effects"] if r["name"] == "fts_row"]
        assert [r["status"] for r in fts_records] == ["failed"]
        assert fts_records[0]["recovery_strategy"] == "life-index index"
        pending_records = [r for r in result["side_effects"] if r["name"] == "mark_pending"]
        assert [r["status"] for r in pending_records] == ["queued"]

    def test_mark_pending_failure_cannot_report_complete_freshness(
        self,
        data_dir: Path,
        monkeypatch,
    ):
        """A queue write failure cannot claim queued or complete freshness."""
        import tools.write_journal.core as write_core

        clear_pending()
        monkeypatch.setattr(
            write_core,
            "upsert_fts_row",
            lambda *_args: (_ for _ in ()).throw(OSError("synthetic FTS persistence failure")),
        )
        monkeypatch.setattr(
            write_core,
            "mark_pending",
            lambda *_args: (_ for _ in ()).throw(OSError("synthetic pending persistence failure")),
        )

        result = _write_journal(data_dir)

        assert result["success"] is True
        assert result["write_outcome"] == "success_degraded"
        assert result["index_status"] == "degraded"
        assert get_pending() == []
        pending_records = [
            item for item in result["side_effects"] if item["name"] == "mark_pending"
        ]
        assert [item["status"] for item in pending_records] == ["failed"]
        assert "pending persistence failure" in pending_records[0]["error"]
        assert pending_records[0]["recovery_strategy"] == "life-index index --rebuild"

    def test_three_writes_leave_queue_empty(self, data_dir: Path):
        """Three sequential successful writes queue nothing."""
        clear_pending()
        for i in range(3):
            result = _write_journal(data_dir, date=f"2026-03-{15+i}T10:00:00")
            assert result["success"] is True
        assert get_pending() == []
