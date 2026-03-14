#!/usr/bin/env python3
"""
Unit tests for tools/edit_journal/__init__.py

Tests cover:
- Journal parsing
- Frontmatter updates
- Index operations
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add project root to path for proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestParseJournal:
    """Tests for parse_journal function"""

    def test_parse_valid_journal(self, tmp_path):
        """Parse a valid journal file"""
        from tools.edit_journal import parse_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            """---
title: Test Journal
date: 2026-03-14
location: Beijing
---

# Test Content
""",
            encoding="utf-8",
        )

        metadata, body = parse_journal(journal)

        assert metadata.get("title") == "Test Journal"
        assert "Test Content" in body

    def test_parse_nonexistent_file(self, tmp_path):
        """Parse nonexistent file"""
        from tools.edit_journal import parse_journal

        nonexistent = tmp_path / "nonexistent.md"
        metadata, body = parse_journal(nonexistent)

        assert "_error" in metadata or metadata.get("title") is None


class TestRemoveFromIndex:
    """Tests for remove_from_index function"""

    def test_remove_existing_entry(self, tmp_path):
        """Remove existing entry from index"""
        from tools.edit_journal import remove_from_index

        index_file = tmp_path / "index.md"
        index_file.write_text(
            """# 主题: work

- [2026-03-14] [Test](../../Journals/2026/03/test_001.md)
- [2026-03-15] [Other](../../Journals/2026/03/other_001.md)
""",
            encoding="utf-8",
        )

        result = remove_from_index(index_file, "test_001.md")

        assert result is True
        content = index_file.read_text(encoding="utf-8")
        assert "test_001.md" not in content
        assert "other_001.md" in content

    def test_remove_nonexistent_entry(self, tmp_path):
        """Remove nonexistent entry returns False"""
        from tools.edit_journal import remove_from_index

        index_file = tmp_path / "index.md"
        index_file.write_text(
            """# 主题: work

- [2026-03-14] [Test](../../Journals/2026/03/test_001.md)
""",
            encoding="utf-8",
        )

        result = remove_from_index(index_file, "nonexistent.md")

        assert result is False

    def test_remove_from_nonexistent_index(self, tmp_path):
        """Remove from nonexistent index returns False"""
        from tools.edit_journal import remove_from_index

        nonexistent = tmp_path / "nonexistent.md"
        result = remove_from_index(nonexistent, "test.md")

        assert result is False


class TestNormalizeToList:
    """Tests for _normalize_to_list helper"""

    def test_string_to_list(self):
        """String becomes list"""
        from tools.edit_journal import _normalize_to_list

        assert _normalize_to_list("work") == ["work"]

    def test_list_unchanged(self):
        """List stays as list"""
        from tools.edit_journal import _normalize_to_list

        assert _normalize_to_list(["work", "learn"]) == ["work", "learn"]

    def test_empty_returns_empty(self):
        """Empty returns empty list"""
        from tools.edit_journal import _normalize_to_list

        assert _normalize_to_list(None) == []
        assert _normalize_to_list("") == []
        assert _normalize_to_list([]) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
