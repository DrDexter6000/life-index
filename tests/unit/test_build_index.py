#!/usr/bin/env python3
"""
Unit tests for tools/build_index/__init__.py
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.build_index import build_all, show_stats


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

        # Mock vector index to fail (skip vector update)
        with patch("tools.lib.semantic_search.get_model") as mock_model:
            mock_model.return_value.load.return_value = False
            with patch("tools.lib.vector_index_simple.update_vector_index_simple") as mock_simple:
                mock_simple.return_value = {"success": False, "error": "No model"}
                with patch("tools.lib.vector_index_simple.get_model") as mock_simple_model:
                    mock_simple_model.return_value.load.return_value = False

                    result = build_all(incremental=True)

        assert result["success"] is True
        assert result["fts"]["success"] is True
        assert result["fts"]["added"] == 5
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

        with patch("tools.lib.semantic_search.get_model") as mock_model:
            mock_model.return_value.load.return_value = False
            with patch("tools.lib.vector_index_simple.update_vector_index_simple"):
                with patch("tools.lib.vector_index_simple.get_model") as mock_simple_model:
                    mock_simple_model.return_value.load.return_value = False

                    result = build_all(incremental=True)

        assert result["success"] is False
        assert result["fts"]["success"] is False
        assert "error" in result["fts"]

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

        with patch("tools.lib.semantic_search.get_model") as mock_model:
            mock_model.return_value.load.return_value = False
            with patch("tools.lib.vector_index_simple.update_vector_index_simple"):
                with patch("tools.lib.vector_index_simple.get_model") as mock_simple_model:
                    mock_simple_model.return_value.load.return_value = False

                    result = build_all(incremental=True)

        assert result["success"] is False
        assert result["fts"]["success"] is False
        assert "Unexpected error" in result["fts"]["error"]

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
    def test_build_all_vec_only_mode(self, mock_file_lock, mock_lock_path):
        """Test vector-only mode skips FTS index"""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        with patch("tools.lib.semantic_search.get_model") as mock_model:
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance
            mock_model_instance.load.return_value = True

            with patch("tools.lib.semantic_search.update_vector_index") as mock_vec:
                mock_vec.return_value = {"success": True, "added": 3, "updated": 1}

                result = build_all(vec_only=True)

        assert result["success"] is True
        assert result["fts"] is None  # Should be None when vec_only=True
        assert result["vector"]["success"] is True

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_vector_with_sqlite_vec(
        self, mock_update_fts, mock_file_lock, mock_lock_path
    ):
        """Test vector index with sqlite-vec backend"""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {"success": True, "added": 0}

        with patch("tools.lib.semantic_search.get_model") as mock_model:
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance
            mock_model_instance.load.return_value = True

            with patch("tools.lib.semantic_search.update_vector_index") as mock_vec:
                mock_vec.return_value = {"success": True, "added": 5, "updated": 2}

                result = build_all(incremental=True)

        assert result["success"] is True
        assert result["vector"]["success"] is True
        assert result["vector"]["added"] == 5

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_build_all_vector_fallback_to_simple(
        self, mock_update_fts, mock_file_lock, mock_lock_path
    ):
        """Test vector index fallback to simple backend when sqlite-vec fails"""
        mock_lock_path.return_value = Path("/tmp/test.lock")
        mock_lock = MagicMock()
        mock_file_lock.return_value = mock_lock
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_update_fts.return_value = {"success": True, "added": 0}

        # sqlite-vec fails (model.load returns False)
        with patch("tools.lib.semantic_search.get_model") as mock_model:
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance
            mock_model_instance.load.return_value = False
            # simple index succeeds
            with patch("tools.lib.vector_index_simple.update_vector_index_simple") as mock_simple:
                mock_simple.return_value = {"success": True, "added": 3}
                with patch("tools.lib.vector_index_simple.get_model") as mock_simple_model:
                    mock_simple_model_instance = MagicMock()
                    mock_simple_model.return_value = mock_simple_model_instance
                    mock_simple_model_instance.load.return_value = True

                    result = build_all(incremental=True)

        assert result["success"] is True
        assert result["vector"]["success"] is True
        assert result["vector"]["added"] == 3

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

        with patch("tools.lib.semantic_search.get_model") as mock_model:
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance
            mock_model_instance.load.return_value = True
            with patch("tools.lib.semantic_search.update_vector_index") as mock_vec:
                mock_vec.return_value = {"success": True, "added": 10}

                result = build_all(incremental=False)

        assert result["success"] is True
        # Verify incremental=False is passed
        mock_update_fts.assert_called_once_with(incremental=False)

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

        with patch("tools.lib.semantic_search.get_model") as mock_model:
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance
            mock_model_instance.load.return_value = False
            with patch("tools.lib.vector_index_simple.update_vector_index_simple"):
                with patch("tools.lib.vector_index_simple.get_model") as mock_simple_model:
                    mock_simple_model_instance = MagicMock()
                    mock_simple_model.return_value = mock_simple_model_instance
                    mock_simple_model_instance.load.return_value = False

                    result = build_all()

        assert "duration_seconds" in result
        assert isinstance(result["duration_seconds"], (int, float))
        assert result["duration_seconds"] >= 0


class TestShowStats:
    """Tests for show_stats function"""

    @patch("tools.build_index.USER_DATA_DIR")
    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_fts_exists(self, mock_fts_stats, mock_data_dir):
        """Test show_stats with FTS index"""
        mock_fts_stats.return_value = {
            "exists": True,
            "total_documents": 100,
            "db_size_mb": 1.5,
            "last_updated": "2026-03-14T10:00:00",
        }
        mock_data_dir.__truediv__ = MagicMock()

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

    @patch("tools.build_index.USER_DATA_DIR")
    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_fts_not_exists(self, mock_fts_stats, mock_data_dir):
        """Test show_stats when FTS index doesn't exist"""
        mock_fts_stats.return_value = {
            "exists": False,
            "total_documents": 0,
            "db_size_mb": 0,
            "last_updated": None,
        }
        mock_data_dir.__truediv__ = MagicMock()

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

    @patch("tools.build_index.USER_DATA_DIR")
    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_with_sqlite_vec(self, mock_fts_stats, mock_data_dir):
        """Test show_stats with sqlite-vec backend"""
        mock_fts_stats.return_value = {
            "exists": True,
            "total_documents": 50,
            "db_size_mb": 0.8,
            "last_updated": "2026-03-14T10:00:00",
        }
        mock_data_dir.__truediv__ = MagicMock()

        with patch("tools.lib.semantic_search.get_stats") as mock_vec:
            mock_vec.return_value = {
                "exists": True,
                "total_vectors": 200,
                "db_size_mb": 2.5,
                "model_loaded": True,
            }
            with patch("tools.build_index.logger"):
                show_stats()

        mock_fts_stats.assert_called_once()
        mock_vec.assert_called()

    @patch("tools.build_index.USER_DATA_DIR")
    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_fallback_to_simple_index(self, mock_fts_stats, mock_data_dir):
        """Test show_stats fallback to simple vector index"""
        mock_fts_stats.return_value = {
            "exists": True,
            "total_documents": 30,
            "db_size_mb": 0.5,
            "last_updated": "2026-03-14T10:00:00",
        }
        mock_data_dir.__truediv__ = MagicMock()

        # Mock semantic_search.get_stats to raise ImportError to trigger fallback
        with patch("tools.lib.semantic_search.get_stats") as mock_vec:
            mock_vec.side_effect = ImportError("No sqlite-vec")
            with patch("tools.lib.vector_index_simple.get_index") as mock_get_index:
                mock_index = MagicMock()
                mock_get_index.return_value = mock_index
                mock_index.stats.return_value = {
                    "exists": True,
                    "total_vectors": 100,
                    "index_size_mb": 1.2,
                }
                with patch("tools.build_index.logger"):
                    show_stats()

        mock_fts_stats.assert_called_once()

    @patch("tools.build_index.USER_DATA_DIR")
    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_no_vector_backend(self, mock_fts_stats, mock_data_dir):
        """Test show_stats when no vector backend available"""
        mock_fts_stats.return_value = {
            "exists": True,
            "total_documents": 10,
            "db_size_mb": 0.2,
            "last_updated": None,
        }
        mock_data_dir.__truediv__ = MagicMock()

        # Mock semantic_search.get_stats to raise ImportError
        with patch("tools.lib.semantic_search.get_stats") as mock_vec:
            mock_vec.side_effect = ImportError("No sqlite-vec")
            with patch("tools.lib.vector_index_simple.get_index") as mock_get_index:
                mock_get_index.side_effect = ImportError("No simple index")
                with patch("tools.build_index.logger"):
                    show_stats()

        mock_fts_stats.assert_called_once()

    @patch("tools.build_index.get_model_cache_dir")
    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_cache_directory_exists(self, mock_fts_stats, mock_cache_dir_getter):
        """Test show_stats with existing cache directory"""
        mock_fts_stats.return_value = {
            "exists": True,
            "total_documents": 5,
            "db_size_mb": 0.1,
            "last_updated": None,
        }

        # Create mock path for cache directory
        mock_cache_dir = MagicMock()
        mock_cache_dir.exists.return_value = True
        mock_cache_dir.rglob.return_value = []
        mock_cache_dir_getter.return_value = mock_cache_dir

        with patch("tools.lib.semantic_search.get_stats") as mock_vec:
            mock_vec.return_value = {
                "exists": True,
                "total_vectors": 50,
                "model_loaded": True,
                "db_size_mb": 1.0,
            }
            with patch("tools.build_index.logger"):
                show_stats()

        mock_cache_dir.exists.assert_called()

    @patch("tools.build_index.get_model_cache_dir")
    @patch("tools.build_index.get_fts_stats")
    def test_show_stats_cache_directory_not_exists(self, mock_fts_stats, mock_cache_dir_getter):
        """Test show_stats when cache directory doesn't exist"""
        mock_fts_stats.return_value = {
            "exists": False,
            "total_documents": 0,
            "db_size_mb": 0,
            "last_updated": None,
        }

        mock_cache_dir = MagicMock()
        mock_cache_dir.exists.return_value = False
        mock_cache_dir_getter.return_value = mock_cache_dir

        # Mock semantic_search.get_stats to return existing vector index
        with patch("tools.lib.semantic_search.get_stats") as mock_vec:
            mock_vec.return_value = {
                "exists": True,
                "total_vectors": 5,
                "model_loaded": False,
                "db_size_mb": 0.1,
            }
            with patch("tools.build_index.logger"):
                show_stats()

        mock_cache_dir.exists.assert_called()


class TestIntegration:
    """Integration-style tests for build_all"""

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_full_workflow_success(self, mock_update_fts, mock_file_lock, mock_lock_path):
        """Test complete successful workflow"""
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

        with patch("tools.lib.semantic_search.get_model") as mock_model:
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance
            mock_model_instance.load.return_value = True

            with patch("tools.lib.semantic_search.update_vector_index") as mock_vec:
                mock_vec.return_value = {
                    "success": True,
                    "added": 8,
                    "updated": 3,
                }

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

        # Verify vector result
        assert result["vector"]["success"] is True
        assert result["vector"]["added"] == 8
        assert result["vector"]["updated"] == 3

    @patch("tools.build_index.get_index_lock_path")
    @patch("tools.build_index.FileLock")
    @patch("tools.build_index.update_fts_index")
    def test_partial_failure_continues(self, mock_update_fts, mock_file_lock, mock_lock_path):
        """Test that FTS failure doesn't prevent vector index update"""
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

        with patch("tools.lib.semantic_search.get_model") as mock_model:
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance
            mock_model_instance.load.return_value = True

            with patch("tools.lib.semantic_search.update_vector_index") as mock_vec:
                # Vector succeeds
                mock_vec.return_value = {
                    "success": True,
                    "added": 5,
                    "updated": 0,
                }

                result = build_all(incremental=True)

        # Overall should fail because FTS failed
        assert result["success"] is False
        # But vector should still have been updated
        assert result["vector"]["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
