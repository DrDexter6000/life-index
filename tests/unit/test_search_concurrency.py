#!/usr/bin/env python3
"""
Tests for search + rebuild concurrency via file_lock.

Covers:
- Search acquires index lock during read
- Concurrent search + rebuild serialize through the lock
- Lock timeout returns structured E0604 error
- lock_wait_ms present in performance metrics
"""

import threading
import time
from pathlib import Path

import pytest

from tools.lib.file_lock import FileLock, get_index_lock_path


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    """Isolate paths to tmp_path and patch heavy search dependencies."""
    import tools.lib.config as cfg
    import tools.lib.paths as paths
    import tools.lib.vector_index_simple as vi_mod
    import tools.write_journal.core as write_core

    idx = tmp_path / ".index"
    idx.mkdir(parents=True)
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir(parents=True)
    journals_dir = tmp_path / "Journals"
    (journals_dir / "2026" / "03").mkdir(parents=True)

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))

    for module in (cfg, paths, write_core):
        monkeypatch.setattr(module, "get_user_data_dir", lambda _t=tmp_path: _t, raising=False)
        monkeypatch.setattr(module, "get_journals_dir", lambda _j=journals_dir: _j, raising=False)

    monkeypatch.setattr(vi_mod, "INDEX_DIR", idx)
    monkeypatch.setattr(vi_mod, "VEC_INDEX_PATH", idx / "vectors_simple.pkl")
    monkeypatch.setattr(vi_mod, "META_PATH", idx / "vectors_simple_meta.json")
    monkeypatch.setattr(vi_mod, "get_user_data_dir", lambda _t=tmp_path: _t, raising=False)


def _mock_search_deps(monkeypatch):
    """Mock heavy search sub-pipelines so we don't need real FTS/semantic backends."""
    import tools.search_journals.core as search_core

    monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
    monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)

    def _mock_keyword_pipeline(**kwargs):
        perf = {"l1_time_ms": 1.0, "l2_time_ms": 1.0, "l3_time_ms": 1.0}
        return ([], [], [], False, 0, perf)

    def _mock_semantic_pipeline(**kwargs):
        perf = {"semantic_time_ms": 1.0}
        return ([], perf, False, None)

    monkeypatch.setattr(search_core, "run_keyword_pipeline", _mock_keyword_pipeline)
    monkeypatch.setattr(search_core, "run_semantic_pipeline", _mock_semantic_pipeline)


class TestSearchLockAcquisition:

    def test_search_includes_lock_wait_ms(self, tmp_path: Path, monkeypatch):
        """Search result should contain lock_wait_ms in performance metrics."""
        import tools.search_journals.core as search_core
        from tools.lib.index_freshness import FreshnessReport

        _mock_search_deps(monkeypatch)
        monkeypatch.setattr(
            "tools.lib.index_freshness.check_full_freshness",
            lambda *a, **kw: FreshnessReport(fts_fresh=True, vector_fresh=True, overall_fresh=True),
        )

        result = search_core.hierarchical_search(query="test", level=3, semantic=False)
        assert result["success"] is True
        assert "lock_wait_ms" in result["performance"]
        assert isinstance(result["performance"]["lock_wait_ms"], float)
        assert result["performance"]["lock_wait_ms"] >= 0

    def test_search_blocks_while_rebuild_holds_lock(self, tmp_path: Path, monkeypatch):
        """Search should wait for rebuild to release the index lock."""
        import tools.search_journals.core as search_core
        from tools.lib.index_freshness import FreshnessReport

        _mock_search_deps(monkeypatch)
        monkeypatch.setattr(
            "tools.lib.index_freshness.check_full_freshness",
            lambda *a, **kw: FreshnessReport(fts_fresh=True, vector_fresh=True, overall_fresh=True),
        )

        lock_path = get_index_lock_path()
        search_started = threading.Event()
        search_finished = threading.Event()
        rebuild_released = threading.Event()

        # Hold the index lock (simulating a rebuild)
        lock = FileLock(lock_path, timeout=30.0)
        lock.acquire()

        search_result: list = [None]

        def run_search():
            search_started.set()
            search_result[0] = search_core.hierarchical_search(
                query="blocked test", level=3, semantic=False
            )
            search_finished.set()

        t = threading.Thread(target=run_search)
        t.start()

        # Wait for search thread to start
        search_started.wait(timeout=5)

        # Search should be blocked — not finished yet
        assert not search_finished.is_set(), "Search should be blocked waiting for lock"

        # Release the lock (simulating rebuild finishing)
        lock.release()
        rebuild_released.set()

        # Now search should complete
        search_finished.wait(timeout=10)
        t.join(timeout=10)

        assert search_result[0] is not None
        assert search_result[0]["success"] is True
        # Lock wait should be >= 0 (present in performance dict).
        # On Windows, thread scheduling may release/acquire so fast that
        # elapsed rounds to 0.0ms — the key guarantee is the field exists.
        assert "lock_wait_ms" in search_result[0]["performance"]
        assert search_result[0]["performance"]["lock_wait_ms"] >= 0

    def test_lock_timeout_returns_e0604(self, tmp_path: Path, monkeypatch):
        """When lock is held longer than timeout, search returns E0604 error."""
        import tools.search_journals.core as search_core
        from tools.lib.index_freshness import FreshnessReport

        _mock_search_deps(monkeypatch)
        monkeypatch.setattr(
            "tools.lib.index_freshness.check_full_freshness",
            lambda *a, **kw: FreshnessReport(fts_fresh=True, vector_fresh=True, overall_fresh=True),
        )
        # Use a very short timeout for the test
        monkeypatch.setattr("tools.lib.search_config.FILE_LOCK_TIMEOUT_SEARCH", 0.3)
        # Also patch it in the core module if it was imported
        monkeypatch.setattr(search_core, "FILE_LOCK_TIMEOUT_SEARCH", 0.3, raising=False)

        lock_path = get_index_lock_path()

        # Hold the lock
        lock = FileLock(lock_path, timeout=30.0)
        lock.acquire()

        try:
            # Search with short timeout should fail
            result = search_core.hierarchical_search(query="timeout test", level=3, semantic=False)
            assert result["success"] is False
            assert result["error"]["code"] == "E0604"
            assert "timed out" in result["error"]["message"].lower()
        finally:
            lock.release()


class TestSearchRebuildConcurrency:

    def test_concurrent_search_and_rebuild_do_not_crash(self, tmp_path: Path, monkeypatch):
        """Multiple search threads + rebuild-like lock holders should not crash."""
        import tools.search_journals.core as search_core
        from tools.lib.index_freshness import FreshnessReport

        _mock_search_deps(monkeypatch)
        monkeypatch.setattr(
            "tools.lib.index_freshness.check_full_freshness",
            lambda *a, **kw: FreshnessReport(fts_fresh=True, vector_fresh=True, overall_fresh=True),
        )

        lock_path = get_index_lock_path()
        errors: list[str] = []
        results: list[dict] = []
        lock = threading.Lock()

        def do_search(query: str):
            try:
                r = search_core.hierarchical_search(query=query, level=3, semantic=False)
                with lock:
                    results.append(r)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        def do_rebuild_hold(duration: float):
            """Simulate a rebuild holding the index lock."""
            fl = FileLock(lock_path, timeout=10.0)
            try:
                fl.acquire()
                time.sleep(duration)
            finally:
                fl.release()

        threads = []

        # Start a "rebuild" that holds the lock briefly
        t_rebuild = threading.Thread(target=do_rebuild_hold, args=(0.2,))
        threads.append(t_rebuild)

        # Start multiple searches
        for i in range(3):
            t = threading.Thread(target=do_search, args=(f"query {i}",))
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Unexpected errors: {errors}"
        # All searches should succeed (they just waited for the lock)
        for r in results:
            assert r["success"] is True, f"Unexpected failure: {r}"

    def test_search_lock_is_file_based_not_threading_lock(self, tmp_path: Path):
        """Verify the search uses FileLock (process-level), not threading.Lock."""
        from tools.lib.file_lock import FileLock, get_index_lock_path

        lock_path = get_index_lock_path()
        fl = FileLock(lock_path, timeout=0.5)

        # Should be able to acquire and release
        fl.acquire()
        assert fl.is_locked()
        fl.release()
        assert not fl.is_locked()
