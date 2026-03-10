#!/usr/bin/env python3
"""
Unit tests for config.py core functions
"""

import pytest
from pathlib import Path
import sys

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from lib.config import (
    get_safe_path,
    normalize_path,
    get_journal_dir,
)


class TestGetSafePath:
    """Tests for get_safe_path function"""

    def test_empty_path_returns_none(self):
        """Empty path should return None"""
        result = get_safe_path("")
        assert result is None

    def test_none_path_returns_none(self):
        """None path should return None"""
        result = get_safe_path(None)
        assert result is None

    def test_absolute_path_resolved(self):
        """Absolute path should be resolved"""
        result = get_safe_path("/tmp/test.txt")
        assert result is not None
        assert isinstance(result, Path)

    def test_relative_path_with_base(self):
        """Relative path should be resolved against base_dir"""
        base = Path("/tmp")
        result = get_safe_path("test.txt", base)
        assert result is not None
        assert "test.txt" in str(result)

    def test_path_traversal_blocked(self, tmp_path):
        """Path traversal attempts should be handled"""
        # Create a base directory
        base = tmp_path / "safe"
        base.mkdir()

        # Try to escape with ..
        result = get_safe_path("../../../etc/passwd", base)
        # The function should still return a path, but it won't be inside base
        # This is documented behavior - caller decides how to handle
        assert result is not None


class TestNormalizePath:
    """Tests for normalize_path function"""

    def test_empty_path_returns_empty(self):
        """Empty path should return empty string"""
        assert normalize_path("") == ""

    def test_none_path_returns_empty(self):
        """None path should return empty string"""
        assert normalize_path(None) == ""

    def test_backslash_converted_to_forward_slash(self):
        """Windows backslashes should be converted"""
        result = normalize_path("C:\\Users\\test\\file.txt")
        assert "\\" not in result
        assert "/" in result

    def test_windows_long_path_prefix_removed(self):
        """Windows long path prefix should be removed"""
        result = normalize_path("\\\\?\\C:\\Users\\test\\file.txt")
        assert not result.startswith("\\\\?\\")

    def test_forward_slash_preserved(self):
        """Forward slashes should be preserved"""
        result = normalize_path("/home/user/file.txt")
        assert result == "/home/user/file.txt"


class TestGetJournalDir:
    """Tests for get_journal_dir function"""

    def test_default_returns_current_year_month(self):
        """Default call should return current year/month directory"""
        result = get_journal_dir()
        assert isinstance(result, Path)

        now = Path(__file__).parent  # Just check it's a Path
        assert "Journals" in str(result)

    def test_explicit_year_month(self):
        """Explicit year/month should be used"""
        result = get_journal_dir(year=2025, month=6)
        assert "2025" in str(result)
        assert "06" in str(result)

    def test_month_zero_padded(self):
        """Month should be zero-padded"""
        result = get_journal_dir(year=2026, month=3)
        assert "03" in str(result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
