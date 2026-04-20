"""Tests for pending writes queue (Round 12 Phase 1 Task 1.1)."""

import json
import pytest
from pathlib import Path

from tools.lib.pending_writes import (
    mark_pending,
    get_pending,
    clear_pending,
    has_pending,
    _pending_file,
)


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    """Create an index directory for testing."""
    idx = tmp_path / ".index"
    idx.mkdir()
    return idx


@pytest.fixture(autouse=True)
def _override_index_dir(index_dir: Path, monkeypatch):
    """Override the get_index_dir getter for all tests."""
    import tools.lib.pending_writes as mod
    monkeypatch.setattr(mod, "get_index_dir", lambda: index_dir)


class TestMarkPending:
    def test_creates_pending_file(self, index_dir: Path):
        mark_pending("Journals/2026/03/life-index_2026-03-01_001.md")
        pfile = index_dir / "pending_writes.json"
        assert pfile.exists()

    def test_appends_path(self, index_dir: Path):
        mark_pending("Journals/2026/03/a.md")
        pending = get_pending()
        assert "Journals/2026/03/a.md" in pending

    def test_duplicate_paths_deduplicated(self, index_dir: Path):
        mark_pending("Journals/2026/03/a.md")
        mark_pending("Journals/2026/03/a.md")
        mark_pending("Journals/2026/03/a.md")
        pending = get_pending()
        assert pending.count("Journals/2026/03/a.md") == 1

    def test_multiple_paths(self, index_dir: Path):
        mark_pending("Journals/2026/03/a.md")
        mark_pending("Journals/2026/03/b.md")
        assert len(get_pending()) == 2


class TestGetPending:
    def test_no_file_returns_empty(self, index_dir: Path):
        assert get_pending() == []

    def test_corrupt_json_returns_empty(self, index_dir: Path):
        pfile = index_dir / "pending_writes.json"
        pfile.write_text("NOT JSON{{{}}}")
        assert get_pending() == []

    def test_returns_all_paths(self, index_dir: Path):
        mark_pending("a.md")
        mark_pending("b.md")
        assert set(get_pending()) == {"a.md", "b.md"}


class TestClearPending:
    def test_clears_all(self, index_dir: Path):
        mark_pending("a.md")
        clear_pending()
        assert get_pending() == []

    def test_clear_when_empty(self, index_dir: Path):
        clear_pending()  # Should not crash
        assert get_pending() == []


class TestHasPending:
    def test_false_when_empty(self, index_dir: Path):
        assert has_pending() is False

    def test_true_after_mark(self, index_dir: Path):
        mark_pending("a.md")
        assert has_pending() is True

    def test_false_after_clear(self, index_dir: Path):
        mark_pending("a.md")
        clear_pending()
        assert has_pending() is False


class TestAtomicWrite:
    def test_no_temp_file_left(self, index_dir: Path):
        mark_pending("a.md")
        temp_files = list(index_dir.glob("pending_writes.json.tmp*"))
        assert len(temp_files) == 0

    def test_file_is_valid_json(self, index_dir: Path):
        mark_pending("a.md")
        pfile = index_dir / "pending_writes.json"
        data = json.loads(pfile.read_text(encoding="utf-8"))
        assert "pending" in data
        assert isinstance(data["pending"], list)
