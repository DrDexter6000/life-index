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

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.write_journal.core import apply_confirmation_updates, write_journal

# ── Documented field contracts ──

REQUIRED_SUCCESS_FIELDS = {
    "success",
    "write_outcome",
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
    "confirmation",
    "related_candidates",
    "new_entities_detected",
    "metrics",
}

VALID_INDEX_STATUS = {"complete", "degraded", "not_started"}
VALID_SIDE_EFFECTS_STATUS = {"complete", "degraded", "not_started"}
VALID_WRITE_OUTCOME = {
    "success",
    "success_pending_confirmation",
    "success_degraded",
    "failed",
}


@pytest.fixture(autouse=True)
def mock_vector_update():
    """Isolate from vector index/model loading."""
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


def _run_write(data: dict, writable_env: dict, dry_run: bool = False) -> dict:
    """Helper: run write_journal with all necessary mocks."""
    with patch("tools.write_journal.core.get_journals_dir", return_value=writable_env["journals_dir"]):
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


def _load_golden(name: str) -> dict:
    return json.loads(
        (Path(__file__).parent / "goldens" / name).read_text(encoding="utf-8")
    )


def _normalize_write_snapshot(result: dict) -> dict:
    normalized = json.loads(json.dumps(result))
    allowed_fields = {
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
        "error",
        "metrics",
    }
    normalized = {
        key: value for key, value in normalized.items() if key in allowed_fields
    }
    normalized["journal_path"] = "JOURNAL_PATH"
    normalized["confirmation_message"] = (
        f"日志已保存至：JOURNAL_PATH\n\n"
        f"本次记录地点：{normalized['location_used']}\n"
        f"天气：{normalized['weather_used']}\n"
        "请确认这个地点是否正确。如果不对，请告诉我正确地点。"
        "我会基于新地点更新地点和天气。"
    )
    confirmation = normalized.get("confirmation")
    if isinstance(confirmation, dict):
        confirmation["journal_path"] = "JOURNAL_PATH"
    normalized["related_candidates"] = []
    if isinstance(confirmation, dict):
        confirmation["related_candidates"] = []
    normalized["metrics"] = {}
    return normalized


def _normalize_confirm_snapshot(result: dict) -> dict:
    normalized = json.loads(json.dumps(result))
    normalized["journal_path"] = "JOURNAL_PATH"
    return normalized


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
        assert isinstance(result["confirmation"], dict)
        assert isinstance(result["related_candidates"], list)
        assert isinstance(result["new_entities_detected"], list)
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

    def test_write_outcome_is_valid_enum(self, writable_env):
        """write_outcome is one of the documented values."""
        data = {
            "date": "2026-03-14",
            "title": "Outcome Test",
            "content": "Content.",
            "topic": ["work"],
            "abstract": "Abstract.",
            "mood": [],
            "tags": [],
        }
        result = _run_write(data, writable_env)
        assert result["write_outcome"] in VALID_WRITE_OUTCOME

    def test_successful_write_outcome_is_pending_confirmation(self, writable_env):
        """Successful write with needs_confirmation=True → success_pending_confirmation."""
        data = {
            "date": "2026-03-14",
            "title": "Pending Test",
            "content": "Content.",
            "topic": ["work"],
            "abstract": "Abstract.",
            "mood": [],
            "tags": [],
        }
        result = _run_write(data, writable_env)
        if result["success"]:
            assert result["write_outcome"] == "success_pending_confirmation"

    def test_failed_write_outcome_is_failed(self, writable_env):
        """Failed write → write_outcome is 'failed'."""
        data = {}  # Missing required 'date' field
        result = _run_write(data, writable_env)
        assert result["success"] is False
        assert result["write_outcome"] == "failed"


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

    def test_explicit_location_still_requires_confirmation(self, writable_env):
        """Any successful write must require post-write location confirmation."""
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
        assert result["needs_confirmation"] is True
        assert "Beijing, China" in result["confirmation_message"]

    def test_any_successful_write_requires_confirmation(self, writable_env):
        """Contract: any successful write must request location confirmation."""
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
                assert result["needs_confirmation"] is True
                assert len(result["confirmation_message"]) > 0

    def test_confirmation_payload_is_structured(self, writable_env):
        data = {
            "date": "2026-03-14",
            "title": "Structured Confirmation",
            "content": "Content.",
            "topic": ["work"],
            "abstract": "Abstract.",
            "mood": [],
            "tags": [],
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["confirmation"]["location"] == result["location_used"]
        assert result["confirmation"]["weather"] == result["weather_used"]
        assert "related_candidates" in result["confirmation"]

    def test_confirmation_payload_supports_related_entry_approval(self, writable_env):
        data = {
            "date": "2026-03-14",
            "title": "Structured Confirmation",
            "content": "Content.",
            "topic": ["work"],
            "abstract": "Abstract.",
            "mood": [],
            "tags": [],
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["confirmation"]["supports_related_entry_approval"] is True

    def test_related_candidates_have_structured_fields(self, writable_env):
        data = {
            "date": "2026-03-14",
            "title": "Candidate Contract",
            "content": "Content.",
            "topic": ["work"],
            "abstract": "Abstract.",
            "mood": [],
            "tags": [],
        }
        result = _run_write(data, writable_env)

        assert result["success"] is True
        for candidate in result["related_candidates"]:
            assert "rel_path" in candidate
            assert "score" in candidate
            assert "match_reason" in candidate
            assert "reasons" in candidate
            assert "score_breakdown" in candidate


class TestConfirmWorkflowContract:
    def test_apply_confirmation_updates_returns_feedback_summary(self, tmp_path):
        from tools.write_journal.core import apply_confirmation_updates

        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            '---\ntitle: "Source"\ndate: 2026-03-14\nlocation: "Old City"\nweather: "Old Weather"\nrelated_entries: []\n---\n\n\nBody\n',
            encoding="utf-8",
        )

        with (
            patch("tools.edit_journal.edit_journal") as mock_edit,
            patch("tools.write_journal.core.init_metadata_cache") as mock_cache,
            patch(
                "tools.write_journal.core.build_journal_path_fields",
                return_value={
                    "path": "Journals/2026/03/source.md",
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
                    "location": {"old": "Old City", "new": "New City"},
                    "related_entries": {
                        "old": [],
                        "new": ["Journals/2026/03/target.md"],
                    },
                },
                "journal_path": str(journal_path),
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                location="New City",
                approved_related_entries=["Journals/2026/03/target.md"],
            )

        assert result["success"] is True
        assert result["confirm_status"] == "complete"
        assert "applied_fields" in result
        assert "ignored_fields" in result
        assert "approved_related_entries" in result
        assert result["requested_related_entries"] == ["Journals/2026/03/target.md"]
        assert result["relation_summary"] == {
            "source_entry": {
                "rel_path": "Journals/2026/03/source.md",
                "related_entries": ["Journals/2026/03/target.md"],
                "backlinked_by": [],
            },
            "approved_related_context": [
                {
                    "rel_path": "Journals/2026/03/target.md",
                    "backlinked_by": [],
                }
            ],
        }

    def test_apply_confirmation_updates_returns_candidate_approval_summary(
        self, tmp_path
    ):
        from tools.write_journal.core import apply_confirmation_updates

        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            '---\ntitle: "Source"\ndate: 2026-03-14\nlocation: "Old City"\nweather: "Old Weather"\nrelated_entries: []\n---\n\n\nBody\n',
            encoding="utf-8",
        )

        candidate_context = [
            {
                "candidate_id": 1,
                "rel_path": "Journals/2026/03/first.md",
                "title": "First",
            },
            {
                "candidate_id": 2,
                "rel_path": "Journals/2026/03/second.md",
                "title": "Second",
            },
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
                approved_related_candidate_ids=[1],
                rejected_related_candidate_ids=[2],
                candidate_context=candidate_context,
            )

        assert result["success"] is True
        assert result["approved_candidate_ids"] == [1]
        assert result["rejected_candidate_ids"] == [2]
        assert result["approval_summary"] == {
            "approved": [
                {
                    "candidate_id": 1,
                    "rel_path": "Journals/2026/03/first.md",
                    "title": "First",
                }
            ],
            "rejected": [
                {
                    "candidate_id": 2,
                    "rel_path": "Journals/2026/03/second.md",
                    "title": "Second",
                }
            ],
        }


class TestWriteJournalGoldenSnapshots:
    def test_write_result_matches_golden_snapshot(self, writable_env):
        data = {
            "date": "2026-03-14",
            "title": "Golden Write",
            "content": "Golden body.",
            "topic": ["work"],
            "abstract": "Golden abstract.",
            "mood": [],
            "tags": [],
        }

        with (
            patch(
                "tools.write_journal.core.get_default_location",
                return_value="Chongqing, China",
            ),
            patch(
                "tools.write_journal.core.normalize_location",
                return_value="Chongqing, China",
            ),
            patch(
                "tools.write_journal.core.suggest_related_entries",
                return_value=[],
            ),
            patch(
                "tools.write_journal.core.load_entity_graph",
                return_value=[],
            ),
        ):
            result = _run_write(data, writable_env, dry_run=False)

        assert _normalize_write_snapshot(result) == _load_golden("write_result.json")

    def test_confirm_result_matches_golden_snapshot(self, tmp_path):
        journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            '---\ntitle: "Source"\ndate: 2026-03-14\nlocation: "Old City"\nweather: "Old Weather"\nrelated_entries: []\n---\n\n\nBody\n',
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
                side_effect=[[], ["Journals/2026/03/source.md"]],
            ),
        ):
            mock_cache.return_value.close = lambda: None
            mock_edit.return_value = {
                "success": True,
                "changes": {
                    "location": {"old": "Old City", "new": "New City"},
                    "related_entries": {
                        "old": [],
                        "new": ["Journals/2026/03/approved.md"],
                    },
                },
                "journal_path": str(journal_path),
                "error": None,
            }
            result = apply_confirmation_updates(
                journal_path=journal_path,
                location="New City",
                approved_related_candidate_ids=[1],
                rejected_related_candidate_ids=[2],
                candidate_context=candidate_context,
            )

        assert _normalize_confirm_snapshot(result) == _load_golden(
            "confirm_result.json"
        )


class TestWriteJournalAttachmentResultContract:
    def test_auto_detected_attachment_summary_exposed(self, writable_env, tmp_path):
        source_file = tmp_path / "design.png"
        source_file.write_text("image", encoding="utf-8")

        data = {
            "date": "2026-03-14",
            "title": "Attachment Summary",
            "content": f"日志附件：{source_file}",
            "topic": ["create"],
            "abstract": "Attachment contract.",
            "mood": [],
            "tags": [],
        }

        result = _run_write(data, writable_env)

        assert result["success"] is True
        assert result["attachments_detected_count"] == 1
        assert result["attachments_processed_count"] == 1
        assert result["attachments_failed_count"] == 0
        assert len(result["attachments_processed"]) == 1


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
