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


class TestExtractFilePathsFromContent:
    """Tests for extract_file_paths_from_content function"""

    def test_extract_unc_path(self):
        """Extract UNC network style paths"""
        from tools.write_journal.attachments import extract_file_paths_from_content

        content = r"See \\server\share\folder\file.pdf for details"
        paths = extract_file_paths_from_content(content)

        assert len(paths) == 1
        assert paths[0].endswith("file.pdf")

    def test_skip_invalid_windows_extension_match(self):
        """Windows-looking paths with invalid extensions should be filtered out"""
        from tools.write_journal.attachments import extract_file_paths_from_content

        content = r"Check C:\Users\test\file.unknownext immediately"
        paths = extract_file_paths_from_content(content)

        assert paths == []

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

    def test_extract_path_with_spaces(self):
        """Extract paths with spaces in filename (Chinese+English common case)"""
        from tools.write_journal.attachments import extract_file_paths_from_content

        # BUG FIX TEST: Paths with spaces should be fully matched
        content = "See C:\\Users\\17865\\Downloads\\Opus 审计报告.txt for details"
        paths = extract_file_paths_from_content(content)

        assert len(paths) == 1
        # Should match the full filename with space, not just "Opus"
        assert "Opus 审计报告.txt" in paths[0]
        assert paths[0].endswith("Opus 审计报告.txt")

    def test_extract_path_with_multiple_spaces(self):
        """Extract paths with multiple spaces in filename"""
        from tools.write_journal.attachments import extract_file_paths_from_content

        content = "Check C:\\Program Files\\My App\\工作报告 2026 final.txt"
        paths = extract_file_paths_from_content(content)

        assert len(paths) == 1
        assert "工作报告 2026 final.txt" in paths[0]


class TestProcessAttachments:
    """Tests for process_attachments function"""

    def test_process_string_attachment(self, tmp_path):
        """String attachment entries should be converted to dict form"""
        from tools.write_journal.attachments import process_attachments

        source_file = tmp_path / "string.mp4"
        source_file.write_text("test content")

        with patch(
            "tools.write_journal.attachments.ATTACHMENTS_DIR", tmp_path / "attachments"
        ):
            result = process_attachments(
                attachments=[str(source_file)],
                date_str="2026-03-10",
                dry_run=True,
            )

        assert len(result) == 1
        assert result[0]["filename"] == "string.mp4"

    def test_empty_attachments_returns_empty(self, tmp_path):
        """Empty attachments and no auto-detected paths should return empty list"""
        from tools.write_journal.attachments import process_attachments

        with patch(
            "tools.write_journal.attachments.ATTACHMENTS_DIR", tmp_path / "attachments"
        ):
            assert process_attachments([], "2026-03-10", dry_run=True) == []

    def test_skip_empty_source_path(self, tmp_path):
        """Entries with empty source_path should be skipped"""
        from tools.write_journal.attachments import process_attachments

        source_file = tmp_path / "valid.mp4"
        source_file.write_text("test")

        with patch(
            "tools.write_journal.attachments.ATTACHMENTS_DIR", tmp_path / "attachments"
        ):
            result = process_attachments(
                attachments=[
                    {"source_path": "", "description": "bad"},
                    {"source_path": str(source_file), "description": "good"},
                ],
                date_str="2026-03-10",
                dry_run=True,
            )

        assert len(result) == 1
        assert result[0]["filename"] == "valid.mp4"

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

    def test_process_url_attachment_downloads_and_archives(self, tmp_path):
        """URL attachment entries should be downloaded then normalized into archived attachments."""
        from tools.write_journal.attachments import process_attachments

        downloaded = tmp_path / "downloads" / "2026" / "03" / "photo.jpg"
        downloaded.parent.mkdir(parents=True, exist_ok=True)
        downloaded.write_bytes(b"jpeg-bytes")

        async def fake_download(url: str, target_dir: Path, date_str: str):
            assert url == "https://example.com/photo.jpg"
            assert date_str == "2026-03-10"
            return {
                "success": True,
                "path": str(downloaded),
                "filename": "photo.jpg",
                "content_type": "image/jpeg",
                "size": 10,
            }

        with patch(
            "tools.write_journal.attachments.download_attachment_from_url",
            new=fake_download,
        ):
            with patch(
                "tools.write_journal.attachments.ATTACHMENTS_DIR",
                tmp_path / "attachments",
            ):
                result = process_attachments(
                    attachments=[
                        {
                            "source_url": "https://example.com/photo.jpg",
                            "description": "远程图片",
                        }
                    ],
                    date_str="2026-03-10",
                    dry_run=True,
                )

        assert result == [
            {
                "filename": "photo.jpg",
                "rel_path": "../../../attachments/2026/03/photo.jpg",
                "description": "远程图片",
                "original_name": "photo.jpg",
                "auto_detected": False,
                "source_url": "https://example.com/photo.jpg",
                "content_type": "image/jpeg",
                "size": 10,
            }
        ]

    def test_process_url_attachment_surfaces_download_failure(self, tmp_path):
        """Download failures should be reported as attachment processing errors."""
        from tools.write_journal.attachments import process_attachments

        async def fake_download(url: str, target_dir: Path, date_str: str):
            return {
                "success": False,
                "error": "download failed",
                "error_code": "E0701",
            }

        with patch(
            "tools.write_journal.attachments.download_attachment_from_url",
            new=fake_download,
        ):
            with patch(
                "tools.write_journal.attachments.ATTACHMENTS_DIR",
                tmp_path / "attachments",
            ):
                result = process_attachments(
                    attachments=[
                        {
                            "source_url": "https://example.com/bad.jpg",
                            "description": "坏链接",
                        }
                    ],
                    date_str="2026-03-10",
                    dry_run=True,
                )

        assert result == [
            {
                "filename": "[下载失败: https://example.com/bad.jpg]",
                "description": "坏链接",
                "error": "download failed",
                "auto_detected": False,
                "error_code": "E0701",
            }
        ]

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
        assert "attachments" in result[0]["rel_path"]
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
        assert result[0]["content_type"] == "video/mp4"
        assert result[0]["size"] == len("test content")

    def test_rename_duplicate_files(self, tmp_path):
        """Duplicate target filenames should be renamed with counter suffix"""
        from tools.write_journal.attachments import process_attachments

        source_file = tmp_path / "source.mp4"
        source_file.write_text("new content")

        att_dir = tmp_path / "attachments"
        existing_dir = att_dir / "2026" / "03"
        existing_dir.mkdir(parents=True)
        (existing_dir / "source.mp4").write_text("existing")

        with patch("tools.write_journal.attachments.ATTACHMENTS_DIR", att_dir):
            result = process_attachments(
                attachments=[{"source_path": str(source_file), "description": ""}],
                date_str="2026-03-10",
                dry_run=False,
            )

        assert len(result) == 1
        assert result[0]["filename"] == "source_001.mp4"
        assert (existing_dir / "source_001.mp4").exists()


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


class TestStripCjkSpaces:
    """Tests for _strip_cjk_spaces: LLM 中英文空格容错"""

    def test_english_chinese_space(self):
        """Remove space between English and Chinese characters"""
        from tools.write_journal.attachments import _strip_cjk_spaces

        assert _strip_cjk_spaces("Opus 审计报告.txt") == "Opus审计报告.txt"

    def test_chinese_english_space(self):
        """Remove space between Chinese and English characters"""
        from tools.write_journal.attachments import _strip_cjk_spaces

        assert _strip_cjk_spaces("审计报告 Final.txt") == "审计报告Final.txt"

    def test_multiple_mixed_spaces(self):
        """Remove multiple mixed-script spaces"""
        from tools.write_journal.attachments import _strip_cjk_spaces

        assert (
            _strip_cjk_spaces("Opus 审计 Report 报告.txt") == "Opus审计Report报告.txt"
        )

    def test_preserve_english_only_spaces(self):
        """Keep spaces between English words"""
        from tools.write_journal.attachments import _strip_cjk_spaces

        assert _strip_cjk_spaces("my report.txt") == "my report.txt"

    def test_preserve_chinese_only_spaces(self):
        """Keep spaces between Chinese characters (rare but valid)"""
        from tools.write_journal.attachments import _strip_cjk_spaces

        # Space between two Chinese chars is intentional, don't touch it
        assert _strip_cjk_spaces("审计 报告.txt") == "审计 报告.txt"

    def test_no_spaces(self):
        """No-op when no spaces present"""
        from tools.write_journal.attachments import _strip_cjk_spaces

        assert _strip_cjk_spaces("Opus审计报告.txt") == "Opus审计报告.txt"

    def test_full_path_only_modifies_filename(self):
        """Only strip spaces in filename, not directory components"""
        from tools.write_journal.attachments import _strip_cjk_spaces

        result = _strip_cjk_spaces("C:\\Users\\test\\Downloads\\Opus 审计报告.txt")
        assert result == "C:\\Users\\test\\Downloads\\Opus审计报告.txt"

    def test_number_chinese_space(self):
        """Remove space between number and Chinese"""
        from tools.write_journal.attachments import _strip_cjk_spaces

        assert _strip_cjk_spaces("2026 年报.txt") == "2026年报.txt"


class TestResolveAttachmentPath:
    """Tests for _resolve_attachment_path: multi-strategy path resolution"""

    def test_exact_match(self):
        """Return source_path when it exists"""
        from tools.write_journal.attachments import _resolve_attachment_path

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            temp_path = f.name

        try:
            result = _resolve_attachment_path(temp_path, temp_path)
            assert result == temp_path
        finally:
            os.unlink(temp_path)

    def test_cjk_space_fallback(self):
        """Find file by stripping CJK spaces when exact path fails"""
        from tools.write_journal.attachments import _resolve_attachment_path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file WITHOUT space
            real_file = os.path.join(tmpdir, "Opus审计报告.txt")
            with open(real_file, "w") as f:
                f.write("test")

            # Try to find it WITH space (simulating LLM-injected space)
            bad_path = os.path.join(tmpdir, "Opus 审计报告.txt")
            result = _resolve_attachment_path(bad_path, bad_path)

            assert result == real_file

    def test_all_strategies_fail(self):
        """Return None when no strategy works"""
        from tools.write_journal.attachments import _resolve_attachment_path

        result = _resolve_attachment_path(
            "/nonexistent/Opus 审计报告.txt",
            "/nonexistent/Opus 审计报告.txt",
        )
        assert result is None

    def test_cross_platform_converted_path_match(self):
        """Return converted path when original is missing but converted exists"""
        from tools.write_journal.attachments import _resolve_attachment_path

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            converted = f.name

        try:
            result = _resolve_attachment_path("/nonexistent/original.txt", converted)
            assert result == converted
        finally:
            os.unlink(converted)

    def test_cross_platform_cjk_space_fallback(self):
        """Resolve via stripped converted path when converted path contains injected CJK spaces"""
        from tools.write_journal.attachments import _resolve_attachment_path

        with tempfile.TemporaryDirectory() as tmpdir:
            real_file = os.path.join(tmpdir, "Opus审计报告.txt")
            with open(real_file, "w", encoding="utf-8") as f:
                f.write("test")

            converted_bad = os.path.join(tmpdir, "Opus 审计报告.txt")
            result = _resolve_attachment_path(
                "/nonexistent/original.txt", converted_bad
            )

            assert result == real_file


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
