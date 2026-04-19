"""Tests for write_journal pending queue integration (Round 12 Phase 1 Task 1.2)."""

import json
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
    monkeypatch.setattr(paths, "get_journals_dir", lambda _j=data_dir / "Journals": _j, raising=False)


def _write_journal(data_dir: Path) -> dict:
    """Call write_journal core with minimal data."""
    from tools.write_journal.core import write_journal
    return write_journal({
        "title": "Test R12 Write",
        "content": "Content for round 12 pending test.",
        "date": "2026-03-15T10:00:00",
        "topic": ["life"],
    })


class TestWritePendingIntegration:
    def test_write_adds_pending(self, data_dir: Path):
        """After writing, pending_writes.json should contain the new journal path."""
        clear_pending()
        result = _write_journal(data_dir)
        assert result.get("success") or result.get("write_outcome") in ("success", "success_degraded")
        assert has_pending()
        pending = get_pending()
        assert len(pending) >= 1
        assert any("life-index_2026-03-15" in p for p in pending)

    def test_three_writes_three_pending(self, data_dir: Path):
        """Three sequential writes should produce 3 pending entries."""
        clear_pending()
        for i in range(3):
            from tools.write_journal.core import write_journal
            write_journal({
                "title": f"Test {i}",
                "content": f"Content {i}",
                "date": f"2026-03-{15+i}T10:00:00",
                "topic": ["life"],
            })
        assert len(get_pending()) == 3
