#!/usr/bin/env python3
"""Regression tests for write-time related candidate confirmation snapshots."""

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.write_journal.core import apply_confirmation_updates, write_journal


@pytest.fixture
def writable_env(tmp_path: Path) -> dict[str, Path]:
    journals_dir = tmp_path / "Journals"
    journals_dir.mkdir(parents=True)
    attachments_dir = tmp_path / "attachments"
    attachments_dir.mkdir(parents=True)
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir(parents=True)
    lock_path = cache_dir / "journals.lock"
    lock_path.touch()
    return {
        "journals_dir": journals_dir,
        "attachments_dir": attachments_dir,
        "cache_dir": cache_dir,
        "lock_path": lock_path,
    }


def _write_with_related_candidates(
    data: dict,
    env: dict[str, Path],
    candidate_entries: list[dict],
) -> dict:
    fake_conn = MagicMock()
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "tools.write_journal.core.get_journals_dir",
                return_value=env["journals_dir"],
            )
        )
        stack.enter_context(
            patch(
                "tools.write_journal.core.get_journals_lock_path",
                return_value=env["lock_path"],
            )
        )
        stack.enter_context(
            patch("tools.write_journal.core.get_year_month", return_value=(2026, 3))
        )
        stack.enter_context(patch("tools.write_journal.core.get_next_sequence", return_value=1))
        stack.enter_context(
            patch("tools.write_journal.core.query_weather_for_location", return_value="Sunny 25C")
        )
        stack.enter_context(
            patch("tools.write_journal.core.normalize_location", return_value="Test City")
        )
        stack.enter_context(
            patch("tools.write_journal.core.extract_file_paths_from_content", return_value=[])
        )
        stack.enter_context(patch("tools.write_journal.core.process_attachments", return_value=[]))
        stack.enter_context(
            patch(
                "tools.write_journal.core.update_monthly_abstract",
                return_value={"abstract_path": None, "updated": False},
            )
        )
        stack.enter_context(patch("tools.write_journal.core.update_topic_index", return_value=[]))
        stack.enter_context(
            patch("tools.write_journal.core.update_project_index", return_value=None)
        )
        stack.enter_context(patch("tools.write_journal.core.update_tag_indices", return_value=[]))
        stack.enter_context(
            patch("tools.write_journal.core.refresh_index_b", return_value={"success": True})
        )
        stack.enter_context(patch("tools.write_journal.core.load_entity_graph", return_value=[]))
        stack.enter_context(
            patch("tools.write_journal.core.init_metadata_cache", return_value=fake_conn)
        )
        stack.enter_context(
            patch(
                "tools.write_journal.core.get_all_cached_metadata",
                return_value=candidate_entries,
            )
        )
        return write_journal(data, dry_run=False)


def test_confirm_candidate_id_uses_write_time_snapshot_when_context_recomputed(
    writable_env: dict[str, Path],
) -> None:
    data = {
        "date": "2026-03-14",
        "title": "Source",
        "content": "Synthetic source entry.",
        "topic": ["work"],
        "people": ["Alice"],
        "project": "Life-Index",
        "tags": ["search", "ranking"],
    }
    write_time_candidates = [
        {
            "rel_path": "Journals/2026/03/old-match.md",
            "date": "2026-03-10",
            "title": "Old Match",
            "abstract": "Synthetic old match",
            "topic": ["work"],
            "people": ["Alice"],
            "project": "Life-Index",
            "tags": ["search", "ranking"],
            "related_entries": [],
        }
    ]
    recomputed_context = [
        {
            "candidate_id": 1,
            "rel_path": "Journals/2026/03/newer-match.md",
            "title": "Newer Match",
        },
        {
            "candidate_id": 2,
            "rel_path": "Journals/2026/03/old-match.md",
            "title": "Old Match",
        },
    ]

    write_result = _write_with_related_candidates(data, writable_env, write_time_candidates)

    assert write_result["success"] is True
    assert write_result["related_candidates"][0]["candidate_id"] == 1
    assert write_result["related_candidates"][0]["rel_path"] == "Journals/2026/03/old-match.md"

    with patch("tools.edit_journal.edit_journal") as mock_edit:
        mock_edit.return_value = {
            "success": True,
            "changes": {
                "related_entries": {
                    "old": [],
                    "new": ["Journals/2026/03/old-match.md"],
                },
            },
            "journal_path": write_result["journal_path"],
            "error": None,
        }
        result = apply_confirmation_updates(
            journal_path=write_result["journal_path"],
            approved_related_candidate_ids=[1],
            candidate_context=recomputed_context,
        )

    assert result["success"] is True
    assert mock_edit.call_args.kwargs["frontmatter_updates"]["add_related_entries"] == [
        "Journals/2026/03/old-match.md"
    ]
    assert result["approved_related_entries"] == ["Journals/2026/03/old-match.md"]
    assert result["approval_summary"]["approved"] == [
        {
            "candidate_id": 1,
            "rel_path": "Journals/2026/03/old-match.md",
            "title": "Old Match",
        }
    ]
