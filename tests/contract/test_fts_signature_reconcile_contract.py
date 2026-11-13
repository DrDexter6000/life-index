#!/usr/bin/env python3
"""Contract tests: signature-based FTS reconciliation on every search.

Each class reproduces a review finding where the index kept serving the wrong
answer without ``index --rebuild``:

- R1: a matching signature hid a missing FTS row.
- R2: a write-through hid earlier outside changes (edit or delete).
- R3: a queued path was skipped because its signature matched.
- R5/R6: edit admitted non-fragments to derived stores and reported nothing.

The read-only preflight is also pinned: a search on an unchanged archive opens
no journal file; a search after one outside edit opens exactly that file.
"""

import os
import sqlite3
from pathlib import Path

import pytest

from tools.lib.journal_files import JOURNAL_FILENAME_RE


def _write_journal(payload: dict) -> dict:
    from tools.write_journal.core import write_journal

    result = write_journal(dict(payload))
    assert result.get("journal_path"), result.get("error")
    return result


def _payload(date: str, title: str, content: str, weather: str = "sunny") -> dict:
    return {
        "title": title,
        "content": content,
        "date": date,
        "topic": "work",
        "weather": weather,
        "tags": ["fts-signature-contract"],
    }


def _build_rebuild() -> dict:
    from tools.build_index import build_all

    result = build_all(incremental=False)
    assert result["success"] is True, result.get("fts")
    return result


def _search(query: str) -> dict:
    from tools.search_journals.core import hierarchical_search

    return hierarchical_search(query=query)


def _merged_names(response: dict) -> set[str]:
    return {
        Path(str(item.get("path") or item.get("journal_route_path") or "")).name
        for item in (response.get("merged_results") or [])
        if item.get("path") or item.get("journal_route_path")
    }


def _fts_paths() -> set[str]:
    from tools.lib.paths import get_fts_db_path

    db_path = get_fts_db_path()
    if not db_path.exists():
        return set()
    conn = sqlite3.connect(str(db_path))
    try:
        try:
            return {row[0] for row in conn.execute("SELECT path FROM journals").fetchall()}
        except sqlite3.Error:
            return set()
    finally:
        conn.close()


def _fts_row(rel_path: str) -> tuple | None:
    from tools.lib.paths import get_fts_db_path

    db_path = get_fts_db_path()
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    try:
        try:
            return conn.execute(
                "SELECT path, content FROM journals WHERE path = ?", (rel_path,)
            ).fetchone()
        except sqlite3.Error:
            return None
    finally:
        conn.close()


def _pending() -> list[str]:
    from tools.lib.pending_writes import get_pending

    return get_pending()


class JournalReadCounter:
    """Count journal fragment content reads (Path.read_text / Path.read_bytes)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.reads: list[str] = []
        orig_read_text = Path.read_text
        orig_read_bytes = Path.read_bytes
        counter = self

        def _is_fragment(path: Path) -> bool:
            path = Path(path)
            return "Journals" in path.parts and JOURNAL_FILENAME_RE.match(path.name) is not None

        def _counting_read_text(path, *args, **kwargs):
            if _is_fragment(path):
                counter.reads.append(str(path))
            return orig_read_text(path, *args, **kwargs)

        def _counting_read_bytes(path, *args, **kwargs):
            if _is_fragment(path):
                counter.reads.append(str(path))
            return orig_read_bytes(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", _counting_read_text)
        monkeypatch.setattr(Path, "read_bytes", _counting_read_bytes)

    @property
    def distinct(self) -> set[str]:
        return set(self.reads)

    def reset(self) -> None:
        self.reads.clear()


@pytest.fixture
def journal_reads(monkeypatch: pytest.MonkeyPatch) -> JournalReadCounter:
    return JournalReadCounter(monkeypatch)


class TestR1MatchingStatsHideMissingRow:
    def test_interrupted_rebuild_is_repaired_by_search(self, isolated_data_dir):
        from tools.lib.search_index import init_fts_db, upsert_fts_row

        word = "signature-r1-word"
        a = _write_journal(_payload("2026-04-01", "A", f"alpha {word}"))
        b = _write_journal(_payload("2026-04-02", "B", f"beta {word}"))
        _build_rebuild()

        # Simulate an interrupted rebuild: the journals table is recreated.
        init_fts_db(force_recreate=True).close()

        # The interrupted rebuild wrote one row through before stopping.
        a_path = Path(a["journal_path"])
        assert upsert_fts_row(a_path) is not None
        assert len(_fts_paths()) == 1

        response = _search(word)

        names = _merged_names(response)
        assert Path(a["journal_path"]).name in names
        assert Path(b["journal_path"]).name in names, (
            "B has a matching signature but no FTS row; the search preflight "
            "must notice the missing row and rebuild it"
        )
        assert len(_fts_paths()) == 2


class TestR2WriteThroughDoesNotHideOutsideChanges:
    def test_outside_edit_is_indexed_after_a_tool_edit(self, isolated_data_dir):
        from tools.edit_journal import edit_journal

        word = "signature-r2-word"
        a = _write_journal(_payload("2026-04-03", "A", f"alpha {word}"))
        b = _write_journal(_payload("2026-04-04", "B", "beta without the token"))
        _build_rebuild()

        b_path = Path(b["journal_path"])
        b_path.write_text(
            b_path.read_text(encoding="utf-8") + f"\n\noutside append {word}\n",
            encoding="utf-8",
        )

        # A tool edit writes A's row through; that must not make the whole
        # archive look fresh.
        edit_result = edit_journal(
            journal_path=Path(a["journal_path"]),
            frontmatter_updates={"weather": "cloudy"},
        )
        assert edit_result["success"] is True

        response = _search(word)

        names = _merged_names(response)
        assert Path(a["journal_path"]).name in names
        assert b_path.name in names, (
            "the outside edit to B happened before the tool edit of A; the next "
            "search must reconcile B's signature"
        )

    def test_outside_delete_is_dropped_after_a_tool_edit(self, isolated_data_dir):
        from tools.edit_journal import edit_journal

        word = "signature-r2-delete-word"
        a = _write_journal(_payload("2026-04-05", "A", f"alpha {word}"))
        b = _write_journal(_payload("2026-04-06", "B", f"beta {word}"))
        _build_rebuild()

        b_path = Path(b["journal_path"])
        b_path.unlink()

        edit_result = edit_journal(
            journal_path=Path(a["journal_path"]),
            frontmatter_updates={"weather": "rainy"},
        )
        assert edit_result["success"] is True

        response = _search(word)

        names = _merged_names(response)
        assert Path(a["journal_path"]).name in names
        assert b_path.name not in names, "a deleted journal must not be returned"
        assert all(not path.endswith(b_path.name) for path in _fts_paths())


class TestR3QueuedPathIsAlwaysReread:
    def test_same_size_same_mtime_edit_is_repaired_from_the_queue(self, isolated_data_dir):
        from tools.edit_journal import edit_journal

        old_word = "queueoldword"
        new_word = "queuenewword"  # same byte length
        a = _write_journal(_payload("2026-04-07", "A", old_word))
        a_path = Path(a["journal_path"])
        _build_rebuild()

        # Normalize the file through an edit so a second edit keeps its size.
        assert (
            edit_journal(journal_path=a_path, frontmatter_updates={}, replace_content=old_word)[
                "success"
            ]
            is True
        )
        _build_rebuild()
        before = a_path.stat()

        import tools.edit_journal as edit_module

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                edit_module,
                "upsert_fts_row",
                lambda *_a, **_k: (_ for _ in ()).throw(
                    RuntimeError("synthetic write-through failure")
                ),
            )
            edit_result = edit_journal(
                journal_path=a_path,
                frontmatter_updates={},
                replace_content=new_word,
            )
        assert edit_result["success"] is True
        assert edit_result["fts_row_updated"] is False
        assert edit_result["pending_marked"] is True
        assert _pending(), "the failed write-through must queue the path"

        # Same byte length and the same mtime tick: only the queue can save it.
        assert a_path.stat().st_size == before.st_size
        os.utime(a_path, ns=(before.st_atime_ns, before.st_mtime_ns))
        assert a_path.stat().st_mtime == before.st_mtime

        response = _search(new_word)

        assert _pending() == [], "the repairing search must acknowledge the queue"
        assert Path(a["journal_path"]).name in _merged_names(
            response
        ), "a queued path must be re-read even when its signature matches"
        rel_path = str(a_path.relative_to(isolated_data_dir)).replace("\\", "/")
        row = _fts_row(rel_path)
        assert row is not None and new_word in row[1]


class TestR5R6EditAdmissionAndReport:
    @pytest.mark.parametrize(
        "rel_path",
        [
            "Journals/2026/03/digest_2026-03-04.md",
            "Journals/2026/03/index_2026-03.md",
            "Journals/2026/03/.revisions/life-index_2026-03-04_001_20260305_101500_000000.md",
        ],
    )
    def test_edit_skips_non_fragment_files(self, isolated_data_dir, rel_path):
        from tools.edit_journal import edit_journal
        from tools.lib.metadata_cache import init_metadata_cache
        from tools.lib.paths import get_fts_db_path

        path = isolated_data_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '---\ntitle: "derived"\ndate: "2026-03-04"\ntopic: [life]\n---\n\nbody\n',
            encoding="utf-8",
        )

        result = edit_journal(journal_path=path, frontmatter_updates={"title": "edited"})

        assert result["success"] is True, result.get("error")
        assert result["error"] is None
        assert result["fts_row_updated"] is False
        assert result["pending_marked"] is False
        assert result["fts_row"] == {
            "status": "skipped",
            "reason": "not_a_live_fragment",
            "recovery": None,
        }
        assert _pending() == []

        rel_db_path = str(path.relative_to(isolated_data_dir)).replace("\\", "/")
        db_path = get_fts_db_path()
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            try:
                try:
                    assert (
                        conn.execute(
                            "SELECT 1 FROM journals WHERE path = ?", (rel_db_path,)
                        ).fetchone()
                        is None
                    )
                except sqlite3.Error:
                    pass
            finally:
                conn.close()

        cache_conn = init_metadata_cache()
        try:
            assert (
                cache_conn.execute(
                    "SELECT 1 FROM metadata_cache WHERE file_path = ?", (rel_db_path,)
                ).fetchone()
                is None
            )
        finally:
            cache_conn.close()

    def test_failed_write_through_and_failed_queue_reports_both(self, isolated_data_dir):
        from tools.edit_journal import edit_journal

        a = _write_journal(_payload("2026-04-08", "A", "r6body"))
        a_path = Path(a["journal_path"])

        import tools.edit_journal as edit_module

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                edit_module,
                "upsert_fts_row",
                lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
            )
            mp.setattr(
                edit_module,
                "mark_pending",
                lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("queue down")),
            )
            result = edit_journal(
                journal_path=a_path,
                frontmatter_updates={"weather": "snowy"},
            )

        assert result["success"] is True
        assert result["error"] is None
        assert result["fts_row_updated"] is False
        assert result["pending_marked"] is False
        assert result["fts_row"]["status"] == "failed"
        assert "boom" in result["fts_row"]["reason"]
        assert "pending_queue_failed" in result["fts_row"]["reason"]
        assert "queue down" in result["fts_row"]["reason"]
        assert result["fts_row"]["recovery"] == "life-index index --rebuild"

    def test_failed_write_through_with_queue_reports_repair_command(self, isolated_data_dir):
        from tools.edit_journal import edit_journal

        a = _write_journal(_payload("2026-04-09", "A", "r6body2"))
        a_path = Path(a["journal_path"])

        import tools.edit_journal as edit_module

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                edit_module,
                "upsert_fts_row",
                lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom2")),
            )
            result = edit_journal(
                journal_path=a_path,
                frontmatter_updates={"weather": "windy"},
            )

        assert result["success"] is True
        assert result["fts_row_updated"] is False
        assert result["pending_marked"] is True
        assert result["fts_row"]["status"] == "failed"
        assert "boom2" in result["fts_row"]["reason"]
        assert result["fts_row"]["recovery"] == "life-index index"


class TestD1UnparsableFragmentIsReachable:
    def test_token_only_in_broken_frontmatter_is_found(self, isolated_data_dir):
        """D1: the raw-text row makes a token in broken frontmatter reachable.

        The L3 fallback scans only the body, so on the old "drop the row"
        behaviour this token was unreachable even though a user could describe
        the fragment with it.
        """
        journal = _write_journal(_payload("2026-06-03", "A", "body without the token"))
        journal_path = Path(journal["journal_path"])
        journal_path.write_text(
            "---\ntitle: [unterminated\ndate: d1rawtoken\n---\n\nbody without the token\n",
            encoding="utf-8",
        )
        _build_rebuild()

        response = _search("d1rawtoken")

        assert response.get("success") is True
        names = _merged_names(response)
        assert journal_path.name in names, (
            "a fragment whose only token is in unparsable frontmatter must still "
            "be returned from its raw-text FTS row"
        )
        hit = next(
            item
            for item in response["merged_results"]
            if journal_path.name in str(item.get("path", ""))
        )
        assert hit.get("date") == "2026-06-03"  # filename fallback


class TestD5OrphanedRebuildMarker:
    def test_dead_schema_upgrade_marker_does_not_block_the_next_search(self, isolated_data_dir):
        """D5: a marker left by a dead builder must not block the repair.

        Reproduction: a schema-version-2 database without ``fts_file_stats``,
        a child that exits right after writing ``.index/.rebuilding``, then a
        fragment is deleted. The next search must remove the deleted row
        instead of answering "rebuild already in progress".
        """
        from tools.lib.paths import get_fts_db_path

        word = "d5-marker-word"
        kept = _write_journal(_payload("2026-06-01", "A", f"alpha {word}"))
        deleted = _write_journal(_payload("2026-06-02", "B", f"beta {word}"))
        _build_rebuild()

        db_path = get_fts_db_path()
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("DROP TABLE IF EXISTS fts_file_stats")
            conn.execute("UPDATE index_meta SET value = '2' WHERE key = 'schema_version'")
            conn.commit()
        finally:
            conn.close()

        from tools.lib.paths import get_user_data_dir

        marker = get_user_data_dir() / ".index" / ".rebuilding"
        marker.write_text("dead builder", encoding="utf-8")

        Path(deleted["journal_path"]).unlink()

        response = _search(word)

        names = _merged_names(response)
        assert Path(kept["journal_path"]).name in names
        assert Path(deleted["journal_path"]).name not in names, (
            "a deleted fragment must not be returned by the search that repairs "
            "the index after an orphaned rebuild marker"
        )
        assert not marker.exists(), "the orphaned marker must be removed and the rebuild proceed"

    def test_marker_left_by_a_real_dead_child_process_does_not_block_the_repair(
        self, isolated_data_dir
    ):
        """D6: the marker comes from a real child that dies while holding it.

        Same scenario as above, but the ``.rebuilding`` marker is written by a
        child process that calls ``os._exit`` immediately afterwards (the way a
        builder killed during the automatic schema-version rebuild leaves it).
        A schema-version-2 database without ``fts_file_stats`` then needs a full
        rebuild that only proceeds if the orphaned marker is removed.
        """
        import subprocess
        import sys

        from tools.lib.paths import get_fts_db_path, get_user_data_dir
        from tools.lib.search_index import FTS_SCHEMA_VERSION

        word = "d6-child-marker-word"
        kept = _write_journal(_payload("2026-06-04", "A", f"alpha {word}"))
        deleted = _write_journal(_payload("2026-06-05", "B", f"beta {word}"))
        _build_rebuild()

        db_path = get_fts_db_path()
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("DROP TABLE IF EXISTS fts_file_stats")
            conn.execute("UPDATE index_meta SET value = '2' WHERE key = 'schema_version'")
            conn.commit()
        finally:
            conn.close()

        marker = get_user_data_dir() / ".index" / ".rebuilding"
        assert not marker.exists()
        child_code = (
            "import os, sys\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, sys.argv[2])\n"
            "from tools.lib.fts_update import _write_rebuild_marker\n"
            "_write_rebuild_marker(Path(sys.argv[1]))\n"
            "os._exit(0)\n"
        )
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                child_code,
                str(marker),
                str(Path(__file__).resolve().parents[2]),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert child.returncode == 0, child.stderr
        assert marker.exists(), "the dead child must have left the rebuild marker behind"

        Path(deleted["journal_path"]).unlink()

        response = _search(word)

        names = _merged_names(response)
        assert Path(kept["journal_path"]).name in names
        assert Path(deleted["journal_path"]).name not in names, (
            "a deleted fragment must not be returned after a real child left an "
            "orphaned rebuild marker"
        )
        assert not marker.exists(), "the orphaned marker must be removed and the rebuild proceed"

        conn = sqlite3.connect(str(db_path))
        try:
            stats_count = conn.execute("SELECT COUNT(*) FROM fts_file_stats").fetchone()[0]
            recorded_version = conn.execute(
                "SELECT value FROM index_meta WHERE key = 'schema_version'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert stats_count == 1, "the rebuild must repopulate the signature table"
        assert int(recorded_version) == FTS_SCHEMA_VERSION


class TestPreflightReadCost:
    @staticmethod
    def _warmup() -> None:
        from tools.lib.metadata_cache import ensure_cache_version_current

        ensure_cache_version_current()

    def test_search_on_unchanged_archive_opens_no_journal(self, isolated_data_dir, journal_reads):
        word = "preflight-unchanged-word"
        _write_journal(_payload("2026-05-01", "A", f"alpha {word}"))
        _write_journal(_payload("2026-05-02", "B", "beta plain"))
        _build_rebuild()
        self._warmup()

        journal_reads.reset()
        response = _search(word)

        assert journal_reads.distinct == set(), (
            "a search on an unchanged archive must not open any journal file, "
            f"opened: {sorted(journal_reads.distinct)}"
        )
        assert response.get("success") is True

    def test_search_after_one_outside_edit_opens_only_that_journal(
        self, isolated_data_dir, journal_reads
    ):
        word = "preflight-outside-edit-word"
        a = _write_journal(_payload("2026-05-03", "A", "alpha plain"))
        b = _write_journal(_payload("2026-05-04", "B", "beta plain"))
        _build_rebuild()
        self._warmup()

        edited = Path(a["journal_path"])
        edited.write_text(
            edited.read_text(encoding="utf-8") + f"\n\noutside {word}\n", encoding="utf-8"
        )

        journal_reads.reset()
        response = _search(word)

        assert journal_reads.distinct == {str(edited)}, (
            "only the changed file may be read, got "
            f"{sorted(journal_reads.distinct)} (B={b['journal_path']})"
        )
        assert edited.name in _merged_names(response)
