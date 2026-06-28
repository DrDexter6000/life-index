#!/usr/bin/env python3
"""
Unit tests for tools/build_index/__init__.py
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.build_index import build_all, show_stats


@pytest.mark.critical
class TestBuildAll:
    """Tests for build_all function"""

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_fts_success(self, mock_update_fts, mock_file_lock, mock_lock_path):
        """Test successful FTS index update"""
        # Setup mocks
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {
            "success": True,
            "added": 5,
            "updated": 2,
            "removed": 1,
        }

        result = build_all(incremental=True)

        assert result["success"] is True
        assert result["fts"]["success"] is True
        assert result["fts"]["added"] == 5
        assert result["vector"] is None
        assert result["semantic_status"] == "disabled"
        mock_update_fts.assert_called_once_with(incremental=True)

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_fts_failure(self, mock_update_fts, mock_file_lock, mock_lock_path):
        """Test FTS index update failure"""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {
            "success": False,
            "error": "Database locked",
        }

        result = build_all(incremental=True)

        assert result["success"] is False
        assert result["fts"]["success"] is False
        assert "error" in result["fts"]
        assert result["vector"] is None

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_fts_exception(self, mock_update_fts, mock_file_lock, mock_lock_path):
        """Test FTS index update with exception"""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.side_effect = RuntimeError("Unexpected error")

        result = build_all(incremental=True)

        assert result["success"] is False
        assert result["fts"]["success"] is False
        assert "Unexpected error" in result["fts"]["error"]
        assert result["vector"] is None

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_fts_only_mode(self, mock_update_fts, mock_file_lock, mock_lock_path):
        """Test FTS-only mode skips vector index"""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {"success": True, "added": 1}

        result = build_all(fts_only=True)

        assert result["success"] is True
        assert result["fts"]["success"] is True
        assert result["vector"] is None  # Should be None when fts_only=True

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_env_fts_only_skips_vector(
        self, mock_update_fts, mock_file_lock, mock_lock_path, monkeypatch
    ):
        """CI can force FTS-only builds without changing user defaults."""
        monkeypatch.setenv("LIFE_INDEX_INDEX_FTS_ONLY", "1")
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)
        mock_update_fts.return_value = {"success": True, "added": 1}

        result = build_all()

        assert result["success"] is True
        assert result["fts"]["success"] is True
        assert result["vector"] is None

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_fts_only_reports_semantic_disabled(
        self, mock_update_fts, mock_file_lock, mock_lock_path
    ):
        """FTS-only builds should honestly report semantic indexing as disabled."""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)
        mock_update_fts.return_value = {"success": True, "added": 1}

        result = build_all(fts_only=True)

        assert result["success"] is True
        assert result["semantic_status"] == "disabled"

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    def test_build_all_vec_only_mode(self, mock_file_lock, mock_lock_path):
        """Test vector-only mode skips FTS index"""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        result = build_all(vec_only=True)

        assert result["success"] is True
        assert result["fts"] is None
        assert result["vector"] is None
        assert result["semantic_status"] == "disabled"
        assert any("deprecated_noop" in warning for warning in result["warnings"])

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_does_not_build_sqlite_vec(
        self, mock_update_fts, mock_file_lock, mock_lock_path, monkeypatch
    ):
        """Default builds no longer call the sqlite-vec semantic backend."""
        monkeypatch.delenv("LIFE_INDEX_INDEX_FTS_ONLY", raising=False)
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {"success": True, "added": 0}

        with (
            patch("tools.lib.semantic_search.get_model") as mock_model,
            patch("tools.lib.semantic_search.update_vector_index") as mock_vec,
        ):
            result = build_all(incremental=True)

        assert result["success"] is True
        assert result["vector"] is None
        mock_model.assert_not_called()
        mock_vec.assert_not_called()

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_does_not_build_simple_vector_fallback(
        self, mock_update_fts, mock_file_lock, mock_lock_path, monkeypatch
    ):
        """Default builds no longer fall back to the simple vector backend."""
        monkeypatch.delenv("LIFE_INDEX_INDEX_FTS_ONLY", raising=False)
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {"success": True, "added": 0}

        with patch("tools.lib.vector_index_simple.update_vector_index_simple") as mock_simple:
            result = build_all(incremental=True)

        assert result["success"] is True
        assert result["vector"] is None
        mock_simple.assert_not_called()

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_full_rebuild(self, mock_update_fts, mock_file_lock, mock_lock_path):
        """Test full rebuild mode (incremental=False)"""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {"success": True, "added": 10}

        result = build_all(incremental=False)

        assert result["success"] is True
        # Verify incremental=False is passed
        mock_update_fts.assert_called_once_with(incremental=False)

    @patch("tools.build_index.update_cache_for_all_journals")
    @patch("tools.build_index.invalidate_cache")
    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_full_rebuild_refreshes_metadata_cache(
        self,
        mock_update_fts,
        mock_file_lock,
        mock_lock_path,
        mock_invalidate_cache,
        mock_update_cache,
    ):
        """Full rebuild should refresh metadata cache used by dashboard/search."""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {"success": True, "added": 10}
        mock_update_cache.return_value = {"updated": 42, "skipped": 0, "errors": 0}

        build_all(incremental=False)

        mock_invalidate_cache.assert_called_once_with()
        mock_update_cache.assert_called_once_with()

    @patch("tools.build_index.rebuild_entry_relations")
    @patch("tools.build_index.update_cache_for_all_journals")
    @patch("tools.build_index.invalidate_cache")
    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_full_rebuild_refreshes_entry_relations(
        self,
        mock_update_fts,
        mock_file_lock,
        mock_lock_path,
        mock_invalidate_cache,
        mock_update_cache,
        mock_rebuild_relations,
    ):
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {"success": True, "added": 10}
        mock_update_cache.return_value = {"updated": 42, "skipped": 0, "errors": 0}

        build_all(incremental=False)

        mock_rebuild_relations.assert_called_once()

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.create_error_response")
    def test_build_all_lock_timeout(self, mock_error_response, mock_file_lock, mock_lock_path):
        """Test lock timeout returns proper error response"""
        from tools.build_index import LockTimeoutError

        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock

        # Simulate lock timeout
        mock_lock.__enter__.side_effect = LockTimeoutError("/tmp/test.lock", 60.0)

        mock_error_response.return_value = {
            "success": False,
            "error": "Lock timeout",
            "error_code": "LOCK_TIMEOUT",
        }

        result = build_all()

        assert result["success"] is False
        mock_error_response.assert_called_once()

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_duration_tracking(self, mock_update_fts, mock_file_lock, mock_lock_path):
        """Test duration_seconds is tracked"""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {"success": True, "added": 0}

        result = build_all()

        assert "duration_seconds" in result
        assert isinstance(result["duration_seconds"], (int, float))
        assert result["duration_seconds"] >= 0

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_includes_rebuild_hint(self, mock_update_fts, mock_file_lock, mock_lock_path):
        """Build results should surface rebuild guidance for historical cache format cleanup."""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {"success": True, "added": 0}

        result = build_all()

        assert "rebuild_hint" in result
        assert "life-index index --rebuild" in result["rebuild_hint"]


class TestIndexCliNonBlockingDefault:
    """CLI-level contract for onboarding-safe index defaults."""

    def test_index_cli_default_uses_fts_only_without_background(self, monkeypatch, capsys):
        import tools.build_index.__main__ as index_cli

        monkeypatch.delenv("LIFE_INDEX_INDEX_FTS_ONLY", raising=False)
        calls: list[dict[str, object]] = []

        def fake_build_all(**kwargs):
            calls.append(kwargs)
            return {
                "success": True,
                "fts": {"success": True, "duration_seconds": 0.01},
                "vector": None,
                "semantic_status": "disabled",
                "duration_seconds": 0.01,
            }

        monkeypatch.setattr("sys.argv", ["life-index-index", "--json"])
        monkeypatch.setattr(index_cli, "build_all", fake_build_all)
        monkeypatch.setattr(index_cli, "ensure_dirs", lambda: None)
        index_cli.main()

        payload = capsys.readouterr().out
        assert calls == [{"incremental": True, "fts_only": True, "vec_only": False}]
        assert '"semantic_status": "disabled"' in payload

    def test_index_cli_fts_only_does_not_start_background(self, monkeypatch, capsys):
        import tools.build_index.__main__ as index_cli

        monkeypatch.delenv("LIFE_INDEX_INDEX_FTS_ONLY", raising=False)
        started = {"called": False}

        def fake_build_all(**kwargs):
            return {
                "success": True,
                "fts": {"success": True, "duration_seconds": 0.01},
                "vector": None,
                "semantic_status": "disabled",
                "duration_seconds": 0.01,
            }

        def fake_start_background_semantic_build(*, incremental):
            started["called"] = True
            return {"status": "building"}

        monkeypatch.setattr("sys.argv", ["life-index-index", "--fts-only", "--json"])
        monkeypatch.setattr(index_cli, "build_all", fake_build_all)
        monkeypatch.setattr(index_cli, "ensure_dirs", lambda: None)
        monkeypatch.setattr(
            index_cli,
            "start_background_semantic_build",
            fake_start_background_semantic_build,
            raising=False,
        )

        index_cli.main()

        payload = capsys.readouterr().out
        assert started["called"] is False
        assert '"semantic_status": "disabled"' in payload

    def test_index_cli_env_fts_only_does_not_start_background(self, monkeypatch, capsys):
        import tools.build_index.__main__ as index_cli

        started = {"called": False}

        def fake_build_all(**kwargs):
            return {
                "success": True,
                "fts": {"success": True, "duration_seconds": 0.01},
                "vector": None,
                "semantic_status": "disabled",
                "duration_seconds": 0.01,
            }

        def fake_start_background_semantic_build(*, incremental):
            started["called"] = True
            return {"status": "building"}

        monkeypatch.setenv("LIFE_INDEX_INDEX_FTS_ONLY", "1")
        monkeypatch.setattr("sys.argv", ["life-index-index", "--json"])
        monkeypatch.setattr(index_cli, "build_all", fake_build_all)
        monkeypatch.setattr(index_cli, "ensure_dirs", lambda: None)
        monkeypatch.setattr(
            index_cli,
            "start_background_semantic_build",
            fake_start_background_semantic_build,
            raising=False,
        )

        index_cli.main()

        payload = capsys.readouterr().out
        assert started["called"] is False
        assert '"semantic_status": "disabled"' in payload


class TestShowStats:
    """Tests for show_stats function"""

    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_fts_exists(self, mock_fts_stats):
        """Test show_stats with FTS index"""
        mock_fts_stats.return_value = {
            "exists": True,
            "total_documents": 100,
            "db_size_mb": 1.5,
            "last_updated": "2026-03-14T10:00:00",
        }

        with patch("tools.lib.semantic_search.get_stats") as mock_vec:
            mock_vec.return_value = {
                "exists": True,
                "total_vectors": 200,
                "model_loaded": True,
                "db_size_mb": 2.5,
            }
            with patch("tools.build_index.logger"):
                show_stats()

        mock_fts_stats.assert_called_once()

    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_fts_not_exists(self, mock_fts_stats):
        """Test show_stats when FTS index doesn't exist"""
        mock_fts_stats.return_value = {
            "exists": False,
            "total_documents": 0,
            "db_size_mb": 0,
            "last_updated": None,
        }

        # Mock semantic_search.get_stats to return existing vector index
        with patch("tools.lib.semantic_search.get_stats") as mock_vec:
            mock_vec.return_value = {
                "exists": True,
                "total_vectors": 10,
                "model_loaded": False,
                "db_size_mb": 0.5,
            }
            with patch("tools.build_index.logger"):
                show_stats()

        mock_fts_stats.assert_called_once()

    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_reports_vector_disabled(self, mock_fts_stats):
        """Stats should explicitly report vector indexing as disabled."""
        mock_fts_stats.return_value = {
            "exists": True,
            "total_documents": 50,
            "db_size_mb": 0.8,
            "last_updated": "2026-03-14T10:00:00",
        }

        with (
            patch("tools.lib.semantic_search.get_stats") as mock_vec,
            patch("tools.build_index.logger") as mock_logger,
        ):
            show_stats()

        mock_fts_stats.assert_called_once()
        mock_vec.assert_not_called()
        logged = "\n".join(str(call.args[0]) for call in mock_logger.info.call_args_list)
        assert "Semantic/Vector Index" in logged
        assert "Disabled" in logged

    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_does_not_fallback_to_simple_vector_index(self, mock_fts_stats):
        """Stats should not inspect legacy simple vector index files."""
        mock_fts_stats.return_value = {
            "exists": True,
            "total_documents": 30,
            "db_size_mb": 0.5,
            "last_updated": "2026-03-14T10:00:00",
        }

        with (
            patch("tools.lib.semantic_search.get_stats") as mock_vec,
            patch("tools.lib.vector_index_simple.get_index") as mock_get_index,
            patch("tools.build_index.logger"),
        ):
            show_stats()

        mock_fts_stats.assert_called_once()
        mock_vec.assert_not_called()
        mock_get_index.assert_not_called()

    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_no_vector_backend(self, mock_fts_stats):
        """Test show_stats when no vector backend available"""
        mock_fts_stats.return_value = {
            "exists": True,
            "total_documents": 10,
            "db_size_mb": 0.2,
            "last_updated": None,
        }

        with patch("tools.build_index.logger"):
            show_stats()

        mock_fts_stats.assert_called_once()

    @patch("tools.build_index.get_fts_stats")
    @patch("tools.build_index.get_cache_stats")
    def test_show_stats_reports_metadata_cache(self, mock_cache_stats, mock_fts_stats):
        """Stats should still include metadata cache information."""
        mock_fts_stats.return_value = {
            "exists": True,
            "total_documents": 5,
            "db_size_mb": 0.1,
            "last_updated": None,
        }
        mock_cache_stats.return_value = {
            "total_entries": 5,
            "db_size_mb": 0.1,
            "last_updated": None,
            "last_update": None,
            "cache_path": "C:/tmp/metadata_cache.db",
            "rebuild_hint": "",
        }

        with patch("tools.build_index.logger") as mock_logger:
            show_stats()

        logged = "\n".join(str(call.args[0]) for call in mock_logger.info.call_args_list)
        assert "Metadata Cache" in logged
        assert "Entries: 5" in logged

    @patch("tools.build_index.get_fts_stats")
    @patch("tools.build_index.get_cache_stats")
    def test_show_stats_logs_metadata_cache_rebuild_hint(self, mock_cache_stats, mock_fts_stats):
        """Stats output should surface metadata cache rebuild guidance."""
        mock_fts_stats.return_value = {
            "exists": True,
            "total_documents": 5,
            "db_size_mb": 0.1,
            "last_updated": None,
        }
        mock_cache_stats.return_value = {
            "total_entries": 10,
            "db_size_mb": 0.2,
            "last_update": "2026-03-14T10:00:00",
            "cache_path": "C:/tmp/metadata_cache.db",
            "rebuild_hint": "如发现旧缓存路径格式导致的异常，可执行 `life-index index --rebuild` 进行重建。",
        }

        with patch("tools.build_index.logger") as mock_logger:
            show_stats()

        logged = "\n".join(str(call.args[0]) for call in mock_logger.info.call_args_list)
        assert "metadata cache" in logged.lower()
        assert "life-index index --rebuild" in logged


class TestIntegration:
    """Integration-style tests for build_all"""

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_full_workflow_success(
        self, mock_update_fts, mock_file_lock, mock_lock_path, monkeypatch
    ):
        """Test complete successful workflow"""
        monkeypatch.delenv("LIFE_INDEX_INDEX_FTS_ONLY", raising=False)
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {
            "success": True,
            "added": 10,
            "updated": 5,
            "removed": 2,
        }

        with patch("tools.lib.semantic_search.update_vector_index") as mock_vec:
            result = build_all(incremental=True)

        # Verify result structure
        assert result["success"] is True
        assert "fts" in result
        assert "vector" in result
        assert "duration_seconds" in result

        # Verify FTS result
        assert result["fts"]["success"] is True
        assert result["fts"]["added"] == 10
        assert result["fts"]["updated"] == 5
        assert result["fts"]["removed"] == 2

        assert result["vector"] is None
        mock_vec.assert_not_called()

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_partial_failure_continues(
        self, mock_update_fts, mock_file_lock, mock_lock_path, monkeypatch
    ):
        """FTS failure remains the overall failure; vector build is removed."""
        monkeypatch.delenv("LIFE_INDEX_INDEX_FTS_ONLY", raising=False)
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        # FTS fails
        mock_update_fts.return_value = {
            "success": False,
            "error": "Database error",
        }

        with patch("tools.lib.semantic_search.update_vector_index") as mock_vec:
            result = build_all(incremental=True)

        # Overall should fail because FTS failed
        assert result["success"] is False
        assert result["vector"] is None
        mock_vec.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
