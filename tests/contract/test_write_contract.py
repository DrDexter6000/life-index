#!/usr/bin/env python3
"""
Contract tests: write_journal response shape

Verifies that write_journal() output conforms to the contract
documented in docs/API.md and SKILL.md:
1. Success response contains all documented fields
2. Field types match documentation
3. Status field values are from documented enum sets
4. needs_confirmation tracks location_auto_filled
5. Error cases return structured error responses
6. Validation rejects missing required fields
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.write_journal.core import write_journal


# ── Documented field contracts ──

REQUIRED_SUCCESS_FIELDS = {
    "success",
    "journal_path",
    "updated_indices",
    "index_status",
    "side_effects_status",
    "attachments_processed",
    "location_used",
    "location_auto_filled",
    "weather_used",
    "weather_auto_filled",
    "needs_confirmation",
    "confirmation_message",
    "metrics",
}

VALID_INDEX_STATUS = {"complete", "degraded", "not_started"}
VALID_SIDE_EFFECTS_STATUS = {"complete", "degraded", "not_started"}


@pytest.fixture(autouse=True)
def mock_vector_update():
    """Isolate from vector index/model loading."""
    with patch("tools.write_journal.core.update_vector_index", return_value=False):
        yield


@pytest.fixture
def writable_env(tmp_path):
    """Set up a writable environment with all required directories."""
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


def _run_write(data: dict, writable_env: dict, dry_run: bool = False) -> dict:
    """Helper: run write_journal with all necessary mocks."""
    with patch("tools.write_journal.core.JOURNALS_DIR", writable_env["journals_dir"]):
        with patch(
            "tools.write_journal.core.get_journals_lock_path",
            return_value=writable_env["lock_path"],
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
                                    with patch(
                                        "tools.write_journal.core.update_monthly_abstract",
                                        return_value="abstract.md",
                                    ):
                                        return write_journal(data, dry_run=dry_run)


class TestWriteJournalResponseShape:
    """write_journal() response contains all documented fields with correct types."""

    def test_success_response_has_all_required_fields(self, writable_env):
        """Successful write returns all fields documented in API.md."""
        data = {
            "date": "2026-03-14",
            "title": "Test Journal",
            "content": "Test content.",
            "topic": ["work"],
            "abstract": "Test abstract.",
            "mood": ["专注"],
            "tags": ["test"],
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        for field in REQUIRED_SUCCESS_FIELDS:
            assert field in result, f"Missing required field: {field}"

    def test_success_field_types(self, writable_env):
        """Field types match API.md documentation."""
        data = {
            "date": "2026-03-14",
            "title": "Type Check",
            "content": "Content for type checking.",
            "topic": ["work"],
            "abstract": "Abstract.",
            "mood": [],
            "tags": [],
        }
        result = _run_write(data, writable_env)

        assert isinstance(result["success"], bool)
        assert isinstance(result["journal_path"], str)
        assert isinstance(result["updated_indices"], list)
        assert isinstance(result["index_status"], str)
        assert isinstance(result["side_effects_status"], str)
        assert isinstance(result["attachments_processed"], list)
        assert isinstance(result["location_used"], str)
        assert isinstance(result["location_auto_filled"], bool)
        assert isinstance(result["weather_used"], str)
        assert isinstance(result["weather_auto_filled"], bool)
        assert isinstance(result["needs_confirmation"], bool)
        assert isinstance(result["confirmation_message"], str)
        assert isinstance(result["metrics"], dict)


class TestWriteJournalStatusEnums:
    """Status fields use only documented enum values."""

    def test_index_status_is_valid_enum(self, writable_env):
        """index_status is one of: complete, degraded, not_started."""
        data = {
            "date": "2026-03-14",
            "title": "Enum Test",
            "content": "Content.",
            "topic": ["work"],
            "abstract": "Abstract.",
            "mood": [],
            "tags": [],
        }
        result = _run_write(data, writable_env)
        assert result["index_status"] in VALID_INDEX_STATUS

    def test_side_effects_status_is_valid_enum(self, writable_env):
        """side_effects_status is one of: complete, degraded, not_started."""
        data = {
            "date": "2026-03-14",
            "title": "Enum Test",
            "content": "Content.",
            "topic": ["work"],
            "abstract": "Abstract.",
            "mood": [],
            "tags": [],
        }
        result = _run_write(data, writable_env)
        assert result["side_effects_status"] in VALID_SIDE_EFFECTS_STATUS

    def test_failure_sets_not_started_statuses(self, writable_env):
        """On failure, index_status and side_effects_status are 'not_started'."""
        data = {}  # Missing required 'date' field
        result = _run_write(data, writable_env)

        assert result["success"] is False
        assert result["index_status"] == "not_started"
        assert result["side_effects_status"] == "not_started"


class TestWriteJournalConfirmationContract:
    """needs_confirmation semantics match SKILL.md documentation."""

    def test_auto_filled_location_triggers_confirmation(self, writable_env):
        """When location is auto-filled, needs_confirmation must be True."""
        data = {
            "date": "2026-03-14",
            "title": "Auto Location",
            "content": "No location mentioned.",
            "topic": ["life"],
            "abstract": "No location.",
            "mood": [],
            "tags": [],
            # Note: no 'location' field → auto-fill triggers
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["location_auto_filled"] is True
        assert result["needs_confirmation"] is True
        assert len(result["confirmation_message"]) > 0

    def test_explicit_location_no_confirmation(self, writable_env):
        """When location is explicitly provided, needs_confirmation is False."""
        data = {
            "date": "2026-03-14",
            "title": "Explicit Location",
            "content": "Content with explicit location.",
            "location": "Beijing, China",
            "topic": ["work"],
            "abstract": "Has location.",
            "mood": [],
            "tags": [],
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["location_auto_filled"] is False
        assert result["needs_confirmation"] is False

    def test_needs_confirmation_equals_location_auto_filled(self, writable_env):
        """Contract: needs_confirmation == location_auto_filled."""
        for loc_value in [None, "", "Beijing, China"]:
            data = {
                "date": "2026-03-14",
                "title": "Confirmation Tracking",
                "content": "Content.",
                "topic": ["work"],
                "abstract": "Abstract.",
                "mood": [],
                "tags": [],
            }
            if loc_value:
                data["location"] = loc_value

            result = _run_write(data, writable_env)
            if result["success"]:
                assert result["needs_confirmation"] == result["location_auto_filled"], (
                    f"needs_confirmation ({result['needs_confirmation']}) != "
                    f"location_auto_filled ({result['location_auto_filled']}) "
                    f"for location={loc_value!r}"
                )


class TestWriteJournalValidation:
    """Input validation matches API.md error codes."""

    def test_missing_date_returns_failure(self, writable_env):
        """Missing 'date' field results in success=False."""
        data = {
            "title": "No Date",
            "content": "Missing date field.",
        }
        result = _run_write(data, writable_env)
        assert result["success"] is False

    def test_journal_path_is_string_on_success(self, writable_env):
        """On success, journal_path is a non-empty string."""
        data = {
            "date": "2026-03-14",
            "title": "Path Test",
            "content": "Content.",
            "topic": ["work"],
            "abstract": "Abstract.",
            "mood": [],
            "tags": [],
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert isinstance(result["journal_path"], str)
        assert len(result["journal_path"]) > 0

    def test_journal_path_is_none_on_failure(self, writable_env):
        """On failure, journal_path remains None."""
        data = {}  # Missing everything
        result = _run_write(data, writable_env)

        assert result["success"] is False
        assert result["journal_path"] is None


class TestWriteJournalDryRun:
    """Dry-run mode returns success without writing files."""

    def test_dry_run_returns_success_with_preview(self, writable_env):
        """Dry-run returns success=True and content_preview."""
        data = {
            "date": "2026-03-14",
            "title": "Dry Run Test",
            "content": "Dry run content.",
            "topic": ["work"],
            "abstract": "Dry run abstract.",
            "mood": [],
            "tags": [],
        }
        result = _run_write(data, writable_env, dry_run=True)

        assert result["success"] is True
        assert "content_preview" in result
        assert isinstance(result["content_preview"], str)
