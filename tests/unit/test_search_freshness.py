"""Tests for search index freshness checking (Round 9 T1.1)."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def fts_db(tmp_path: Path):
    """Create a temporary FTS database for testing."""
    db_path = tmp_path / ".index" / "journals_fts.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS journals USING fts5(
            path, title, content, date, location, weather,
            topic, project, tags, mood, people,
            file_hash UNINDEXED, modified_time UNINDEXED
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()
    return db_path


def _write_meta(db_path: Path, entries: dict[str, str]) -> None:
    conn = sqlite3.connect(str(db_path))
    for key, value in entries.items():
        conn.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()
    conn.close()


class TestCheckIndexFreshness:
    """Test check_index_freshness() public API."""

    def test_no_fts_db(self, tmp_path: Path) -> None:
        from tools.lib.search_index import check_index_freshness

        with patch("tools.lib.search_index.get_fts_db_path", lambda: tmp_path / "nonexistent.db"):
            result = check_index_freshness()
        assert result["stale"] is True
        assert result["reason"] == "no_fts_db"
        assert result["fts_document_count"] == 0

    def test_no_meta(self, fts_db: Path) -> None:
        from tools.lib.search_index import check_index_freshness

        with patch("tools.lib.search_index.get_fts_db_path", lambda: fts_db):
            result = check_index_freshness()
        assert result["stale"] is True
        assert result["reason"] == "no_meta"

    def test_tokenizer_mismatch(self, fts_db: Path) -> None:
        from tools.lib.search_index import check_index_freshness
        from tools.lib.search_constants import TOKENIZER_VERSION

        _write_meta(
            fts_db,
            {
                "tokenizer_version": str(TOKENIZER_VERSION + 999),
                "schema_version": "1",
                "dict_hash": "fake",
            },
        )
        with patch("tools.lib.search_index.get_fts_db_path", lambda: fts_db):
            result = check_index_freshness()
        assert result["stale"] is True
        assert result["reason"] == "tokenizer_mismatch"

    def test_schema_mismatch(self, fts_db: Path) -> None:
        from tools.lib.search_index import check_index_freshness
        from tools.lib.search_constants import TOKENIZER_VERSION

        _write_meta(
            fts_db,
            {
                "tokenizer_version": str(TOKENIZER_VERSION),
                "schema_version": "999",
                "dict_hash": "fake",
            },
        )
        with patch("tools.lib.search_index.get_fts_db_path", lambda: fts_db):
            result = check_index_freshness()
        assert result["stale"] is True
        assert result["reason"] == "schema_mismatch"

    def test_dict_hash_mismatch(self, fts_db: Path) -> None:
        from tools.lib.search_index import check_index_freshness
        from tools.lib.search_constants import TOKENIZER_VERSION
        from tools.lib.search_index import FTS_SCHEMA_VERSION

        _write_meta(
            fts_db,
            {
                "tokenizer_version": str(TOKENIZER_VERSION),
                "schema_version": str(FTS_SCHEMA_VERSION),
                "dict_hash": "definitely_wrong_hash",
            },
        )
        with patch("tools.lib.search_index.get_fts_db_path", lambda: fts_db):
            result = check_index_freshness()
        # dict_hash mismatch may or may not be detected depending on
        # whether entity_graph.yaml exists — but staleness should be True
        assert result["stale"] is True

    def test_fresh_index(self, fts_db: Path) -> None:
        from tools.lib.search_index import (
            check_index_freshness,
            init_fts_db,
            write_index_meta,
        )

        # Properly initialize with current version
        with patch("tools.lib.search_index.get_fts_db_path", lambda: fts_db):
            with patch("tools.lib.search_index.get_index_dir", lambda: fts_db.parent):
                conn = init_fts_db()
                write_index_meta(conn)
                conn.close()
                result = check_index_freshness()

        assert result["stale"] is False
        assert result["reason"] is None
        assert result["fts_document_count"] == 0
        assert result["last_updated"] is not None

    def test_freshness_in_search_result(self, tmp_path: Path) -> None:
        """Test that hierarchical_search includes index_status in result."""
        from tools.lib.index_freshness import FreshnessReport

        # Mock the freshness guard so we don't touch real data / trigger auto-index
        fresh_report = FreshnessReport(
            fts_fresh=True, vector_fresh=True, overall_fresh=True, issues=[]
        )

        with patch(
            "tools.lib.index_freshness.check_full_freshness", return_value=fresh_report
        ):
            with patch("tools.lib.pending_writes.has_pending", return_value=False):
                from tools.search_journals.core import hierarchical_search

                result = hierarchical_search(query="test", level=3, semantic=False)

        assert "index_status" in result
        # Phase 3 contract: freshness sub-dict, not flat "stale" key
        assert "freshness" in result["index_status"]
        assert "overall_fresh" in result["index_status"]["freshness"]
        assert isinstance(result["index_status"]["freshness"]["overall_fresh"], bool)
