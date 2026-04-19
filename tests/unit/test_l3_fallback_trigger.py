"""Tests for L3 fulltext fallback trigger conditions (D9)."""

import sqlite3
import time
from pathlib import Path

from unittest.mock import patch


class TestHasWritesSince:
    def test_no_files_newer(self, tmp_path: Path) -> None:
        """All files older than ts -> False (index is fresh)."""
        from tools.lib.fs_consistency import has_writes_since

        year_dir = tmp_path / "2026" / "03"
        year_dir.mkdir(parents=True)

        journal = year_dir / "life-index_2026-03-01_001.md"
        journal.write_text("test", encoding="utf-8")
        file_mtime = journal.stat().st_mtime

        assert has_writes_since(file_mtime + 1, tmp_path) is False

    def test_file_newer_than_ts(self, tmp_path: Path) -> None:
        """A file with mtime > ts -> True (index is stale)."""
        from tools.lib.fs_consistency import has_writes_since

        year_dir = tmp_path / "2026" / "03"
        year_dir.mkdir(parents=True)

        ts = time.time() - 100
        journal = year_dir / "life-index_2026-03-01_001.md"
        journal.write_text("test", encoding="utf-8")

        assert has_writes_since(ts, tmp_path) is True

    def test_nonexistent_root(self, tmp_path: Path) -> None:
        """Non-existent root -> False."""
        from tools.lib.fs_consistency import has_writes_since

        assert has_writes_since(0, tmp_path / "nonexistent") is False

    def test_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory -> False."""
        from tools.lib.fs_consistency import has_writes_since

        assert has_writes_since(0, tmp_path) is False


class TestGetLastSyncTs:
    def test_valid_timestamp(self, tmp_path: Path) -> None:
        """Valid last_updated in index_meta -> returns float."""
        from tools.lib.fs_consistency import get_last_sync_ts

        db_path = tmp_path / "journals_fts.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE index_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO index_meta VALUES ('last_updated', '2026-04-17T12:00:00+00:00')"
        )
        conn.commit()
        conn.close()

        ts = get_last_sync_ts(db_path)
        assert ts is not None
        assert isinstance(ts, float)

    def test_missing_key(self, tmp_path: Path) -> None:
        """No last_updated key -> None."""
        from tools.lib.fs_consistency import get_last_sync_ts

        db_path = tmp_path / "journals_fts.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE index_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.close()

        assert get_last_sync_ts(db_path) is None

    def test_no_db_file(self, tmp_path: Path) -> None:
        """No SQLite file -> None."""
        from tools.lib.fs_consistency import get_last_sync_ts

        assert get_last_sync_ts(tmp_path / "nonexistent.db") is None


class TestL3FallbackTrigger:
    def test_skips_full_scan_when_fts_is_fresh(self) -> None:
        """Fresh index + low FTS recall should not trigger full scan."""
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
            patch("tools.lib.fs_consistency.get_last_sync_ts", return_value=123.0),
            patch("tools.lib.fs_consistency.has_writes_since", return_value=False),
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

    def test_triggers_full_scan_when_index_is_stale(self) -> None:
        """Low FTS recall should still trigger scan when files are newer."""
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
            patch("tools.lib.fs_consistency.get_last_sync_ts", return_value=123.0),
            patch("tools.lib.fs_consistency.has_writes_since", return_value=True),
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

    def test_triggers_full_scan_when_last_sync_is_missing(self) -> None:
        """Old index without last_updated metadata should still fallback."""
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
            patch("tools.lib.fs_consistency.get_last_sync_ts", return_value=None),
            patch("tools.search_journals.keyword_pipeline.search_l3_content", return_value=[])
            as mock_scan,
        ):
            mock_l2.return_value = {
                "results": [],
                "truncated": False,
                "total_available": 0,
            }

            run_keyword_pipeline(query="needle")

        mock_scan.assert_called_once()
