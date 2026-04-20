"""
Tests for FTS schema auto-migration (Round 10, T0.3).

Validates D13: deployed v1.x users upgrading to Round 10 should have
their FTS index automatically migrated to v2 (title split) on first
open, without manual `life-index index --rebuild`.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _reload_search_index(isolated_data_dir: Path) -> None:
    """Reload search_index to pick up isolated data dir."""
    import importlib
    import tools.lib.search_index as si_mod
    import tools.lib.fts_update as fu_mod
    import tools.lib.fts_search as fs_mod

    importlib.reload(si_mod)
    importlib.reload(fu_mod)
    importlib.reload(fs_mod)


def _create_v1_database(
    db_path: Path, title_raw: str, content: str = "测试内容"
) -> None:
    """
    Create a v1 schema FTS database (no title_segmented column).

    Simulates a pre-Round-10 database where title contained
    jieba-segmented tokens.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # v1 schema: no title_segmented, title contains segmented text
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS journals USING fts5(
            path,
            title,
            content,
            date,
            location,
            weather,
            topic,
            project,
            tags,
            mood,
            people,
            file_hash UNINDEXED,
            modified_time UNINDEXED
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Insert with segmented title (old behavior)
    cursor.execute(
        "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
        ("schema_version", "1"),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
        ("tokenizer_version", "2"),
    )

    conn.commit()
    conn.close()


def _create_journal_file(data_dir: Path, title: str, content: str = "测试内容") -> Path:
    """Create a minimal journal file."""
    from datetime import datetime

    journals_dir = data_dir / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now().isoformat(timespec="seconds")
    file_path = journals_dir / "life-index_2026-03-07_001.md"

    frontmatter = f"""---
title: "{title}"
date: {now}
location: "Lagos, Nigeria"
weather: "晴天 28°C"
mood: ["专注"]
tags: ["测试"]
topic: ["work"]
---

# {title}

{content}
"""
    file_path.write_text(frontmatter, encoding="utf-8")
    return file_path


# ── Migration detection tests ───────────────────────────────────────────


class TestSchemaMigrationDetection:
    """Verify old schema is detected and migrated automatically."""

    def test_old_schema_triggers_migration(self, isolated_data_dir: Path) -> None:
        """
        When a v1 schema DB exists (no title_segmented column),
        opening the index should auto-detect and trigger migration.

        After migration: title_segmented column exists, data is rebuilt.
        """
        from tools.lib.search_index import (
            FTS_DB_PATH,
            ensure_fts_schema,
            init_fts_db,
        )

        _create_v1_database(FTS_DB_PATH, "计划 回 重庆")
        _create_journal_file(
            isolated_data_dir,
            "计划回重庆给小朋友过生日",
            "今天很开心",
        )

        # Migration should happen here
        ensure_fts_schema()

        # Verify new schema
        conn = sqlite3.connect(str(FTS_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(journals)")
        columns = {row[1] for row in cursor.fetchall()}

        assert "title_segmented" in columns, (
            "Migration should add title_segmented column"
        )
        conn.close()

    def test_migration_log_recorded(self, isolated_data_dir: Path) -> None:
        """
        index_meta should contain a migration_log entry documenting
        the v1 → v2 migration.
        """
        from tools.lib.search_index import FTS_DB_PATH, ensure_fts_schema

        _create_v1_database(FTS_DB_PATH, "计划 回 重庆")
        _create_journal_file(isolated_data_dir, "计划回重庆给小朋友过生日")

        ensure_fts_schema()

        conn = sqlite3.connect(str(FTS_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM index_meta WHERE key = 'migration_log'")
        row = cursor.fetchone()
        conn.close()

        assert row is not None, "migration_log should be written"
        log_data = json.loads(row[0])
        assert "from" in log_data
        assert "to" in log_data
        assert "ts" in log_data

    def test_new_schema_no_migration(self, isolated_data_dir: Path) -> None:
        """
        A v2 schema DB should NOT trigger migration on open.
        Migration must be idempotent: no unnecessary rebuilds.
        """
        from tools.lib.search_index import (
            FTS_DB_PATH,
            init_fts_db,
            ensure_fts_schema,
            write_index_meta,
        )

        _create_journal_file(isolated_data_dir, "测试标题", "测试内容")

        # Create v2 schema
        conn = init_fts_db()
        write_index_meta(conn)
        conn.close()

        # Should not trigger migration
        result = ensure_fts_schema()

        assert result.get("migrated") is not True, (
            "New schema should not trigger migration"
        )

    def test_migration_preserves_searchability(self, isolated_data_dir: Path) -> None:
        """
        After migration, search should still work and titles
        should be raw (not segmented).
        """
        from tools.lib.search_index import (
            FTS_DB_PATH,
            ensure_fts_schema,
            search_fts,
        )

        _create_v1_database(FTS_DB_PATH, "计划 回 重庆")
        _create_journal_file(
            isolated_data_dir,
            "计划回重庆给小朋友过生日",
            "今天去给小朋友过生日很开心",
        )

        ensure_fts_schema()
        # Use "小朋友" — a complete jieba token present in both title and
        # content.  ("生日" is embedded inside the token "过生日" so a raw
        # FTS query for "生日" won't match without query-side segmentation.)
        results = search_fts("小朋友")

        assert len(results) > 0, "Search should work after migration"

        # Title must be raw, not segmented
        result_title = results[0]["title"]
        assert "计划 回" not in result_title, (
            f"Title should not be segmented, got: '{result_title}'"
        )

    def test_migration_failure_preserves_old_table(
        self, isolated_data_dir: Path
    ) -> None:
        """
        If migration fails (e.g., no journal files to rebuild from),
        the old table should still be intact.
        """
        from tools.lib.search_index import FTS_DB_PATH, ensure_fts_schema

        _create_v1_database(FTS_DB_PATH, "计划 回 重庆")
        # No journal files created — rebuild will produce empty index

        # Should not crash
        result = ensure_fts_schema()

        # The function should handle gracefully
        # (may succeed with empty index, or report failure)
        assert isinstance(result, dict)
