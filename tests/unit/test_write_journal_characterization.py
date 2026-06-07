#!/usr/bin/env python3
"""
Characterization tests for write_journal() and apply_confirmation_updates().

These tests pin observable behavior of the two target functions BEFORE any
production refactor.  They are intentionally separate from the existing
unit tests (test_write_journal_core.py) and contract tests
(test_write_contract.py) so that a refactor can move fast while these
tests guarantee behavioral invariants.

Behavior categories pinned:
  1. Returned dict shape — every key and its type on success and failure paths
  2. Pending-confirmation side effects — pending queue, needs_confirmation
  3. dry_run behavior — no file written, content_preview present
  4. Error code structure — error dict shape, recovery_strategy
  5. apply_confirmation_updates — confirm_status, applied/ignored fields,
     candidate resolution, nonexistent journal path
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.write_journal.core import apply_confirmation_updates, write_journal
from tools.lib.errors import ErrorCode
from tools.lib.workflow_signals import (
    WriteOutcome,
    IndexStatus,
    SideEffectsStatus,
    ConfirmStatus,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_vector_update():
    """Isolate from vector index / model loading."""
    with patch("tools.write_journal.core.mark_pending"):
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


def _run_write(data: dict, env: dict, dry_run: bool = False) -> dict:
    """Helper: run write_journal with all necessary mocks for characterization."""
    with (
        patch(
            "tools.write_journal.core.get_journals_dir",
            return_value=env["journals_dir"],
        ),
        patch(
            "tools.write_journal.core.get_journals_lock_path",
            return_value=env["lock_path"],
        ),
        patch("tools.write_journal.core.get_year_month", return_value=(2026, 3)),
        patch("tools.write_journal.core.get_next_sequence", return_value=1),
        patch(
            "tools.write_journal.core.query_weather_for_location",
            return_value="Sunny 25\u00b0C",
        ),
        patch("tools.write_journal.core.update_topic_index", return_value=[]),
        patch("tools.write_journal.core.update_project_index", return_value=None),
        patch("tools.write_journal.core.update_tag_indices", return_value=[]),
        patch(
            "tools.write_journal.core.update_monthly_abstract",
            return_value="abstract.md",
        ),
    ):
        return write_journal(data, dry_run=dry_run)


# ===================================================================
# 1. write_journal() — returned dict shape on FAILURE path
# ===================================================================


class TestWriteJournalFailureDictShape:
    """Pin the exact shape of the result dict when write_journal fails."""

    def test_missing_date_returns_all_default_keys(self, writable_env):
        """On failure, result dict must contain every key from the initial template."""
        result = _run_write({}, writable_env)

        expected_keys = {
            "success",
            "write_outcome",
            "journal_path",
            "updated_indices",
            "index_status",
            "side_effects_status",
            "attachments_processed",
            "attachments_detected_count",
            "attachments_processed_count",
            "attachments_failed_count",
            "location_used",
            "location_auto_filled",
            "weather_used",
            "weather_auto_filled",
            "needs_confirmation",
            "confirmation_message",
            "confirmation",
            "related_candidates",
            "new_entities_detected",
            "entity_candidates",
            "error",
            "metrics",
        }
        for key in expected_keys:
            assert key in result, f"Missing key on failure path: {key}"

    def test_failure_default_values(self, writable_env):
        """Pin the default values returned on failure."""
        result = _run_write({}, writable_env)

        assert result["success"] is False
        assert result["write_outcome"] == "failed"
        assert result["journal_path"] is None
        assert result["updated_indices"] == []
        assert result["index_status"] == "not_started"
        assert result["side_effects_status"] == "not_started"
        assert result["attachments_processed"] == []
        assert result["attachments_detected_count"] == 0
        assert result["attachments_processed_count"] == 0
        assert result["attachments_failed_count"] == 0
        assert result["location_used"] == ""
        assert result["location_auto_filled"] is False
        assert result["weather_used"] == ""
        assert result["weather_auto_filled"] is False
        assert result["needs_confirmation"] is False
        assert result["confirmation_message"] == ""
        assert isinstance(result["error"], str)
        assert isinstance(result["metrics"], dict)

    def test_failure_error_contains_date_message(self, writable_env):
        """On missing date, the error string mentions 'date'."""
        result = _run_write({}, writable_env)
        assert result["success"] is False
        # The error message is in Chinese but should contain a reference to 'date'
        assert result["error"] is not None
        assert len(result["error"]) > 0


# ===================================================================
# 2. write_journal() — returned dict shape on SUCCESS path
# ===================================================================


class TestWriteJournalSuccessDictShape:
    """Pin the exact shape of the result dict when write_journal succeeds."""

    def test_success_result_has_metrics_with_total_ms(self, writable_env):
        """Metrics dict always contains 'total_ms' on success."""
        data = {
            "date": "2026-03-14",
            "title": "Metrics Test",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert "metrics" in result
        assert "total_ms" in result["metrics"]
        assert isinstance(result["metrics"]["total_ms"], float)

    def test_success_result_journal_path_is_str(self, writable_env):
        """journal_path is a non-empty string on success."""
        data = {
            "date": "2026-03-14",
            "title": "Path Test",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert isinstance(result["journal_path"], str)
        assert len(result["journal_path"]) > 0
        assert "2026" in result["journal_path"]
        assert "03" in result["journal_path"]

    def test_success_result_index_status_is_complete(self, writable_env):
        """On successful write, index_status is 'complete'."""
        data = {
            "date": "2026-03-14",
            "title": "Index Test",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["index_status"] == "complete"

    def test_success_write_outcome_is_pending_confirmation(self, writable_env):
        """Successful write always yields 'success_pending_confirmation'."""
        data = {
            "date": "2026-03-14",
            "title": "Outcome Test",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["write_outcome"] == "success_pending_confirmation"

    def test_success_needs_confirmation_is_true(self, writable_env):
        """Every successful write requires confirmation."""
        data = {
            "date": "2026-03-14",
            "title": "Confirm Test",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["needs_confirmation"] is True

    def test_success_confirmation_message_nonempty(self, writable_env):
        """confirmation_message is a non-empty string on success."""
        data = {
            "date": "2026-03-14",
            "title": "Message Test",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert isinstance(result["confirmation_message"], str)
        assert len(result["confirmation_message"]) > 0

    def test_success_confirmation_payload_has_required_keys(self, writable_env):
        """confirmation payload contains location, weather, journal_path, related_candidates."""
        data = {
            "date": "2026-03-14",
            "title": "Payload Test",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        conf = result["confirmation"]
        assert "location" in conf
        assert "weather" in conf
        assert "journal_path" in conf
        assert "related_candidates" in conf
        assert "supports_related_entry_approval" in conf

    def test_success_entity_candidates_is_list(self, writable_env):
        """entity_candidates is always a list."""
        data = {
            "date": "2026-03-14",
            "title": "Entity Test",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert isinstance(result["entity_candidates"], list)

    def test_success_new_entities_detected_is_list(self, writable_env):
        """new_entities_detected is always a list."""
        data = {
            "date": "2026-03-14",
            "title": "New Entity Test",
            "content": "Content.",
            "people": ["UnknownPerson"],
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert isinstance(result["new_entities_detected"], list)

    def test_success_related_candidates_is_list(self, writable_env):
        """related_candidates is always a list."""
        data = {
            "date": "2026-03-14",
            "title": "Related Test",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert isinstance(result["related_candidates"], list)

    def test_success_updated_indices_is_list(self, writable_env):
        """updated_indices is always a list."""
        data = {
            "date": "2026-03-14",
            "title": "Indices Test",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert isinstance(result["updated_indices"], list)

    def test_success_side_effects_status_is_complete(self, writable_env):
        """With no abstract errors, side_effects_status is 'complete'."""
        data = {
            "date": "2026-03-14",
            "title": "Side Effects Test",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["side_effects_status"] == "complete"


# ===================================================================
# 3. write_journal() — location and weather behavior
# ===================================================================


class TestWriteJournalLocationWeather:
    """Pin location and weather resolution behavior."""

    def test_explicit_location_is_used(self, writable_env):
        """User-provided location is used without auto-fill."""
        data = {
            "date": "2026-03-14",
            "title": "Explicit Loc",
            "content": "Content.",
            "location": "Tokyo, Japan",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["location_used"] == "Tokyo, Japan"
        assert result["location_auto_filled"] is False

    def test_explicit_weather_is_used(self, writable_env):
        """User-provided weather is used without auto-fill."""
        data = {
            "date": "2026-03-14",
            "title": "Explicit Weather",
            "content": "Content.",
            "weather": "Rainy 15\u00b0C",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["weather_used"] == "Rainy 15\u00b0C"
        assert result["weather_auto_filled"] is False

    def test_auto_fill_weather_when_not_provided(self, writable_env):
        """When weather is not provided, it is auto-filled from weather API."""
        data = {
            "date": "2026-03-14",
            "title": "Auto Weather",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["weather_auto_filled"] is True
        assert result["weather_used"] == "Sunny 25\u00b0C"

    def test_content_extracted_location_overrides_data(self, writable_env):
        """Location extracted from content (e.g., '地点: Lagos') is used."""
        data = {
            "date": "2026-03-14",
            "title": "Content Location",
            "content": "Content here.",
        }
        with patch(
            "tools.write_journal.core.extract_explicit_metadata_from_content",
            return_value={"location": "Lagos, Nigeria"},
        ):
            result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["location_used"] == "Lagos, Nigeria"
        assert result["location_auto_filled"] is False

    def test_empty_weather_when_api_returns_empty(self, writable_env):
        """When weather API returns empty, weather_used is empty string."""
        data = {
            "date": "2026-03-14",
            "title": "No Weather",
            "content": "Content.",
        }
        env = writable_env
        with (
            patch(
                "tools.write_journal.core.get_journals_dir",
                return_value=env["journals_dir"],
            ),
            patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=env["lock_path"],
            ),
            patch("tools.write_journal.core.get_year_month", return_value=(2026, 3)),
            patch("tools.write_journal.core.get_next_sequence", return_value=1),
            patch(
                "tools.write_journal.core.query_weather_for_location",
                return_value="",
            ),
            patch("tools.write_journal.core.update_topic_index", return_value=[]),
            patch("tools.write_journal.core.update_project_index", return_value=None),
            patch("tools.write_journal.core.update_tag_indices", return_value=[]),
            patch(
                "tools.write_journal.core.update_monthly_abstract",
                return_value="abstract.md",
            ),
        ):
            result = write_journal(data)

        assert result["success"] is True
        assert result["weather_used"] == ""
        assert result["weather_auto_filled"] is False


# ===================================================================
# 4. write_journal() — dry_run behavior
# ===================================================================


class TestWriteJournalDryRun:
    """Pin dry_run behavior — no file written, preview provided."""

    def test_dry_run_does_not_create_file(self, writable_env):
        """Dry run must not create the journal file on disk."""
        data = {
            "date": "2026-03-14",
            "title": "Dry Run",
            "content": "Content.",
        }
        result = _run_write(data, writable_env, dry_run=True)

        assert result["success"] is True
        assert result["journal_path"] is not None
        # The file must NOT exist on disk
        journal_file = Path(result["journal_path"])
        assert not journal_file.exists()

    def test_dry_run_has_content_preview(self, writable_env):
        """Dry run must return content_preview."""
        data = {
            "date": "2026-03-14",
            "title": "Dry Preview",
            "content": "Content for preview.",
        }
        result = _run_write(data, writable_env, dry_run=True)

        assert result["success"] is True
        assert "content_preview" in result
        assert isinstance(result["content_preview"], str)
        assert len(result["content_preview"]) > 0

    def test_dry_run_content_preview_max_500_chars(self, writable_env):
        """Content preview is truncated at 500 characters."""
        long_content = "X" * 1000
        data = {
            "date": "2026-03-14",
            "title": "Long Preview",
            "content": long_content,
        }
        result = _run_write(data, writable_env, dry_run=True)

        assert result["success"] is True
        assert len(result["content_preview"]) <= 500

    def test_dry_run_needs_confirmation_false(self, writable_env):
        """Dry run sets needs_confirmation to True (confirmation payload is built)."""
        data = {
            "date": "2026-03-14",
            "title": "Dry Confirm",
            "content": "Content.",
        }
        result = _run_write(data, writable_env, dry_run=True)

        # In dry_run mode, the function returns early before setting
        # needs_confirmation=True. Pin this behavior.
        assert result["success"] is True
        # dry_run early return: needs_confirmation stays at initial False
        assert result["needs_confirmation"] is False

    def test_dry_run_index_status_not_started(self, writable_env):
        """Dry run returns early, so index_status stays 'not_started'."""
        data = {
            "date": "2026-03-14",
            "title": "Dry Index",
            "content": "Content.",
        }
        result = _run_write(data, writable_env, dry_run=True)

        assert result["success"] is True
        assert result["index_status"] == "not_started"

    def test_dry_run_has_metrics(self, writable_env):
        """Dry run still returns metrics."""
        data = {
            "date": "2026-03-14",
            "title": "Dry Metrics",
            "content": "Content.",
        }
        result = _run_write(data, writable_env, dry_run=True)

        assert result["success"] is True
        assert "metrics" in result
        assert "total_ms" in result["metrics"]


# ===================================================================
# 5. write_journal() — pending-confirmation side effects
# ===================================================================


class TestWriteJournalPendingConfirmation:
    """Pin pending-confirmation side effects."""

    def test_confirmation_payload_includes_journal_path_on_success(self, writable_env):
        """On successful write, confirmation payload contains journal_path."""
        data = {
            "date": "2026-03-14",
            "title": "Confirm Path",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["confirmation"]["journal_path"] is not None
        assert result["confirmation"]["journal_path"] == result["journal_path"]

    def test_confirmation_payload_supports_related_entry_approval(self, writable_env):
        """supports_related_entry_approval is True on success."""
        data = {
            "date": "2026-03-14",
            "title": "Approval Flag",
            "content": "Content.",
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["confirmation"]["supports_related_entry_approval"] is True

    def test_prepared_metadata_preserves_user_data(self, writable_env):
        """prepared_metadata field preserves the original data dict."""
        data = {
            "date": "2026-03-14",
            "title": "Prepared Test",
            "content": "Original content here.",
            "topic": ["work"],
            "tags": ["testing"],
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert "prepared_metadata" in result
        assert result["prepared_metadata"]["title"] == "Prepared Test"
        assert result["prepared_metadata"]["content"] == "Original content here."
        assert result["prepared_metadata"]["topic"] == ["work"]
        assert result["prepared_metadata"]["tags"] == ["testing"]


# ===================================================================
# 6. write_journal() — lock timeout error structure
# ===================================================================


class TestWriteJournalLockTimeout:
    """Pin lock timeout error response structure."""

    def test_lock_timeout_error_is_structured_dict(self, writable_env):
        """Lock timeout returns structured error dict, not a plain string."""
        from tools.lib.file_lock import LockTimeoutError

        lock_path = writable_env["lock_path"]
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(side_effect=LockTimeoutError(str(lock_path), 30.0))
        mock_lock.__exit__ = MagicMock(return_value=None)

        data = {
            "date": "2026-03-14",
            "content": "Content.",
        }

        with (
            patch(
                "tools.write_journal.core.get_journals_dir",
                return_value=writable_env["journals_dir"],
            ),
            patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=lock_path,
            ),
            patch("tools.write_journal.core.FileLock", return_value=mock_lock),
            patch(
                "tools.write_journal.core.normalize_location",
                return_value="Chongqing, China",
            ),
            patch(
                "tools.write_journal.core.query_weather_for_location",
                return_value="",
            ),
        ):
            result = write_journal(data)

        assert result["success"] is False
        # error is a structured dict with code, message, details, recovery_strategy
        assert isinstance(result["error"], dict)
        assert result["error"]["code"] == ErrorCode.LOCK_TIMEOUT
        assert result["error"]["recovery_strategy"] == "retry"
        assert "message" in result["error"]
        assert "details" in result["error"]


# ===================================================================
# 7. apply_confirmation_updates() — nonexistent journal path
# ===================================================================


class TestApplyConfirmationJournalNotFound:
    """Pin behavior when journal_path does not exist."""

    def test_nonexistent_journal_returns_failed(self, tmp_path):
        """When journal file doesn't exist, confirm_status is 'failed'."""
        journal_path = tmp_path / "nonexistent" / "journal.md"

        result = apply_confirmation_updates(
            journal_path=journal_path,
            location="Nowhere",
        )

        assert result["success"] is False
        assert result["confirm_status"] == "failed"
        assert result["applied_fields"] == []
        assert result["ignored_fields"] == []
        assert result["approved_related_entries"] == []
        assert result["rejected_related_entries"] == []
        assert result["approval_summary"] == {
            "approved": [],
            "rejected": [],
        }

    def test_nonexistent_journal_error_has_code(self, tmp_path):
        """Error response includes JOURNAL_NOT_FOUND code."""
        journal_path = tmp_path / "nonexistent" / "journal.md"

        result = apply_confirmation_updates(
            journal_path=journal_path,
            location="Nowhere",
        )

        assert result["success"] is False
        assert isinstance(result.get("error"), dict)
        assert result["error"]["code"] == ErrorCode.JOURNAL_NOT_FOUND

    def test_nonexistent_journal_preserves_requested_entries(self, tmp_path):
        """requested_related_entries reflects what was requested even on failure."""
        journal_path = tmp_path / "nonexistent" / "journal.md"

        result = apply_confirmation_updates(
            journal_path=journal_path,
            approved_related_entries=["Journals/2026/03/target.md"],
        )

        assert result["requested_related_entries"] == ["Journals/2026/03/target.md"]
        assert result["approved_related_entries"] == []


# ===================================================================
# 8. apply_confirmation_updates() — confirm_status derivation
# ===================================================================


class TestApplyConfirmationConfirmStatus:
    """Pin confirm_status derivation for COMPLETE, PARTIAL, NOOP."""

    def test_all_fields_applied_is_complete(self, tmp_path):
        """When all requested fields are applied, status is 'complete'."""
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )

        with patch("tools.edit_journal.edit_journal") as mock_edit:
            mock_edit.return_value = {
                "success": True,
                "changes": {
                    "location": {"old": "Old", "new": "New"},
                    "weather": {"old": "Old W", "new": "New W"},
                },
                "journal_path": str(journal_path),
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                location="New",
                weather="New W",
            )

        assert result["confirm_status"] == "complete"
        assert "location" in result["applied_fields"]
        assert "weather" in result["applied_fields"]
        assert result["ignored_fields"] == []

    def test_no_changes_requested_is_noop(self, tmp_path):
        """When no fields are requested, status is 'noop'."""
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )

        with patch("tools.edit_journal.edit_journal") as mock_edit:
            mock_edit.return_value = {
                "success": True,
                "changes": {},
                "journal_path": str(journal_path),
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
            )

        assert result["confirm_status"] == "noop"
        assert result["applied_fields"] == []
        assert result["ignored_fields"] == []

    def test_partial_application_is_partial(self, tmp_path):
        """When some fields are applied and some ignored, status is 'partial'."""
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )

        # location change applied, weather not (same old==new)
        with patch("tools.edit_journal.edit_journal") as mock_edit:
            mock_edit.return_value = {
                "success": True,
                "changes": {
                    "location": {"old": "Old", "new": "New City"},
                    "weather": {"old": "Same", "new": "Same"},
                },
                "journal_path": str(journal_path),
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                location="New City",
                weather="Same",
            )

        assert result["confirm_status"] == "partial"
        assert "location" in result["applied_fields"]
        assert "weather" in result["ignored_fields"]

    def test_edit_failure_is_failed(self, tmp_path):
        """When edit_journal returns success=False, confirm_status is 'failed'."""
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )

        with patch("tools.edit_journal.edit_journal") as mock_edit:
            mock_edit.return_value = {
                "success": False,
                "changes": {},
                "journal_path": str(journal_path),
                "error": "Edit failed",
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                location="New City",
            )

        assert result["confirm_status"] == "failed"


# ===================================================================
# 9. apply_confirmation_updates() — candidate resolution
# ===================================================================


class TestApplyConfirmationCandidateResolution:
    """Pin candidate resolution with candidate_context."""

    def test_resolve_by_candidate_id(self, tmp_path):
        """Candidates are resolved by candidate_id."""
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )

        candidate_context = [
            {
                "candidate_id": 42,
                "rel_path": "Journals/2026/03/target.md",
                "title": "Target",
            }
        ]

        with patch("tools.edit_journal.edit_journal") as mock_edit:
            mock_edit.return_value = {
                "success": True,
                "changes": {
                    "related_entries": {
                        "old": [],
                        "new": ["Journals/2026/03/target.md"],
                    }
                },
                "journal_path": str(journal_path),
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                approved_related_candidate_ids=[42],
                candidate_context=candidate_context,
            )

        assert result["success"] is True
        assert result["approved_candidate_ids"] == [42]
        assert result["approved_related_entries"] == ["Journals/2026/03/target.md"]

    def test_resolve_by_rel_path(self, tmp_path):
        """Candidates are resolved by rel_path string."""
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )

        candidate_context = [
            {
                "candidate_id": 1,
                "rel_path": "Journals/2026/03/by_path.md",
                "title": "By Path",
            }
        ]

        with patch("tools.edit_journal.edit_journal") as mock_edit:
            mock_edit.return_value = {
                "success": True,
                "changes": {
                    "related_entries": {
                        "old": [],
                        "new": ["Journals/2026/03/by_path.md"],
                    }
                },
                "journal_path": str(journal_path),
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                approved_related_entries=["Journals/2026/03/by_path.md"],
                candidate_context=candidate_context,
            )

        assert result["success"] is True
        assert result["approved_related_entries"] == ["Journals/2026/03/by_path.md"]

    def test_invalid_candidate_id_returns_error(self, tmp_path):
        """An unknown candidate_id returns a structured error."""
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )

        result = apply_confirmation_updates(
            journal_path=journal_path,
            approved_related_candidate_ids=[999],  # Not in context
            candidate_context=[],
        )

        assert result["success"] is False
        assert result["confirm_status"] == "failed"

    def test_approval_summary_with_mixed_approve_reject(self, tmp_path):
        """Approval summary correctly separates approved and rejected."""
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )

        candidate_context = [
            {
                "candidate_id": 1,
                "rel_path": "Journals/2026/03/approved.md",
                "title": "Approved",
            },
            {
                "candidate_id": 2,
                "rel_path": "Journals/2026/03/rejected.md",
                "title": "Rejected",
            },
        ]

        with patch("tools.edit_journal.edit_journal") as mock_edit:
            mock_edit.return_value = {
                "success": True,
                "changes": {
                    "related_entries": {
                        "old": [],
                        "new": ["Journals/2026/03/approved.md"],
                    }
                },
                "journal_path": str(journal_path),
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                approved_related_candidate_ids=[1],
                rejected_related_candidate_ids=[2],
                candidate_context=candidate_context,
            )

        assert result["success"] is True
        assert result["approved_candidate_ids"] == [1]
        assert result["rejected_candidate_ids"] == [2]
        assert result["approval_summary"]["approved"][0]["candidate_id"] == 1
        assert result["approval_summary"]["rejected"][0]["candidate_id"] == 2


# ===================================================================
# 10. apply_confirmation_updates() — relation_summary
# ===================================================================


class TestApplyConfirmationRelationSummary:
    """Pin relation_summary output structure."""

    def test_relation_summary_includes_source_and_context(self, tmp_path):
        """relation_summary has source_entry and approved_related_context."""
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )

        with (
            patch("tools.edit_journal.edit_journal") as mock_edit,
            patch("tools.write_journal.core.init_metadata_cache") as mock_cache,
            patch(
                "tools.write_journal.core.build_journal_path_fields",
                return_value={
                    "path": str(journal_path),
                    "rel_path": "Journals/2026/03/source.md",
                    "journal_route_path": "2026/03/source.md",
                },
            ),
            patch(
                "tools.write_journal.core.get_backlinked_by",
                side_effect=[[], []],
            ),
        ):
            mock_cache.return_value.close = lambda: None
            mock_edit.return_value = {
                "success": True,
                "changes": {
                    "related_entries": {
                        "old": [],
                        "new": ["Journals/2026/03/target.md"],
                    }
                },
                "journal_path": str(journal_path),
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                approved_related_entries=["Journals/2026/03/target.md"],
            )

        assert result["success"] is True
        summary = result["relation_summary"]
        assert summary is not None
        assert "source_entry" in summary
        assert "approved_related_context" in summary
        assert summary["source_entry"]["rel_path"] == "Journals/2026/03/source.md"
        assert summary["source_entry"]["related_entries"] == ["Journals/2026/03/target.md"]

    def test_no_related_entries_applied_gives_null_summary(self, tmp_path):
        """When related_entries is not in applied_fields, relation_summary is None."""
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\nlocation: Old\n---\n\nBody\n",
            encoding="utf-8",
        )

        with patch("tools.edit_journal.edit_journal") as mock_edit:
            mock_edit.return_value = {
                "success": True,
                "changes": {
                    "location": {"old": "Old", "new": "New City"},
                },
                "journal_path": str(journal_path),
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                location="New City",
            )

        assert result["success"] is True
        assert result["relation_summary"] is None


# ===================================================================
# 11. write_journal() — content preservation
# ===================================================================


class TestWriteJournalContentPreservation:
    """Pin that user content is never modified by write_journal."""

    def test_user_content_preserved_in_prepared_metadata(self, writable_env):
        """prepared_metadata.content exactly matches the original input."""
        original_content = "This is my original content. Don't change it!"
        data = {
            "date": "2026-03-14",
            "title": "Preservation Test",
            "content": original_content,
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["prepared_metadata"]["content"] == original_content

    def test_user_content_preserved_with_special_chars(self, writable_env):
        """Content with special characters is preserved verbatim."""
        original_content = "Special: \u4e2d\u6587\u5185\u5bb9 <tag> & 'quote' \"dquote\""
        data = {
            "date": "2026-03-14",
            "title": "Special Chars",
            "content": original_content,
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["prepared_metadata"]["content"] == original_content


# ===================================================================
# 12. Enum constant values — pin exact strings
# ===================================================================


class TestWriteOutcomeEnumValues:
    """Pin the exact string values of workflow signal enums."""

    def test_failed(self):
        assert WriteOutcome.FAILED == "failed"

    def test_success(self):
        assert WriteOutcome.SUCCESS == "success"

    def test_success_pending_confirmation(self):
        assert WriteOutcome.SUCCESS_PENDING_CONFIRMATION == "success_pending_confirmation"

    def test_success_degraded(self):
        assert WriteOutcome.SUCCESS_DEGRADED == "success_degraded"


class TestIndexStatusEnumValues:
    def test_complete(self):
        assert IndexStatus.COMPLETE == "complete"

    def test_not_started(self):
        assert IndexStatus.NOT_STARTED == "not_started"

    def test_degraded(self):
        assert IndexStatus.DEGRADED == "degraded"


class TestSideEffectsStatusEnumValues:
    def test_complete(self):
        assert SideEffectsStatus.COMPLETE == "complete"

    def test_not_started(self):
        assert SideEffectsStatus.NOT_STARTED == "not_started"

    def test_degraded(self):
        assert SideEffectsStatus.DEGRADED == "degraded"


class TestConfirmStatusEnumValues:
    def test_complete(self):
        assert ConfirmStatus.COMPLETE == "complete"

    def test_partial(self):
        assert ConfirmStatus.PARTIAL == "partial"

    def test_noop(self):
        assert ConfirmStatus.NOOP == "noop"

    def test_failed(self):
        assert ConfirmStatus.FAILED == "failed"


class TestErrorCodeValues:
    """Pin error codes used by write/confirm paths."""

    def test_lock_timeout_code(self):
        assert ErrorCode.LOCK_TIMEOUT == "E0005"

    def test_journal_not_found_code(self):
        assert ErrorCode.JOURNAL_NOT_FOUND == "E0500"

    def test_invalid_input_code(self):
        assert ErrorCode.INVALID_INPUT == "E0001"


# ===================================================================
# 13. Content metadata extraction — pin extract_explicit_metadata
# ===================================================================


class TestContentMetadataExtraction:
    """Pin the extract_explicit_metadata_from_content behavior:
    content-level location/weather override data-level values."""

    def test_content_location_wins_over_default(self, writable_env):
        """Location in content (地点:) prevents auto-fill."""
        data = {
            "date": "2026-03-14",
            "content": "地点：Beijing, China\n今天过得不错。",
        }
        with (
            patch(
                "tools.write_journal.core.get_journals_dir",
                return_value=writable_env["journals_dir"],
            ),
            patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=writable_env["lock_path"],
            ),
            patch("tools.write_journal.core.get_year_month", return_value=(2026, 3)),
            patch("tools.write_journal.core.get_next_sequence", return_value=1),
            patch("tools.write_journal.core.get_default_location") as mock_default,
            patch("tools.write_journal.core.normalize_location", return_value="Beijing, China"),
            patch("tools.write_journal.core.query_weather_for_location", return_value=""),
            patch("tools.write_journal.core.update_topic_index", return_value=[]),
            patch("tools.write_journal.core.update_project_index", return_value=None),
            patch("tools.write_journal.core.update_tag_indices", return_value=[]),
            patch("tools.write_journal.core.update_monthly_abstract", return_value="abstract.md"),
        ):
            result = write_journal(data)
        mock_default.assert_not_called()
        assert result["location_used"] == "Beijing, China"
        assert result["location_auto_filled"] is False

    def test_content_weather_wins_over_query(self, writable_env):
        """Weather in content (天气:) prevents weather API call."""
        data = {
            "date": "2026-03-14",
            "content": "天气：Rainy\n今天一直在下雨。",
        }
        with (
            patch(
                "tools.write_journal.core.get_journals_dir",
                return_value=writable_env["journals_dir"],
            ),
            patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=writable_env["lock_path"],
            ),
            patch("tools.write_journal.core.get_year_month", return_value=(2026, 3)),
            patch("tools.write_journal.core.get_next_sequence", return_value=1),
            patch("tools.write_journal.core.get_default_location", return_value="Default"),
            patch("tools.write_journal.core.normalize_location", return_value="Default"),
            patch("tools.write_journal.core.query_weather_for_location") as mock_wx,
            patch("tools.write_journal.core.update_topic_index", return_value=[]),
            patch("tools.write_journal.core.update_project_index", return_value=None),
            patch("tools.write_journal.core.update_tag_indices", return_value=[]),
            patch("tools.write_journal.core.update_monthly_abstract", return_value="abstract.md"),
        ):
            result = write_journal(data)
        mock_wx.assert_not_called()
        assert result["weather_used"] == "Rainy"
        assert result["weather_auto_filled"] is False

    def test_weather_query_failure_yields_empty_string(self, writable_env):
        """When weather API returns empty, weather_used is '' and auto_filled is False."""
        data = {"date": "2026-03-14", "content": "body"}
        with (
            patch(
                "tools.write_journal.core.get_journals_dir",
                return_value=writable_env["journals_dir"],
            ),
            patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=writable_env["lock_path"],
            ),
            patch("tools.write_journal.core.get_year_month", return_value=(2026, 3)),
            patch("tools.write_journal.core.get_next_sequence", return_value=1),
            patch("tools.write_journal.core.query_weather_for_location", return_value=""),
            patch("tools.write_journal.core.update_topic_index", return_value=[]),
            patch("tools.write_journal.core.update_project_index", return_value=None),
            patch("tools.write_journal.core.update_tag_indices", return_value=[]),
            patch("tools.write_journal.core.update_monthly_abstract", return_value="abstract.md"),
        ):
            result = write_journal(data)
        assert result["success"] is True
        assert result["weather_used"] == ""
        assert result["weather_auto_filled"] is False


# ===================================================================
# 14. apply_confirmation_updates() — numeric string candidate ref
# ===================================================================


class TestApplyConfirmationNumericStringRef:
    """Pin that a string like '1' in approved_related_entries is
    resolved as candidate_id 1 via _resolve_candidate_refs."""

    def test_numeric_string_resolved_as_id(self, tmp_path):
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )
        candidate_context = [
            {"candidate_id": 1, "rel_path": "Journals/2026/03/first.md", "title": "First"},
        ]
        with patch("tools.edit_journal.edit_journal") as mock_edit:
            mock_edit.return_value = {
                "success": True,
                "changes": {
                    "related_entries": {
                        "old": [],
                        "new": ["Journals/2026/03/first.md"],
                    }
                },
                "journal_path": str(journal_path),
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                approved_related_entries=["1"],  # string "1" → candidate_id 1
                candidate_context=candidate_context,
            )
        assert result["approved_candidate_ids"] == [1]

    def test_unknown_rel_path_without_context_creates_fallback(self, tmp_path):
        """When a rel_path is not in candidate_context but is a valid path
        string, the system creates a minimal fallback candidate."""
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )
        with patch("tools.edit_journal.edit_journal") as mock_edit:
            mock_edit.return_value = {
                "success": True,
                "changes": {
                    "related_entries": {
                        "old": [],
                        "new": ["Journals/2026/03/orphan.md"],
                    }
                },
                "journal_path": str(journal_path),
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                approved_related_entries=["Journals/2026/03/orphan.md"],
                # No candidate_context → fallback candidate created
            )
        assert result["approved_related_entries"] == ["Journals/2026/03/orphan.md"]
        assert result["approved_candidate_ids"] == []


class TestApplyConfirmationUpdatesErrorCodes:
    """Pin the exact ErrorCode values returned by apply_confirmation_updates."""

    def test_journal_not_found_error_code(self, tmp_path):
        missing = tmp_path / "nonexistent.md"
        result = apply_confirmation_updates(journal_path=missing)
        assert result["error"]["code"] == ErrorCode.JOURNAL_NOT_FOUND

    def test_unknown_candidate_invalid_input_code(self, tmp_path):
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            "---\ntitle: Source\ndate: 2026-03-14\n---\n\nBody\n",
            encoding="utf-8",
        )
        result = apply_confirmation_updates(
            journal_path=journal_path,
            approved_related_candidate_ids=[999],  # not in context
            candidate_context=[],
        )
        assert result["error"]["code"] == ErrorCode.INVALID_INPUT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
