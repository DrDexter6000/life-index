from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from tools.edit_journal import edit_journal
from tools.edit_journal.__main__ import main


pytestmark = pytest.mark.critical


def test_edit_journal_writes_frontmatter_and_body_with_triple_newline(
    tmp_path: Path,
) -> None:
    journal_path = tmp_path / "life-index_2026-03-25_001.md"
    journal_path.write_text(
        '---\ntitle: "原标题"\ndate: 2026-03-25\n---\n\n\n原正文\n',
        encoding="utf-8",
    )

    with patch("tools.edit_journal.update_vector_index", return_value=True):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"title": "新标题"},
            replace_content="新正文",
        )

    assert result["success"] is True
    written = journal_path.read_text(encoding="utf-8")
    assert 'title: "新标题"' in written
    assert "---\n\n\n新正文" in written


def test_edit_journal_normalizes_links_string_to_list(tmp_path: Path) -> None:
    journal_path = tmp_path / "life-index_2026-03-25_001.md"
    journal_path.write_text(
        '---\ntitle: "原标题"\ndate: 2026-03-25\n---\n\n\n原正文\n',
        encoding="utf-8",
    )

    with patch("tools.edit_journal.update_vector_index", return_value=True):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"links": "https://a.com, https://b.com"},
        )

    assert result["success"] is True
    written = journal_path.read_text(encoding="utf-8")
    assert 'links: ["https://a.com", "https://b.com"]' in written


def test_edit_journal_cli_parses_set_links(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    def fake_edit_journal(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "journal_path": str(kwargs["journal_path"]),
            "changes": {},
            "revision_path": None,
        }

    monkeypatch.setattr(
        "tools.edit_journal.__main__.edit_journal",
        fake_edit_journal,
    )
    monkeypatch.setattr("tools.edit_journal.__main__.ensure_dirs", lambda: None)
    monkeypatch.setattr("tools.edit_journal.__main__._emit_json", lambda payload: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "edit_journal",
            "--journal",
            str(tmp_path / "sample.md"),
            "--set-links",
            "https://a.com, https://b.com",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert captured["frontmatter_updates"]["links"] == [
        "https://a.com",
        "https://b.com",
    ]


def test_edit_journal_normalizes_related_entries_string_to_list(tmp_path: Path) -> None:
    journal_path = tmp_path / "life-index_2026-03-25_001.md"
    journal_path.write_text(
        '---\ntitle: "原标题"\ndate: 2026-03-25\n---\n\n\n原正文\n',
        encoding="utf-8",
    )

    with patch("tools.edit_journal.update_vector_index", return_value=True):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={
                "related_entries": "Journals/2026/03/a.md, Journals/2026/03/b.md"
            },
        )

    assert result["success"] is True
    written = journal_path.read_text(encoding="utf-8")
    assert (
        'related_entries: ["Journals/2026/03/a.md", "Journals/2026/03/b.md"]' in written
    )


def test_edit_journal_cli_parses_set_related_entries(
    monkeypatch, tmp_path: Path
) -> None:
    captured: dict = {}

    def fake_edit_journal(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "journal_path": str(kwargs["journal_path"]),
            "changes": {},
            "revision_path": None,
        }

    monkeypatch.setattr("tools.edit_journal.__main__.edit_journal", fake_edit_journal)
    monkeypatch.setattr("tools.edit_journal.__main__.ensure_dirs", lambda: None)
    monkeypatch.setattr("tools.edit_journal.__main__._emit_json", lambda payload: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "edit_journal",
            "--journal",
            str(tmp_path / "sample.md"),
            "--set-related-entries",
            "Journals/2026/03/a.md, Journals/2026/03/b.md",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert captured["frontmatter_updates"]["related_entries"] == [
        "Journals/2026/03/a.md",
        "Journals/2026/03/b.md",
    ]


def test_edit_journal_add_related_entry(tmp_path: Path) -> None:
    journal_path = tmp_path / "life-index_2026-03-25_001.md"
    journal_path.write_text(
        '---\ntitle: "原标题"\ndate: 2026-03-25\nrelated_entries: ["Journals/2026/03/a.md"]\n---\n\n\n原正文\n',
        encoding="utf-8",
    )

    with patch("tools.edit_journal.update_vector_index", return_value=True):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"add_related_entries": ["Journals/2026/03/b.md"]},
        )

    assert result["success"] is True
    written = journal_path.read_text(encoding="utf-8")
    assert (
        'related_entries: ["Journals/2026/03/a.md", "Journals/2026/03/b.md"]' in written
    )


def test_edit_journal_remove_related_entry(tmp_path: Path) -> None:
    journal_path = tmp_path / "life-index_2026-03-25_001.md"
    journal_path.write_text(
        '---\ntitle: "原标题"\ndate: 2026-03-25\nrelated_entries: ["Journals/2026/03/a.md", "Journals/2026/03/b.md"]\n---\n\n\n原正文\n',
        encoding="utf-8",
    )

    with patch("tools.edit_journal.update_vector_index", return_value=True):
        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"remove_related_entries": ["Journals/2026/03/a.md"]},
        )

    assert result["success"] is True
    written = journal_path.read_text(encoding="utf-8")
    assert 'related_entries: ["Journals/2026/03/b.md"]' in written


def test_edit_journal_updates_relation_table_incrementally(tmp_path: Path) -> None:
    journal_path = tmp_path / "Journals" / "2026" / "03" / "source.md"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(
        '---\ntitle: "原标题"\ndate: 2026-03-25\nrelated_entries: ["Journals/2026/03/a.md"]\n---\n\n\n原正文\n',
        encoding="utf-8",
    )

    import tools.lib.metadata_cache as mc

    with (
        patch("tools.edit_journal.update_vector_index", return_value=True),
        patch("tools.edit_journal.JOURNALS_DIR", tmp_path / "Journals"),
        patch.object(mc, "USER_DATA_DIR", tmp_path),
        patch.object(mc, "JOURNALS_DIR", tmp_path / "Journals"),
        patch.object(mc, "CACHE_DIR", tmp_path / ".cache"),
        patch.object(mc, "METADATA_DB_PATH", tmp_path / ".cache" / "metadata_cache.db"),
    ):
        conn = mc.init_metadata_cache()
        try:
            mc.add_entry_relations(
                conn,
                "Journals/2026/03/source.md",
                ["Journals/2026/03/a.md"],
            )
        finally:
            conn.close()

        result = edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"add_related_entries": ["Journals/2026/03/b.md"]},
        )

        conn = mc.init_metadata_cache()
        try:
            backlinks_a = mc.get_backlinked_by(conn, "Journals/2026/03/a.md")
            backlinks_b = mc.get_backlinked_by(conn, "Journals/2026/03/b.md")
        finally:
            conn.close()

    assert result["success"] is True
    assert backlinks_a == ["Journals/2026/03/source.md"]
    assert backlinks_b == ["Journals/2026/03/source.md"]


def test_edit_journal_cli_parses_add_related_entry(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    def fake_edit_journal(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "journal_path": str(kwargs["journal_path"]),
            "changes": {},
            "revision_path": None,
        }

    monkeypatch.setattr("tools.edit_journal.__main__.edit_journal", fake_edit_journal)
    monkeypatch.setattr("tools.edit_journal.__main__.ensure_dirs", lambda: None)
    monkeypatch.setattr("tools.edit_journal.__main__._emit_json", lambda payload: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "edit_journal",
            "--journal",
            str(tmp_path / "sample.md"),
            "--add-related-entry",
            "Journals/2026/03/a.md",
            "--add-related-entry",
            "Journals/2026/03/b.md",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert captured["frontmatter_updates"]["add_related_entries"] == [
        "Journals/2026/03/a.md",
        "Journals/2026/03/b.md",
    ]


def test_edit_journal_cli_parses_remove_related_entry(
    monkeypatch, tmp_path: Path
) -> None:
    captured: dict = {}

    def fake_edit_journal(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "journal_path": str(kwargs["journal_path"]),
            "changes": {},
            "revision_path": None,
        }

    monkeypatch.setattr("tools.edit_journal.__main__.edit_journal", fake_edit_journal)
    monkeypatch.setattr("tools.edit_journal.__main__.ensure_dirs", lambda: None)
    monkeypatch.setattr("tools.edit_journal.__main__._emit_json", lambda payload: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "edit_journal",
            "--journal",
            str(tmp_path / "sample.md"),
            "--remove-related-entry",
            "Journals/2026/03/a.md",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert captured["frontmatter_updates"]["remove_related_entries"] == [
        "Journals/2026/03/a.md"
    ]
