"""Contract tests for workflow signal enums."""

import json

import pytest

from tools.lib.workflow_signals import (
    WriteOutcome,
    IndexStatus,
    SideEffectsStatus,
    ConfirmStatus,
    RecoveryStrategy,
    derive_write_outcome,
)


class TestEnumValues:
    """Verify enum string values match existing JSON output format."""

    def test_write_outcome_values(self):
        assert set(WriteOutcome) == {
            "success",
            "success_pending_confirmation",
            "success_degraded",
            "failed",
        }

    def test_index_status_values(self):
        assert set(IndexStatus) == {"complete", "degraded", "not_started"}

    def test_side_effects_status_values(self):
        assert set(SideEffectsStatus) == {"complete", "degraded", "not_started"}

    def test_confirm_status_values(self):
        assert set(ConfirmStatus) == {"complete", "partial", "noop", "failed"}

    def test_recovery_strategy_values(self):
        assert set(RecoveryStrategy) == {
            "ask_user",
            "skip_optional",
            "continue_empty",
            "fail",
            "retry",
        }


class TestStrEnumBackwardCompat:
    """StrEnum values serialize as plain strings — no breakage."""

    def test_index_status_is_string(self):
        assert IndexStatus.COMPLETE == "complete"
        assert isinstance(IndexStatus.COMPLETE, str)

    def test_write_outcome_json_serializable(self):
        d = {"write_outcome": WriteOutcome.SUCCESS_PENDING_CONFIRMATION}
        assert json.dumps(d) == '{"write_outcome": "success_pending_confirmation"}'

    def test_side_effects_status_is_string(self):
        assert SideEffectsStatus.DEGRADED == "degraded"
        assert isinstance(SideEffectsStatus.DEGRADED, str)

    def test_confirm_status_is_string(self):
        assert ConfirmStatus.PARTIAL == "partial"
        assert isinstance(ConfirmStatus.PARTIAL, str)

    def test_recovery_strategy_is_string(self):
        assert RecoveryStrategy.RETRY == "retry"
        assert isinstance(RecoveryStrategy.RETRY, str)


class TestDeriveWriteOutcome:
    """derive_write_outcome correctly maps component fields to outcome."""

    def test_failed(self):
        assert (
            derive_write_outcome(
                success=False,
                needs_confirmation=False,
                index_status="not_started",
                side_effects_status="not_started",
            )
            == WriteOutcome.FAILED
        )

    def test_success_pending_confirmation(self):
        assert (
            derive_write_outcome(
                success=True,
                needs_confirmation=True,
                index_status="complete",
                side_effects_status="complete",
            )
            == WriteOutcome.SUCCESS_PENDING_CONFIRMATION
        )

    def test_confirmation_takes_priority_over_degraded(self):
        """When both confirmation needed AND degraded, confirmation wins."""
        assert (
            derive_write_outcome(
                success=True,
                needs_confirmation=True,
                index_status="degraded",
                side_effects_status="complete",
            )
            == WriteOutcome.SUCCESS_PENDING_CONFIRMATION
        )

    def test_success_degraded_index(self):
        assert (
            derive_write_outcome(
                success=True,
                needs_confirmation=False,
                index_status="degraded",
                side_effects_status="complete",
            )
            == WriteOutcome.SUCCESS_DEGRADED
        )

    def test_success_degraded_side_effects(self):
        assert (
            derive_write_outcome(
                success=True,
                needs_confirmation=False,
                index_status="complete",
                side_effects_status="degraded",
            )
            == WriteOutcome.SUCCESS_DEGRADED
        )

    def test_full_success(self):
        assert (
            derive_write_outcome(
                success=True,
                needs_confirmation=False,
                index_status="complete",
                side_effects_status="complete",
            )
            == WriteOutcome.SUCCESS
        )

    def test_failed_overrides_confirmation(self):
        """Failed takes absolute priority, even with needs_confirmation."""
        assert (
            derive_write_outcome(
                success=False,
                needs_confirmation=True,
                index_status="complete",
                side_effects_status="complete",
            )
            == WriteOutcome.FAILED
        )

    def test_both_degraded(self):
        """Both index and side_effects degraded → still SUCCESS_DEGRADED."""
        assert (
            derive_write_outcome(
                success=True,
                needs_confirmation=False,
                index_status="degraded",
                side_effects_status="degraded",
            )
            == WriteOutcome.SUCCESS_DEGRADED
        )
