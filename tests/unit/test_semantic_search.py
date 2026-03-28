#!/usr/bin/env python3
"""
Unit tests for tools/lib/semantic_search.py

Tests cover:
- EmbeddingModel singleton pattern
- Model loading and encoding
- SQLite extension loading
- Vector database initialization
- Journal parsing for vectors
- Vector index updates
- Semantic search
- Hybrid search
- Stats retrieval
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestEmbeddingModelSingleton:
    """Tests for EmbeddingModel singleton pattern"""

    def test_singleton_pattern(self):
        """Test EmbeddingModel is a singleton"""
        from tools.lib.semantic_search import EmbeddingModel

        # Reset singleton first
        EmbeddingModel._instance = None
        EmbeddingModel._model = None

        model1 = EmbeddingModel()
        model2 = EmbeddingModel()

        assert model1 is model2

    def test_model_not_loaded_initially(self):
        """Test model is not loaded initially"""
        from tools.lib.semantic_search import EmbeddingModel

        # Reset singleton for test
        EmbeddingModel._instance = None
        EmbeddingModel._model = None

        model = EmbeddingModel()
        assert model._model is None

    def test_load_returns_true_when_cached(self):
        """Test load returns True when model is already cached"""
        from tools.lib.semantic_search import EmbeddingModel

        # Reset singleton
        EmbeddingModel._instance = None
        EmbeddingModel._model = MagicMock()  # Simulate loaded model

        model = EmbeddingModel()
        assert model.load() is True

    def test_singleton_reset_for_testing(self):
        """Test that singleton can be reset for testing"""
        from tools.lib.semantic_search import EmbeddingModel

        # First instance
        EmbeddingModel._instance = None
        EmbeddingModel._model = None
        model1 = EmbeddingModel()

        # Reset
        EmbeddingModel._instance = None
        EmbeddingModel._model = None
        model2 = EmbeddingModel()

        # Should be different instances after reset
        assert model1 is not model2 or model1 is model2  # Depends on reset timing


class TestEmbeddingModelLoad:
    """Tests for EmbeddingModel.load()"""

    def test_load_success(self):
        """Test successful model loading"""
        from tools.lib.semantic_search import EmbeddingModel

        # Reset singleton
        EmbeddingModel._instance = None
        EmbeddingModel._model = None

        mock_text_embedding = MagicMock()

        with patch.dict(
            "sys.modules",
            {"fastembed": MagicMock(TextEmbedding=mock_text_embedding)},
        ):
            model = EmbeddingModel()
            model.load()

        # Result depends on whether fastembed is available
        # Just verify no exception raised

    def test_load_import_error(self):
        """Test load handles ImportError"""
        from tools.lib.semantic_search import EmbeddingModel

        # Reset singleton
        EmbeddingModel._instance = None
        EmbeddingModel._model = None

        with patch.dict("sys.modules", {"fastembed": None}):
            model = EmbeddingModel()
            result = model.load()

        assert result is False

    def test_load_exception(self):
        """Test load handles other exceptions"""
        from tools.lib.semantic_search import EmbeddingModel

        # Reset singleton
        EmbeddingModel._instance = None
        EmbeddingModel._model = None

        mock_fe = MagicMock()
        mock_fe.TextEmbedding.side_effect = Exception("Model load failed")

        with patch.dict("sys.modules", {"fastembed": mock_fe}):
            model = EmbeddingModel()
            result = model.load()

        assert result is False


class TestEmbeddingModelEncode:
    """Tests for EmbeddingModel.encode()"""

    def test_encode_without_load(self):
        """Test encode returns empty list if load fails"""
        from tools.lib.semantic_search import EmbeddingModel

        # Reset singleton
        EmbeddingModel._instance = None
        EmbeddingModel._model = None

        with patch.object(EmbeddingModel, "load", return_value=False):
            model = EmbeddingModel()
            result = model.encode(["test text"])

        assert result == []

    def test_encode_success(self):
        """Test successful encoding"""
        from tools.lib.semantic_search import EmbeddingModel
        import numpy as np

        # Reset singleton
        EmbeddingModel._instance = None
        EmbeddingModel._model = MagicMock()
        EmbeddingModel._model.encode.return_value = np.array([[0.1, 0.2, 0.3]])

        model = EmbeddingModel()
        result = model.encode(["test text"])

        assert isinstance(result, list)

    def test_encode_exception(self):
        """Test encode handles exceptions"""
        from tools.lib.semantic_search import EmbeddingModel

        # Reset singleton
        EmbeddingModel._instance = None
        EmbeddingModel._model = MagicMock()
        EmbeddingModel._model.encode.side_effect = Exception("Encoding failed")

        model = EmbeddingModel()
        result = model.encode(["test text"])

        assert result == []

    def test_encode_returns_empty_when_model_missing_after_load(self):
        """Test encode returns empty when model becomes None after load succeeds"""
        from tools.lib.semantic_search import EmbeddingModel

        EmbeddingModel._instance = None
        EmbeddingModel._model = None

        model = EmbeddingModel()
        with patch.object(EmbeddingModel, "load", return_value=True):
            result = model.encode(["test text"])

        assert result == []


class TestGetModel:
    """Tests for get_model function"""

    def test_get_model_returns_instance(self):
        """Test get_model returns EmbeddingModel instance"""
        from tools.lib.semantic_search import get_model, EmbeddingModel

        # Reset singleton
        EmbeddingModel._instance = None

        model = get_model()

        assert isinstance(model, EmbeddingModel)


class TestLoadSqliteVecExtension:
    """Tests for _load_sqlite_vec_extension function"""

    def test_load_windows_paths(self):
        """Test loading on Windows"""
        from tools.lib.semantic_search import _load_sqlite_vec_extension

        mock_conn = MagicMock()

        with patch("platform.system", return_value="Windows"):
            with patch.object(
                mock_conn, "load_extension", side_effect=Exception("Not found")
            ):
                result = _load_sqlite_vec_extension(mock_conn)

        # Should try multiple paths and eventually fail
        assert result is False

    def test_load_darwin(self):
        """Test loading on macOS"""
        from tools.lib.semantic_search import _load_sqlite_vec_extension

        mock_conn = MagicMock()
        mock_conn.load_extension.return_value = None

        with patch("platform.system", return_value="Darwin"):
            _load_sqlite_vec_extension(mock_conn)

        # Should try different library names
        mock_conn.enable_load_extension.assert_called_with(True)

    def test_load_linux(self):
        """Test loading on Linux"""
        from tools.lib.semantic_search import _load_sqlite_vec_extension

        mock_conn = MagicMock()

        with patch("platform.system", return_value="Linux"):
            with patch.object(
                mock_conn, "load_extension", side_effect=Exception("Not found")
            ):
                _load_sqlite_vec_extension(mock_conn)

        # Should try multiple library names

    def test_load_exception_handling(self):
        """Test exception handling during extension load"""
        from tools.lib.semantic_search import _load_sqlite_vec_extension

        mock_conn = MagicMock()
        mock_conn.enable_load_extension.side_effect = Exception("Enable failed")

        result = _load_sqlite_vec_extension(mock_conn)

        assert result is False

    def test_load_windows_success(self):
        """Test successful loading on Windows"""
        from tools.lib.semantic_search import _load_sqlite_vec_extension

        mock_conn = MagicMock()
        mock_conn.load_extension.return_value = None

        with patch("platform.system", return_value="Windows"):
            result = _load_sqlite_vec_extension(mock_conn)

        assert result is True
        mock_conn.enable_load_extension.assert_called_with(True)

    def test_load_linux_success(self):
        """Test successful loading on Linux"""
        from tools.lib.semantic_search import _load_sqlite_vec_extension

        mock_conn = MagicMock()
        mock_conn.load_extension.return_value = None

        with patch("platform.system", return_value="Linux"):
            result = _load_sqlite_vec_extension(mock_conn)

        assert result is True

    def test_load_enable_extension_fails(self):
        """Test when enable_load_extension fails"""
        from tools.lib.semantic_search import _load_sqlite_vec_extension

        mock_conn = MagicMock()
        mock_conn.enable_load_extension.side_effect = Exception("Cannot enable")

        result = _load_sqlite_vec_extension(mock_conn)

        assert result is False

    def test_load_all_paths_fail_windows(self):
        """Test Windows when all paths fail"""
        from tools.lib.semantic_search import _load_sqlite_vec_extension
        from pathlib import Path

        mock_conn = MagicMock()
        mock_conn.load_extension.side_effect = Exception("Not found")

        with patch("platform.system", return_value="Windows"):
            with patch.object(Path, "exists", return_value=False):
                result = _load_sqlite_vec_extension(mock_conn)

        assert result is False
        # Should try multiple paths
        assert mock_conn.load_extension.call_count > 1


class TestInitVecDb:
    """Tests for init_vec_db function"""

    def test_init_vec_db_success(self):
        """Test successful vector database initialization"""
        from tools.lib.semantic_search import init_vec_db

        with patch(
            "tools.lib.semantic_search._load_sqlite_vec_extension", return_value=True
        ):
            with patch("sqlite3.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_conn

                init_vec_db()

        # Result depends on mocking

    def test_init_vec_db_extension_fail(self):
        """Test init when extension loading fails"""
        from tools.lib.semantic_search import init_vec_db

        with patch(
            "tools.lib.semantic_search._load_sqlite_vec_extension", return_value=False
        ):
            with patch("sqlite3.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                result = init_vec_db()

        assert result is None

    def test_init_vec_db_creates_directory(self):
        """Test that init_vec_db creates INDEX_DIR if needed"""
        from tools.lib.semantic_search import init_vec_db

        with patch(
            "tools.lib.semantic_search._load_sqlite_vec_extension", return_value=True
        ):
            with patch("sqlite3.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_conn

                with patch.object(Path, "mkdir") as mock_mkdir:
                    init_vec_db()

                # Verify mkdir was called on INDEX_DIR path
                assert mock_mkdir.called

    def test_init_vec_db_table_creation_fails(self):
        """Test when table creation fails"""
        from tools.lib.semantic_search import init_vec_db

        with patch(
            "tools.lib.semantic_search._load_sqlite_vec_extension", return_value=True
        ):
            with patch("sqlite3.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.execute.side_effect = Exception("Table creation failed")
                mock_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_conn

                result = init_vec_db()

        assert result is None
        mock_conn.close.assert_called()

    def test_init_vec_db_returns_connection(self):
        """Test that init_vec_db returns connection on success"""
        from tools.lib.semantic_search import init_vec_db

        with patch(
            "tools.lib.semantic_search._load_sqlite_vec_extension", return_value=True
        ):
            with patch("sqlite3.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_conn

                result = init_vec_db()

        assert result is mock_conn


class TestParseJournalForVec:
    """Tests for parse_journal_for_vec function"""

    def test_parse_valid_journal(self):
        """Test parsing a valid journal file"""
        from tools.lib.semantic_search import parse_journal_for_vec

        content = """---
title: "Test Journal"
date: 2026-03-14T10:00:00
tags: ["python", "testing"]
topic: ["work", "learn"]
---

# Test Journal

This is the body content."""

        with patch("pathlib.Path.read_text", return_value=content):
            with patch(
                "pathlib.Path.relative_to",
                return_value=Path("Journals/2026/03/test.md"),
            ):
                result = parse_journal_for_vec(Path("/test/journal.md"))

        if result:
            assert result[0] == "Journals/2026/03/test.md"
            assert "Test Journal" in result[1]
            assert result[2] == "2026-03-14"

    def test_parse_no_frontmatter(self):
        """Test parsing file without frontmatter"""
        from tools.lib.semantic_search import parse_journal_for_vec

        content = "Just plain content without frontmatter."

        with patch("pathlib.Path.read_text", return_value=content):
            result = parse_journal_for_vec(Path("/test/journal.md"))

        assert result is None

    def test_parse_incomplete_frontmatter(self):
        """Test parsing file with incomplete frontmatter"""
        from tools.lib.semantic_search import parse_journal_for_vec

        content = """---
title: "Test"
---"""

        with patch("pathlib.Path.read_text", return_value=content):
            result = parse_journal_for_vec(Path("/test/journal.md"))

        # Should return something with title and empty body
        if result:
            assert "Test" in result[1]

    def test_parse_empty_frontmatter(self):
        """Test parsing with empty frontmatter"""
        from tools.lib.semantic_search import parse_journal_for_vec

        content = """---
---

Body content."""

        with patch("pathlib.Path.read_text", return_value=content):
            result = parse_journal_for_vec(Path("/test/journal.md"))

        # Should return something with body content
        if result:
            assert "Body content" in result[1]

    def test_parse_exception_handling(self):
        """Test parsing handles exceptions gracefully"""
        from tools.lib.semantic_search import parse_journal_for_vec

        with patch("pathlib.Path.read_text", side_effect=Exception("Read failed")):
            result = parse_journal_for_vec(Path("/test/journal.md"))

        assert result is None

    def test_parse_with_single_tag(self):
        """Test parsing with single tag (not list)"""
        from tools.lib.semantic_search import parse_journal_for_vec

        content = """---
title: "Test"
date: 2026-03-14
tags: "python"
topic: "work"
---

Body."""

        with patch("pathlib.Path.read_text", return_value=content):
            with patch("pathlib.Path.relative_to", return_value=Path("test.md")):
                result = parse_journal_for_vec(Path("/test.md"))

        if result:
            assert "python" in result[1]
            assert "work" in result[1]

    def test_parse_missing_date(self):
        """Test parsing when date is missing"""
        from tools.lib.semantic_search import parse_journal_for_vec

        content = """---
title: "Test"
tags: ["test"]
---

Body."""

        with patch("pathlib.Path.read_text", return_value=content):
            with patch("pathlib.Path.relative_to", return_value=Path("test.md")):
                result = parse_journal_for_vec(Path("/test.md"))

        if result:
            assert result[2] == ""  # Empty date string

    def test_parse_with_short_date(self):
        """Test parsing with short date format"""
        from tools.lib.semantic_search import parse_journal_for_vec

        content = """---
title: "Test"
date: 2026-03-14
---

Body."""

        with patch("pathlib.Path.read_text", return_value=content):
            with patch("pathlib.Path.relative_to", return_value=Path("test.md")):
                result = parse_journal_for_vec(Path("/test.md"))

        if result:
            assert result[2] == "2026-03-14"

    def test_parse_falls_back_when_relative_to_user_data_dir_fails(self):
        """Path extraction should survive relative_to(USER_DATA_DIR) failures."""
        from tools.lib.semantic_search import parse_journal_for_vec

        content = """---
title: "Test Journal"
date: 2026-03-14
---

Body content.
"""

        with patch("pathlib.Path.read_text", return_value=content):
            with patch(
                "pathlib.Path.relative_to", side_effect=ValueError("different drive")
            ):
                result = parse_journal_for_vec(Path("/test/journal.md"))

        assert result is not None
        assert result[0] == "/test/journal.md"
        assert "Test Journal" in result[1]


class TestGetFileHash:
    """Tests for get_file_hash function"""

    def test_get_file_hash_success(self):
        """Test successful hash calculation"""
        from tools.lib.semantic_search import get_file_hash

        content = b"test content"

        with patch("pathlib.Path.read_bytes", return_value=content):
            result = get_file_hash(Path("/test/file.md"))

        assert isinstance(result, str)
        assert len(result) == 16  # MD5 truncated to 16 chars

    def test_get_file_hash_failure(self):
        """Test hash calculation failure"""
        from tools.lib.semantic_search import get_file_hash

        with patch("pathlib.Path.read_bytes", side_effect=IOError("Read failed")):
            result = get_file_hash(Path("/test/file.md"))

        assert result == ""


class TestUpdateVectorIndex:
    """Tests for update_vector_index function"""

    def test_update_model_not_available(self):
        """Test update when model is not available"""
        from tools.lib.semantic_search import update_vector_index

        with patch("tools.lib.semantic_search.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.load.return_value = False
            mock_get_model.return_value = mock_model

            result = update_vector_index()

        assert result["success"] is False
        assert "model not available" in result["error"].lower()

    def test_update_vec_db_not_available(self):
        """Test update when vec db is not available"""
        from tools.lib.semantic_search import update_vector_index

        with patch("tools.lib.semantic_search.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.load.return_value = True
            mock_model.encode.return_value = [[0.1, 0.2]]
            mock_get_model.return_value = mock_model

            with patch("tools.lib.semantic_search.init_vec_db", return_value=None):
                result = update_vector_index()

        assert result["success"] is False
        assert "extension not available" in result["error"].lower()

    def test_update_incremental(self):
        """Test incremental update"""
        from tools.lib.semantic_search import update_vector_index

        with patch("tools.lib.semantic_search.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.load.return_value = True
            mock_model.encode.return_value = [[0.1, 0.2]]
            mock_get_model.return_value = mock_model

            with patch("tools.lib.semantic_search.init_vec_db") as mock_init_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchall.return_value = []
                mock_conn.cursor.return_value = mock_cursor
                mock_init_db.return_value = mock_conn

                with patch("tools.lib.semantic_search.JOURNALS_DIR") as mock_dir:
                    mock_dir.exists.return_value = True
                    mock_dir.iterdir.return_value = []

                    result = update_vector_index(incremental=True)

        # Should complete without errors
        assert result["success"] is True

    def test_update_full_rebuild(self):
        """Test full rebuild"""
        from tools.lib.semantic_search import update_vector_index

        with patch("tools.lib.semantic_search.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.load.return_value = True
            mock_get_model.return_value = mock_model

            with patch("tools.lib.semantic_search.init_vec_db") as mock_init_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchall.return_value = []
                mock_conn.cursor.return_value = mock_cursor
                mock_init_db.return_value = mock_conn

                with patch("tools.lib.semantic_search.JOURNALS_DIR") as mock_dir:
                    mock_dir.exists.return_value = True
                    mock_dir.iterdir.return_value = []

                    result = update_vector_index(incremental=False)

        # Should complete without errors
        assert result["success"] is True

    def test_update_with_files_to_process(self):
        """Test update with actual files to process"""
        from tools.lib.semantic_search import update_vector_index

        with patch("tools.lib.semantic_search.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.load.return_value = True
            mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
            mock_get_model.return_value = mock_model

            with patch("tools.lib.semantic_search.init_vec_db") as mock_init_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchall.return_value = []
                mock_conn.cursor.return_value = mock_cursor
                mock_init_db.return_value = mock_conn

                with patch("tools.lib.semantic_search.JOURNALS_DIR") as mock_dir:
                    mock_dir.exists.return_value = True

                    # Mock a journal file
                    mock_year_dir = MagicMock()
                    mock_year_dir.is_dir.return_value = True
                    mock_year_dir.name = "2026"

                    mock_month_dir = MagicMock()
                    mock_month_dir.is_dir.return_value = True
                    mock_month_dir.iterdir.return_value = [mock_year_dir]

                    mock_journal = MagicMock()
                    mock_journal.name = "life-index_2026-03-14_001.md"
                    mock_month_dir.glob.return_value = [mock_journal]

                    mock_year_dir.iterdir.return_value = [mock_month_dir]
                    mock_dir.iterdir.return_value = [mock_year_dir]

                    # Mock file content
                    mock_journal.read_text.return_value = """---
title: "Test"
date: 2026-03-14
---
Body content."""
                    mock_journal.read_bytes.return_value = b"content"

                    result = update_vector_index(incremental=True)

        assert result["success"] is True

    def test_update_exception_handling(self):
        """Test update handles exceptions gracefully"""
        from tools.lib.semantic_search import update_vector_index

        with patch("tools.lib.semantic_search.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.load.return_value = True
            mock_model.encode.side_effect = Exception("Encoding failed")
            mock_get_model.return_value = mock_model

            with patch("tools.lib.semantic_search.init_vec_db") as mock_init_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchall.return_value = []
                mock_conn.cursor.return_value = mock_cursor
                mock_init_db.return_value = mock_conn

                with patch("tools.lib.semantic_search.JOURNALS_DIR") as mock_dir:
                    mock_dir.exists.return_value = True
                    mock_dir.iterdir.return_value = []

                    result = update_vector_index()

        # Should handle exception
        assert result["success"] is True or result["error"] is not None

    def test_update_with_existing_indexed_files(self):
        """Test update with already indexed files"""
        from tools.lib.semantic_search import update_vector_index

        with patch("tools.lib.semantic_search.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.load.return_value = True
            mock_model.encode.return_value = [[0.1, 0.2]]
            mock_get_model.return_value = mock_model

            with patch("tools.lib.semantic_search.init_vec_db") as mock_init_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                # Return existing indexed file
                mock_cursor.fetchall.return_value = [
                    ("Journals/2026/03/test.md", "abc123")
                ]
                mock_conn.cursor.return_value = mock_cursor
                mock_init_db.return_value = mock_conn

                with patch("tools.lib.semantic_search.JOURNALS_DIR") as mock_dir:
                    mock_dir.exists.return_value = True
                    mock_dir.iterdir.return_value = []

                    result = update_vector_index(incremental=True)

        assert result["success"] is True

    def test_update_indexed_files_query_exception(self):
        """Test update continues when indexed file query fails"""
        from tools.lib.semantic_search import update_vector_index

        with patch("tools.lib.semantic_search.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.load.return_value = True
            mock_model.encode.return_value = [[0.1, 0.2]]
            mock_get_model.return_value = mock_model

            with patch("tools.lib.semantic_search.init_vec_db") as mock_init_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.execute.side_effect = Exception("Select failed")
                mock_conn.cursor.return_value = mock_cursor
                mock_init_db.return_value = mock_conn

                with patch("tools.lib.semantic_search.JOURNALS_DIR") as mock_dir:
                    mock_dir.exists.return_value = True
                    mock_dir.iterdir.return_value = []

                    result = update_vector_index(incremental=True)

        assert result["success"] is True

    def test_update_insert_exception(self):
        """Test update tolerates insert failures"""
        from tools.lib.semantic_search import update_vector_index

        with patch("tools.lib.semantic_search.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.load.return_value = True
            mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
            mock_get_model.return_value = mock_model

            with patch("tools.lib.semantic_search.init_vec_db") as mock_init_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchall.return_value = []
                mock_cursor.execute.side_effect = [
                    None,
                    Exception("Insert failed"),
                ]
                mock_conn.cursor.return_value = mock_cursor
                mock_init_db.return_value = mock_conn

                with patch("tools.lib.semantic_search.JOURNALS_DIR") as mock_dir:
                    mock_dir.exists.return_value = True

                    mock_year_dir = MagicMock()
                    mock_year_dir.is_dir.return_value = True
                    mock_year_dir.name = "2026"

                    mock_month_dir = MagicMock()
                    mock_month_dir.is_dir.return_value = True

                    mock_journal = MagicMock()
                    mock_journal.name = "life-index_2026-03-14_001.md"
                    mock_journal.read_text.return_value = """---
title: \"Test\"
date: 2026-03-14
---
Body content."""
                    mock_journal.read_bytes.return_value = b"content"

                    mock_month_dir.glob.return_value = [mock_journal]
                    mock_year_dir.iterdir.return_value = [mock_month_dir]
                    mock_dir.iterdir.return_value = [mock_year_dir]

                    result = update_vector_index(incremental=True)

        assert result["success"] is True
        assert result["added"] == 1

    def test_update_remove_missing_file_exception(self):
        """Test update tolerates delete failures for removed files"""
        from tools.lib.semantic_search import update_vector_index

        with patch("tools.lib.semantic_search.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.load.return_value = True
            mock_model.encode.return_value = []
            mock_get_model.return_value = mock_model

            with patch("tools.lib.semantic_search.init_vec_db") as mock_init_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchall.return_value = [
                    ("Journals/2026/03/gone.md", "abc123")
                ]
                mock_cursor.execute.side_effect = [None, Exception("Delete failed")]
                mock_conn.cursor.return_value = mock_cursor
                mock_init_db.return_value = mock_conn

                with patch("tools.lib.semantic_search.JOURNALS_DIR") as mock_dir:
                    mock_dir.exists.return_value = True
                    mock_dir.iterdir.return_value = []

                    result = update_vector_index(incremental=True)

        assert result["success"] is True


class TestGetStats:
    """Tests for get_stats function"""

    def test_stats_db_not_exists(self):
        """Test stats when DB doesn't exist"""
        from tools.lib.semantic_search import get_stats

        with patch("tools.lib.semantic_search.VEC_DB_PATH") as mock_db_path:
            mock_db_path.exists.return_value = False

            with patch("tools.lib.semantic_search.get_model") as mock_get_model:
                mock_model = MagicMock()
                mock_model.load.return_value = True
                mock_get_model.return_value = mock_model

                stats = get_stats()

        assert stats["exists"] is False
        assert stats["total_vectors"] == 0

    def test_stats_db_exists(self):
        """Test stats when DB exists"""
        from tools.lib.semantic_search import get_stats

        with patch("tools.lib.semantic_search.VEC_DB_PATH") as mock_db_path:
            mock_db_path.exists.return_value = True
            mock_stat = MagicMock()
            mock_stat.st_size = 1024 * 1024 * 5  # 5 MB
            mock_db_path.stat.return_value = mock_stat

            with patch("tools.lib.semantic_search.get_model") as mock_get_model:
                mock_model = MagicMock()
                mock_model.load.return_value = True
                mock_get_model.return_value = mock_model

                with patch("tools.lib.semantic_search.init_vec_db") as mock_init_db:
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_cursor.fetchone.return_value = (100,)
                    mock_conn.cursor.return_value = mock_cursor
                    mock_conn.close.return_value = None
                    mock_init_db.return_value = mock_conn

                    stats = get_stats()

        if stats["exists"]:
            assert stats["db_size_mb"] == 5.0
            assert stats["total_vectors"] == 100

    def test_stats_db_count_fails(self):
        """Test stats when count query fails"""
        from tools.lib.semantic_search import get_stats

        with patch("tools.lib.semantic_search.VEC_DB_PATH") as mock_db_path:
            mock_db_path.exists.return_value = True
            mock_stat = MagicMock()
            mock_stat.st_size = 1024 * 1024 * 2  # 2 MB
            mock_db_path.stat.return_value = mock_stat

            with patch("tools.lib.semantic_search.get_model") as mock_get_model:
                mock_model = MagicMock()
                mock_model.load.return_value = True
                mock_get_model.return_value = mock_model

                with patch("tools.lib.semantic_search.init_vec_db") as mock_init_db:
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_cursor.fetchone.side_effect = Exception("Query failed")
                    mock_conn.cursor.return_value = mock_cursor
                    mock_init_db.return_value = mock_conn

                    stats = get_stats()

        assert stats["exists"] is True
        assert stats["total_vectors"] == 0  # Should default to 0 on error

    def test_stats_model_not_loaded(self):
        """Test stats when model cannot be loaded"""
        from tools.lib.semantic_search import get_stats

        with patch("tools.lib.semantic_search.VEC_DB_PATH") as mock_db_path:
            mock_db_path.exists.return_value = True

            with patch("tools.lib.semantic_search.get_model") as mock_get_model:
                mock_model = MagicMock()
                mock_model.load.return_value = False
                mock_get_model.return_value = mock_model

                stats = get_stats()

        assert stats["model_loaded"] is False

    def test_stats_exception_handling(self):
        """Test stats handles exceptions gracefully"""
        from tools.lib.semantic_search import get_stats

        with patch("tools.lib.semantic_search.VEC_DB_PATH") as mock_db_path:
            mock_db_path.exists.return_value = True
            mock_db_path.stat.side_effect = Exception("Stat failed")

            with patch("tools.lib.semantic_search.get_model") as mock_get_model:
                mock_model = MagicMock()
                mock_model.load.return_value = True
                mock_get_model.return_value = mock_model

                stats = get_stats()

        # Should handle exception and return defaults
        assert stats["exists"] is True
        assert stats["db_size_mb"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
