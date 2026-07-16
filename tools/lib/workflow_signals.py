"""
Workflow signal enums for Life Index.

Provides machine-readable enums for all workflow states returned by tools.
StrEnum values are plain strings — fully backward compatible with existing JSON output.
"""

from enum import StrEnum
from typing import Any, Sequence


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


class SideEffectExecutionStatus(StrEnum):
    """Execution state for one transactional write effect."""

    COMPLETE = "complete"
    QUEUED = "queued"
    SKIPPED = "skipped"
    FAILED = "failed"
    COMPENSATED = "compensated"


INDEX_SIDE_EFFECT_NAMES = frozenset(
    {
        "legacy_indices",
        "metadata_relations",
        "mark_pending",
        "index_b",
        "auto_index",
    }
)


def derive_write_statuses(
    side_effects: Sequence[dict[str, Any]],
    *,
    needs_confirmation: bool,
    preview: bool = False,
) -> dict[str, bool | str]:
    """Project compatibility fields from the single execution record sequence."""
    valid_statuses = {status.value for status in SideEffectExecutionStatus}
    for record in side_effects:
        status = str(record.get("status", ""))
        if status not in valid_statuses:
            raise ValueError(f"invalid side-effect status: {status!r}")

    incomplete_statuses = {
        SideEffectExecutionStatus.FAILED,
        SideEffectExecutionStatus.QUEUED,
        SideEffectExecutionStatus.COMPENSATED,
    }

    if preview:
        preview_records = [
            record for record in side_effects if record.get("name") == "write_preview"
        ]
        preview_complete = bool(
            preview_records
            and preview_records[-1].get("status") == SideEffectExecutionStatus.COMPLETE
        )
        if preview_complete:
            preview_degraded = any(
                record.get("name") != "write_preview"
                and record.get("status") in incomplete_statuses
                for record in side_effects
            )
            return {
                "success": True,
                "write_outcome": (
                    WriteOutcome.SUCCESS_DEGRADED if preview_degraded else WriteOutcome.SUCCESS
                ),
                "index_status": IndexStatus.NOT_STARTED,
                "side_effects_status": (
                    SideEffectsStatus.DEGRADED if preview_degraded else SideEffectsStatus.COMPLETE
                ),
            }

    journal_records = [record for record in side_effects if record.get("name") == "journal_commit"]
    journal_committed = bool(
        journal_records and journal_records[-1].get("status") == SideEffectExecutionStatus.COMPLETE
    )
    if not journal_committed:
        return {
            "success": False,
            "write_outcome": WriteOutcome.FAILED,
            "index_status": IndexStatus.NOT_STARTED,
            "side_effects_status": SideEffectsStatus.NOT_STARTED,
        }

    index_records = [
        record for record in side_effects if record.get("name") in INDEX_SIDE_EFFECT_NAMES
    ]
    index_degraded = any(record.get("status") in incomplete_statuses for record in index_records)
    side_effects_degraded = any(
        record.get("name") != "journal_commit" and record.get("status") in incomplete_statuses
        for record in side_effects
    )

    index_status = IndexStatus.DEGRADED if index_degraded else IndexStatus.COMPLETE
    side_effects_status = (
        SideEffectsStatus.DEGRADED if side_effects_degraded else SideEffectsStatus.COMPLETE
    )
    if index_degraded or side_effects_degraded:
        write_outcome = WriteOutcome.SUCCESS_DEGRADED
    elif needs_confirmation:
        write_outcome = WriteOutcome.SUCCESS_PENDING_CONFIRMATION
    else:
        write_outcome = WriteOutcome.SUCCESS

    return {
        "success": True,
        "write_outcome": write_outcome,
        "index_status": index_status,
        "side_effects_status": side_effects_status,
    }


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
    CONTINUE = "continue"
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
    2. Any degraded status → SUCCESS_DEGRADED
    3. Needs confirmation → SUCCESS_PENDING_CONFIRMATION
    4. All good → SUCCESS
    """
    if not success:
        return WriteOutcome.FAILED
    if index_status == IndexStatus.DEGRADED or side_effects_status == SideEffectsStatus.DEGRADED:
        return WriteOutcome.SUCCESS_DEGRADED
    if needs_confirmation:
        return WriteOutcome.SUCCESS_PENDING_CONFIRMATION
    return WriteOutcome.SUCCESS
