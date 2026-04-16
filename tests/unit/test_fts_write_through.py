#!/usr/bin/env python3
"""
Unit tests for FTS write-through in write_journal/index_updater.py

Tests cover:
- update_fts_index: single-entry FTS insert from in-memory data
- Idempotent behavior (same rel_path overwrites)
- Chinese segmentation applied correctly
- Error handling (DB errors return False, never raise)
- index_meta.last_updated is refreshed after write-through
"""

import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
from contextlib import ExitStack

import pytest


class TestUpdateFtsIndex:
    """Tests for update_fts_index function"""

    def _setup_fts_env(self, tmp_path: Path):
        """Create isolated FTS environment for testing."""
        user_data_dir = tmp_path / "Life-Index"
        journals_dir = user_data_dir / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)
        index_dir = user_data_dir / ".index"
        index_dir.mkdir(parents=True)
        fts_db_path = index_dir / "journals_fts.db"
        return user_data_dir, journals_dir, index_dir, fts_db_path

    def _make_journal_path(self, journals_dir: Path) -> Path:
        return journals_dir / "2026" / "03" / "life-index_2026-03-04_001.md"

    def _patched_env(self, journals_dir, user_data_dir, fts_db_path, index_dir):
        """Return context manager with all necessary patches for FTS write-through tests."""
        return ExitStack()  # placeholder, we'll use nested context managers directly

    def test_basic_insert(self, tmp_path: Path):
        """Basic FTS write-through inserts a row."""
        from tools.write_journal.index_updater import update_fts_index

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(
            tmp_path
        )
        journal_path = self._make_journal_path(journals_dir)

        data = {
            "title": "想念女儿",
            "content": "今天在阳台上看日落，想起了乐乐小时候的模样",
            "date": "2026-03-04T19:43:00",
            "location": "Lagos, Nigeria",
            "weather": "晴天 28C",
            "topic": ["think"],
            "tags": ["亲子", "回忆"],
            "mood": ["思念"],
            "people": ["乐乐"],
            "project": "LifeIndex",
        }

        with (
            patch("tools.lib.config.JOURNALS_DIR", journals_dir),
            patch("tools.lib.config.USER_DATA_DIR", user_data_dir),
            patch("tools.lib.search_index.FTS_DB_PATH", fts_db_path),
            patch("tools.lib.search_index.INDEX_DIR", index_dir),
        ):
            result = update_fts_index(journal_path, data)

        assert result is True

        conn = sqlite3.connect(str(fts_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM journals")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT path, date, location, weather FROM journals")
        row = cursor.fetchone()
        assert "Journals/2026/03/life-index_2026-03-04_001.md" in row[0]
        assert row[1] == "2026-03-04"
        assert row[2] == "Lagos, Nigeria"
        conn.close()

    def test_idempotent_overwrite(self, tmp_path: Path):
        """Calling twice with same path should not duplicate rows."""
        from tools.write_journal.index_updater import update_fts_index

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(
            tmp_path
        )
        journal_path = self._make_journal_path(journals_dir)

        data = {
            "title": "First Title",
            "content": "First content",
            "date": "2026-03-04T10:00:00",
        }

        with (
            patch("tools.lib.config.JOURNALS_DIR", journals_dir),
            patch("tools.lib.config.USER_DATA_DIR", user_data_dir),
            patch("tools.lib.search_index.FTS_DB_PATH", fts_db_path),
            patch("tools.lib.search_index.INDEX_DIR", index_dir),
        ):
            update_fts_index(journal_path, data)

            data2 = {
                "title": "Updated Title",
                "content": "Updated content",
                "date": "2026-03-04T10:00:00",
            }
            update_fts_index(journal_path, data2)

        conn = sqlite3.connect(str(fts_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM journals")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_chinese_segmentation_applied(self, tmp_path: Path):
        """Chinese text should be segmented for FTS."""
        from tools.write_journal.index_updater import update_fts_index

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(
            tmp_path
        )
        journal_path = self._make_journal_path(journals_dir)

        data = {
            "title": "想念女儿",
            "content": "今天想起了乐乐小时候的模样",
            "date": "2026-03-04",
        }

        with (
            patch("tools.lib.config.JOURNALS_DIR", journals_dir),
            patch("tools.lib.config.USER_DATA_DIR", user_data_dir),
            patch("tools.lib.search_index.FTS_DB_PATH", fts_db_path),
            patch("tools.lib.search_index.INDEX_DIR", index_dir),
        ):
            result = update_fts_index(journal_path, data)

        assert result is True

        conn = sqlite3.connect(str(fts_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT title, content FROM journals")
        row = cursor.fetchone()
        assert row is not None
        # Segmented text should have content (not empty)
        assert len(row[0]) > 0
        assert len(row[1]) > 0
        conn.close()

    def test_list_fields_normalized(self, tmp_path: Path):
        """Topic/tags/mood/people as lists should be normalized to comma-joined strings."""
        from tools.write_journal.index_updater import update_fts_index

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(
            tmp_path
        )
        journal_path = self._make_journal_path(journals_dir)

        data = {
            "title": "Test",
            "content": "Content",
            "date": "2026-03-04",
            "topic": ["work", "learn"],
            "tags": ["python", "ai"],
            "mood": ["专注", "充实"],
            "people": ["乐乐", "朋友"],
        }

        with (
            patch("tools.lib.config.JOURNALS_DIR", journals_dir),
            patch("tools.lib.config.USER_DATA_DIR", user_data_dir),
            patch("tools.lib.search_index.FTS_DB_PATH", fts_db_path),
            patch("tools.lib.search_index.INDEX_DIR", index_dir),
        ):
            result = update_fts_index(journal_path, data)

        assert result is True

        conn = sqlite3.connect(str(fts_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT topic, tags, mood, people FROM journals")
        row = cursor.fetchone()
        assert row is not None
        assert "work" in row[0]
        assert "learn" in row[0]
        assert "python" in row[1]
        assert "ai" in row[1]
        assert "专注" in row[2]
        assert "乐乐" in row[3]
        conn.close()

    def test_index_meta_last_updated_refreshed(self, tmp_path: Path):
        """write_index_meta should be called, refreshing last_updated."""
        from tools.write_journal.index_updater import update_fts_index

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(
            tmp_path
        )
        journal_path = self._make_journal_path(journals_dir)

        data = {"title": "Test", "content": "Content", "date": "2026-03-04"}

        with (
            patch("tools.lib.config.JOURNALS_DIR", journals_dir),
            patch("tools.lib.config.USER_DATA_DIR", user_data_dir),
            patch("tools.lib.search_index.FTS_DB_PATH", fts_db_path),
            patch("tools.lib.search_index.INDEX_DIR", index_dir),
        ):
            result = update_fts_index(journal_path, data)

        assert result is True

        conn = sqlite3.connect(str(fts_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM index_meta WHERE key = 'last_updated'")
        row = cursor.fetchone()
        assert row is not None
        assert "202" in row[0]
        conn.close()

    def test_db_error_returns_false(self, tmp_path: Path):
        """Database error should return False, never raise."""
        from tools.write_journal.index_updater import update_fts_index

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(
            tmp_path
        )
        journal_path = self._make_journal_path(journals_dir)

        data = {"title": "Test", "content": "Content", "date": "2026-03-04"}

        with (
            patch("tools.lib.config.JOURNALS_DIR", journals_dir),
            patch("tools.lib.config.USER_DATA_DIR", user_data_dir),
            patch("tools.lib.search_index.FTS_DB_PATH", fts_db_path),
            patch("tools.lib.search_index.INDEX_DIR", index_dir),
            patch(
                "tools.lib.search_index.init_fts_db",
                side_effect=sqlite3.Error("DB broken"),
            ),
        ):
            result = update_fts_index(journal_path, data)

        assert result is False

    def test_empty_data_fields_handled(self, tmp_path: Path):
        """Missing/empty data fields should not crash."""
        from tools.write_journal.index_updater import update_fts_index

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(
            tmp_path
        )
        journal_path = self._make_journal_path(journals_dir)

        data = {"date": "2026-03-04"}

        with (
            patch("tools.lib.config.JOURNALS_DIR", journals_dir),
            patch("tools.lib.config.USER_DATA_DIR", user_data_dir),
            patch("tools.lib.search_index.FTS_DB_PATH", fts_db_path),
            patch("tools.lib.search_index.INDEX_DIR", index_dir),
        ):
            result = update_fts_index(journal_path, data)

        assert result is True

        conn = sqlite3.connect(str(fts_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM journals")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_fts_searchable_after_write_through(self, tmp_path: Path):
        """Document inserted via write-through should be FTS-searchable."""
        from tools.write_journal.index_updater import update_fts_index
        from tools.lib.search_index import search_fts

        user_data_dir, journals_dir, index_dir, fts_db_path = self._setup_fts_env(
            tmp_path
        )
        journal_path = self._make_journal_path(journals_dir)

        data = {
            "title": "重构搜索模块",
            "content": "今天完成了双管道检索架构的重构工作",
            "date": "2026-03-04",
            "tags": ["重构", "优化"],
        }

        with (
            patch("tools.lib.config.JOURNALS_DIR", journals_dir),
            patch("tools.lib.config.USER_DATA_DIR", user_data_dir),
            patch("tools.lib.search_index.FTS_DB_PATH", fts_db_path),
            patch("tools.lib.search_index.INDEX_DIR", index_dir),
        ):
            result = update_fts_index(journal_path, data)

        assert result is True

        # Search using the same patched DB path
        with patch("tools.lib.search_index.FTS_DB_PATH", fts_db_path):
            results = search_fts("重构")

        assert len(results) >= 1
        found = any(
            "重构" in r.get("title", "") or "重构" in r.get("content", "")
            for r in results
        )
        assert found


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
