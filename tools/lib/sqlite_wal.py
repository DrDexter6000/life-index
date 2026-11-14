#!/usr/bin/env python3
"""
Life Index - WAL-mode SQLite open helper

Opening a derived SQLite store (metadata cache, FTS index) while another
process is opening or writing it: switching a database into WAL needs a
lock the busy timeout does not reliably cover, so SQLITE_BUSY can surface
at once — before the caller's own work, as an uncaught exception. The open
here reads the current journal mode first (lock-free once the database is
in WAL) and only attempts the switch when needed, retrying a busy open or
switch within a bounded window before raising.
"""

import sqlite3
import time
from pathlib import Path

# How long one open waits for a concurrent initializer's lock before giving
# up, and how long it pauses between attempts.
WAL_OPEN_MAX_WAIT_SECONDS = 5.0
WAL_OPEN_RETRY_PAUSE_SECONDS = 0.2


def _is_busy_error(exc: sqlite3.OperationalError) -> bool:
    """Whether the error is a transient lock (retryable), not corruption."""
    message = str(exc).lower()
    return "locked" in message or "busy" in message


def connect_wal(db_path: Path) -> sqlite3.Connection:
    """Open the database in WAL mode, tolerating a concurrent open.

    When the database is already in WAL mode (the steady state), no mode
    switch is attempted at all — the switch is the one step whose lock the
    busy timeout does not reliably cover. A busy open or switch is retried
    within ``WAL_OPEN_MAX_WAIT_SECONDS`` and only then raises.
    """
    conn = sqlite3.connect(str(db_path), timeout=WAL_OPEN_MAX_WAIT_SECONDS)
    deadline = time.monotonic() + WAL_OPEN_MAX_WAIT_SECONDS
    while True:
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()
            if str(mode[0]).lower() != "wal":
                conn.execute("PRAGMA journal_mode=WAL")
            return conn
        except sqlite3.OperationalError as exc:
            if not _is_busy_error(exc) or time.monotonic() >= deadline:
                conn.close()
                raise
            time.sleep(WAL_OPEN_RETRY_PAUSE_SECONDS)
