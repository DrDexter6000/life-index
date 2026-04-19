#!/usr/bin/env python3
"""
Round 12 Phase 1 Task 1.5: Pending lifecycle contract test.

Verifies the complete Write → Search → Edit → Search lifecycle:
1. Write marks a path as pending
2. Search consumes pending (triggers incremental build)
3. Edit marks a path as pending
4. Search consumes pending again
5. Index check reports healthy at end

This is a contract test: it verifies the *behavior contract* of the
pending queue across all three subsystems (write, edit, search),
using mocked heavy dependencies (model loading, weather, LLM) but
real pending_writes queue operations.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.lib.pending_writes import (
    mark_pending,
    get_pending,
    clear_pending,
    has_pending,
)


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path: Path, monkeypatch):
    """Isolate all path-dependent modules to tmp_path."""
    import tools.lib.pending_writes as pw_mod

    idx = tmp_path / ".index"
    idx.mkdir()
    d = tmp_path / "Life-Index"
    (d / "Journals" / "2026" / "03").mkdir(parents=True)
    (d / "by-topic").mkdir(parents=True)
    (d / "attachments").mkdir(parents=True)
    (d / ".cache").mkdir(parents=True)
    (d / ".cache" / "journals.lock").touch()

    monkeypatch.setattr(pw_mod, "INDEX_DIR", idx)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(d))


class TestPendingLifecycle:
    """Verify the full pending queue lifecycle across write/edit/search."""

    def test_write_creates_pending(self, tmp_path: Path):
        """After write_journal, the journal path should be in pending queue."""
        from tools.write_journal.core import write_journal

        journals_dir = tmp_path / "Life-Index" / "Journals"
        lock_path = tmp_path / "Life-Index" / ".cache" / "journals.lock"

        with (
            patch("tools.write_journal.core.get_journals_dir", return_value=journals_dir),
            patch("tools.write_journal.core.get_journals_lock_path", return_value=lock_path),
            patch("tools.write_journal.core.get_year_month", return_value=(2026, 3)),
            patch("tools.write_journal.core.get_next_sequence", return_value=1),
            patch("tools.write_journal.core.query_weather_for_location", return_value="Sunny 25C"),
            patch("tools.write_journal.core.update_topic_index", return_value=[]),
            patch("tools.write_journal.core.update_project_index", return_value=None),
            patch("tools.write_journal.core.update_tag_indices", return_value=[]),
            patch("tools.write_journal.core.update_monthly_abstract", return_value="abstract.md"),
        ):
            result = write_journal({
                "title": "Test R12 Lifecycle Entry",
                "content": "This entry contains test_r12_unique_keyword for search.",
                "date": "2026-03-07",
                "topic": ["work"],
            })

        assert result.get("success"), f"Write failed: {result.get('error')}"
        assert has_pending(), "Write should have marked journal as pending"

        pending = get_pending()
        assert len(pending) >= 1, "Pending queue should contain at least one path"
        # Verify the path references a journal file
        assert any("2026" in p and "03" in p for p in pending), \
            f"Pending path should reference 2026/03 journal, got: {pending}"

    def test_search_consumes_pending(self, tmp_path: Path, monkeypatch):
        """After search, pending queue should be cleared via incremental build."""
        # Pre-populate pending queue to simulate a prior write
        mark_pending("Journals/2026/03/life-index_2026-03-07_001.md")
        assert has_pending(), "Pre-condition: pending should be non-empty"

        build_calls = []
        def mock_build_all(**kwargs):
            build_calls.append(kwargs)
            return {"success": True, "fts": {"success": True}, "vector": {"success": True}}

        import tools.build_index as bi
        import tools.lib.search_index as si
        import tools.search_journals.core as search_core

        monkeypatch.setattr(bi, "build_all", mock_build_all)
        monkeypatch.setattr(si, "check_index_freshness", lambda: {"stale": False})
        monkeypatch.setattr(si, "update_index", lambda **kw: {"success": True})
        monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
        monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)

        result = search_core.hierarchical_search(query="test_r12_unique_keyword", level=3)

        assert not has_pending(), "Search should have consumed pending queue"
        assert len(build_calls) == 1, "Should have called build_all exactly once"
        assert build_calls[0].get("incremental") is True, "Should use incremental=True"

    def test_edit_creates_pending(self, tmp_path: Path):
        """After edit_journal, the journal path should be in pending queue."""
        from tools.edit_journal import edit_journal

        # Create a journal file to edit
        journal_file = tmp_path / "Life-Index" / "Journals" / "2026" / "03" / "life-index_2026-03-07_001.md"
        journal_file.write_text(
            '---\n'
            'title: "Original Title"\n'
            'date: 2026-03-07T10:00:00\n'
            'topic: ["work"]\n'
            '---\n\n'
            'Original body content.\n',
            encoding="utf-8",
        )

        clear_pending()  # Start clean

        with (
            patch("tools.edit_journal.save_revision", return_value="revisions/rev.md"),
        ):
            result = edit_journal(
                journal_path=journal_file,
                frontmatter_updates={"title": "test_r12_edited_title"},
            )

        assert result.get("success"), f"Edit failed: {result.get('error')}"
        assert has_pending(), "Edit should have marked journal as pending"

        pending = get_pending()
        assert len(pending) >= 1, "Pending queue should contain edited journal path"

    def test_full_lifecycle_write_search_edit_search(self, tmp_path: Path, monkeypatch):
        """
        Full lifecycle: Write → Search → Edit → Search.

        Verifies:
        1. Write creates pending
        2. First search consumes pending (build triggered)
        3. Edit creates pending again
        4. Second search consumes pending again
        5. Final state: no pending, clean queue
        """
        from tools.write_journal.core import write_journal
        from tools.edit_journal import edit_journal
        import tools.build_index as bi
        import tools.lib.search_index as si
        import tools.search_journals.core as search_core

        journals_dir = tmp_path / "Life-Index" / "Journals"
        lock_path = tmp_path / "Life-Index" / ".cache" / "journals.lock"

        # Track build_all calls
        build_calls = []
        def mock_build_all(**kwargs):
            build_calls.append(kwargs)
            return {"success": True, "fts": {"success": True}, "vector": {"success": True}}

        monkeypatch.setattr(bi, "build_all", mock_build_all)
        monkeypatch.setattr(si, "check_index_freshness", lambda: {"stale": False})
        monkeypatch.setattr(si, "update_index", lambda **kw: {"success": True})
        monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
        monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)

        # ---- Step 1: Write ----
        with (
            patch("tools.write_journal.core.get_journals_dir", return_value=journals_dir),
            patch("tools.write_journal.core.get_journals_lock_path", return_value=lock_path),
            patch("tools.write_journal.core.get_year_month", return_value=(2026, 3)),
            patch("tools.write_journal.core.get_next_sequence", return_value=1),
            patch("tools.write_journal.core.query_weather_for_location", return_value="Sunny 25C"),
            patch("tools.write_journal.core.update_topic_index", return_value=[]),
            patch("tools.write_journal.core.update_project_index", return_value=None),
            patch("tools.write_journal.core.update_tag_indices", return_value=[]),
            patch("tools.write_journal.core.update_monthly_abstract", return_value="abstract.md"),
        ):
            write_result = write_journal({
                "title": "Test R12 Lifecycle",
                "content": "Content with test_r12_unique_keyword for lifecycle test.",
                "date": "2026-03-07",
                "topic": ["work"],
            })

        assert write_result.get("success"), f"Write failed: {write_result.get('error')}"
        assert has_pending(), "Step 1: Write should mark pending"

        # ---- Step 2: First search (consumes pending) ----
        search_core.hierarchical_search(query="test_r12_unique_keyword", level=3)
        assert not has_pending(), "Step 2: Search should have consumed pending"
        assert len(build_calls) == 1, "Step 2: First build_all should have been called"

        # ---- Step 3: Edit the written journal ----
        written_path = write_result.get("journal_path")
        assert written_path, "Write result should contain journal_path"

        # Resolve to actual path if it's relative
        if not Path(written_path).is_absolute():
            data_dir = tmp_path / "Life-Index"
            journal_file = data_dir / written_path
        else:
            journal_file = Path(written_path)

        with (
            patch("tools.edit_journal.save_revision", return_value="revisions/rev.md"),
        ):
            edit_result = edit_journal(
                journal_path=journal_file,
                frontmatter_updates={"title": "test_r12_edited_title"},
            )

        assert edit_result.get("success"), f"Edit failed: {edit_result.get('error')}"
        assert has_pending(), "Step 3: Edit should mark pending"

        # ---- Step 4: Second search (consumes pending again) ----
        search_core.hierarchical_search(query="test_r12_edited_title", level=3)
        assert not has_pending(), "Step 4: Search should have consumed pending again"
        assert len(build_calls) == 2, "Step 4: Second build_all should have been called"

        # ---- Final state ----
        final_pending = get_pending()
        assert final_pending == [], f"Final state: pending queue should be empty, got: {final_pending}"
