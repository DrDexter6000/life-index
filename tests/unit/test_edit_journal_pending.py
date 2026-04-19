"""Tests for edit_journal pending queue integration (Round 12 Phase 1 Task 1.3)."""

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
    write_result = write_journal({
        "title": "Original Title",
        "content": "Original content.",
        "date": "2026-03-15T10:00:00",
        "topic": ["life"],
    })
    assert write_result.get("success") or write_result.get("write_outcome") == "success"
    journal_path = Path(write_result["journal_path"])

    # Clear pending from write (we want to test edit's pending)
    clear_pending()

    # Edit
    return edit_journal(
        journal_path=journal_path,
        frontmatter_updates={"title": "Edited Title"},
    )


class TestEditPendingIntegration:
    def test_edit_adds_pending(self, tmp_path: Path):
        """After editing, pending_writes.json should contain the edited journal path."""
        result = _create_and_edit(tmp_path)
        assert result.get("success")
        assert has_pending()
        pending = get_pending()
        assert len(pending) >= 1

    def test_content_edit_triggers_pending(self, tmp_path: Path):
        """Content-related edit (title) triggers pending."""
        from tools.write_journal.core import write_journal
        from tools.edit_journal import edit_journal

        write_result = write_journal({
            "title": "Before Edit",
            "content": "Some content.",
            "date": "2026-03-16T10:00:00",
            "topic": ["work"],
        })
        clear_pending()
        edit_result = edit_journal(
            journal_path=Path(write_result["journal_path"]),
            frontmatter_updates={"title": "After Edit"},
        )
        assert edit_result.get("success")
        assert has_pending()

    def test_non_content_edit_also_triggers_pending(self, tmp_path: Path):
        """Non-content edit (weather/location) also triggers pending (FTS needs update)."""
        from tools.write_journal.core import write_journal
        from tools.edit_journal import edit_journal

        write_result = write_journal({
            "title": "Weather Test",
            "content": "Some content.",
            "date": "2026-03-17T10:00:00",
            "topic": ["life"],
        })
        clear_pending()
        edit_result = edit_journal(
            journal_path=Path(write_result["journal_path"]),
            frontmatter_updates={"weather": "Sunny 30°C"},
        )
        assert edit_result.get("success")
        assert has_pending()
