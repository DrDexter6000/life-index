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

from tools.write_journal.core import write_journal


@pytest.fixture(autouse=True)
def mock_vector_update_side_effect():
    """Keep write_journal unit tests isolated from vector index/model loading."""
    with patch("tools.write_journal.core.update_vector_index", return_value=False):
        yield


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

    def test_configured_default_location_used(self, tmp_path):
        """Test that configured default location is used when none provided"""
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
                            "tools.write_journal.core.get_default_location",
                            return_value="Lagos, Nigeria",
                        ):
                            with patch(
                                "tools.write_journal.core.normalize_location",
                                return_value="Lagos, Nigeria",
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
                                                            (tmp_path / ".cache").mkdir(
                                                                parents=True,
                                                                exist_ok=True,
                                                            )
                                                            (
                                                                tmp_path
                                                                / ".cache"
                                                                / "journals.lock"
                                                            ).touch()
                                                            result = write_journal(data)

        assert result["location_used"] == "Lagos, Nigeria"

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

    def test_content_location_overrides_default_location(self, tmp_path):
        """Explicit location in content should win over default fallback"""
        data = {
            "date": "2026-03-14",
            "content": "地点：Beijing, China\n今天过得不错。",
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
                            "tools.write_journal.core.get_default_location",
                            return_value="Lagos, Nigeria",
                        ) as mock_default:
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
                                                            (tmp_path / ".cache").mkdir(
                                                                parents=True,
                                                                exist_ok=True,
                                                            )
                                                            (
                                                                tmp_path
                                                                / ".cache"
                                                                / "journals.lock"
                                                            ).touch()
                                                            result = write_journal(data)

        mock_default.assert_not_called()
        assert result["location_used"] == "Beijing, China"
        assert result["location_auto_filled"] is False


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

    def test_content_weather_preserved_without_query(self, tmp_path):
        """Explicit weather in content should skip auto query"""
        data = {
            "date": "2026-03-14",
            "content": "天气：Rainy\n今天一直在下雨。",
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
                            "tools.write_journal.core.get_default_location",
                            return_value="Lagos, Nigeria",
                        ):
                            with patch(
                                "tools.write_journal.core.normalize_location",
                                return_value="Lagos, Nigeria",
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
                                                            (tmp_path / ".cache").mkdir(
                                                                parents=True,
                                                                exist_ok=True,
                                                            )
                                                            (
                                                                tmp_path
                                                                / ".cache"
                                                                / "journals.lock"
                                                            ).touch()
                                                            result = write_journal(data)

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
                "rel_path": "../../../attachments/2026/03/file.pdf",
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
                "rel_path": "../../../attachments/2026/03/document.pdf",
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

        assert result["needs_confirmation"] is False
        assert result["confirmation_message"] == ""

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

    def test_confirmation_only_when_default_location_used(self, tmp_path):
        """Default location should trigger follow-up confirmation"""
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
                            "tools.write_journal.core.get_default_location",
                            return_value="Lagos, Nigeria",
                        ):
                            with patch(
                                "tools.write_journal.core.normalize_location",
                                return_value="Lagos, Nigeria",
                            ):
                                with patch(
                                    "tools.write_journal.core.query_weather_for_location",
                                    return_value="Sunny 33°C",
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
                                                            (tmp_path / ".cache").mkdir(
                                                                parents=True,
                                                                exist_ok=True,
                                                            )
                                                            (
                                                                tmp_path
                                                                / ".cache"
                                                                / "journals.lock"
                                                            ).touch()
                                                            result = write_journal(data)

        assert result["needs_confirmation"] is True
        assert "默认地点" in result["confirmation_message"]
        assert "Lagos, Nigeria" in result["confirmation_message"]


class TestWriteJournalWorkflowChains:
    """Workflow-chain tests for write + correction flow"""

    def test_default_location_write_then_edit_location_and_weather(self, tmp_path):
        """Write with default location, then correct location and weather together"""
        from tools.edit_journal import edit_journal

        data = {
            "date": "2026-03-14",
            "title": "Workflow Test",
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
                            "tools.write_journal.core.get_default_location",
                            return_value="Lagos, Nigeria",
                        ):
                            with patch(
                                "tools.write_journal.core.normalize_location",
                                side_effect=["Lagos, Nigeria"],
                            ):
                                with patch(
                                    "tools.write_journal.core.query_weather_for_location",
                                    return_value="Sunny 33°C",
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
                                                            (tmp_path / ".cache").mkdir(
                                                                parents=True,
                                                                exist_ok=True,
                                                            )
                                                            (
                                                                tmp_path
                                                                / ".cache"
                                                                / "journals.lock"
                                                            ).touch()
                                                            write_result = (
                                                                write_journal(data)
                                                            )

        assert write_result["success"] is True
        assert write_result["needs_confirmation"] is True

        journal_path = Path(write_result["journal_path"])

        with patch("tools.edit_journal.update_vector_index", return_value=False):
            edit_result = edit_journal(
                journal_path,
                {"location": "Beijing, China", "weather": "Cloudy 18°C"},
            )

        assert edit_result["success"] is True
        content = journal_path.read_text(encoding="utf-8")
        assert 'location: "Beijing, China"' in content
        assert 'weather: "Cloudy 18°C"' in content

    def test_manual_weather_fallback_can_complete_location_correction(self, tmp_path):
        """Manual weather input should still allow correction after auto weather failure"""
        from tools.edit_journal import edit_journal

        data = {
            "date": "2026-03-14",
            "title": "Fallback Workflow Test",
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
                            "tools.write_journal.core.get_default_location",
                            return_value="Lagos, Nigeria",
                        ):
                            with patch(
                                "tools.write_journal.core.normalize_location",
                                side_effect=["Lagos, Nigeria"],
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
                                                            (tmp_path / ".cache").mkdir(
                                                                parents=True,
                                                                exist_ok=True,
                                                            )
                                                            (
                                                                tmp_path
                                                                / ".cache"
                                                                / "journals.lock"
                                                            ).touch()
                                                            write_result = (
                                                                write_journal(data)
                                                            )

        assert write_result["success"] is True
        assert write_result["needs_confirmation"] is True
        assert write_result["weather_used"] == ""

        journal_path = Path(write_result["journal_path"])

        with patch("tools.edit_journal.update_vector_index", return_value=False):
            edit_result = edit_journal(
                journal_path,
                {
                    "location": "Beijing, China",
                    "weather": "Manual fallback: Cloudy 18°C",
                },
            )

        assert edit_result["success"] is True
        content = journal_path.read_text(encoding="utf-8")
        assert 'location: "Beijing, China"' in content
        assert 'weather: "Manual fallback: Cloudy 18°C"' in content


class TestWriteJournalTransactionRollback:
    """Tests for transaction rollback and cleanup scenarios"""

    def test_index_update_failure_cleans_temp_file(self, tmp_path):
        """Test that temp file is cleaned up when index update fails"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "topic": "work",
        }

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        lock_path = tmp_path / ".cache" / "journals.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        with patch("tools.write_journal.core.JOURNALS_DIR", journals_dir):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
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
                                                side_effect=OSError(
                                                    "Index write failed"
                                                ),
                                            ):
                                                result = write_journal(data)

        assert result["success"] is False
        assert "索引更新失败" in result["error"]
        # Temp file should not exist after cleanup
        temp_file = month_dir / "life-index_2026-03-14_001.md.tmp"
        assert not temp_file.exists()

    def test_index_update_failure_with_runtime_error(self, tmp_path):
        """Test that RuntimeError during index update is handled"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "topic": "work",
        }

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        lock_path = tmp_path / ".cache" / "journals.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        with patch("tools.write_journal.core.JOURNALS_DIR", journals_dir):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
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
                                                side_effect=RuntimeError(
                                                    "Runtime failure"
                                                ),
                                            ):
                                                result = write_journal(data)

        assert result["success"] is False
        assert "索引更新失败" in result["error"]

    def test_tag_index_update_failure_cleanup(self, tmp_path):
        """Test cleanup when tag index update fails"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "tags": ["python", "testing"],
        }

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        lock_path = tmp_path / ".cache" / "journals.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        with patch("tools.write_journal.core.JOURNALS_DIR", journals_dir):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
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
                                                        side_effect=IOError(
                                                            "Tag index failed"
                                                        ),
                                                    ):
                                                        result = write_journal(data)

        assert result["success"] is False
        assert "索引更新失败" in result["error"]

    def test_file_write_error_cleans_temp_file(self, tmp_path):
        """Test that OSError during file write cleans up temp file"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        lock_path = tmp_path / ".cache" / "journals.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        with patch("tools.write_journal.core.JOURNALS_DIR", journals_dir):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
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
                                        # Mock open to raise OSError for temp files
                                        import io

                                        def mock_open_error(
                                            file, mode="r", *args, **kwargs
                                        ):
                                            if ".tmp" in str(file):
                                                raise OSError("Disk full")
                                            # Return a mock file object for other calls
                                            return io.StringIO("test content")

                                        with patch(
                                            "builtins.open", side_effect=mock_open_error
                                        ):
                                            result = write_journal(data)

        assert result["success"] is False
        assert "Disk full" in result["error"]

    def test_temp_file_already_deleted_during_cleanup(self, tmp_path):
        """Test cleanup when temp file is already deleted"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "topic": "work",
        }

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        lock_path = tmp_path / ".cache" / "journals.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        # Track temp file operations
        temp_file_path = month_dir / "life-index_2026-03-14_001.md.tmp"

        with patch("tools.write_journal.core.JOURNALS_DIR", journals_dir):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
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
                                                side_effect=RuntimeError("Index error"),
                                            ):
                                                # Ensure temp file doesn't exist for cleanup
                                                # (simulating already deleted)
                                                result = write_journal(data)

        assert result["success"] is False
        # Cleanup should not fail even if temp file doesn't exist
        assert "索引更新失败" in result["error"]


class TestWriteJournalAbstractUpdate:
    """Tests for abstract update error handling"""

    def test_abstract_update_error_continues_successfully(self, tmp_path):
        """Test that abstract update error is recorded but doesn't fail write"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        lock_path = tmp_path / ".cache" / "journals.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        with patch("tools.write_journal.core.JOURNALS_DIR", journals_dir):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
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
                                            side_effect=OSError(
                                                "Abstract update failed"
                                            ),
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
                                                        result = write_journal(data)

        # Abstract error should not prevent successful write
        assert result["success"] is True
        assert "monthly_abstract_error" in result
        assert "Abstract update failed" in result["monthly_abstract_error"]

    def test_abstract_update_runtime_error_handled(self, tmp_path):
        """Test that RuntimeError in abstract update is handled"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        lock_path = tmp_path / ".cache" / "journals.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        with patch("tools.write_journal.core.JOURNALS_DIR", journals_dir):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
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
                                            side_effect=RuntimeError(
                                                "Subprocess failed"
                                            ),
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
                                                        result = write_journal(data)

        assert result["success"] is True
        assert "Subprocess failed" in result["monthly_abstract_error"]


class TestWriteJournalSequenceRetry:
    """Tests for sequence retry logic when file exists"""

    def test_file_exists_triggers_retry(self, tmp_path):
        """Test that existing file triggers sequence retry"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        # Create existing file with sequence 1
        existing_file = month_dir / "life-index_2026-03-14_001.md"
        existing_file.write_text("existing content", encoding="utf-8")

        lock_path = tmp_path / ".cache" / "journals.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        sequence_calls = [1, 2]  # First call returns 1, second returns 2

        def mock_get_next_sequence(date_str):
            return sequence_calls.pop(0)

        with patch("tools.write_journal.core.JOURNALS_DIR", journals_dir):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence",
                        side_effect=mock_get_next_sequence,
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
                                                        result = write_journal(data)

        assert result["success"] is True
        # Should write to _002.md since _001.md exists
        assert "_002.md" in result["journal_path"]

    def test_file_exists_last_retry_uses_existing_sequence(self, tmp_path):
        """Test that last retry uses the sequence even if file exists"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        # Create existing file with sequence 1
        existing_file = month_dir / "life-index_2026-03-14_001.md"
        existing_file.write_text("existing content", encoding="utf-8")

        lock_path = tmp_path / ".cache" / "journals.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        # Always return 1 (simulating race condition where file keeps existing)
        with patch("tools.write_journal.core.JOURNALS_DIR", journals_dir):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
            ):
                with patch(
                    "tools.write_journal.core.get_year_month", return_value=(2026, 3)
                ):
                    with patch(
                        "tools.write_journal.core.get_next_sequence",
                        return_value=1,  # Always return 1
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
                                                        result = write_journal(data)

        # On last retry, it should still succeed (overwrites existing)
        assert result["success"] is True


class TestWriteJournalProjectIndexUpdate:
    """Tests for project index update paths"""

    def test_project_index_returns_path(self, tmp_path):
        """Test that project index update returning a path is recorded"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "project": "Life-Index",
        }

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        lock_path = tmp_path / ".cache" / "journals.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        by_topic_dir = tmp_path / "by-topic"
        project_index = by_topic_dir / "项目_Life-Index.md"

        with patch("tools.write_journal.core.JOURNALS_DIR", journals_dir):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
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
                                                    return_value=project_index,
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        result = write_journal(data)

        assert result["success"] is True
        assert len(result["updated_indices"]) == 1
        assert "项目_Life-Index.md" in result["updated_indices"][0]

    def test_project_index_returns_none_not_recorded(self, tmp_path):
        """Test that project index update returning None is not recorded"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
            "project": "NonExistent",
        }

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir(parents=True)
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        lock_path = tmp_path / ".cache" / "journals.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        with patch("tools.write_journal.core.JOURNALS_DIR", journals_dir):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
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
                                                    return_value=None,  # Returns None
                                                ):
                                                    with patch(
                                                        "tools.write_journal.core.update_tag_indices",
                                                        return_value=[],
                                                    ):
                                                        result = write_journal(data)

        assert result["success"] is True
        # Project index returning None should not add to updated_indices
        assert len(result["updated_indices"]) == 0


class TestWriteJournalLockTimeoutDetails:
    """Tests for detailed lock timeout handling"""

    def test_lock_timeout_includes_details(self, tmp_path):
        """Test that lock timeout error includes detailed info"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        from tools.lib.file_lock import LockTimeoutError

        lock_path = tmp_path / "test.lock"
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(
            side_effect=LockTimeoutError(str(lock_path), 30.0)
        )
        mock_lock.__exit__ = MagicMock(return_value=None)

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
            ):
                with patch("tools.write_journal.core.FileLock", return_value=mock_lock):
                    with patch(
                        "tools.write_journal.core.normalize_location",
                        return_value="Chongqing, China",
                    ):
                        result = write_journal(data)

        assert result["success"] is False
        assert result["error"] is not None
        # error is a dict with code, message, details, recovery_strategy
        assert result["error"]["code"] == "E0005"  # LOCK_TIMEOUT
        assert "lock" in result["error"]["message"].lower()

    def test_lock_timeout_has_error_code(self, tmp_path):
        """Test that lock timeout returns proper error code"""
        data = {
            "date": "2026-03-14",
            "content": "Test content",
        }

        from tools.lib.file_lock import LockTimeoutError

        lock_path = tmp_path / "test.lock"
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(
            side_effect=LockTimeoutError(str(lock_path), 30.0)
        )
        mock_lock.__exit__ = MagicMock(return_value=None)

        with patch("tools.write_journal.core.JOURNALS_DIR", tmp_path / "Journals"):
            with patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
            ):
                with patch("tools.write_journal.core.FileLock", return_value=mock_lock):
                    with patch(
                        "tools.write_journal.core.normalize_location",
                        return_value="Chongqing, China",
                    ):
                        result = write_journal(data)

        # Check for error code in nested error dict
        assert result["error"]["code"] == "E0005"  # LOCK_TIMEOUT code
        assert result["error"]["recovery_strategy"] == "retry"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
