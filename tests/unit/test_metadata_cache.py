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
from unittest.mock import patch

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
    rebuild_entry_relations,
    get_backlinked_by,
    add_entry_relations,
    replace_entry_relations,
)
from tools.lib.config import JOURNALS_DIR


class TestMetadataCache:
    """Tests for metadata cache functionality"""

    def test_init_metadata_cache(self, tmp_path):
        """Test cache database initialization (isolated temp dir)"""
        from tools.lib import metadata_cache

        cache_dir = tmp_path / ".cache"
        cache_db = cache_dir / "metadata_cache.db"

        with patch.object(metadata_cache, "CACHE_DIR", cache_dir):
            with patch.object(metadata_cache, "METADATA_DB_PATH", cache_db):
                conn = metadata_cache.init_metadata_cache()
                assert conn is not None
                assert cache_db.exists()

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
        test_content = '---\ntitle: "Test Journal"\ndate: 2026-03-13\nlocation: "Beijing"\nweather: "Sunny"\ntopic: ["work"]\nproject: "Test"\ntags: ["test", "example"]\nmood: ["happy"]\npeople: ["Alice"]\nabstract: "Test abstract"\nlinks: ["https://example.com/ref"]\nrelated_entries: ["Journals/2026/03/other.md"]\n---\n\n# Test Journal\n\nThis is test content.\n'
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
            assert result["links"] == ["https://example.com/ref"]
            assert result["related_entries"] == ["Journals/2026/03/other.md"]

            # Verify it's in the database
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title FROM metadata_cache WHERE file_path = ?",
                (str(test_file).replace("\\", "/"),),
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
            '---\ntitle: "Cached Test"\ndate: 2026-03-13\nlinks: ["https://example.com/cached"]\nrelated_entries: ["Journals/2026/03/source.md"]\n---\n\nContent\n',
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
            assert cached["links"] == ["https://example.com/cached"]
            assert cached["related_entries"] == ["Journals/2026/03/source.md"]
        finally:
            conn.close()

    def test_rebuild_entry_relations_and_backlinks(self, tmp_path):
        journals_dir = tmp_path / "Journals"
        src = journals_dir / "2026" / "03" / "source.md"
        dst = journals_dir / "2026" / "03" / "target.md"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(
            '---\ntitle: "Source"\ndate: 2026-03-13\nrelated_entries: ["Journals/2026/03/target.md"]\n---\n\nBody\n',
            encoding="utf-8",
        )
        dst.write_text(
            '---\ntitle: "Target"\ndate: 2026-03-13\n---\n\nBody\n',
            encoding="utf-8",
        )

        import tools.lib.metadata_cache as mc

        with (
            patch.object(mc, "USER_DATA_DIR", tmp_path),
            patch.object(mc, "JOURNALS_DIR", journals_dir),
            patch.object(mc, "CACHE_DIR", tmp_path / ".cache"),
            patch.object(
                mc, "METADATA_DB_PATH", tmp_path / ".cache" / "metadata_cache.db"
            ),
        ):
            conn = init_metadata_cache()
            try:
                parse_and_cache_journal(conn, src)
                parse_and_cache_journal(conn, dst)
                rebuild_entry_relations(conn)
                backlinks = get_backlinked_by(conn, "Journals/2026/03/target.md")
            finally:
                conn.close()

        assert backlinks == ["Journals/2026/03/source.md"]

    def test_add_entry_relations_updates_backlinks_incrementally(self, tmp_path):
        import tools.lib.metadata_cache as mc

        with (
            patch.object(mc, "USER_DATA_DIR", tmp_path),
            patch.object(mc, "JOURNALS_DIR", tmp_path / "Journals"),
            patch.object(mc, "CACHE_DIR", tmp_path / ".cache"),
            patch.object(
                mc, "METADATA_DB_PATH", tmp_path / ".cache" / "metadata_cache.db"
            ),
        ):
            conn = init_metadata_cache()
            try:
                add_entry_relations(
                    conn,
                    "Journals/2026/03/source.md",
                    ["Journals/2026/03/target.md"],
                )
                backlinks = get_backlinked_by(conn, "Journals/2026/03/target.md")
            finally:
                conn.close()

        assert backlinks == ["Journals/2026/03/source.md"]

    def test_replace_entry_relations_replaces_existing_backlinks(self, tmp_path):
        import tools.lib.metadata_cache as mc

        with (
            patch.object(mc, "USER_DATA_DIR", tmp_path),
            patch.object(mc, "JOURNALS_DIR", tmp_path / "Journals"),
            patch.object(mc, "CACHE_DIR", tmp_path / ".cache"),
            patch.object(
                mc, "METADATA_DB_PATH", tmp_path / ".cache" / "metadata_cache.db"
            ),
        ):
            conn = init_metadata_cache()
            try:
                add_entry_relations(
                    conn,
                    "Journals/2026/03/source.md",
                    ["Journals/2026/03/old.md"],
                )
                replace_entry_relations(
                    conn,
                    "Journals/2026/03/source.md",
                    ["Journals/2026/03/new.md"],
                )
                old_backlinks = get_backlinked_by(conn, "Journals/2026/03/old.md")
                new_backlinks = get_backlinked_by(conn, "Journals/2026/03/new.md")
            finally:
                conn.close()

        assert old_backlinks == []
        assert new_backlinks == ["Journals/2026/03/source.md"]

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


class TestParseAndCacheJournalEdgeCases:
    """Tests for edge cases in parse_and_cache_journal"""

    def test_parse_and_cache_journal_exception_handling(self, tmp_path, monkeypatch):
        """Test exception handling in parse_and_cache_journal (lines 178-179)"""
        test_file = tmp_path / "test.md"
        test_file.write_text(
            '---\ntitle: "Test"\ndate: 2026-03-13\n---\n\nContent\n',
            encoding="utf-8",
        )

        # Mock parse_journal_file to raise an exception
        def mock_parse_raise(*args, **kwargs):
            raise ValueError("Simulated parse error")

        import tools.lib.metadata_cache as mc

        monkeypatch.setattr(mc, "parse_journal_file", mock_parse_raise)

        conn = init_metadata_cache()
        try:
            result = parse_and_cache_journal(conn, test_file)
            assert result is None
        finally:
            conn.close()

    def test_parse_and_cache_journal_preserves_string_topic_for_safe_upstream_normalization(
        self, tmp_path
    ):
        """Legacy scalar topic values remain readable without breaking callers that normalize them."""
        test_file = tmp_path / "string_topic.md"
        test_file.write_text(
            '---\ntitle: "String Topic"\ndate: 2026-03-13\ntopic: "think"\n---\n\nContent\n',
            encoding="utf-8",
        )

        conn = init_metadata_cache()
        try:
            cached = parse_and_cache_journal(conn, test_file)
            all_entries = get_all_cached_metadata(conn)
        finally:
            conn.close()

        assert cached is not None
        assert cached["topic"] == "think"
        matched = next(item for item in all_entries if item["title"] == "String Topic")
        assert matched["topic"] == "think"


class TestConnectionManagement:
    """Tests for connection management in cache functions"""

    def test_get_or_update_metadata_creates_connection(self, tmp_path):
        """Test get_or_update_metadata with conn=None creates its own connection (lines 233-237)"""
        test_file = tmp_path / "test.md"
        test_file.write_text(
            '---\ntitle: "Auto Connection Test"\ndate: 2026-03-13\n---\n\nContent\n',
            encoding="utf-8",
        )

        # Call without providing connection
        result = get_or_update_metadata(test_file, conn=None)
        assert result is not None
        assert result["title"] == "Auto Connection Test"

    def test_get_all_cached_metadata_creates_connection(self, tmp_path):
        """Test get_all_cached_metadata with conn=None creates its own connection (lines 256-260)"""
        # Clean state
        invalidate_cache()

        # Add a test file
        test_file = tmp_path / "test.md"
        test_file.write_text(
            '---\ntitle: "All Metadata Test"\ndate: 2026-03-13\n---\n\nContent\n',
            encoding="utf-8",
        )

        get_or_update_metadata(test_file)

        # Call without providing connection
        results = get_all_cached_metadata(conn=None)
        assert isinstance(results, list)
        assert len(results) >= 1

        # Verify the entry is there
        found = any(r["title"] == "All Metadata Test" for r in results)
        assert found


class TestInvalidateCacheSpecificFile:
    """Tests for invalidating cache for specific files"""

    def test_invalidate_cache_specific_file(self, tmp_path):
        """Test invalidate_cache with specific file_path (line 307)"""
        # Clean slate
        invalidate_cache()

        # Create two test files
        test_file1 = tmp_path / "test1.md"
        test_file1.write_text(
            '---\ntitle: "File 1"\ndate: 2026-03-13\n---\n\nContent\n',
            encoding="utf-8",
        )

        test_file2 = tmp_path / "test2.md"
        test_file2.write_text(
            '---\ntitle: "File 2"\ndate: 2026-03-13\n---\n\nContent\n',
            encoding="utf-8",
        )

        # Cache both
        get_or_update_metadata(test_file1)
        get_or_update_metadata(test_file2)

        # Verify both are cached
        stats = get_cache_stats()
        assert stats["total_entries"] >= 2

        # Invalidate only file1
        invalidate_cache(test_file1)

        # Verify file1 is gone but file2 remains
        conn = init_metadata_cache()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM metadata_cache WHERE file_path = ?",
                (str(test_file1).replace("\\", "/"),),
            )
            count1 = cursor.fetchone()[0]
            assert count1 == 0

            cursor.execute(
                "SELECT COUNT(*) FROM metadata_cache WHERE file_path = ?",
                (str(test_file2).replace("\\", "/"),),
            )
            count2 = cursor.fetchone()[0]
            assert count2 == 1
        finally:
            conn.close()

    def test_get_cached_metadata_reads_legacy_backslash_path_row(self, tmp_path):
        """Legacy Windows-style cache rows remain readable after normalization rollout."""
        journals_dir = tmp_path / "Journals"
        journal_file = journals_dir / "2026" / "03" / "legacy.md"
        journal_file.parent.mkdir(parents=True)
        journal_file.write_text(
            '---\ntitle: "Legacy Row"\ndate: 2026-03-13\n---\n\nContent\n',
            encoding="utf-8",
        )

        with (
            patch("tools.lib.metadata_cache.USER_DATA_DIR", tmp_path),
            patch("tools.lib.metadata_cache.JOURNALS_DIR", journals_dir),
        ):
            conn = init_metadata_cache()
            try:
                mtime, size = get_file_signature(journal_file)
                legacy_path = str(journal_file)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO metadata_cache
                    (file_path, date, title, location, weather, topic, project,
                     tags, mood, people, abstract, file_mtime, file_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        legacy_path,
                        "2026-03-13",
                        "Legacy Row",
                        "",
                        "",
                        "[]",
                        "",
                        "[]",
                        "[]",
                        "[]",
                        "",
                        mtime,
                        size,
                    ),
                )
                conn.commit()

                result = get_cached_metadata(conn, journal_file)
            finally:
                conn.close()

        assert result is not None
        assert result["title"] == "Legacy Row"
        assert result["file_path"] == str(journal_file).replace("\\", "/")
        assert result["rel_path"] == "Journals/2026/03/legacy.md"

    def test_invalidate_cache_removes_legacy_backslash_path_row(self, tmp_path):
        """Specific-file invalidation removes old cache rows stored with legacy separators."""
        invalidate_cache()

        journals_dir = tmp_path / "Journals"
        journal_file = journals_dir / "2026" / "03" / "legacy_delete.md"
        journal_file.parent.mkdir(parents=True)
        journal_file.write_text(
            '---\ntitle: "Legacy Delete"\ndate: 2026-03-13\n---\n\nContent\n',
            encoding="utf-8",
        )

        conn = init_metadata_cache()
        try:
            mtime, size = get_file_signature(journal_file)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO metadata_cache
                (file_path, date, title, location, weather, topic, project,
                 tags, mood, people, abstract, file_mtime, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(journal_file),
                    "2026-03-13",
                    "Legacy Delete",
                    "",
                    "",
                    "[]",
                    "",
                    "[]",
                    "[]",
                    "[]",
                    "",
                    mtime,
                    size,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        invalidate_cache(journal_file)

        conn = init_metadata_cache()
        try:
            cursor = conn.cursor()
            normalized = str(journal_file).replace("\\", "/")
            legacy = str(journal_file)
            if legacy == normalized:
                cursor.execute(
                    "SELECT COUNT(*) FROM metadata_cache WHERE file_path = ?",
                    (normalized,),
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM metadata_cache WHERE file_path IN (?, ?)",
                    (normalized, legacy),
                )
            remaining = cursor.fetchone()[0]
        finally:
            conn.close()

        assert remaining == 0


class TestUpdateCacheForAllJournals:
    """Tests for update_cache_for_all_journals function (lines 348-391)"""

    def test_update_cache_for_all_journals_empty_dir(self, monkeypatch, tmp_path):
        """Test update_cache_for_all_journals with empty JOURNALS_DIR"""
        # Mock JOURNALS_DIR to empty temp directory
        import tools.lib.metadata_cache as mc

        monkeypatch.setattr(mc, "JOURNALS_DIR", tmp_path)

        # Clean cache
        invalidate_cache()

        result = update_cache_for_all_journals()
        assert result["updated"] == 0
        assert result["skipped"] == 0
        assert result["errors"] == 0

    def test_update_cache_for_all_journals_with_journals(self, monkeypatch, tmp_path):
        """Test update_cache_for_all_journals with actual journal files"""
        import tools.lib.metadata_cache as mc

        # Create mock journal directory structure
        journals_dir = tmp_path / "Journals"
        year_dir = journals_dir / "2026"
        month_dir = year_dir / "03"
        month_dir.mkdir(parents=True)

        # Create test journal files
        journal1 = month_dir / "life-index_2026-03-01_001.md"
        journal1.write_text(
            '---\ntitle: "Journal 1"\ndate: 2026-03-01\ntopic: ["work"]\n---\n\nContent 1\n',
            encoding="utf-8",
        )

        journal2 = month_dir / "life-index_2026-03-02_001.md"
        journal2.write_text(
            '---\ntitle: "Journal 2"\ndate: 2026-03-02\ntopic: ["life"]\n---\n\nContent 2\n',
            encoding="utf-8",
        )

        # Mock JOURNALS_DIR
        monkeypatch.setattr(mc, "JOURNALS_DIR", journals_dir)

        # Clean cache
        invalidate_cache()

        result = update_cache_for_all_journals()
        assert result["updated"] == 2
        assert result["skipped"] == 0
        assert result["errors"] == 0

    def test_update_cache_for_all_journals_skips_cached(self, monkeypatch, tmp_path):
        """Test update_cache_for_all_journals skips already cached files"""
        import tools.lib.metadata_cache as mc

        # Create mock journal directory structure
        journals_dir = tmp_path / "Journals"
        year_dir = journals_dir / "2026"
        month_dir = year_dir / "03"
        month_dir.mkdir(parents=True)

        journal1 = month_dir / "life-index_2026-03-01_001.md"
        journal1.write_text(
            '---\ntitle: "Cached Journal"\ndate: 2026-03-01\ntopic: ["work"]\n---\n\nContent\n',
            encoding="utf-8",
        )

        monkeypatch.setattr(mc, "JOURNALS_DIR", journals_dir)

        # Clean cache and run once
        invalidate_cache()
        result1 = update_cache_for_all_journals()
        assert result1["updated"] == 1

        # Run again - should skip cached file
        result2 = update_cache_for_all_journals()
        assert result2["updated"] == 0
        assert result2["skipped"] == 1

    def test_update_cache_for_all_journals_progress_callback(
        self, monkeypatch, tmp_path
    ):
        """Test update_cache_for_all_journals with progress callback"""
        import tools.lib.metadata_cache as mc

        # Create mock journal directory structure
        journals_dir = tmp_path / "Journals"
        year_dir = journals_dir / "2026"
        month_dir = year_dir / "03"
        month_dir.mkdir(parents=True)

        journal1 = month_dir / "life-index_2026-03-01_001.md"
        journal1.write_text(
            '---\ntitle: "Journal 1"\ndate: 2026-03-01\ntopic: ["work"]\n---\n\nContent\n',
            encoding="utf-8",
        )

        monkeypatch.setattr(mc, "JOURNALS_DIR", journals_dir)

        # Track callback invocations
        callback_calls = []

        def progress_callback(updated, skipped, errors):
            callback_calls.append((updated, skipped, errors))

        invalidate_cache()
        result = update_cache_for_all_journals(progress_callback)

        assert len(callback_calls) >= 1
        assert result["updated"] == 1

    def test_update_cache_for_all_journals_error_handling(self, monkeypatch, tmp_path):
        """Test update_cache_for_all_journals handles errors during journal iteration"""
        import tools.lib.metadata_cache as mc

        # Create mock journal directory structure
        journals_dir = tmp_path / "Journals"
        year_dir = journals_dir / "2026"
        month_dir = year_dir / "03"
        month_dir.mkdir(parents=True)

        # Valid journal
        journal1 = month_dir / "life-index_2026-03-01_001.md"
        journal1.write_text(
            '---\ntitle: "Valid Journal"\ndate: 2026-03-01\ntopic: ["work"]\n---\n\nContent\n',
            encoding="utf-8",
        )

        # Another journal that will cause an error
        journal2 = month_dir / "life-index_2026-03-02_001.md"
        journal2.write_text(
            '---\ntitle: "Error Journal"\ndate: 2026-03-02\ntopic: ["work"]\n---\n\nContent\n',
            encoding="utf-8",
        )

        monkeypatch.setattr(mc, "JOURNALS_DIR", journals_dir)

        # Mock parse_and_cache_journal to raise an exception for journal2
        original_parse = mc.parse_and_cache_journal
        call_count = [0]

        def mock_parse_with_error(conn, file_path):
            call_count[0] += 1
            if "2026-03-02" in str(file_path):
                raise IOError("Simulated IO error")
            return original_parse(conn, file_path)

        monkeypatch.setattr(mc, "parse_and_cache_journal", mock_parse_with_error)

        invalidate_cache()
        result = update_cache_for_all_journals()

        assert result["updated"] == 1
        assert result["errors"] == 1

    def test_update_cache_for_all_journals_skips_non_year_dirs(
        self, monkeypatch, tmp_path
    ):
        """Test update_cache_for_all_journals skips non-year directories"""
        import tools.lib.metadata_cache as mc

        # Create mock journal directory structure
        journals_dir = tmp_path / "Journals"

        # Non-year directory (should be skipped)
        non_year_dir = journals_dir / "notes"
        non_year_dir.mkdir(parents=True)

        # Valid year directory
        year_dir = journals_dir / "2026"
        month_dir = year_dir / "03"
        month_dir.mkdir(parents=True)

        journal1 = month_dir / "life-index_2026-03-01_001.md"
        journal1.write_text(
            '---\ntitle: "Journal"\ndate: 2026-03-01\ntopic: ["work"]\n---\n\nContent\n',
            encoding="utf-8",
        )

        monkeypatch.setattr(mc, "JOURNALS_DIR", journals_dir)

        invalidate_cache()
        result = update_cache_for_all_journals()

        assert result["updated"] == 1

    def test_update_cache_for_all_journals_nonexistent_dir(self, monkeypatch, tmp_path):
        """Test update_cache_for_all_journals when JOURNALS_DIR doesn't exist"""
        import tools.lib.metadata_cache as mc

        nonexistent = tmp_path / "nonexistent"
        monkeypatch.setattr(mc, "JOURNALS_DIR", nonexistent)

        invalidate_cache()
        result = update_cache_for_all_journals()

        assert result["updated"] == 0
        assert result["skipped"] == 0
        assert result["errors"] == 0

    def test_update_cache_for_all_journals_skips_non_dir_months(
        self, monkeypatch, tmp_path
    ):
        """Test update_cache_for_all_journals skips non-directory items in year dir (line 362)"""
        import tools.lib.metadata_cache as mc

        # Create mock journal directory structure
        journals_dir = tmp_path / "Journals"
        year_dir = journals_dir / "2026"
        year_dir.mkdir(parents=True)

        # Create a file (not directory) in year dir - should be skipped
        non_dir_file = year_dir / "notes.txt"
        non_dir_file.write_text("some notes", encoding="utf-8")

        # Create valid month directory with journal
        month_dir = year_dir / "03"
        month_dir.mkdir()

        journal1 = month_dir / "life-index_2026-03-01_001.md"
        journal1.write_text(
            '---\ntitle: "Journal"\ndate: 2026-03-01\ntopic: ["work"]\n---\n\nContent\n',
            encoding="utf-8",
        )

        monkeypatch.setattr(mc, "JOURNALS_DIR", journals_dir)

        invalidate_cache()
        result = update_cache_for_all_journals()

        # Should process the valid journal, skip the non-dir file
        assert result["updated"] == 1
        assert result["errors"] == 0


class TestCachePerformance:
    """Tests for cache performance characteristics"""

    def test_cache_faster_than_parsing(self, tmp_path):
        """Test that cached reads are fast enough to be practically useful.

        We use an absolute threshold (5ms) rather than comparing against
        parse_time, because parse_time can be extremely fast in CI/testing
        environments, and Windows scheduler / SQLite timing variance can make
        sub-2ms assertions flaky even when the cache path is working correctly.
        """
        import time

        # Create a test file
        test_file = tmp_path / "perf_test.md"
        test_content = '---\ntitle: "Performance Test"\ndate: 2026-03-13\nlocation: "Beijing"\nweather: "Sunny"\ntopic: ["work", "life"]\nproject: "Test"\ntags: ["tag1", "tag2", "tag3"]\nmood: ["happy", "productive"]\npeople: ["Alice", "Bob"]\nabstract: "This is a test abstract for performance testing"\n---\n\n# Performance Test\n\nThis is the content of the performance test file.\nIt has multiple lines to simulate a real journal entry.\n\n## Section 1\n\nSome content here.\n\n## Section 2\n\nMore content here.\n'
        test_file.write_text(test_content, encoding="utf-8")

        # First call - parse and cache
        result1 = get_or_update_metadata(test_file)

        # Second call - from cache (measure)
        start = time.perf_counter()
        result2 = get_or_update_metadata(test_file)
        cache_time = time.perf_counter() - start

        # Both should return same result
        assert result1 is not None
        assert result2 is not None
        assert result1["title"] == result2["title"]

        # Cache read should complete within 5ms (practically instantaneous)
        assert cache_time < 0.005, (
            f"Cache read took {cache_time * 1000:.2f}ms, expected < 5ms"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
