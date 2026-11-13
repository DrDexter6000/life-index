"""Tests for L3 fulltext fallback trigger conditions (D9).

The fallback rule is the per-fragment signature check
(``fs_consistency.index_is_current`` → ``fts_update.inspect_fts_index``), not
the old "newest journal mtime vs index_meta.last_updated" comparison.
"""

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    import tools.lib.pending_writes as pw_mod

    idx = tmp_path / ".index"
    idx.mkdir(parents=True)
    monkeypatch.setattr(pw_mod, "get_index_dir", lambda: idx)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))


def _journal(tmp_path: Path, name: str, body: str = "test") -> Path:
    month = tmp_path / "Journals" / "2026" / "03"
    month.mkdir(parents=True, exist_ok=True)
    journal = month / name
    journal.write_text(f"---\ntitle: t\ndate: 2026-03-01\n---\n\n{body}\n", encoding="utf-8")
    return journal


class TestIndexIsCurrent:
    def test_current_index(self, tmp_path: Path) -> None:
        """Every live fragment has a row and a matching signature -> current."""
        from tools.lib.fs_consistency import index_is_current
        from tools.lib.search_index import update_index

        _journal(tmp_path, "life-index_2026-03-01_001.md")
        assert update_index(incremental=False)["success"] is True

        assert index_is_current() is True

    def test_outside_edit_is_not_current(self, tmp_path: Path) -> None:
        """An outside edit with no index update -> not current."""
        from tools.lib.fs_consistency import index_is_current
        from tools.lib.search_index import update_index

        journal = _journal(tmp_path, "life-index_2026-03-01_001.md")
        assert update_index(incremental=False)["success"] is True

        journal.write_text(
            journal.read_text(encoding="utf-8") + "\noutside edit\n", encoding="utf-8"
        )

        assert index_is_current() is False

    def test_deleted_file_is_not_current(self, tmp_path: Path) -> None:
        """A row for a vanished file -> not current."""
        from tools.lib.fs_consistency import index_is_current
        from tools.lib.search_index import update_index

        journal = _journal(tmp_path, "life-index_2026-03-01_001.md")
        assert update_index(incremental=False)["success"] is True

        journal.unlink()

        assert index_is_current() is False

    def test_no_index_is_not_current(self, tmp_path: Path) -> None:
        """No FTS database -> not current (fallback stays enabled)."""
        from tools.lib.fs_consistency import index_is_current

        assert index_is_current() is False


class TestL3FallbackTrigger:
    def test_skips_full_scan_when_index_is_current(self) -> None:
        """Current index + low FTS recall should not trigger full scan."""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        fts_rows = [
            {
                "path": "Journals/2026/03/a.md",
                "date": "2026-03-01",
                "title": "A",
                "relevance": 88,
                "location": "",
                "weather": "",
                "topic": [],
                "project": "",
                "tags": [],
                "mood": [],
                "people": [],
            }
        ]

        with (
            patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2,
            patch("tools.lib.search_index.search_fts", return_value=fts_rows),
            patch("tools.lib.fs_consistency.index_is_current", return_value=True),
            patch("tools.search_journals.keyword_pipeline.search_l3_content") as mock_scan,
        ):
            mock_l2.return_value = {
                "results": [],
                "truncated": False,
                "total_available": 0,
            }

            _, _, l3_results, _, _, _ = run_keyword_pipeline(query="irrelevant")

        assert len(l3_results) == 1
        mock_scan.assert_not_called()

    def test_triggers_full_scan_when_index_is_not_current(self) -> None:
        """Low FTS recall should trigger the scan when signatures disagree."""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        fts_rows = [
            {
                "path": "Journals/2026/03/a.md",
                "date": "2026-03-01",
                "title": "A",
                "relevance": 88,
                "location": "",
                "weather": "",
                "topic": [],
                "project": "",
                "tags": [],
                "mood": [],
                "people": [],
            }
        ]
        scan_rows = [
            {
                "path": "Journals/2026/03/b.md",
                "journal_route_path": "Journals/2026/03/b.md",
                "title": "B",
                "relevance": 77,
            }
        ]

        with (
            patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2,
            patch("tools.lib.search_index.search_fts", return_value=fts_rows),
            patch("tools.lib.fs_consistency.index_is_current", return_value=False),
            patch(
                "tools.search_journals.keyword_pipeline.search_l3_content",
                return_value=scan_rows,
            ) as mock_scan,
        ):
            mock_l2.return_value = {
                "results": [],
                "truncated": False,
                "total_available": 0,
            }

            _, _, l3_results, _, _, _ = run_keyword_pipeline(query="needle")

        assert {item.get("title") for item in l3_results} == {"A", "B"}
        mock_scan.assert_called_once()

    def test_preflight_verdict_true_skips_the_second_check(self) -> None:
        """A real preflight verdict avoids a duplicate scan and skips fallback."""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        fts_rows = [
            {
                "path": "Journals/2026/03/a.md",
                "date": "2026-03-01",
                "title": "A",
                "relevance": 88,
                "location": "",
                "weather": "",
                "topic": [],
                "project": "",
                "tags": [],
                "mood": [],
                "people": [],
            }
        ]

        with (
            patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2,
            patch("tools.lib.search_index.search_fts", return_value=fts_rows),
            patch("tools.lib.fs_consistency.index_is_current", return_value=False),
            patch("tools.search_journals.keyword_pipeline.search_l3_content") as mock_scan,
        ):
            mock_l2.return_value = {
                "results": [],
                "truncated": False,
                "total_available": 0,
            }

            _, _, l3_results, _, _, _ = run_keyword_pipeline(
                query="needle", index_signature_current=True
            )

        assert len(l3_results) == 1
        mock_scan.assert_not_called()

    def test_preflight_verdict_false_triggers_the_fallback(self) -> None:
        """A not-current preflight verdict is authoritative for the fallback."""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        fts_rows = [
            {
                "path": "Journals/2026/03/a.md",
                "date": "2026-03-01",
                "title": "A",
                "relevance": 88,
                "location": "",
                "weather": "",
                "topic": [],
                "project": "",
                "tags": [],
                "mood": [],
                "people": [],
            }
        ]

        with (
            patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2,
            patch("tools.lib.search_index.search_fts", return_value=fts_rows),
            patch("tools.lib.fs_consistency.index_is_current", return_value=True),
            patch(
                "tools.search_journals.keyword_pipeline.search_l3_content", return_value=[]
            ) as mock_scan,
        ):
            mock_l2.return_value = {
                "results": [],
                "truncated": False,
                "total_available": 0,
            }

            run_keyword_pipeline(query="needle", index_signature_current=False)

        mock_scan.assert_called_once()
