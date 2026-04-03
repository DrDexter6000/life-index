#!/usr/bin/env python3

from pathlib import Path

from datetime import datetime


def _journal_file(base: Path) -> Path:
    journal = base / "Journals" / "2026" / "04" / "life-index_2026-04-03_001.md"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        '---\ntitle: "旧标题"\ndate: 2026-04-03\n---\n\n# 旧标题\n\n旧内容',
        encoding="utf-8",
    )
    return journal


def test_edit_creates_revision_file(isolated_data_dir: Path) -> None:
    from tools.edit_journal import edit_journal

    journal = _journal_file(isolated_data_dir)

    result = edit_journal(journal, {"title": "新标题"})

    assert result["success"] is True
    assert result["revision_path"]
    assert Path(result["revision_path"]).exists()


def test_revision_filename_format(isolated_data_dir: Path) -> None:
    from tools.edit_journal import edit_journal

    journal = _journal_file(isolated_data_dir)

    result = edit_journal(journal, {"title": "新标题"})
    revision_name = Path(result["revision_path"]).name

    assert revision_name.startswith("life-index_2026-04-03_001_")
    assert revision_name.endswith(".md")


def test_revision_content_matches_original(isolated_data_dir: Path) -> None:
    from tools.edit_journal import edit_journal

    journal = _journal_file(isolated_data_dir)
    original = journal.read_text(encoding="utf-8")

    result = edit_journal(journal, {"title": "新标题"})
    revision = Path(result["revision_path"]).read_text(encoding="utf-8")

    assert revision == original


def test_revision_dir_created_if_absent(isolated_data_dir: Path) -> None:
    from tools.edit_journal import edit_journal

    journal = _journal_file(isolated_data_dir)

    result = edit_journal(journal, {"title": "新标题"})

    assert Path(result["revision_path"]).parent.name == ".revisions"


def test_multiple_edits_create_multiple_revisions(isolated_data_dir: Path) -> None:
    from tools.edit_journal import edit_journal

    journal = _journal_file(isolated_data_dir)

    first = edit_journal(journal, {"title": "新标题1"})
    second = edit_journal(journal, {"title": "新标题2"})

    assert first["revision_path"] != second["revision_path"]


def test_save_revision_generates_unique_path_when_timestamp_repeats(
    tmp_path: Path,
) -> None:
    from tools.lib import revisions

    journal = tmp_path / "Journals" / "2026" / "04" / "life-index_2026-04-03_001.md"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text("original", encoding="utf-8")

    fixed_now = datetime(2026, 4, 3, 16, 2, 18, 928501)

    class FrozenDateTime:
        @classmethod
        def now(cls) -> datetime:
            return fixed_now

    original_datetime = revisions.datetime
    revisions.datetime = FrozenDateTime
    try:
        first = revisions.save_revision(journal, "one")
        second = revisions.save_revision(journal, "two")
    finally:
        revisions.datetime = original_datetime

    assert first != second
    assert first.exists()
    assert second.exists()


def test_write_new_journal_no_revision(isolated_data_dir: Path) -> None:
    from tools.write_journal.core import write_journal

    result = write_journal(
        {"date": "2026-04-03", "title": "新日志", "content": "正文"},
        dry_run=True,
    )

    assert result["success"] is True
    assert "revision_path" not in result
