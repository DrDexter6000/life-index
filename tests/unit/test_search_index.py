#!/usr/bin/env python3
"""
Unit tests for tools/lib/search_index.py

Tests cover:
- FTS5 index creation and management
- Journal parsing
- Index update operations
- FTS search functionality
- File hash computation
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sqlite3
import tempfile


class TestGetFileHash:
    """Tests for get_file_hash function"""

    def test_hash_computation(self, tmp_path):
        """Hash is computed correctly"""
        from tools.lib.search_index import get_file_hash

        test_file = tmp_path / "test.md"
        test_file.write_text("test content", encoding="utf-8")

        result = get_file_hash(test_file)

        assert result != ""
        assert len(result) == 16  # MD5 first 16 chars

    def test_hash_consistency(self, tmp_path):
        """Same content produces same hash"""
        from tools.lib.search_index import get_file_hash

        test_file = tmp_path / "test.md"
        test_file.write_text("same content", encoding="utf-8")

        hash1 = get_file_hash(test_file)
        hash2 = get_file_hash(test_file)

        assert hash1 == hash2

    def test_hash_different_content(self, tmp_path):
        """Different content produces different hash"""
        from tools.lib.search_index import get_file_hash

        file1 = tmp_path / "test1.md"
        file1.write_text("content 1", encoding="utf-8")

        file2 = tmp_path / "test2.md"
        file2.write_text("content 2", encoding="utf-8")

        hash1 = get_file_hash(file1)
        hash2 = get_file_hash(file2)

        assert hash1 != hash2

    def test_hash_nonexistent_file(self, tmp_path):
        """Nonexistent file returns empty string"""
        from tools.lib.search_index import get_file_hash

        nonexistent = tmp_path / "nonexistent.md"
        result = get_file_hash(nonexistent)

        assert result == ""


class TestInitFtsDb:
    """Tests for init_fts_db function"""

    def test_creates_database(self, tmp_path):
        """Database is created successfully"""
        from tools.lib import search_index

        with patch.object(search_index, "FTS_DB_PATH", tmp_path / "test_fts.db"):
            with patch.object(search_index, "INDEX_DIR", tmp_path):
                conn = search_index.init_fts_db()

        assert conn is not None
        conn.close()

    def test_creates_tables(self, tmp_path):
        """FTS5 table is created"""
        from tools.lib import search_index

        db_path = tmp_path / "test_fts.db"
        with patch.object(search_index, "FTS_DB_PATH", db_path):
            with patch.object(search_index, "INDEX_DIR", tmp_path):
                conn = search_index.init_fts_db()

        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='journals'"
        )
        result = cursor.fetchone()

        assert result is not None
        conn.close()

    def test_enables_wal_mode(self, tmp_path):
        """WAL mode is enabled"""
        from tools.lib import search_index

        db_path = tmp_path / "test_fts.db"
        with patch.object(search_index, "FTS_DB_PATH", db_path):
            with patch.object(search_index, "INDEX_DIR", tmp_path):
                conn = search_index.init_fts_db()

        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        result = cursor.fetchone()

        assert result[0].lower() == "wal"
        conn.close()


class TestParseJournal:
    """Tests for parse_journal function"""

    def test_parse_valid_journal(self, tmp_path):
        """Valid journal is parsed correctly"""
        from tools.lib import search_index

        journal = tmp_path / "test.md"
        journal.write_text(
            """---
title: Test Journal
date: 2026-03-14
location: Beijing
---

# Test Content

This is the body.
""",
            encoding="utf-8",
        )

        # Mock USER_DATA_DIR to allow relative_to to work
        with patch.object(search_index, "USER_DATA_DIR", tmp_path):
            result = search_index.parse_journal(journal)

        assert result is not None
        assert result.get("title") == "Test Journal"
        assert result.get("date") == "2026-03-14"

    def test_parse_no_frontmatter(self, tmp_path):
        """File without frontmatter returns None"""
        from tools.lib.search_index import parse_journal

        journal = tmp_path / "test.md"
        journal.write_text("# No Frontmatter\n\nJust content.", encoding="utf-8")

        result = parse_journal(journal)

        assert result is None

    def test_parse_incomplete_frontmatter(self, tmp_path):
        """File with incomplete frontmatter returns None"""
        from tools.lib.search_index import parse_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            """---
title: Test

# Content""",
            encoding="utf-8",
        )

        result = parse_journal(journal)

        assert result is None

    def test_parse_nonexistent_file(self, tmp_path):
        """Nonexistent file returns None"""
        from tools.lib.search_index import parse_journal

        nonexistent = tmp_path / "nonexistent.md"
        result = parse_journal(nonexistent)

        assert result is None

    def test_parse_extracts_body(self, tmp_path):
        """Body content is extracted"""
        from tools.lib import search_index

        journal = tmp_path / "test.md"
        journal.write_text(
            """---
title: Test
date: 2026-03-14
---

# Heading

Body paragraph.
""",
            encoding="utf-8",
        )

        # Mock USER_DATA_DIR to allow relative_to to work
        with patch.object(search_index, "USER_DATA_DIR", tmp_path):
            result = search_index.parse_journal(journal)

        assert result is not None
        assert "Body paragraph" in result.get("content", "")


class TestNormalizeToStr:
    """Tests for _normalize_to_str function"""

    def test_string_passthrough(self):
        """String passes through unchanged"""
        from tools.lib.search_index import _normalize_to_str

        assert _normalize_to_str("test") == "test"

    def test_list_to_string(self):
        """List is converted to string"""
        from tools.lib.search_index import _normalize_to_str

        result = _normalize_to_str(["a", "b", "c"])
        assert "a" in result

    def test_none_to_empty(self):
        """None becomes empty string"""
        from tools.lib.search_index import _normalize_to_str

        assert _normalize_to_str(None) == ""

    def test_number_to_string(self):
        """Number is converted to string"""
        from tools.lib.search_index import _normalize_to_str

        assert _normalize_to_str(123) == "123"


class TestSearchFts:
    """Tests for search_fts function"""

    def test_search_returns_results(self, tmp_path):
        """Search returns matching results"""
        from tools.lib import search_index

        db_path = tmp_path / "test_fts.db"
        with patch.object(search_index, "FTS_DB_PATH", db_path):
            with patch.object(search_index, "INDEX_DIR", tmp_path):
                conn = search_index.init_fts_db()

                # Insert test data
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO journals (path, title, content, date, location, weather, topic, project, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        "test.md",
                        "Test Journal",
                        "Python programming",
                        "2026-03-14",
                        "Beijing",
                        "Sunny",
                        "work",
                        "Life-Index",
                        "python",
                    ),
                )
                conn.commit()
                conn.close()

                # search_fts manages its own connection
                results = search_index.search_fts("Python")

                assert len(results) >= 1

    def test_search_no_results(self, tmp_path):
        """Search with no matches returns empty list"""
        from tools.lib import search_index

        db_path = tmp_path / "test_fts.db"
        with patch.object(search_index, "FTS_DB_PATH", db_path):
            with patch.object(search_index, "INDEX_DIR", tmp_path):
                conn = search_index.init_fts_db()
                conn.close()

                results = search_index.search_fts("nonexistent_keyword_xyz")

                assert results == []

    def test_search_no_index(self, tmp_path):
        """Search without index returns empty list"""
        from tools.lib import search_index

        db_path = tmp_path / "nonexistent.db"
        with patch.object(search_index, "FTS_DB_PATH", db_path):
            results = search_index.search_fts("test")

            assert results == []


class TestGetStats:
    """Tests for get_stats function"""

    def test_stats_no_index(self, tmp_path):
        """Stats with no index shows not exists"""
        from tools.lib import search_index

        db_path = tmp_path / "nonexistent.db"
        with patch.object(search_index, "FTS_DB_PATH", db_path):
            stats = search_index.get_stats()

            assert stats.get("exists") is False

    def test_stats_with_index(self, tmp_path):
        """Stats with index shows data"""
        from tools.lib import search_index

        db_path = tmp_path / "test_fts.db"
        with patch.object(search_index, "FTS_DB_PATH", db_path):
            with patch.object(search_index, "INDEX_DIR", tmp_path):
                conn = search_index.init_fts_db()

                # Insert test data
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO journals (path, title, content, date, location, weather, topic, project, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    ("test.md", "Test", "Content", "2026-03-14", "", "", "", "", ""),
                )
                conn.commit()
                conn.close()

                stats = search_index.get_stats()

                assert stats.get("exists") is True
                assert stats.get("total_documents", 0) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
