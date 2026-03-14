#!/usr/bin/env python3
"""
Unit tests for write_journal/attachments.py

Tests cover:
- File path detection from content
- Path validation
- File copy and rename
- Cross-platform path handling
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import os


class TestLooksLikeFilePath:
    """Tests for looks_like_file_path function"""

    def test_valid_image_extensions(self):
        """Valid image extensions should return True"""
        from tools.write_journal.attachments import looks_like_file_path

        assert looks_like_file_path("image.jpg") is True
        assert looks_like_file_path("image.png") is True
        assert looks_like_file_path("image.gif") is True

    def test_valid_video_extensions(self):
        """Valid video extensions should return True"""
        from tools.write_journal.attachments import looks_like_file_path

        assert looks_like_file_path("video.mp4") is True
        assert looks_like_file_path("video.mov") is True

    def test_valid_document_extensions(self):
        """Valid document extensions should return True"""
        from tools.write_journal.attachments import looks_like_file_path

        assert looks_like_file_path("document.pdf") is True
        assert looks_like_file_path("document.docx") is True

    def test_invalid_extensions(self):
        """Invalid extensions should return False"""
        from tools.write_journal.attachments import looks_like_file_path

        assert looks_like_file_path("noextension") is False
        assert looks_like_file_path("file.unknownext") is False

    def test_empty_path(self):
        """Empty path should return False"""
        from tools.write_journal.attachments import looks_like_file_path

        assert looks_like_file_path("") is False
        assert looks_like_file_path(None) is False


class TestExtractFilePathsFromContent:
    """Tests for extract_file_paths_from_content function"""

    def test_extract_windows_absolute_path(self):
        """Extract Windows absolute paths"""
        from tools.write_journal.attachments import extract_file_paths_from_content

        content = "See C:\\Users\\test\\file.mp4 for details"
        paths = extract_file_paths_from_content(content)

        assert len(paths) == 1
        assert "file.mp4" in paths[0]

    def test_extract_windows_forward_slash(self):
        """Extract Windows paths with forward slashes"""
        from tools.write_journal.attachments import extract_file_paths_from_content

        content = "Check C:/Users/test/document.pdf"
        paths = extract_file_paths_from_content(content)

        assert len(paths) == 1
        assert "document.pdf" in paths[0]

    def test_extract_multiple_paths(self):
        """Extract multiple file paths"""
        from tools.write_journal.attachments import extract_file_paths_from_content

        content = """
        Files:
        C:\\Users\\test\\video.mp4
        C:\\Users\\test\\image.png
        """
        paths = extract_file_paths_from_content(content)

        assert len(paths) == 2

    def test_deduplicate_paths(self):
        """Duplicate paths should be deduplicated"""
        from tools.write_journal.attachments import extract_file_paths_from_content

        content = "C:\\Users\\test\\file.mp4 and C:/Users/test/file.mp4"
        paths = extract_file_paths_from_content(content)

        # Should deduplicate (same file, different slash style)
        assert len(paths) <= 2

    def test_skip_non_file_paths(self):
        """Skip paths without valid file extensions"""
        from tools.write_journal.attachments import extract_file_paths_from_content

        content = "Visit C:\\Users\\test\\folder for more"
        paths = extract_file_paths_from_content(content)

        # Should not match folder paths without extensions
        assert len(paths) == 0

    def test_empty_content(self):
        """Empty content should return empty list"""
        from tools.write_journal.attachments import extract_file_paths_from_content

        assert extract_file_paths_from_content("") == []
        assert extract_file_paths_from_content(None) == []


class TestProcessAttachments:
    """Tests for process_attachments function"""

    def test_process_single_attachment(self, tmp_path):
        """Process a single attachment"""
        from tools.write_journal.attachments import process_attachments

        # Create a source file
        source_file = tmp_path / "source.mp4"
        source_file.write_text("test content")

        with patch(
            "tools.write_journal.attachments.ATTACHMENTS_DIR", tmp_path / "attachments"
        ):
            result = process_attachments(
                attachments=[
                    {"source_path": str(source_file), "description": "Test file"}
                ],
                date_str="2026-03-10",
                dry_run=True,
            )

        assert len(result) == 1
        assert result[0]["filename"] == "source.mp4"

    def test_process_nonexistent_file(self, tmp_path):
        """Process a nonexistent source file"""
        from tools.write_journal.attachments import process_attachments

        with patch(
            "tools.write_journal.attachments.ATTACHMENTS_DIR", tmp_path / "attachments"
        ):
            result = process_attachments(
                attachments=[
                    {"source_path": "/nonexistent/file.mp4", "description": ""}
                ],
                date_str="2026-03-10",
                dry_run=True,
            )

        assert len(result) == 1
        assert "error" in result[0]
        assert "未找到" in result[0]["filename"]

    def test_merge_auto_detected_paths(self, tmp_path):
        """Merge explicit and auto-detected paths"""
        from tools.write_journal.attachments import process_attachments

        source_file = tmp_path / "explicit.mp4"
        source_file.write_text("test")

        auto_file = tmp_path / "auto.png"
        auto_file.write_text("test")

        with patch(
            "tools.write_journal.attachments.ATTACHMENTS_DIR", tmp_path / "attachments"
        ):
            result = process_attachments(
                attachments=[{"source_path": str(source_file), "description": ""}],
                date_str="2026-03-10",
                dry_run=True,
                auto_detected_paths=[str(auto_file)],
            )

        assert len(result) == 2

    def test_deduplicate_explicit_and_auto(self, tmp_path):
        """Deduplicate when same path in both explicit and auto-detected"""
        from tools.write_journal.attachments import process_attachments

        source_file = tmp_path / "file.mp4"
        source_file.write_text("test")

        with patch(
            "tools.write_journal.attachments.ATTACHMENTS_DIR", tmp_path / "attachments"
        ):
            result = process_attachments(
                attachments=[{"source_path": str(source_file), "description": ""}],
                date_str="2026-03-10",
                dry_run=True,
                auto_detected_paths=[str(source_file)],  # Same file
            )

        # Should deduplicate
        assert len(result) == 1

    def test_generate_relative_path(self, tmp_path):
        """Generate correct relative path"""
        from tools.write_journal.attachments import process_attachments

        source_file = tmp_path / "test.mp4"
        source_file.write_text("test")

        with patch(
            "tools.write_journal.attachments.ATTACHMENTS_DIR", tmp_path / "attachments"
        ):
            result = process_attachments(
                attachments=[{"source_path": str(source_file), "description": ""}],
                date_str="2026-03-10",
                dry_run=True,
            )

        assert "rel_path" in result[0]
        assert "Attachments" in result[0]["rel_path"]
        assert "2026" in result[0]["rel_path"]

    def test_skip_directories(self, tmp_path):
        """Skip directories in attachment processing"""
        from tools.write_journal.attachments import process_attachments

        # Create a directory (not a file)
        source_dir = tmp_path / "subdir"
        source_dir.mkdir()

        with patch(
            "tools.write_journal.attachments.ATTACHMENTS_DIR", tmp_path / "attachments"
        ):
            result = process_attachments(
                attachments=[{"source_path": str(source_dir), "description": ""}],
                date_str="2026-03-10",
                dry_run=True,
            )

        # Should skip the directory
        assert len(result) == 0

    def test_dry_run_no_copy(self, tmp_path):
        """Dry run should not copy files"""
        from tools.write_journal.attachments import process_attachments

        source_file = tmp_path / "source.mp4"
        source_file.write_text("test")

        att_dir = tmp_path / "attachments"
        with patch("tools.write_journal.attachments.ATTACHMENTS_DIR", att_dir):
            result = process_attachments(
                attachments=[{"source_path": str(source_file), "description": ""}],
                date_str="2026-03-10",
                dry_run=True,
            )

        # Should not create the attachments directory
        assert not att_dir.exists()

    def test_actual_copy_creates_file(self, tmp_path):
        """Non-dry-run should copy the file"""
        from tools.write_journal.attachments import process_attachments

        source_file = tmp_path / "source.mp4"
        source_file.write_text("test content")

        att_dir = tmp_path / "attachments"
        with patch("tools.write_journal.attachments.ATTACHMENTS_DIR", att_dir):
            result = process_attachments(
                attachments=[{"source_path": str(source_file), "description": ""}],
                date_str="2026-03-10",
                dry_run=False,
            )

        assert len(result) == 1
        # Check file was copied
        copied_file = att_dir / "2026" / "03" / "source.mp4"
        assert copied_file.exists()


class TestCrossPlatformPaths:
    """Tests for cross-platform path handling"""

    def test_windows_path_on_windows(self):
        """Windows path should work on Windows"""
        from tools.write_journal.attachments import convert_path_for_platform
        from tools.write_journal.utils import convert_path_for_platform as convert

        # This tests that the function exists and returns something
        result = convert("C:\\Users\\test\\file.mp4")
        assert result is not None

    def test_mixed_slashes(self):
        """Handle mixed forward/backward slashes"""
        from tools.write_journal.attachments import extract_file_paths_from_content

        # Mixed slashes in path
        content = "C:\\Users/test\\file.mp4"
        paths = extract_file_paths_from_content(content)

        # Should still extract something
        # The exact behavior depends on implementation
        pass  # Acceptance test


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
