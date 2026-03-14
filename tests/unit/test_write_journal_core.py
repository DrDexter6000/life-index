#!/usr/bin/env python3
"""
Unit tests for write_journal/core.py

Tests cover:
- write_journal main function
- Validation and error handling
- Location and weather handling
- Dry run mode
- Lock timeout handling
- Attachment processing
- Index updates
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from tools.write_journal.core import write_journal


class TestWriteJournalBasic:
    """Tests for basic write_journal functionality"""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Mock all dependencies for write_journal"""
        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)

        by_topic_dir = tmp_path / "by-topic"
        by_topic_dir.mkdir(parents=True)

        attachments_dir = tmp_path / "attachments"
        attachments_dir.mkdir(parents=True)

        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir(parents=True)

        lock_path = cache_dir / "journals.lock"
        lock_path.touch()

        return {
            "journals_dir": journals_dir,
            "by_topic_dir": by_topic_dir,
            "attachments_dir": attachments_dir,
            "cache_dir": cache_dir,
            "lock_path": lock_path,
            "user_data_dir": tmp_path,
        }

    def test_basic_success(self, mock_deps, tmp_path):
        """Test basic successful journal write"""
        data = {
            "date": "2026-03-14",
            "title": "Test Journal",
            "content": "This is test content.",
        }

        with patch("tools.write_journal.core.JOURNALS_DIR", mock_deps["journals_dir"]):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=mock_deps["lock_path"],
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.query_weather_for_location",
                            return_value="Sunny 25°C",
                        ):
                            with patch(
                                "tools.write_journal.core.normalize_location",
                                return_value="Chongqing, China",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={
                                                "abstract_path": None,
                                                "updated": False,
                                            },
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        result = write_journal(
                                                            data, dry_run=False
                                                        )

        assert result["success"] is True
        assert result["journal_path"] is not None
        assert "location_used" in result
        assert result["needs_confirmation"] is True

    def test_basic_success_dry_run(self, mock_deps, tmp_path):
        """Test dry run mode does not create file"""
        data = {
            "date": "2026-03-14",
            "title": "Test Journal",
            "content": "This is test content.",
        }

        with patch("tools.write_journal.core.JOURNALS_DIR", mock_deps["journals_dir"]):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=mock_deps["lock_path"],
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.query_weather_for_location",
                            return_value="Sunny 25°C",
                        ):
                            with patch(
                                "tools.write_journal.core.normalize_location",
                                return_value="Chongqing, China",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        result = write_journal(data, dry_run=True)

        assert result["success"] is True
        assert result["journal_path"] is not None
        assert "content_preview" in result
        # Dry run returns early without confirmation message
        assert result["needs_confirmation"] is False


class TestWriteJournalValidation:
    """Tests for input validation"""

    def test_missing_date_field(self):
        """Test that missing date field raises error"""
        data = {
            "title": "Test Journal",
            "content": "This is test content.",
        }

        result = write_journal(data)

        assert result["success"] is False
        assert result["error"] is not None
        assert "date" in result["error"].lower()

    def test_empty_date_field(self):
        """Test that empty date field raises error"""
        data = {
            "date": "",
            "title": "Test Journal",
            "content": "This is test content.",
        }

        result = write_journal(data)

        assert result["success"] is False
        assert result["error"] is not None


class TestWriteJournalLocation:
    """Tests for location handling"""

    def test_default_location_used(self, tmp_path):
        """Test that default location is used when none provided"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Chongqing, China",
                        ) as mock_norm:
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        # Default location should be used (Chongqing, China)
        assert result["location_used"] == "Chongqing, China"

    def test_user_provided_location_preserved(self, tmp_path):
        """Test that user-provided location is preserved"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "location": "Beijing, China",
        }

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Beijing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        assert result["location_used"] == "Beijing, China"


class TestWriteJournalWeather:
    """Tests for weather handling"""

    def test_auto_fill_weather(self, tmp_path):
        """Test that weather is auto-filled when not provided"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Chongqing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="Sunny 28°C/22°C",
                            ) as mock_weather:
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        assert result["weather_used"] == "Sunny 28°C/22°C"
        assert result["weather_auto_filled"] is True

    def test_user_provided_weather_preserved(self, tmp_path):
        """Test that user-provided weather is preserved"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "weather": "Rainy",
        }

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Chongqing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location"
                            ) as mock_weather:
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        # Weather query should not be called since user provided weather
        mock_weather.assert_not_called()
        assert result["weather_used"] == "Rainy"
        assert result["weather_auto_filled"] is False

    def test_weather_query_failure_graceful(self, tmp_path):
        """Test that weather query failure is handled gracefully"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Chongqing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        # Should succeed even without weather
        assert result["success"] is True
        assert result["weather_used"] == ""


class TestWriteJournalLockTimeout:
    """Tests for lock timeout handling"""

    def test_lock_timeout_returns_error(self, tmp_path):
        """Test that lock timeout returns structured error"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        from tools.lib.file_lock import LockTimeoutError

        # Create a mock lock that raises LockTimeoutError
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(
            side_effect=LockTimeoutError(str(tmp_path / "test.lock"), 30.0)
        )
        mock_lock.__exit__ = MagicMock(return_value=None)

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / "test.lock",
            ):
                with patch("tools.write_journal.core.FileLock", return_value=mock_lock):
                    with patch(
                        "tools.write_journal.core.normalize_location",
                        return_value="Chongqing, China",
                    ):
                        result = write_journal(data)

        assert result["success"] is False
        assert "error" in result


class TestWriteJournalAttachments:
    """Tests for attachment processing"""

    def test_attachments_processed(self, tmp_path):
        """Test that attachments are processed correctly"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "attachments": [
                {"source_path": "/path/to/file.pdf", "description": "Test file"}
            ],
        }

        mock_attachments = [
            {
                "filename": "file.pdf",
                "rel_path": "../../../Attachments/2026/03/file.pdf",
                "description": "Test file",
            }
        ]

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Chongqing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=mock_attachments,
                                    ) as mock_proc:
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        assert result["attachments_processed"] == mock_attachments

    def test_auto_detected_attachments(self, tmp_path):
        """Test that auto-detected file paths are processed"""
        data = {
            "date": "2026-03-14",
            "content": "Check this file: C:\\Users\\test\\document.pdf",
        }

        auto_detected = ["C:\\Users\\test\\document.pdf"]
        mock_attachments = [
            {
                "filename": "document.pdf",
                "rel_path": "../../../Attachments/2026/03/document.pdf",
                "description": "",
            }
        ]

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Chongqing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=auto_detected,
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=mock_attachments,
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        assert result["attachments_processed"] == mock_attachments


class TestWriteJournalIndexUpdates:
    """Tests for index update operations"""

    def test_topic_index_updated(self, tmp_path):
        """Test that topic index is updated"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "topic": "work",
        }

        mock_topic_indices = [tmp_path / "by-topic" / "主题_work.md"]

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Chongqing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=mock_topic_indices,
                                            ) as mock_topic:
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        assert len(result["updated_indices"]) == 1

    def test_project_index_updated(self, tmp_path):
        """Test that project index is updated"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "project": "Life-Index",
        }

        mock_project_index = tmp_path / "by-topic" / "项目_Life-Index.md"

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Chongqing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=mock_project_index,
                                                ) as mock_proj:
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        assert len(result["updated_indices"]) == 1

    def test_tag_indices_updated(self, tmp_path):
        """Test that tag indices are updated"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "tags": ["python", "testing"],
        }

        mock_tag_indices = [
            tmp_path / "by-topic" / "标签_python.md",
            tmp_path / "by-topic" / "标签_testing.md",
        ]

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Chongqing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=mock_tag_indices,
                                                    ) as mock_tags:
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        assert len(result["updated_indices"]) == 2


class TestWriteJournalMetrics:
    """Tests for performance metrics"""

    def test_metrics_included(self, tmp_path):
        """Test that metrics are included in result"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Chongqing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        assert "metrics" in result
        assert isinstance(result["metrics"], dict)


class TestWriteJournalConfirmation:
    """Tests for confirmation message"""

    def test_confirmation_message_includes_location(self, tmp_path):
        """Test that confirmation message includes location"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "location": "Beijing, China",
        }

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Beijing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        assert result["needs_confirmation"] is True
        assert "Beijing, China" in result["confirmation_message"]

    def test_confirmation_message_includes_weather(self, tmp_path):
        """Test that confirmation message includes weather"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "weather": "Sunny",
        }

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=tmp_path / ".cache" / "journals.lock",
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence", return_value=1
                    ):
                        with patch(
                            "tools.write_journal.core.normalize_location",
                            return_value="Chongqing, China",
                        ):
                            with patch(
                                "tools.write_journal.core.query_weather_for_location",
                                return_value="",
                            ):
                                with patch(
                                    "tools.write_journal.core.extract_file_paths_from_content",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.process_attachments",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "tools.write_journal.core.update_monthly_abstract",
                                            return_value={},
                                        ):
                                            with patch(
                                                "tools.write_journal.core.update_topic_index",
                                                return_value=[],
                                            ):
                                                with patch(
                                                    "tools.write_journal.core.update_project_index",
                                                    return_value=None,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        # Create lock file parent
                                                        (tmp_path / ".cache").mkdir(
                                                            parents=True, exist_ok=True
                                                        )
                                                        (
                                                            tmp_path
                                                            / ".cache"
                                                            / "journals.lock"
                                                        ).touch()
                                                        result = write_journal(data)

        assert result["needs_confirmation"] is True
        assert "Sunny" in result["confirmation_message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
