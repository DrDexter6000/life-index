"""Tests for freshness observability (Phase 2b-4).

Covers:
- jieba_version stored in index_meta during write_index_meta()
- jieba version mismatch emits INFO reindex suggestion
- dict_hash mismatch emits INFO suggestion
- Legacy index_meta without jieba_version doesn't crash
- RRF small-n (n < 8) emits observable event in hybrid results
"""

import logging
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.lib.search_index import init_fts_db, write_index_meta
from tools.search_journals.ranking import merge_and_rank_results_hybrid


@pytest.fixture
def fts_conn(tmp_path: Path, monkeypatch):
    """Create an isolated FTS database for testing."""
    import tools.lib.paths as paths_mod
    import tools.lib.search_index as si_mod

    idx = tmp_path / ".index"
    idx.mkdir(parents=True)
    data = tmp_path / "Life-Index"
    (data / "Journals" / "2026" / "03").mkdir(parents=True)

    monkeypatch.setattr(paths_mod, "get_index_dir", lambda: idx)
    monkeypatch.setattr(paths_mod, "get_fts_db_path", lambda: idx / "journals_fts.db")
    monkeypatch.setattr(paths_mod, "get_journals_dir", lambda: data / "Journals")
    monkeypatch.setattr(paths_mod, "get_user_data_dir", lambda: data)
    monkeypatch.setattr(si_mod, "INDEX_DIR", idx)
    monkeypatch.setattr(si_mod, "FTS_DB_PATH", idx / "journals_fts.db")
    monkeypatch.setattr(si_mod, "USER_DATA_DIR", data)
    monkeypatch.setattr(si_mod, "JOURNALS_DIR", data / "Journals")

    conn = init_fts_db()
    yield conn
    conn.close()


class TestJiebaVersionInIndexMeta:
    """Part 1: jieba_version key stored in index_meta."""

    def test_jieba_version_stored_in_index_meta(self, fts_conn: sqlite3.Connection):
        """write_index_meta includes jieba_version key."""
        with patch("tools.lib.search_index.get_dict_hash", return_value="abc123"):
            write_index_meta(fts_conn)

        cursor = fts_conn.cursor()
        cursor.execute("SELECT value FROM index_meta WHERE key = 'jieba_version'")
        row = cursor.fetchone()
        assert row is not None, "jieba_version key must exist in index_meta"
        # Value should be a non-empty string (actual jieba version)
        assert isinstance(row[0], str)
        assert len(row[0]) > 0

    def test_stored_jieba_version_matches_runtime(self, fts_conn: sqlite3.Connection):
        """Stored version matches the currently installed jieba version."""
        import jieba

        with patch("tools.lib.search_index.get_dict_hash", return_value="abc123"):
            write_index_meta(fts_conn)

        cursor = fts_conn.cursor()
        cursor.execute("SELECT value FROM index_meta WHERE key = 'jieba_version'")
        row = cursor.fetchone()
        assert row[0] == jieba.__version__


class TestTokenizerFreshnessLogging:
    """Part 2: Freshness logging for jieba version and dict_hash."""

    def test_jieba_version_mismatch_emits_reindex_suggestion(
        self, fts_conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
    ):
        """Mock version mismatch → log INFO suggestion to rebuild."""
        # Write a stale jieba_version
        cursor = fts_conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            ("jieba_version", "0.0.1-old"),
        )
        fts_conn.commit()

        from tools.lib.index_freshness import check_tokenizer_freshness

        db_path = fts_conn.execute("PRAGMA database_list").fetchone()[2]

        with caplog.at_level(logging.INFO, logger="tools.lib.index_freshness"):
            check_tokenizer_freshness(Path(db_path))

        assert any(
            "differs from index's" in record.message and "jieba" in record.message.lower()
            for record in caplog.records
        ), f"Expected jieba version mismatch log, got: {[r.message for r in caplog.records]}"

    def test_dict_hash_mismatch_emits_suggestion(
        self, fts_conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
    ):
        """Mock hash mismatch → log INFO suggestion."""
        cursor = fts_conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            ("dict_hash", "stale_hash_999"),
        )
        fts_conn.commit()

        from tools.lib.index_freshness import check_tokenizer_freshness

        db_path = fts_conn.execute("PRAGMA database_list").fetchone()[2]

        with (
            caplog.at_level(logging.INFO, logger="tools.lib.index_freshness"),
            patch("tools.lib.chinese_tokenizer.get_dict_hash", return_value="new_hash_123"),
        ):
            check_tokenizer_freshness(Path(db_path))

        assert any(
            "differs from index's" in record.message and "dict hash" in record.message.lower()
            for record in caplog.records
        ), f"Expected dict hash mismatch log, got: {[r.message for r in caplog.records]}"

    def test_legacy_index_meta_without_jieba_version_no_crash(
        self, fts_conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
    ):
        """Missing jieba_version key doesn't crash — backward compatible."""
        from tools.lib.index_freshness import check_tokenizer_freshness

        db_path = fts_conn.execute("PRAGMA database_list").fetchone()[2]

        # Should not raise any exception
        with caplog.at_level(logging.INFO, logger="tools.lib.index_freshness"):
            check_tokenizer_freshness(Path(db_path))

        # No jieba mismatch log should appear (no stored version to compare)
        jieba_logs = [
            r for r in caplog.records if "jieba" in r.message.lower() and "differs" in r.message
        ]
        assert len(jieba_logs) == 0

    def test_no_db_file_no_crash(self, tmp_path: Path):
        """Non-existent FTS DB doesn't crash."""
        from tools.lib.index_freshness import check_tokenizer_freshness

        # Should silently return
        check_tokenizer_freshness(tmp_path / "nonexistent.db")


class TestRRFSmallNObservability:
    """Part 3: RRF small-n event in merge_and_rank_results_hybrid."""

    def _make_result(self, path: str, relevance: int = 50, similarity: float = 0.7) -> dict:
        """Create a minimal search result dict."""
        return {
            "path": path,
            "title": f"Entry {path}",
            "relevance": relevance,
            "similarity": similarity,
            "metadata": {},
        }

    def test_rrf_small_n_emits_observable_event(self):
        """n=3 scenario → event appears in result dicts."""
        l3_results = [
            self._make_result("a.md", relevance=80),
            self._make_result("b.md", relevance=60),
        ]
        semantic_results = [
            self._make_result("a.md", similarity=0.8),
            self._make_result("c.md", similarity=0.7),
        ]

        with (
            patch(
                "tools.search_journals.ranking.init_metadata_cache",
                return_value=sqlite3.connect(":memory:"),
            ),
            patch("tools.search_journals.ranking.enrich_semantic_result", side_effect=lambda r: r),
        ):
            results = merge_and_rank_results_hybrid(
                l1_results=[],
                l2_results=[],
                l3_results=l3_results,
                semantic_results=semantic_results,
                query="test",
            )

        # With 3 unique paths (a, b, c), n=3 < 8
        assert len(results) > 0
        # At least one result should have the event
        events_found = []
        for r in results:
            events = r.get("events", [])
            events_found.extend([e for e in events if e.get("event") == "rrf_small_n_fallback"])
        assert len(events_found) > 0, "Expected rrf_small_n_fallback event in results"
        event = events_found[0]
        assert event["n"] == 3
        assert event["fallback_threshold"] == 8
        assert "score_stats" in event
        stats = event["score_stats"]
        assert stats["count"] == 3
        assert stats["min"] <= stats["max"]
        assert "mean" in stats

    def test_rrf_large_n_no_event(self):
        """n >= 8 → no small-n event emitted."""
        # Create 10 FTS results and 5 semantic results (some overlap)
        l3_results = [self._make_result(f"doc_{i}.md", relevance=80 - i) for i in range(10)]
        semantic_results = [
            self._make_result(f"doc_{i}.md", similarity=0.9 - i * 0.05) for i in range(5)
        ]

        with (
            patch(
                "tools.search_journals.ranking.init_metadata_cache",
                return_value=sqlite3.connect(":memory:"),
            ),
            patch("tools.search_journals.ranking.enrich_semantic_result", side_effect=lambda r: r),
        ):
            results = merge_and_rank_results_hybrid(
                l1_results=[],
                l2_results=[],
                l3_results=l3_results,
                semantic_results=semantic_results,
                query="test",
            )

        for r in results:
            events = r.get("events", [])
            rrf_events = [e for e in events if e.get("event") == "rrf_small_n_fallback"]
            assert len(rrf_events) == 0, "No small-n event expected when n >= 8"

    def test_rrf_small_n_logs_at_info(self, caplog: pytest.LogCaptureFixture):
        """RRF small-n triggers INFO-level log."""
        l3_results = [self._make_result("a.md", relevance=50)]
        semantic_results = [self._make_result("b.md", similarity=0.6)]

        with (
            caplog.at_level(logging.INFO, logger="tools.search_journals.ranking"),
            patch(
                "tools.search_journals.ranking.init_metadata_cache",
                return_value=sqlite3.connect(":memory:"),
            ),
            patch("tools.search_journals.ranking.enrich_semantic_result", side_effect=lambda r: r),
        ):
            merge_and_rank_results_hybrid(
                l1_results=[],
                l2_results=[],
                l3_results=l3_results,
                semantic_results=semantic_results,
                query="test",
            )

        assert any(
            "RRF small-n fallback" in record.message and "n=2" in record.message
            for record in caplog.records
        ), f"Expected RRF small-n INFO log, got: {[r.message for r in caplog.records]}"
