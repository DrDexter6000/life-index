"""Concurrency behavior of the derived SQLite stores (metadata cache, FTS).

Two ``write`` processes opening the same derived store at once used to race
on ``PRAGMA journal_mode=WAL``: the switch needs a lock the busy timeout
does not reliably cover, so the loser saw ``database is locked`` at once —
before the journal commit, as an uncaught traceback instead of an error
envelope. Both stores open through the one shared helper
(``tools/lib/sqlite_wal.py``); these tests pin that helper's behavior per
store — no mode switch when already WAL, retry on busy, bounded failure —
and the advisory degradation of the write path. The reproduction is
deterministic: no real process race, a connection stand-in reports the
store busy exactly as often as the test decides.
"""

import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest

from tools.lib import metadata_cache, search_index, sqlite_wal
from tools.write_journal import core as write_core

# Each store opens through the shared connect_wal; the tests exercise each.
STORES = [
    pytest.param(
        metadata_cache,
        "get_cache_dir",
        "get_metadata_db_path",
        "init_metadata_cache",
        id="metadata_cache",
    ),
    pytest.param(search_index, "get_index_dir", "get_fts_db_path", "init_fts_db", id="fts_index"),
]


class _ProbingConnection(sqlite3.Connection):
    """A real connection that can fake a busy WAL switch and record SQL."""

    switch_busy_times: int = 0  # report "database is locked" N more times
    switch_attempts: int = 0  # how often the switch statement ran
    executed: list[str] = []  # every execute() call, in order

    @classmethod
    def reset(cls, switch_busy_times: int = 0) -> None:
        cls.switch_busy_times = switch_busy_times
        cls.switch_attempts = 0
        cls.executed = []

    def execute(self, sql: Any, *args: Any, **kwargs: Any) -> sqlite3.Cursor:
        probe = type(self)
        statement = str(sql)
        probe.executed.append(statement)
        if "journal_mode=WAL" in statement:  # the switch form only, not the read
            probe.switch_attempts += 1
            if probe.switch_busy_times > 0:
                probe.switch_busy_times -= 1
                raise sqlite3.OperationalError("database is locked")
        return super().execute(sql, *args, **kwargs)


class _AlwaysBusyConnection:
    """Stands in for a connection whose every statement reports the store busy."""

    def execute(self, *_args: Any, **_kwargs: Any) -> sqlite3.Cursor:
        raise sqlite3.OperationalError("database is locked")

    def close(self) -> None:
        pass


@pytest.fixture
def probe_connect(monkeypatch: pytest.MonkeyPatch):
    """Route ``sqlite3.connect`` through the probing connection."""
    real_connect = sqlite3.connect

    def connect_with_probe(path: Any, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        kwargs["factory"] = _ProbingConnection
        return real_connect(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect_with_probe)


def _use_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    dir_getter: str,
    db_getter: str,
    init_name: str,
) -> Any:
    """Point one store module at a fresh temporary database."""
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    monkeypatch.setattr(module, dir_getter, lambda: store_dir)
    monkeypatch.setattr(module, db_getter, lambda: store_dir / "derived.db")
    return getattr(module, init_name)


@pytest.mark.parametrize("module,dir_getter,db_getter,init_name", STORES)
def test_open_waits_out_a_busy_wal_switch_and_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    probe_connect,
    module,
    dir_getter,
    db_getter,
    init_name,
) -> None:
    """A transient lock during the mode switch is retried, not fatal."""
    init = _use_store(tmp_path, monkeypatch, module, dir_getter, db_getter, init_name)
    monkeypatch.setattr(sqlite_wal, "WAL_OPEN_RETRY_PAUSE_SECONDS", 0.01)
    _ProbingConnection.reset(switch_busy_times=2)

    conn = init()
    try:
        assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        assert _ProbingConnection.switch_attempts == 3  # two busy, then the switch
    finally:
        conn.close()


@pytest.mark.parametrize("module,dir_getter,db_getter,init_name", STORES)
def test_no_mode_switch_when_the_database_is_already_wal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    probe_connect,
    module,
    dir_getter,
    db_getter,
    init_name,
) -> None:
    """The steady state opens without attempting the lock-needing switch."""
    init = _use_store(tmp_path, monkeypatch, module, dir_getter, db_getter, init_name)
    db_path = getattr(module, db_getter)()
    setup = sqlite3.connect(str(db_path))  # a real, unprobed connection
    setup.execute("PRAGMA journal_mode=WAL")
    setup.close()
    _ProbingConnection.reset()

    conn = init()
    try:
        assert "PRAGMA journal_mode" in _ProbingConnection.executed  # mode read first
        assert not any("journal_mode=WAL" in sql for sql in _ProbingConnection.executed)
    finally:
        conn.close()


@pytest.mark.parametrize("module,dir_getter,db_getter,init_name", STORES)
def test_busy_forever_raises_within_the_bounded_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    probe_connect,
    module,
    dir_getter,
    db_getter,
    init_name,
) -> None:
    """A lock that never releases gives up after bounded retries, not at once."""
    init = _use_store(tmp_path, monkeypatch, module, dir_getter, db_getter, init_name)
    monkeypatch.setattr(sqlite_wal, "WAL_OPEN_MAX_WAIT_SECONDS", 0.3)
    monkeypatch.setattr(sqlite_wal, "WAL_OPEN_RETRY_PAUSE_SECONDS", 0.02)
    _ProbingConnection.reset(switch_busy_times=10**9)  # the lock never releases

    started = time.monotonic()
    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        init()
    assert time.monotonic() - started < 5  # bounded, never an endless retry
    assert _ProbingConnection.switch_attempts >= 2  # it retried before giving up


def test_write_succeeds_without_candidates_when_the_cache_stays_busy(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A busy metadata cache degrades the advisory candidates step, never the
    journal: no uncaught traceback, the write commits, the degraded step is
    recorded honestly."""
    real_connect = sqlite3.connect

    def busy_metadata_cache_only(path: Any, *args: Any, **kwargs: Any) -> Any:
        if str(path).endswith("metadata_cache.db"):
            return _AlwaysBusyConnection()
        return real_connect(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", busy_metadata_cache_only)
    monkeypatch.setattr(sqlite_wal, "WAL_OPEN_MAX_WAIT_SECONDS", 0.2)
    monkeypatch.setattr(sqlite_wal, "WAL_OPEN_RETRY_PAUSE_SECONDS", 0.02)

    result = write_core.write_journal(
        {
            "date": "2026-03-14",
            "title": "Busy cache journal",
            "content": "The journal survives a locked metadata cache.",
            "topic": ["work"],
            "location": "Test City",
            "weather": "Sunny",
        }
    )

    assert result["success"] is True
    assert result["write_outcome"] == "success_degraded"
    assert result["related_candidates"] == []
    assert result["confirmation"]["related_candidates"] == []
    record = next(item for item in result["side_effects"] if item["name"] == "related_candidates")
    assert record["status"] == "failed"
    assert record["phase"] == "pre_commit"
    assert record["blocking"] is False
    assert "database is locked" in record["error"]
    # Nothing needs repairing: the journal is committed and the candidates are
    # advisory — the recovery text must not send the agent into a rebuild.
    assert record["recovery_strategy"] == (
        "no action needed for this write: the journal is committed and "
        "related candidates are advisory, the cache was only busy; run "
        "life-index index --rebuild only if this record keeps appearing"
    )

    journal_path = Path(result["journal_path"])
    assert journal_path.is_file()
    by_name = {item["name"]: item for item in result["side_effects"]}
    assert by_name["journal_commit"]["status"] == "complete"
    assert by_name["fts_row"]["status"] == "complete"  # the FTS store is not weakened
