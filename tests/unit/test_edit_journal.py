from pathlib import Path
from unittest.mock import patch

from tools.edit_journal import edit_journal


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
