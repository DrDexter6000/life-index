#!/usr/bin/env python3
"""
Unit tests for the FTS single-row write-through (tools/lib/search_index.py)

The write-through builds the row from the committed file via the same parse
path a full rebuild uses (``fts_update.parse_journal`` + ``insert_fts_doc``),
so the stored row carries the real ``file_hash`` and the file's real mtime.

Tests cover:
- upsert_fts_row: single-entry FTS row built from the committed file
- Idempotent behavior (same rel_path overwrites)
- Chinese segmentation applied correctly
- List fields normalized the same way a rebuild normalizes them
- index_meta.last_updated is refreshed; version keys are not masked
- The (mtime, size) signature lands in fts_file_stats
- Error handling (DB errors raise; the write core records the failure)
- FTS-searchable after write-through
"""

import sqlite3
from pathlib import Path

import pytest


class TestUpsertFtsRow:
    """Tests for upsert_fts_row (write/edit post-commit FTS write-through)."""

    def _setup_fts_env(self, tmp_path: Path):
        """Create an isolated FTS environment with one committed journal."""
        import os

        user_data_dir = tmp_path / "Life-Index"
        journals_dir = user_data_dir / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)
        index_dir = user_data_dir / ".index"
        index_dir.mkdir(parents=True)
        fts_db_path = index_dir / "journals_fts.db"
        os.environ["LIFE_INDEX_DATA_DIR"] = str(user_data_dir)
        return user_data_dir, journals_dir, index_dir, fts_db_path

    def _write_journal_file(self, journals_dir: Path, body: str) -> Path:
        journal_path = journals_dir / "2026" / "03" / "life-index_2026-03-04_001.md"
        journal_path.write_text(
            "---\n"
            'title: "想念伙伴"\n'
            'date: "2026-03-04"\n'
            "topic:\n  - think\n"
            "tags:\n  - 亲子\n  - 回忆\n"
            "location: Lagos, Nigeria\n"
            "weather: 晴天 28C\n"
            "mood:\n  - 思念\n"
            "people:\n  - 晴岚\n"
            "project: LifeIndex\n"
            "---\n\n"
            f"{body}\n",
            encoding="utf-8",
        )
        return journal_path

    def test_basic_upsert_from_committed_file(self, tmp_path: Path):
        """The row is built from the committed file, not from in-memory data."""
        from tools.lib.search_index import upsert_fts_row

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(tmp_path)
        journal_path = self._write_journal_file(
            journals_dir, "今天在阳台上看日落，想起了晴岚小时候的模样"
        )

        doc = upsert_fts_row(journal_path)

        assert doc is not None
        assert doc["path"] == "Journals/2026/03/life-index_2026-03-04_001.md"
        assert doc["title"] == "想念伙伴"
        assert doc["date"] == "2026-03-04"
        assert doc["location"] == "Lagos, Nigeria"
        assert doc["weather"] == "晴天 28C"

        conn = sqlite3.connect(str(fts_db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM journals")
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT path, date, location, weather FROM journals")
            row = cursor.fetchone()
            assert "Journals/2026/03/life-index_2026-03-04_001.md" in row[0]
            assert row[1] == "2026-03-04"
            assert row[2] == "Lagos, Nigeria"
        finally:
            conn.close()

    def test_row_carries_real_hash_and_mtime(self, tmp_path: Path):
        """file_hash is the real content hash; modified_time is the file mtime."""
        import hashlib
        from datetime import datetime

        from tools.lib.search_index import upsert_fts_row

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(tmp_path)
        journal_path = self._write_journal_file(journals_dir, "正文内容")

        doc = upsert_fts_row(journal_path)

        expected_hash = hashlib.md5(journal_path.read_bytes(), usedforsecurity=False).hexdigest()[
            :16
        ]
        expected_mtime = datetime.fromtimestamp(journal_path.stat().st_mtime).isoformat()
        assert doc["file_hash"] == expected_hash
        assert doc["modified_time"] == expected_mtime

    def test_idempotent_overwrite(self, tmp_path: Path):
        """Upserting twice must not duplicate rows and must refresh content."""
        from tools.lib.search_index import upsert_fts_row

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(tmp_path)
        journal_path = self._write_journal_file(journals_dir, "第一版正文")

        upsert_fts_row(journal_path)
        journal_path.write_text(
            journal_path.read_text(encoding="utf-8") + "\n第二版追加正文。\n",
            encoding="utf-8",
        )
        doc = upsert_fts_row(journal_path)

        assert doc is not None
        conn = sqlite3.connect(str(fts_db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM journals")
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT content FROM journals")
            stored = cursor.fetchone()[0]
            assert "第二版追加正文" in stored or "追加" in stored
        finally:
            conn.close()

    def test_chinese_segmentation_applied(self, tmp_path: Path):
        """Chinese title/body go through the same jieba segmentation as rebuild."""
        from tools.lib.search_index import upsert_fts_row

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(tmp_path)
        journal_path = self._write_journal_file(journals_dir, "今天想起了晴岚小时候的模样")

        doc = upsert_fts_row(journal_path)

        assert doc["title_segmented"], "segmented title column must be stored"
        assert doc["content"], "segmented content column must be stored"

    def test_list_fields_normalized(self, tmp_path: Path):
        """Topic/tags/mood/people lists are normalized like a rebuild row."""
        from tools.lib.search_index import upsert_fts_row

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(tmp_path)
        journal_path = self._write_journal_file(journals_dir, "正文")

        doc = upsert_fts_row(journal_path)

        assert doc["topic"] == "think"
        assert "亲子" in doc["tags"]
        assert doc["mood"] == "思念"
        assert doc["people"] == "晴岚"

    def test_last_updated_refreshed_without_masking_versions(self, tmp_path: Path):
        """last_updated is refreshed; version keys keep signalling rebuilds."""
        from tools.lib.search_index import upsert_fts_row

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(tmp_path)
        journal_path = self._write_journal_file(journals_dir, "正文")

        conn = sqlite3.connect(str(fts_db_path))
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute(
                "INSERT OR REPLACE INTO index_meta (key, value) VALUES " "('schema_version', '2')"
            )
            conn.commit()
        finally:
            conn.close()

        assert upsert_fts_row(journal_path) is not None

        conn = sqlite3.connect(str(fts_db_path))
        try:
            last_updated = conn.execute(
                "SELECT value FROM index_meta WHERE key = 'last_updated'"
            ).fetchone()
            assert last_updated is not None and "202" in last_updated[0]
            # The stale recorded version must survive so the next incremental
            # scan still triggers its one-time rebuild.
            schema_version = conn.execute(
                "SELECT value FROM index_meta WHERE key = 'schema_version'"
            ).fetchone()
            assert schema_version is not None and schema_version[0] == "2"
        finally:
            conn.close()

    def test_file_stat_recorded(self, tmp_path: Path):
        """The (mtime, size) signature lands in the fts_file_stats side table."""
        from tools.lib.search_index import upsert_fts_row

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(tmp_path)
        journal_path = self._write_journal_file(journals_dir, "正文")

        upsert_fts_row(journal_path)

        stat = journal_path.stat()
        conn = sqlite3.connect(str(fts_db_path))
        try:
            row = conn.execute(
                "SELECT mtime, size FROM fts_file_stats WHERE path = ?",
                ("Journals/2026/03/life-index_2026-03-04_001.md",),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == stat.st_mtime
        assert row[1] == stat.st_size

    def test_unparsable_file_returns_none(self, tmp_path: Path):
        """A file without frontmatter yields no row (None, no raise)."""
        from tools.lib.search_index import upsert_fts_row

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(tmp_path)
        journal_path = journals_dir / "2026" / "03" / "life-index_2026-03-04_001.md"
        journal_path.write_text("no frontmatter here\n", encoding="utf-8")

        assert upsert_fts_row(journal_path) is None

    def test_db_error_raises(self, tmp_path: Path):
        """Database errors raise so the write core records fts_row=failed."""
        from unittest.mock import patch

        from tools.lib.search_index import upsert_fts_row

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(tmp_path)
        journal_path = self._write_journal_file(journals_dir, "正文")

        with patch(
            "tools.lib.search_index.init_fts_db",
            side_effect=sqlite3.Error("DB broken"),
        ):
            with pytest.raises(sqlite3.Error):
                upsert_fts_row(journal_path)

    def test_fts_searchable_after_write_through(self, tmp_path: Path):
        """A row inserted via write-through is FTS-searchable."""
        from tools.lib.search_index import search_fts, upsert_fts_row

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(tmp_path)
        journal_path = self._write_journal_file(journals_dir, "今天完成了双管道检索架构的重构工作")

        assert upsert_fts_row(journal_path) is not None

        results = search_fts("重构")
        assert len(results) >= 1
        found = any("重构" in r.get("title", "") or "重构" in r.get("snippet", "") for r in results)
        assert found


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
