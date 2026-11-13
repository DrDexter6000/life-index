#!/usr/bin/env python3
"""Contract tests: edit_journal response shape and golden snapshots."""

import json
from pathlib import Path
from unittest.mock import patch

from tools.edit_journal import edit_journal

REQUIRED_EDIT_FIELDS = {
    "success",
    "journal_path",
    "revision_path",
    "changes",
    "content_modified",
    "indices_updated",
    "fts_row_updated",
    "pending_marked",
    "index_b_updated",
    "metadata_cache_updated",
    "error",
}


def _load_golden(name: str) -> dict:
    return json.loads((Path(__file__).parent / "goldens" / name).read_text(encoding="utf-8"))


def _index_b_refresh_fixture() -> dict:
    return {
        "success": True,
        "updated": True,
        "artifact": "index-b",
        "payload": {"written_docs": [".life-index/index-b/manifest.json"]},
    }


def test_edit_response_has_all_required_fields(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.md"
    journal_path.write_text(
        '---\ntitle: "Original"\ndate: 2026-03-14\n---\n\n\nBody\n',
        encoding="utf-8",
    )

    with (
        patch("tools.edit_journal.mark_pending"),
        patch("tools.edit_journal.refresh_index_b", return_value=_index_b_refresh_fixture()),
    ):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"title": "Updated"},
        )

    for field in REQUIRED_EDIT_FIELDS:
        assert field in result, f"Missing required field: {field}"


def test_edit_result_matches_golden_snapshot(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.md"
    journal_path.write_text(
        '---\ntitle: "Original"\ndate: 2026-03-14\n---\n\n\nBody\n',
        encoding="utf-8",
    )

    with (
        patch("tools.edit_journal.mark_pending"),
        patch("tools.edit_journal.save_revision", return_value="REVISION_PATH"),
        patch("tools.edit_journal.refresh_index_b", return_value=_index_b_refresh_fixture()),
    ):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"title": "Updated"},
            replace_content="New body",
        )

    normalized = dict(result)
    normalized["journal_path"] = "JOURNAL_PATH"

    assert normalized == _load_golden("edit_result.json")


def test_edit_of_unparsable_frontmatter_reports_complete_raw_row(
    isolated_data_dir: Path,
) -> None:
    """D1: an edit whose committed file still has unparsable frontmatter is complete."""
    journal_path = isolated_data_dir / "Journals" / "2026" / "03" / "life-index_2026-03-04_001.md"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(
        "---\ntitle: [not, a, string]\ndate: 2026-03-04\n---\n\nraw body token\n",
        encoding="utf-8",
    )

    with patch("tools.edit_journal.refresh_index_b", return_value=_index_b_refresh_fixture()):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"weather": "sunny"},
        )

    assert result["success"] is True, result.get("error")
    assert result["fts_row_updated"] is True
    assert result["pending_marked"] is False
    assert result["fts_row"] == {
        "status": "complete",
        "reason": "unparsable_frontmatter_indexed_as_text",
        "recovery": None,
    }
    assert result["metadata_cache_updated"] in (True, False)
