"""Tests for edit_journal pending queue integration (Round 12 Phase 1 Task 1.3).

Since the FTS write-through landed, a successful edit no longer queues the
journal: its FTS row is replaced at commit time (``fts_row_updated=true``)
and nothing enters the pending queue. The queue is the failure-repair path,
used exactly when the edit's FTS row write-through failed.
"""

import pytest
from pathlib import Path

from tools.lib.pending_writes import get_pending, clear_pending, has_pending


@pytest.fixture(autouse=True)
def _isolate_index(tmp_path: Path, monkeypatch):
    """Isolate pending_writes and data dir to tmp_path."""
    import tools.lib.pending_writes as pw_mod

    d = tmp_path / "Life-Index"
    idx = d / ".index"
    idx.mkdir(parents=True)
    (d / "Journals" / "2026" / "03").mkdir(parents=True)

    monkeypatch.setattr(pw_mod, "get_index_dir", lambda: idx)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(d))


def _create_and_edit(tmp_path: Path) -> dict:
    """Write a journal then edit it, returning edit result."""
    from tools.write_journal.core import write_journal
    from tools.edit_journal import edit_journal

    # Write
    write_result = write_journal(
        {
            "title": "Original Title",
            "content": "Original content.",
            "date": "2026-03-15T10:00:00",
            "topic": ["life"],
        }
    )
    assert write_result.get("success") or write_result.get("write_outcome") == "success"
    journal_path = Path(write_result["journal_path"])

    # A successful write-through leaves nothing pending
    clear_pending()

    # Edit
    return edit_journal(
        journal_path=journal_path,
        frontmatter_updates={"title": "Edited Title"},
    )


class TestEditPendingIntegration:
    def test_edit_with_completed_fts_row_adds_no_pending(self, tmp_path: Path):
        """A successful edit write-through leaves the queue empty."""
        result = _create_and_edit(tmp_path)
        assert result.get("success")
        assert result.get("fts_row_updated") is True
        assert result.get("pending_marked") is False
        assert not has_pending()
        assert get_pending() == []

    def test_content_edit_replaces_fts_row_without_pending(self, tmp_path: Path):
        """Content-related edit (title) replaces the FTS row, no queue entry."""
        from tools.write_journal.core import write_journal
        from tools.edit_journal import edit_journal

        write_result = write_journal(
            {
                "title": "Before Edit",
                "content": "Some content.",
                "date": "2026-03-16T10:00:00",
                "topic": ["work"],
            }
        )
        clear_pending()
        edit_result = edit_journal(
            journal_path=Path(write_result["journal_path"]),
            frontmatter_updates={"title": "After Edit"},
        )
        assert edit_result.get("success")
        assert edit_result.get("fts_row_updated") is True
        assert not has_pending()

    def test_non_content_edit_replaces_fts_row_without_pending(self, tmp_path: Path):
        """Non-content edit (weather/location) also replaces the FTS row."""
        from tools.write_journal.core import write_journal
        from tools.edit_journal import edit_journal

        write_result = write_journal(
            {
                "title": "Weather Test",
                "content": "Some content.",
                "date": "2026-03-17T10:00:00",
                "topic": ["life"],
            }
        )
        clear_pending()
        edit_result = edit_journal(
            journal_path=Path(write_result["journal_path"]),
            frontmatter_updates={"weather": "Sunny 30°C"},
        )
        assert edit_result.get("success")
        assert edit_result.get("fts_row_updated") is True
        assert not has_pending()

    def test_failed_fts_row_write_through_queues_the_path(self, tmp_path: Path):
        """A failed edit write-through falls back to the durable pending queue."""
        from tools.write_journal.core import write_journal
        from tools.edit_journal import edit_journal

        write_result = write_journal(
            {
                "title": "Repair Test",
                "content": "Some content.",
                "date": "2026-03-18T10:00:00",
                "topic": ["life"],
            }
        )
        clear_pending()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "tools.edit_journal.upsert_fts_row",
                lambda *_a, **_k: (_ for _ in ()).throw(
                    RuntimeError("synthetic edit FTS write-through failure")
                ),
            )
            edit_result = edit_journal(
                journal_path=Path(write_result["journal_path"]),
                frontmatter_updates={"title": "Queued Edit"},
            )
        assert edit_result.get("success")
        assert edit_result.get("fts_row_updated") is False
        assert edit_result.get("pending_marked") is True
        assert has_pending()
        pending = get_pending()
        assert len(pending) >= 1
        assert any("life-index_2026-03-18" in p for p in pending)
