#!/usr/bin/env python3
"""Contract test: FTS row write-through and stat-based incremental scan.

Baseline measured on the pre-write-through implementation (300 synthetic
journals, counting read_text/read_bytes of fragment files under Journals/):

- one write                                : 904 fragment reads (all from the
  month/year/root index + Index B refresh; the FTS index itself read 0) and
  ``write_outcome=success_degraded`` / ``index_status=degraded`` with
  ``mark_pending=queued`` — the new journal was not in the FTS index yet
- first full-text search after that write  : 303 reads = 301 whole-archive
  file hashes + 1 re-parse + 1 hit display read (the pending queue was
  consumed into an incremental scan that hashed every journal)
- ``life-index index`` with nothing changed: 301 reads (every file hashed
  again just to learn that nothing changed)

Target behaviour pinned here:

- write/edit write the committed journal's FTS row through from the committed
  file via the same file → row path a full rebuild uses (real ``file_hash``,
  the file's real mtime in ``modified_time``);
- a successful write-through leaves the pending queue empty
  (``mark_pending=skipped``) and the envelope reports ``index_status=
  complete`` / ``write_outcome`` without degradation;
- a failed write-through queues the path exactly as before
  (``mark_pending=queued``, ``success_degraded``) and the next search
  preflight repairs the index;
- the incremental scan decides "unchanged" from the file's ``(mtime, size)``
  recorded in the ``fts_file_stats`` side table and reads only new/changed
  files; deleted files lose their row as before. Existing v2 installations
  (no stats rows) rebuild once automatically through the recorded
  schema-version mechanism.
"""

import os
import sqlite3
from pathlib import Path

import pytest

from tools.lib.journal_files import JOURNAL_FILENAME_RE

N_JOURNALS = 40

WRITE_PAYLOAD = {
    "title": "全新写入的目标日志",
    "content": "这是契约测试中写入的新日志正文，包含唯一全文词汇。",
    "date": "2026-04-15",
    "topic": "work",
    "tags": ["fts-write-through-contract"],
    "location": "唯一确认地点",
    "weather": "cloudy",
    "people": [],
}

DISTINCTIVE_WORD = "唯一全文词汇"


def _is_journal_fragment(path: Path) -> bool:
    path = Path(path)
    return "Journals" in path.parts and JOURNAL_FILENAME_RE.match(path.name) is not None


class JournalReadCounter:
    """Count journal fragment content reads (Path.read_text / Path.read_bytes)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.reads: list[str] = []
        orig_read_text = Path.read_text
        orig_read_bytes = Path.read_bytes
        counter = self

        def _counting_read_text(path, *args, **kwargs):
            if _is_journal_fragment(path):
                counter.reads.append(str(path))
            return orig_read_text(path, *args, **kwargs)

        def _counting_read_bytes(path, *args, **kwargs):
            if _is_journal_fragment(path):
                counter.reads.append(str(path))
            return orig_read_bytes(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", _counting_read_text)
        monkeypatch.setattr(Path, "read_bytes", _counting_read_bytes)

    @property
    def total(self) -> int:
        return len(self.reads)

    @property
    def distinct(self) -> int:
        return len(set(self.reads))

    def reset(self) -> None:
        self.reads.clear()


@pytest.fixture
def journal_reads(monkeypatch: pytest.MonkeyPatch) -> JournalReadCounter:
    return JournalReadCounter(monkeypatch)


def _make_synthetic_journals(data_dir: Path, n: int) -> list[Path]:
    """Create n synthetic fragment journals across three months."""
    per_date: dict[str, int] = {}
    created: list[Path] = []
    for i in range(n):
        month = (i % 3) + 1
        day = (i % 28) + 1
        date_str = f"2026-{month:02d}-{day:02d}"
        per_date[date_str] = per_date.get(date_str, 0) + 1
        seq = per_date[date_str]
        month_dir = data_dir / "Journals" / "2026" / f"{month:02d}"
        month_dir.mkdir(parents=True, exist_ok=True)
        journal = month_dir / f"life-index_{date_str}_{seq:03d}.md"
        journal.write_text(
            "---\n"
            "schema_version: 2.1.0\n"
            f'date: "{date_str}"\n'
            f"title: 第{i + 1}篇合成日志\n"
            "topic: life\n"
            "tags:\n  - fts-write-through-contract\n"
            "location: 测试城市\n"
            "weather: sunny\n"
            "mood:\n  - calm\n"
            "people: []\n"
            "---\n\n"
            f"# 第{i + 1}篇合成日志\n\n"
            f"这是第{i + 1}篇合成日志的正文内容。\n",
            encoding="utf-8",
        )
        created.append(journal)
    return created


def _warm_index_to_steady_state() -> None:
    """Populate FTS rows, stats rows, the manifest, and the cache sidecar."""
    from tools.build_index import build_all
    from tools.lib.metadata_cache import ensure_cache_version_current

    build_all(incremental=False)
    ensure_cache_version_current()


def _fulltext_search(query: str) -> dict:
    from tools.search_journals.core import hierarchical_search

    return hierarchical_search(query=query)


def _write_one_journal(payload: dict | None = None) -> dict:
    from tools.write_journal.core import write_journal

    return write_journal(dict(payload or WRITE_PAYLOAD))


def _fts_rows(order_by_path: bool = True) -> list[dict]:
    from tools.lib.paths import get_fts_db_path

    conn = sqlite3.connect(str(get_fts_db_path()))
    try:
        cursor = conn.execute(
            "SELECT * FROM journals" + (" ORDER BY path" if order_by_path else "")
        )
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def _fts_row_for(rel_path: str) -> dict | None:
    from tools.lib.paths import get_fts_db_path

    conn = sqlite3.connect(str(get_fts_db_path()))
    try:
        cursor = conn.execute("SELECT * FROM journals WHERE path = ?", (rel_path,))
        columns = [description[0] for description in cursor.description]
        row = cursor.fetchone()
        return dict(zip(columns, row)) if row is not None else None
    finally:
        conn.close()


def _pending() -> list[str]:
    from tools.lib.pending_writes import get_pending

    return get_pending()


def _written_rel_path(result: dict) -> str:
    from tools.lib.path_contract import build_journal_path_fields
    from tools.lib.paths import get_journals_dir, get_user_data_dir

    return build_journal_path_fields(
        Path(result["journal_path"]),
        journals_dir=get_journals_dir(),
        user_data_dir=get_user_data_dir(),
    )["rel_path"]


# ============================================================
# Search preflight after a write: findable without archive reads
# ============================================================


class TestSearchAfterWrite:
    def test_first_fulltext_search_after_write_reads_no_other_journal(
        self, isolated_data_dir, journal_reads
    ):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_index_to_steady_state()

        result = _write_one_journal()
        assert result.get("journal_path"), result.get("error")
        written = Path(result["journal_path"])
        assert _pending() == [], "a successful write-through must not queue anything"

        journal_reads.reset()
        response = _fulltext_search(DISTINCTIVE_WORD)

        foreign_reads = [path for path in journal_reads.reads if Path(path) != written]
        assert not foreign_reads, (
            f"first full-text search after a write read {len(foreign_reads)} journal "
            "file(s) other than the new one: "
            f"{sorted(set(foreign_reads))[:5]}"
        )
        # The search must actually be served from the FTS index.
        hits = response.get("merged_results") or []
        assert any(written.name in str(item.get("path", "")) for item in hits), (
            f"full-text search must find the new journal by its distinctive word, "
            f"got hits: {[item.get('path') for item in hits]}"
        )


# ============================================================
# Write-through row identity: one file → FTS row code path
# ============================================================


class TestWriteThroughRowIdentity:
    def test_written_row_equals_rebuild_row_column_by_column(self, isolated_data_dir):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_index_to_steady_state()

        result = _write_one_journal()
        assert result.get("journal_path"), result.get("error")
        rel_path = _written_rel_path(result)

        written_row = _fts_row_for(rel_path)
        assert written_row is not None, "write-through must insert the FTS row"
        # The row must carry the real file fingerprint, not a placeholder.
        assert written_row["file_hash"], "write-through must store the real file hash"

        from tools.build_index import build_all

        build_all(incremental=False)
        rebuilt_row = _fts_row_for(rel_path)

        assert rebuilt_row is not None
        assert written_row == rebuilt_row, (
            "write-through row must equal the rebuild row for the same file, "
            f"column by column;\nwritten: {written_row}\nrebuilt: {rebuilt_row}"
        )

    def test_n_write_throughs_equal_one_full_rebuild(self, isolated_data_dir):
        from tools.build_index import build_all

        results = []
        for i in range(6):
            payload = dict(WRITE_PAYLOAD)
            payload["date"] = f"2026-04-1{i + 1}"
            payload["title"] = f"第{i + 1}篇写入穿透日志"
            payload["content"] = f"这是第{i + 1}篇写入穿透日志的正文。{DISTINCTIVE_WORD}"
            payload["tags"] = ["fts-write-through-contract"]
            result = _write_one_journal(payload)
            assert result.get("journal_path"), result.get("error")
            results.append(result)

        write_through_rows = _fts_rows()
        assert len(write_through_rows) == 6

        build_all(incremental=False)
        rebuilt_rows = _fts_rows()

        assert write_through_rows == rebuilt_rows, (
            "N write-throughs must equal one full rebuild " "(SELECT * FROM journals ORDER BY path)"
        )


# ============================================================
# Write envelope: fts_row side effect and pending queue
# ============================================================


class TestWriteEnvelope:
    def test_normal_write_reports_fts_row_complete_and_pending_skipped(self, isolated_data_dir):
        from tools.lib.workflow_signals import INDEX_SIDE_EFFECT_NAMES

        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_index_to_steady_state()

        result = _write_one_journal()
        assert result.get("journal_path"), result.get("error")

        assert "fts_row" in INDEX_SIDE_EFFECT_NAMES
        fts_records = [r for r in result["side_effects"] if r["name"] == "fts_row"]
        assert len(fts_records) == 1
        assert fts_records[0]["phase"] == "post_commit"
        assert fts_records[0]["status"] == "complete"
        assert fts_records[0]["blocking"] is False

        pending_records = [r for r in result["side_effects"] if r["name"] == "mark_pending"]
        assert len(pending_records) == 1
        assert pending_records[0]["status"] == "skipped"

        assert result["index_status"] == "complete"
        assert result["side_effects_status"] == "complete"
        assert result["write_outcome"] != "success_degraded"
        assert result["write_outcome"] == "success_pending_confirmation"
        assert _pending() == []

    def test_forced_write_through_failure_queues_and_degrades(self, isolated_data_dir):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_index_to_steady_state()

        import tools.write_journal.core as write_core

        original = write_core.upsert_fts_row
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                write_core,
                "upsert_fts_row",
                lambda *_a, **_k: (_ for _ in ()).throw(
                    RuntimeError("synthetic FTS write-through failure")
                ),
            )
            result = _write_one_journal()
        assert result.get("journal_path"), result.get("error")
        assert original is not None  # keep the import meaningful for readers

        fts_records = [r for r in result["side_effects"] if r["name"] == "fts_row"]
        assert len(fts_records) == 1
        assert fts_records[0]["status"] == "failed"
        assert fts_records[0]["recovery_strategy"] == "life-index index"

        pending_records = [r for r in result["side_effects"] if r["name"] == "mark_pending"]
        assert [r["status"] for r in pending_records] == ["queued"]

        assert result["success"] is True
        assert result["write_outcome"] == "success_degraded"
        assert result["index_status"] == "degraded"
        assert _written_rel_path(result) in _pending()

        # The next search preflight consumes the queue and repairs the index.
        response = _fulltext_search(DISTINCTIVE_WORD)
        assert _pending() == []
        hits = response.get("merged_results") or []
        assert any(
            Path(result["journal_path"]).name in str(item.get("path", "")) for item in hits
        ), "the repairing search must find the journal after queue consumption"


# ============================================================
# Edit write-through: replace the row, queue only on failure
# ============================================================


class TestEditWriteThrough:
    def _setup(self, isolated_data_dir: Path) -> Path:
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_index_to_steady_state()
        result = _write_one_journal()
        assert result.get("journal_path"), result.get("error")
        return Path(result["journal_path"])

    def test_edit_replaces_fts_row(self, isolated_data_dir):
        written = self._setup(isolated_data_dir)
        assert _pending() == []

        from tools.edit_journal import edit_journal

        edit_result = edit_journal(
            journal_path=written,
            frontmatter_updates={},
            replace_content=f"编辑后的正文，包含替换后词汇{DISTINCTIVE_WORD}。",
        )
        assert edit_result.get("success") is True, edit_result.get("error")
        assert edit_result.get("fts_row_updated") is True
        assert _pending() == [], "a successful edit write-through must not queue anything"

        response = _fulltext_search("替换后词汇")
        hits = response.get("merged_results") or []
        assert any(
            written.name in str(item.get("path", "")) for item in hits
        ), "the new distinctive word must find the edited journal"

    def test_forced_edit_write_through_failure_queues(self, isolated_data_dir):
        written = self._setup(isolated_data_dir)

        import tools.edit_journal as edit_module

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                edit_module,
                "upsert_fts_row",
                lambda *_a, **_k: (_ for _ in ()).throw(
                    RuntimeError("synthetic edit FTS write-through failure")
                ),
            )
            from tools.edit_journal import edit_journal

            edit_result = edit_journal(
                journal_path=written,
                frontmatter_updates={},
                replace_content=f"编辑失败的正文，包含失败后词汇{DISTINCTIVE_WORD}。",
            )
        assert edit_result.get("success") is True, edit_result.get("error")
        assert edit_result.get("fts_row_updated") is False
        assert edit_result.get("pending_marked") is True
        assert _pending() != []

        # The next search preflight repairs the row from the queue.
        response = _fulltext_search("失败后词汇")
        assert _pending() == []
        hits = response.get("merged_results") or []
        assert any(written.name in str(item.get("path", "")) for item in hits)


# ============================================================
# Incremental scan: decide "unchanged" from (mtime, size)
# ============================================================


class TestIncrementalStatScan:
    def _incremental_index(self) -> dict:
        from tools.build_index import build_all

        return build_all(incremental=True)

    def test_index_after_outside_edit_reads_only_that_file(self, isolated_data_dir, journal_reads):
        journals = _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_index_to_steady_state()

        edited = journals[7]
        stat = edited.stat()
        edited.write_text(
            edited.read_text(encoding="utf-8")
            + "\n\n外部编辑追加的正文，改变了外部编辑词汇文件大小。\n",
            encoding="utf-8",
        )
        os.utime(edited, (stat.st_mtime + 10, stat.st_mtime + 10))

        journal_reads.reset()
        self._incremental_index()

        assert journal_reads.distinct == 1, (
            f"incremental index after one outside edit must read exactly that "
            f"file, got {journal_reads.distinct} distinct reads"
        )
        assert set(journal_reads.reads) == {str(edited)}
        row = _fts_row_for(str(edited.relative_to(isolated_data_dir)).replace("\\", "/"))
        assert row is not None, "the re-read file must keep its FTS row"
        # Stored content is jieba-segmented (space-joined tokens).
        segmented_tokens = set(row["content"].split())
        assert {
            "外部",
            "编辑",
            "词汇",
        } <= segmented_tokens, (
            f"the outside-edited text must reach the stored row, got: {row['content']}"
        )

    def test_index_after_outside_delete_drops_the_row(self, isolated_data_dir):
        journals = _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_index_to_steady_state()

        deleted = journals[3]
        rel_path = str(deleted.relative_to(isolated_data_dir)).replace("\\", "/")
        assert _fts_row_for(rel_path) is not None
        deleted.unlink()

        self._incremental_index()

        assert _fts_row_for(rel_path) is None, "deleted files must lose their FTS row"

    def test_index_with_nothing_changed_reads_no_journal(self, isolated_data_dir, journal_reads):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_index_to_steady_state()

        journal_reads.reset()
        result = self._incremental_index()

        assert journal_reads.total == 0, (
            f"incremental index with nothing changed re-read {journal_reads.total} "
            "journal files; expected 0"
        )
        assert result["fts"]["added"] == 0
        assert result["fts"]["updated"] == 0
        assert result["fts"]["removed"] == 0

    def test_legacy_index_without_stats_rebuilds_once_automatically(
        self, isolated_data_dir, journal_reads
    ):
        """Existing pre-stats installations get their one-time rebuild for free.

        An upgraded installation carries an FTS db whose recorded
        schema_version predates the stats side table. The first incremental
        index must notice via the recorded version, fully rebuild once, and
        leave a current stats table behind.
        """
        from tools.lib.paths import get_fts_db_path
        from tools.lib.search_index import FTS_SCHEMA_VERSION

        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_index_to_steady_state()

        conn = sqlite3.connect(str(get_fts_db_path()))
        try:
            conn.execute("DELETE FROM fts_file_stats")
            conn.execute(
                "INSERT OR REPLACE INTO index_meta (key, value) VALUES ('schema_version', '2')"
            )
            conn.commit()
        finally:
            conn.close()

        journal_reads.reset()
        result = self._incremental_index()

        # One parse per journal: the file is read exactly once (bytes) and the
        # same bytes feed both the row content and the file hash (R4).
        assert journal_reads.total == N_JOURNALS, (
            f"the one-time upgrade rebuild must parse each journal exactly once, "
            f"got {journal_reads.total} reads (expected {N_JOURNALS})"
        )
        assert result["fts"]["total"] == N_JOURNALS

        conn = sqlite3.connect(str(get_fts_db_path()))
        try:
            stats_count = conn.execute("SELECT COUNT(*) FROM fts_file_stats").fetchone()[0]
            recorded_version = conn.execute(
                "SELECT value FROM index_meta WHERE key = 'schema_version'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert stats_count == N_JOURNALS
        assert int(recorded_version) == FTS_SCHEMA_VERSION


# ============================================================
# Concurrency: the write-through must not race a full rebuild
# ============================================================


class TestWriteThroughIndexLock:
    """The write-through serializes with index builds through the index lock.

    ``build_all`` holds the index ``FileLock`` for the whole build. Without
    holding the same lock, a write-through inserted between a rebuild's
    enumeration and its delete/insert phase is wiped by the rebuild, nothing
    is queued, and the journal stays unsearchable (CHARTER §1.11 recall-first
    violation).
    """

    def test_write_while_index_lock_held_degrades_and_repairs(self, isolated_data_dir):
        """A busy index lock fails the write-through into the queue fallback."""
        import time as _time

        from tools.lib.file_lock import FileLock, get_index_lock_path
        from tools.lib.pending_writes import get_pending

        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_index_to_steady_state()

        lock = FileLock(get_index_lock_path(), timeout=30.0)
        with lock:
            started = _time.monotonic()
            result = _write_one_journal()
            elapsed = _time.monotonic() - started

            # Prompt return: bounded by the short fts-row lock timeout, not by
            # the 30s holder timeout.
            assert elapsed < 20, f"write blocked {elapsed:.1f}s on the index lock"
            assert Path(result["journal_path"]).exists()

            fts_records = [r for r in result["side_effects"] if r["name"] == "fts_row"]
            assert [r["status"] for r in fts_records] == ["failed"]
            assert fts_records[0]["recovery_strategy"] == "life-index index"
            pending_records = [r for r in result["side_effects"] if r["name"] == "mark_pending"]
            assert [r["status"] for r in pending_records] == ["queued"]
            assert result["write_outcome"] == "success_degraded"
            assert result["index_status"] == "degraded"
            assert _written_rel_path(result) in get_pending()

        # Once the holder releases the lock, the next search preflight consumes
        # the queue and the journal becomes full-text searchable.
        response = _fulltext_search(DISTINCTIVE_WORD)
        assert get_pending() == []
        hits = response.get("merged_results") or []
        written_name = Path(result["journal_path"]).name
        assert any(
            written_name in str(item.get("path", "")) for item in hits
        ), "the repairing search must find the journal after queue consumption"

    def test_write_during_full_rebuild_is_not_lost(self, isolated_data_dir):
        """Deterministic enumeration/write/delete interleave: the row survives.

        The rebuild is paused after its file enumeration and before its
        delete/insert phase; the journal is written during the pause. On the
        unlocked write-through the rebuild's DELETE wipes the just-inserted
        row and nothing repairs it. With the index lock held by the rebuild,
        the write-through times out, queues the path, and the next search
        repairs the index.
        """
        import threading

        from tools.lib import fts_update as fts_update_mod

        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_index_to_steady_state()

        real_scan = fts_update_mod.scan_journal_files
        enumeration_done = threading.Event()
        write_finished = threading.Event()

        def _paused_scan(journals_dir, *args, **kwargs):
            # Consume the real scan fully, then pause the rebuild between
            # enumeration and the delete/insert phase.
            files = list(real_scan(journals_dir, *args, **kwargs))
            enumeration_done.set()
            assert write_finished.wait(timeout=60), "write never finished during pause"
            return files

        rebuild_errors: list[BaseException] = []

        from tools.build_index import build_all

        def _run_rebuild():
            try:
                with pytest.MonkeyPatch.context() as mp:
                    mp.setattr(fts_update_mod, "scan_journal_files", _paused_scan)
                    build_all(incremental=False)
            except BaseException as exc:  # pragma: no cover - surfaced below
                rebuild_errors.append(exc)

        rebuild_thread = threading.Thread(target=_run_rebuild)
        rebuild_thread.start()
        assert enumeration_done.wait(timeout=60), "rebuild never reached enumeration"

        write_outcome: dict = {}

        def _run_write():
            write_outcome["result"] = _write_one_journal()

        write_thread = threading.Thread(target=_run_write)
        write_thread.start()
        write_thread.join(timeout=60)
        write_finished.set()
        rebuild_thread.join(timeout=120)

        assert not write_thread.is_alive(), "write thread hung"
        assert not rebuild_thread.is_alive(), f"rebuild thread hung: {rebuild_errors}"
        assert not rebuild_errors, f"rebuild failed: {rebuild_errors}"

        result = write_outcome["result"]
        assert result.get("journal_path"), result.get("error")
        assert Path(result["journal_path"]).exists()

        response = _fulltext_search(DISTINCTIVE_WORD)
        hits = response.get("merged_results") or []
        written_name = Path(result["journal_path"]).name
        assert any(written_name in str(item.get("path", "")) for item in hits), (
            "a journal written during a full rebuild must remain full-text "
            "searchable after the rebuild finishes"
        )
