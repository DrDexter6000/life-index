#!/usr/bin/env python3
"""Contract tests: edit_journal append-only revision history.

Verifies that edit_journal preserves prior content in human-readable
revision history, satisfying README P1 (Growth Rings) promise.

ADR: docs/adr/ADR-2026-05-25-edit-journal-append-only.md
"""

from pathlib import Path
from unittest.mock import patch

from tools.edit_journal import edit_journal
from tools.lib.revisions import list_revisions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ORIGINAL_JOURNAL = (
    "---\n"
    'title: "Original Title"\n'
    "date: 2026-03-14\n"
    'location: "Lagos, Nigeria"\n'
    'weather: "Sunny 32°C"\n'
    'mood: ["happy"]\n'
    'tags: ["test"]\n'
    "---\n"
    "\n"
    "\n"
    "This is the original body content.\n"
    "It has multiple lines.\n"
)


def _write_journal(path: Path) -> Path:
    """Write a standard test journal and return its path."""
    path.write_text(ORIGINAL_JOURNAL, encoding="utf-8")
    return path


def _parse_frontmatter_from_text(text: str) -> dict[str, str]:
    """Naive frontmatter parser for test assertions."""
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    fm_text = text[3:end].strip()
    result: dict[str, str] = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


# ---------------------------------------------------------------------------
# Test 1: Prior content is preserved in revision history
# ---------------------------------------------------------------------------


def test_edit_journal_preserves_prior_content_in_history(tmp_path: Path) -> None:
    """After edit, the original content must be recoverable from revision files."""
    journal_path = _write_journal(tmp_path / "journal.md")

    with patch("tools.edit_journal.mark_pending"):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"title": "Updated Title"},
        )

    assert result["success"], f"Edit failed: {result.get('error')}"
    assert result["revision_path"], "No revision was created"

    revisions = list_revisions(journal_path)
    assert len(revisions) >= 1, "No revision files found"

    revision_content = revisions[-1].read_text(encoding="utf-8")
    # Byte-for-byte equality: revision must be an exact copy of the original,
    # not just a superset. Catches formatting drift, key reordering, or
    # trailing-whitespace stripping bugs that substring checks would miss.
    assert (
        revision_content == ORIGINAL_JOURNAL
    ), "Revision content does not match original journal byte-for-byte"


# ---------------------------------------------------------------------------
# Test 2: Body is not silently overwritten (recoverable from revision)
# ---------------------------------------------------------------------------


def test_edit_journal_does_not_silently_overwrite_body(tmp_path: Path) -> None:
    """Replace-content must save the prior body in a revision file."""
    journal_path = _write_journal(tmp_path / "journal.md")

    with patch("tools.edit_journal.mark_pending"):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={},
            replace_content="This is the new body.",
        )

    assert result["success"], f"Edit failed: {result.get('error')}"
    assert result["content_modified"], "content_modified should be True"
    assert result["revision_path"], "No revision was created"

    # Current journal has the new body
    current = journal_path.read_text(encoding="utf-8")
    assert "This is the new body." in current

    # Revision preserves the old body
    revisions = list_revisions(journal_path)
    assert len(revisions) >= 1
    revision = revisions[-1].read_text(encoding="utf-8")
    assert (
        "This is the original body content." in revision
    ), "Prior body lost — original body not in revision"


# ---------------------------------------------------------------------------
# Test 3: Frontmatter is not silently overwritten (recoverable from revision)
# ---------------------------------------------------------------------------


def test_edit_journal_does_not_silently_overwrite_frontmatter(tmp_path: Path) -> None:
    """Frontmatter changes must save the prior frontmatter in a revision file."""
    journal_path = _write_journal(tmp_path / "journal.md")

    with patch("tools.edit_journal.mark_pending"):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={
                "title": "New Title",
                "location": "Beijing, China",
                "weather": "Cloudy 15°C",
            },
        )

    assert result["success"], f"Edit failed: {result.get('error')}"
    assert result["revision_path"], "No revision was created"

    # Current journal has new frontmatter
    current = journal_path.read_text(encoding="utf-8")
    assert "New Title" in current

    # Revision preserves old frontmatter
    revisions = list_revisions(journal_path)
    assert len(revisions) >= 1
    revision = revisions[-1].read_text(encoding="utf-8")
    assert "Original Title" in revision, "Prior title lost — not in revision"
    assert "Lagos, Nigeria" in revision, "Prior location lost — not in revision"
    assert "Sunny 32°C" in revision, "Prior weather lost — not in revision"


# ---------------------------------------------------------------------------
# Test 4: Revision storage is human-readable Markdown
# ---------------------------------------------------------------------------


def test_revision_storage_is_human_readable_markdown(tmp_path: Path) -> None:
    """Revision files must be valid Markdown readable by any text editor."""
    journal_path = _write_journal(tmp_path / "journal.md")

    with patch("tools.edit_journal.mark_pending"):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"title": "Another Update"},
        )

    assert result["success"], f"Edit failed: {result.get('error')}"

    revisions = list_revisions(journal_path)
    assert len(revisions) >= 1

    revision_path = revisions[-1]

    # File extension is .md
    assert revision_path.suffix == ".md", f"Revision file is not .md: {revision_path.suffix}"

    # Content is valid UTF-8 text
    content = revision_path.read_text(encoding="utf-8")

    # Contains YAML frontmatter (starts with ---)
    assert content.startswith("---"), "Revision file does not start with YAML frontmatter delimiter"

    # Contains the body (Markdown content after frontmatter)
    assert (
        "This is the original body content." in content
    ), "Revision does not contain Markdown body"

    # Entire content is a valid journal (frontmatter + body)
    fm = _parse_frontmatter_from_text(content)
    assert "title" in fm, "Revision frontmatter missing 'title' field"


# ---------------------------------------------------------------------------
# Test 4b: append_content snapshots prior content
# ---------------------------------------------------------------------------


def test_edit_journal_append_content_snapshots_prior_body(tmp_path: Path) -> None:
    """append_content= must save the prior body in a revision file.

    edit_journal exposes 3 mutation modes (frontmatter-only, replace_content,
    append_content). All 3 must snapshot prior content via save_revision().
    This test covers the append_content path.
    """
    journal_path = _write_journal(tmp_path / "journal.md")

    with patch("tools.edit_journal.mark_pending"):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={},
            append_content="This is appended text.\n",
        )

    assert result["success"], f"Edit failed: {result.get('error')}"
    assert result["content_modified"], "content_modified should be True"
    assert result["revision_path"], "No revision was created for append_content edit"

    # Current journal has the appended text
    current = journal_path.read_text(encoding="utf-8")
    assert "This is appended text." in current
    # Original body is still present (append, not replace)
    assert "This is the original body content." in current

    # Revision preserves the original content byte-for-byte
    revisions = list_revisions(journal_path)
    assert len(revisions) >= 1
    revision = revisions[-1].read_text(encoding="utf-8")
    assert (
        revision == ORIGINAL_JOURNAL
    ), "Revision content does not match original journal byte-for-byte after append"


# ---------------------------------------------------------------------------
# Test 5: Deleting revision storage does not corrupt current journal
# ---------------------------------------------------------------------------


def test_revision_storage_can_be_deleted_without_corruption(tmp_path: Path) -> None:
    """Revision files are non-canonical backups.

    Deleting them must not corrupt or alter the current journal file.
    Rationale: Revisions are full-copy backups, not canonical data. The
    journal file itself is the single source of truth. Revisions exist
    solely for historical recovery. If deleted, the user loses revision
    history but never loses the current journal state.
    """
    journal_path = _write_journal(tmp_path / "journal.md")

    with patch("tools.edit_journal.mark_pending"):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"title": "After First Edit"},
        )

    assert result["success"], f"Edit failed: {result.get('error')}"

    # Record current journal state
    current_before = journal_path.read_text(encoding="utf-8")

    # Delete all revision files
    revisions = list_revisions(journal_path)
    assert len(revisions) >= 1, "Expected at least one revision"
    for rev in revisions:
        rev.unlink()

    # Verify revision directory is empty or gone
    revisions_after = list_revisions(journal_path)
    assert len(revisions_after) == 0, "Revisions not fully deleted"

    # Current journal is unchanged
    current_after = journal_path.read_text(encoding="utf-8")
    assert current_after == current_before, "Journal was corrupted after deleting revisions"

    # Journal still has the edited content
    assert "After First Edit" in current_after
    # Body was not replaced (only frontmatter was updated), so it must remain
    assert (
        "This is the original body content." in current_after
    ), "Original body lost from journal after frontmatter-only edit"
