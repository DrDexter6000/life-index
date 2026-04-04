"""
Workflow signal enums for Life Index.

Provides machine-readable enums for all workflow states returned by tools.
StrEnum values are plain strings — fully backward compatible with existing JSON output.
"""

from enum import StrEnum


class WriteOutcome(StrEnum):
    """Top-level write result — one field tells Agent what to do next."""

    SUCCESS = "success"
    SUCCESS_PENDING_CONFIRMATION = "success_pending_confirmation"
    SUCCESS_DEGRADED = "success_degraded"
    FAILED = "failed"


class IndexStatus(StrEnum):
    """Post-write index update status."""

    COMPLETE = "complete"
    DEGRADED = "degraded"
    NOT_STARTED = "not_started"


class SideEffectsStatus(StrEnum):
    """Post-write side effects (abstract, attachments, etc.) status."""

    COMPLETE = "complete"
    DEGRADED = "degraded"
    NOT_STARTED = "not_started"


class ConfirmStatus(StrEnum):
    """Confirmation subcommand result status."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    NOOP = "noop"
    FAILED = "failed"


class RecoveryStrategy(StrEnum):
    """Error recovery strategy — tells Agent what to do on error."""

    ASK_USER = "ask_user"
    SKIP_OPTIONAL = "skip_optional"
    CONTINUE_EMPTY = "continue_empty"
    FAIL = "fail"
    RETRY = "retry"


def derive_write_outcome(
    *,
    success: bool,
    needs_confirmation: bool,
    index_status: str,
    side_effects_status: str,
) -> WriteOutcome:
    """
    Derive the top-level write_outcome from component fields.

    Priority order:
    1. Failed → FAILED
    2. Needs confirmation → SUCCESS_PENDING_CONFIRMATION (even if also degraded)
    3. Any degraded status → SUCCESS_DEGRADED
    4. All good → SUCCESS
    """
    if not success:
        return WriteOutcome.FAILED
    if needs_confirmation:
        return WriteOutcome.SUCCESS_PENDING_CONFIRMATION
    if (
        index_status == IndexStatus.DEGRADED
        or side_effects_status == SideEffectsStatus.DEGRADED
    ):
        return WriteOutcome.SUCCESS_DEGRADED
    return WriteOutcome.SUCCESS
