"""Filesystem consistency checking for search index freshness.

Determines whether the FTS index might be stale by checking if any journal
files have been modified after the last index sync timestamp.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path


def has_writes_since(ts: float, root: Path) -> bool:
    """Check if any .md file under root has mtime newer than ts.

    Args:
        ts: Unix timestamp from index metadata.
        root: JOURNALS_DIR path to scan.

    Returns:
        True if any .md file has mtime > ts.
    """
    if not root.exists():
        return False

    try:
        for entry in os.scandir(str(root)):
            if entry.is_dir(follow_symlinks=False):
                for sub_entry in os.scandir(entry.path):
                    if sub_entry.is_dir(follow_symlinks=False):
                        for file_entry in os.scandir(sub_entry.path):
                            if file_entry.name.endswith(".md") and file_entry.is_file(
                                follow_symlinks=False
                            ):
                                try:
                                    if file_entry.stat(follow_symlinks=False).st_mtime > ts:
                                        return True
                                except OSError:
                                    continue
                    elif sub_entry.name.endswith(".md") and sub_entry.is_file(
                        follow_symlinks=False
                    ):
                        try:
                            if sub_entry.stat(follow_symlinks=False).st_mtime > ts:
                                return True
                        except OSError:
                            continue
            elif entry.name.endswith(".md") and entry.is_file(follow_symlinks=False):
                try:
                    if entry.stat(follow_symlinks=False).st_mtime > ts:
                        return True
                except OSError:
                    continue
    except OSError:
        return False

    return False


def get_last_sync_ts(fts_db_path: Path) -> float | None:
    """Read last_updated timestamp from index_meta table.

    Args:
        fts_db_path: Path to the FTS SQLite database.

    Returns:
        Unix timestamp, or None if unavailable.
    """
    if not fts_db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(fts_db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM index_meta WHERE key = 'last_updated'")
            row = cursor.fetchone()
            if not row:
                return None
            dt = datetime.fromisoformat(row[0])
            return dt.timestamp()
        finally:
            conn.close()
    except (sqlite3.Error, ValueError, OSError):
        return None
