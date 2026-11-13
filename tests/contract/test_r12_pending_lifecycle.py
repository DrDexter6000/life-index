#!/usr/bin/env python3
"""
Round 12 Phase 1 Task 1.5: Pending lifecycle contract test.

Since the FTS write-through landed, the lifecycle is:

1. Write writes the journal's FTS row through → pending queue stays empty
   (mark_pending=skipped). Only a failed write-through queues the path.
2. Search consumes a non-empty pending queue (triggers incremental build).
3. Edit replaces the journal's FTS row → queue stays empty; only a failed
   write-through queues the path.
4. Search consumes the queue again after a queued (repair) edit.
5. Index check reports healthy at end.

This is a contract test: it verifies the *behavior contract* of the
pending queue across all three subsystems (write, edit, search),
using mocked heavy dependencies (model loading, weather, LLM) but
real pending_writes queue operations.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from tools.lib.pending_writes import (
    mark_pending,
    get_pending,
    clear_pending,
    has_pending,
)


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path: Path, monkeypatch):
    """Isolate all path-dependent modules to tmp_path."""
    idx = tmp_path / ".index"
    idx.mkdir()
    d = tmp_path / "Life-Index"
    (d / "Journals" / "2026" / "03").mkdir(parents=True)
    (d / "by-topic").mkdir(parents=True)
    (d / "attachments").mkdir(parents=True)
    (d / ".cache").mkdir(parents=True)
    (d / ".cache" / "journals.lock").touch()

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(d))


class TestPendingLifecycle:
    """Verify the pending queue lifecycle across write/edit/search."""

    def test_write_with_completed_fts_row_creates_no_pending(self, tmp_path: Path):
        """A successful write-through leaves the queue empty."""
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
            result = write_journal(
                {
                    "title": "Test R12 Lifecycle Entry",
                    "content": "This entry contains test_r12_unique_keyword for search.",
                    "date": "2026-03-07",
                    "topic": ["work"],
                }
            )

        assert result.get("success"), f"Write failed: {result.get('error')}"
        assert not has_pending(), "A completed FTS write-through must not queue anything"
        assert get_pending() == []

    def test_write_with_failed_fts_row_creates_pending(self, tmp_path: Path):
        """A failed write-through queues the journal path for repair."""
        import tools.write_journal.core as write_core

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
            patch(
                write_core.__name__ + ".upsert_fts_row",
                side_effect=RuntimeError("synthetic FTS write-through failure"),
            ),
        ):
            result = write_core.write_journal(
                {
                    "title": "Test R12 Repair Entry",
                    "content": "This entry contains test_r12_repair_keyword for search.",
                    "date": "2026-03-07",
                    "topic": ["work"],
                }
            )

        assert result.get("success"), f"Write failed: {result.get('error')}"
        assert has_pending(), "A failed write-through must queue the journal path"

        pending = get_pending()
        assert len(pending) >= 1, "Pending queue should contain at least one path"
        # Verify the path references a journal file
        assert any(
            "2026" in p and "03" in p for p in pending
        ), f"Pending path should reference 2026/03 journal, got: {pending}"

    def test_search_consumes_pending(self, tmp_path: Path, monkeypatch):
        """After search, pending queue should be cleared via incremental build."""
        # Pre-populate pending queue to simulate a prior failed write-through
        mark_pending("Journals/2026/03/life-index_2026-03-07_001.md")
        assert has_pending(), "Pre-condition: pending should be non-empty"

        build_calls = []

        def mock_build_all(**kwargs):
            build_calls.append(kwargs)
            return {
                "success": True,
                "fts": {
                    "success": True,
                    "pending_repaired": ["Journals/2026/03/life-index_2026-03-07_001.md"],
                },
                "vector": {"success": True},
            }

        import tools.build_index as bi
        import tools.lib.search_index as si
        import tools.search_journals.core as search_core

        monkeypatch.setattr(bi, "build_all", mock_build_all)
        monkeypatch.setattr(si, "check_index_freshness", lambda: {"stale": False})
        monkeypatch.setattr(si, "update_index", lambda **kw: {"success": True})
        monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
        monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)

        search_core.hierarchical_search(query="test_r12_unique_keyword", level=3)

        assert not has_pending(), "Search should have consumed pending queue"
        assert len(build_calls) == 1, "Should have called build_all exactly once"
        assert build_calls[0].get("incremental") is True, "Should use incremental=True"

    def test_edit_with_completed_fts_row_creates_no_pending(self, tmp_path: Path):
        """A successful edit write-through leaves the queue empty."""
        from tools.edit_journal import edit_journal

        # Create a journal file to edit
        journal_file = (
            tmp_path / "Life-Index" / "Journals" / "2026" / "03" / "life-index_2026-03-07_001.md"
        )
        journal_file.write_text(
            "---\n"
            'title: "Original Title"\n'
            "date: 2026-03-07T10:00:00\n"
            'topic: ["work"]\n'
            "---\n\n"
            "Original body content.\n",
            encoding="utf-8",
        )

        clear_pending()  # Start clean

        with (patch("tools.edit_journal.save_revision", return_value="revisions/rev.md"),):
            result = edit_journal(
                journal_path=journal_file,
                frontmatter_updates={"title": "test_r12_edited_title"},
            )

        assert result.get("success"), f"Edit failed: {result.get('error')}"
        assert result.get("fts_row_updated") is True
        assert not has_pending(), "A completed edit write-through must not queue anything"
        assert get_pending() == []

    def test_full_lifecycle_write_search_edit_search(self, tmp_path: Path, monkeypatch):
        """
        Full lifecycle: Write → Search → Edit (repair) → Search.

        Verifies:
        1. Write with a completed write-through creates no pending
        2. Search runs without consuming any queue
        3. Edit with a failed write-through queues the journal again
        4. Second search consumes the queue
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
            return {
                "success": True,
                "fts": {"success": True, "pending_repaired": list(get_pending())},
                "vector": {"success": True},
            }

        monkeypatch.setattr(bi, "build_all", mock_build_all)
        monkeypatch.setattr(si, "check_index_freshness", lambda: {"stale": False})
        monkeypatch.setattr(si, "update_index", lambda **kw: {"success": True})
        monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
        monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)
        # Mock the no-pending freshness guard so only the pending queue can
        # trigger build_all in this lifecycle.
        from tools.lib.index_freshness import FreshnessReport

        monkeypatch.setattr(
            "tools.lib.index_freshness.check_full_freshness",
            lambda _index_dir: FreshnessReport(
                fts_fresh=True, vector_fresh=True, overall_fresh=True, issues=[]
            ),
        )

        # ---- Step 1: Write (write-through succeeds → no pending) ----
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
            write_result = write_journal(
                {
                    "title": "Test R12 Lifecycle",
                    "content": "Content with test_r12_unique_keyword for lifecycle test.",
                    "date": "2026-03-07",
                    "topic": ["work"],
                }
            )

        assert write_result.get("success"), f"Write failed: {write_result.get('error')}"
        assert not has_pending(), "Step 1: completed write-through must not mark pending"

        # ---- Step 2: First search (nothing queued → no build) ----
        search_core.hierarchical_search(query="test_r12_unique_keyword", level=3)
        assert not has_pending(), "Step 2: queue must stay empty"
        assert len(build_calls) == 0, "Step 2: no pending → no build_all call"

        # ---- Step 3: Edit the written journal (write-through fails → queued) ----
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
            patch(
                "tools.edit_journal.upsert_fts_row",
                side_effect=RuntimeError("synthetic edit write-through failure"),
            ),
        ):
            edit_result = edit_journal(
                journal_path=journal_file,
                frontmatter_updates={"title": "test_r12_edited_title"},
            )

        assert edit_result.get("success"), f"Edit failed: {edit_result.get('error')}"
        assert edit_result.get("pending_marked") is True
        assert has_pending(), "Step 3: failed edit write-through must mark pending"

        # ---- Step 4: Second search (consumes pending again) ----
        search_core.hierarchical_search(query="test_r12_edited_title", level=3)
        assert not has_pending(), "Step 4: Search should have consumed pending again"
        assert len(build_calls) == 1, "Step 4: Second build_all should have been called"

        # ---- Final state ----
        final_pending = get_pending()
        assert (
            final_pending == []
        ), f"Final state: pending queue should be empty, got: {final_pending}"

    def test_preflight_keeps_path_queued_during_build(self, tmp_path: Path, monkeypatch):
        """A path queued while the preflight's build runs must survive it.

        The preflight may only remove the paths that were queued when its
        build started. A write that falls back to the queue *during* the build
        (for example because the index lock was held by that very build) must
        still be in the queue afterwards, and the next search must index it.
        Wholesale clear_pending() here would silently drop it.
        """
        import tools.build_index as bi
        import tools.search_journals.core as search_core
        from tools.lib.index_freshness import FreshnessReport

        queued_before = "Journals/2026/03/life-index_2026-03-07_001.md"
        queued_during_build = "Journals/2026/03/life-index_2026-03-08_001.md"

        mark_pending(queued_before)
        assert has_pending(), "Pre-condition: pending should be non-empty"

        build_calls = []

        def mock_build_all(**kwargs):
            build_calls.append(kwargs)
            repaired = list(get_pending())
            # Simulate a concurrent write whose FTS write-through could not
            # get the index lock (held by this very build) and queued itself.
            # Only the first build sees that event; a second re-mark would be
            # a *newer* generation that must survive (pinned elsewhere).
            if len(build_calls) == 1:
                mark_pending(queued_during_build)
            return {
                "success": True,
                "fts": {"success": True, "pending_repaired": repaired},
                "vector": {"success": True},
            }

        monkeypatch.setattr(bi, "build_all", mock_build_all)
        monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
        monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)
        monkeypatch.setattr(
            "tools.lib.index_freshness.check_full_freshness",
            lambda _index_dir: FreshnessReport(
                fts_fresh=True, vector_fresh=True, overall_fresh=True, issues=[]
            ),
        )

        result = search_core.hierarchical_search(query="test_r12_unique_keyword", level=3)

        assert len(build_calls) == 1, "the preflight should have run one build"
        assert result["pending_consumed"] is False, (
            "paths still queued after the preflight must keep the honest " "not-consumed signal"
        )
        pending = get_pending()
        assert (
            queued_during_build in pending
        ), f"a path queued during the preflight build must survive it, got: {pending}"
        assert queued_before not in pending, "the consumed snapshot must be removed"
        assert pending == [queued_during_build]

        # The following search consumes the survivor.
        search_core.hierarchical_search(query="test_r12_unique_keyword", level=3)
        assert len(build_calls) == 2, "the next search must index the surviving path"
        assert get_pending() == []
