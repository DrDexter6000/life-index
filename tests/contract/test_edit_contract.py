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
    "error",
}


def _load_golden(name: str) -> dict:
    return json.loads(
        (Path(__file__).parent / "goldens" / name).read_text(encoding="utf-8")
    )


def test_edit_response_has_all_required_fields(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.md"
    journal_path.write_text(
        '---\ntitle: "Original"\ndate: 2026-03-14\n---\n\n\nBody\n',
        encoding="utf-8",
    )

    with patch("tools.edit_journal.update_vector_index", return_value=False):
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
        patch("tools.edit_journal.update_vector_index", return_value=False),
        patch("tools.edit_journal.save_revision", return_value="REVISION_PATH"),
    ):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"title": "Updated"},
            replace_content="New body",
        )

    normalized = dict(result)
    normalized["journal_path"] = "JOURNAL_PATH"

    assert normalized == _load_golden("edit_result.json")
