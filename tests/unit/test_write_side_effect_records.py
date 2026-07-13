"""Behavior tests for transactional write side-effect records."""

from pathlib import Path

from tools.lib import workflow_signals
from tools.write_journal import core as write_core


def test_status_is_derived_from_single_execution_record_sequence():
    """A failed post-commit effect degrades every compatibility projection."""
    derive = getattr(workflow_signals, "derive_write_statuses", None)
    assert derive is not None, "write summaries must be derived from side-effect records"

    records = [
        {
            "name": "journal_commit",
            "phase": "commit",
            "status": "complete",
            "blocking": True,
        },
        {
            "name": "legacy_indices",
            "phase": "post_commit",
            "status": "failed",
            "blocking": False,
            "error": "synthetic index failure",
            "recovery_strategy": "life-index generate-index",
        },
    ]

    assert derive(records, needs_confirmation=False) == {
        "success": True,
        "write_outcome": "success_degraded",
        "index_status": "degraded",
        "side_effects_status": "degraded",
    }


def test_preview_projection_does_not_hide_failed_attachment_record():
    """A completed preview still exposes a failed preflight attachment effect."""
    records = [
        {
            "name": "attachments",
            "phase": "pre_commit",
            "status": "failed",
            "blocking": False,
            "error": "synthetic missing attachment",
            "recovery_strategy": "fix the attachment source before writing",
        },
        {
            "name": "write_preview",
            "phase": "preview",
            "status": "complete",
            "blocking": False,
        },
    ]

    assert workflow_signals.derive_write_statuses(
        records,
        needs_confirmation=False,
        preview=True,
    ) == {
        "success": True,
        "write_outcome": "success_degraded",
        "index_status": "not_started",
        "side_effects_status": "degraded",
    }


def test_legacy_derivation_cannot_hide_degradation_behind_confirmation():
    assert (
        workflow_signals.derive_write_outcome(
            success=True,
            needs_confirmation=True,
            index_status="degraded",
            side_effects_status="degraded",
        )
        == "success_degraded"
    )


def test_write_envelope_is_projected_from_its_side_effect_records(
    tmp_path: Path,
    monkeypatch,
):
    """A committed journal with failed Index B reports one consistent truth."""
    data_dir = tmp_path / "Life-Index"
    (data_dir / "Journals").mkdir(parents=True)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    monkeypatch.setattr(write_core, "query_weather_for_location", lambda *_args: "Sunny 25C")
    monkeypatch.setattr(write_core, "update_topic_index", lambda *_args: [])
    monkeypatch.setattr(write_core, "update_project_index", lambda *_args: None)
    monkeypatch.setattr(write_core, "update_tag_indices", lambda *_args: [])
    monkeypatch.setattr(write_core, "update_monthly_abstract", lambda *_args: {"success": True})
    monkeypatch.setattr(
        write_core,
        "refresh_index_b",
        lambda *_args: {"success": False, "error": "synthetic Index B failure"},
    )

    result = write_core.write_journal(
        {
            "date": "2026-03-14",
            "title": "Synthetic journal",
            "content": "Synthetic content.",
            "topic": ["work"],
            "abstract": "Synthetic abstract.",
            "mood": [],
            "tags": [],
        }
    )

    assert result["side_effects"], "write must expose the execution record sequence"
    projection = workflow_signals.derive_write_statuses(
        result["side_effects"], needs_confirmation=result["needs_confirmation"]
    )
    for field in (
        "success",
        "write_outcome",
        "index_status",
        "side_effects_status",
    ):
        assert result[field] == projection[field]
    assert result["write_outcome"] == "success_degraded"
    assert any(
        record["name"] == "index_b" and record["status"] == "failed"
        for record in result["side_effects"]
    )
