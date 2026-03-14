#!/usr/bin/env python3
"""
Unit tests for L2 metadata cache module
"""

import pytest
import os
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime

from tools.lib.metadata_cache import (
    init_metadata_cache,
    get_file_signature,
    is_cache_valid,
    parse_and_cache_journal,
    get_cached_metadata,
    get_or_update_metadata,
    get_all_cached_metadata,
    get_cache_stats,
    invalidate_cache,
    update_cache_for_all_journals,
    METADATA_DB_PATH,
)
from tools.lib.config import JOURNALS_DIR


class TestMetadataCache:
    """Tests for metadata cache functionality"""

    def test_init_metadata_cache(self):
        """Test cache database initialization"""
        # Ensure clean state
        if METADATA_DB_PATH.exists():
            METADATA_DB_PATH.unlink()

        conn = init_metadata_cache()
        assert conn is not None
        assert METADATA_DB_PATH.exists()

        # Verify tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "metadata_cache" in tables
        assert "cache_meta" in tables
        conn.close()

    def test_get_file_signature(self, tmp_path):
        """Test file signature generation"""
        test_file = tmp_path / "test.md"
        test_file.write_text("test content", encoding="utf-8")

        mtime, size = get_file_signature(test_file)
        assert mtime > 0
        assert size == len("test content")

    def test_get_file_signature_nonexistent(self, tmp_path):
        """Test file signature for non-existent file"""
        non_existent = tmp_path / "nonexistent.md"
        mtime, size = get_file_signature(non_existent)
        assert mtime == 0
        assert size == 0

    def test_is_cache_valid(self, tmp_path):
        """Test cache validity check"""
        test_file = tmp_path / "test.md"
        test_file.write_text("content", encoding="utf-8")

        mtime, size = get_file_signature(test_file)

        # Should be valid with current signature
        assert is_cache_valid(test_file, mtime, size)

        # Should be invalid with wrong signature
        assert not is_cache_valid(test_file, mtime + 1, size)
        assert not is_cache_valid(test_file, mtime, size + 1)

    def test_parse_and_cache_journal(self, tmp_path):
        """Test parsing and caching a journal file"""
        # Create a test journal file
        test_file = tmp_path / "test_journal.md"
        test_content = '---\ntitle: "Test Journal"\ndate: 2026-03-13\nlocation: "Beijing"\nweather: "Sunny"\ntopic: ["work"]\nproject: "Test"\ntags: ["test", "example"]\nmood: ["happy"]\npeople: ["Alice"]\nabstract: "Test abstract"\n---\n\n# Test Journal\n\nThis is test content.\n'
        test_file.write_text(test_content, encoding="utf-8")

        # Initialize cache
        conn = init_metadata_cache()

        try:
            # Parse and cache
            result = parse_and_cache_journal(conn, test_file)

            assert result is not None
            assert result["title"] == "Test Journal"
            assert result["date"] == "2026-03-13"
            assert result["location"] == "Beijing"
            assert result["topic"] == ["work"]
            assert result["tags"] == ["test", "example"]

            # Verify it's in the database
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title FROM metadata_cache WHERE file_path = ?",
                (str(test_file),),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["title"] == "Test Journal"
        finally:
            conn.close()

    def test_get_cached_metadata(self, tmp_path):
        """Test retrieving cached metadata"""
        # Create and cache a test file
        test_file = tmp_path / "test.md"
        test_file.write_text(
            '---\ntitle: "Cached Test"\ndate: 2026-03-13\n---\n\nContent\n',
            encoding="utf-8",
        )

        conn = init_metadata_cache()

        try:
            # First parse and cache
            parse_and_cache_journal(conn, test_file)

            # Then retrieve from cache
            cached = get_cached_metadata(conn, test_file)

            assert cached is not None
            assert cached["title"] == "Cached Test"
        finally:
            conn.close()

    def test_get_cached_metadata_invalid(self, tmp_path):
        """Test cache invalidation when file changes"""
        test_file = tmp_path / "test.md"
        test_file.write_text(
            '---\ntitle: "Original"\ndate: 2026-03-13\n---\n\nContent\n',
            encoding="utf-8",
        )

        conn = init_metadata_cache()

        try:
            # Cache the file
            parse_and_cache_journal(conn, test_file)

            # Modify the file
            import time

            time.sleep(0.1)  # Ensure different mtime
            test_file.write_text(
                '---\ntitle: "Modified"\ndate: 2026-03-13\n---\n\nNew Content\n',
                encoding="utf-8",
            )

            # Cache should be invalid now
            cached = get_cached_metadata(conn, test_file)
            assert cached is None
        finally:
            conn.close()

    def test_get_or_update_metadata(self, tmp_path):
        """Test get_or_update_metadata function"""
        test_file = tmp_path / "test.md"
        test_file.write_text(
            '---\ntitle: "Auto Test"\ndate: 2026-03-13\n---\n\nContent\n',
            encoding="utf-8",
        )

        # First call should parse and cache
        result1 = get_or_update_metadata(test_file)
        assert result1 is not None
        assert result1["title"] == "Auto Test"

        # Second call should return from cache
        result2 = get_or_update_metadata(test_file)
        assert result2 is not None
        assert result2["title"] == result1["title"]

    def test_cache_stats(self, tmp_path):
        """Test cache statistics"""
        # Clean state
        invalidate_cache()

        # Initially empty
        stats = get_cache_stats()
        assert stats["total_entries"] == 0

        # Add an entry
        test_file = tmp_path / "test.md"
        test_file.write_text(
            '---\ntitle: "Stats Test"\ndate: 2026-03-13\n---\n\nContent\n',
            encoding="utf-8",
        )

        get_or_update_metadata(test_file)

        # Should have one entry now
        stats = get_cache_stats()
        assert stats["total_entries"] == 1

    def test_invalidate_cache(self, tmp_path):
        """Test cache invalidation"""
        # Clean slate
        invalidate_cache()

        # Add an entry
        test_file = tmp_path / "invalidate_test.md"
        test_file.write_text(
            '---\ntitle: "Invalidate Test"\ndate: "2026-03-13"\n---\n\nContent\n',
            encoding="utf-8",
        )

        get_or_update_metadata(test_file)

        # Verify entry exists
        stats = get_cache_stats()
        assert stats["total_entries"] >= 1

        # Invalidate
        invalidate_cache()

        # Should be empty
        stats = get_cache_stats()
        assert stats["total_entries"] == 0


class TestCachePerformance:
    """Tests for cache performance characteristics"""

    def test_cache_faster_than_parsing(self, tmp_path):
        """Test that cached reads are faster than parsing"""
        import time

        # Create a test file
        test_file = tmp_path / "perf_test.md"
        test_content = '---\ntitle: "Performance Test"\ndate: 2026-03-13\nlocation: "Beijing"\nweather: "Sunny"\ntopic: ["work", "life"]\nproject: "Test"\ntags: ["tag1", "tag2", "tag3"]\nmood: ["happy", "productive"]\npeople: ["Alice", "Bob"]\nabstract: "This is a test abstract for performance testing"\n---\n\n# Performance Test\n\nThis is the content of the performance test file.\nIt has multiple lines to simulate a real journal entry.\n\n## Section 1\n\nSome content here.\n\n## Section 2\n\nMore content here.\n'
        test_file.write_text(test_content, encoding="utf-8")

        # First call - parse and cache
        start = time.time()
        result1 = get_or_update_metadata(test_file)
        parse_time = time.time() - start

        # Second call - from cache
        start = time.time()
        result2 = get_or_update_metadata(test_file)
        cache_time = time.time() - start

        # Both should return same result
        assert result1["title"] == result2["title"]

        # Cache should be faster (typically 10-100x)
        # Allow some margin for test environment variance
        assert cache_time < parse_time or cache_time < 0.001  # 1ms threshold


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
