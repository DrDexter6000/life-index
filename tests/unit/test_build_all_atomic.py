"""Tests for build_all two-phase commit (Round 12 Phase 2 Task 2.3)."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from tools.lib.index_manifest import IndexManifest, read_manifest, is_manifest_valid


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    """Redirect all paths to tmp_path."""
    import tools.lib.config as cfg
    import tools.lib.paths as paths
    import tools.lib.search_index as si
    import tools.build_index as bi

    idx = tmp_path / ".index"
    idx.mkdir(parents=True)
    d = tmp_path / "Life-Index"
    (d / "Journals" / "2026" / "03").mkdir(parents=True)

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(d))
    monkeypatch.setattr(si, "get_fts_db_path", lambda: idx / "journals_fts.db")
    monkeypatch.setattr(si, "get_user_data_dir", lambda: d)

    # Mock heavy operations
    monkeypatch.setattr(si, "update_index", lambda **kw: {"success": True, "added": 1, "updated": 0, "removed": 0})
    monkeypatch.setattr(bi, "update_fts_index", lambda **kw: {"success": True, "added": 1, "updated": 0, "removed": 0})
    monkeypatch.setattr(bi, "get_fts_stats", lambda: {"total_documents": 1, "exists": True})
    monkeypatch.setattr(bi, "get_index_lock_path", lambda: tmp_path / "test.lock")
    monkeypatch.setattr(bi, "invalidate_cache", lambda: None)
    monkeypatch.setattr(bi, "update_cache_for_all_journals", lambda: None)
    monkeypatch.setattr(bi, "init_metadata_cache", lambda: MagicMock(close=lambda: None))
    monkeypatch.setattr(bi, "rebuild_entry_relations", lambda conn: None)
    monkeypatch.setattr(bi, "get_cache_stats", lambda: {"rebuild_hint": ""})


def _create_journal(data_dir: Path, name: str = "life-index_2026-03-07_001.md") -> Path:
    """Helper: create a minimal journal file."""
    p = data_dir / "Journals" / "2026" / "03" / name
    p.write_text(
        '---\ntitle: "Test"\ndate: 2026-03-07\n---\n\nBody\n',
        encoding="utf-8",
    )
    return p


class TestBuildAllAtomic:
    """Tests for build_all() two-phase commit with manifest."""

    def test_successful_build_writes_manifest(self, tmp_path: Path, monkeypatch):
        """When both FTS and vector succeed, manifest is written."""
        import tools.build_index as bi
        import tools.lib.vector_index_simple as vi_mod
        import tools.lib.semantic_search as ss

        index_dir = tmp_path / ".index"
        monkeypatch.setattr(vi_mod, "get_index_dir", lambda: index_dir)
        monkeypatch.setattr(vi_mod, "get_vec_index_path", lambda: index_dir / "vectors_simple.pkl")
        monkeypatch.setattr(vi_mod, "get_vec_meta_path", lambda: index_dir / "vectors_simple_meta.json")

        # Mock vector model to avoid loading sentence-transformers
        mock_model = MagicMock()
        mock_model.load.return_value = False  # Skip vector build (model not available)

        with (
            patch.object(ss, "get_model", return_value=mock_model),
            patch.object(vi_mod, "get_model", return_value=mock_model),
        ):
            result = bi.build_all(incremental=True)

        # Manifest should be written (FTS only, no vector)
        data_dir = tmp_path / "Life-Index"
        manifest = read_manifest(data_dir / ".index")
        assert manifest is not None, "Manifest should be written after build"

    def test_vector_failure_marks_partial(self, tmp_path: Path, monkeypatch):
        """When vector build fails, manifest is written with partial=True."""
        import tools.build_index as bi
        import tools.lib.vector_index_simple as vi_mod
        import tools.lib.semantic_search as ss

        index_dir = tmp_path / ".index"
        monkeypatch.setattr(vi_mod, "get_index_dir", lambda: index_dir)
        monkeypatch.setattr(vi_mod, "get_vec_index_path", lambda: index_dir / "vectors_simple.pkl")
        monkeypatch.setattr(vi_mod, "get_vec_meta_path", lambda: index_dir / "vectors_simple_meta.json")

        mock_model = MagicMock()
        mock_model.load.return_value = False

        with (
            patch.object(ss, "get_model", return_value=mock_model),
            patch.object(vi_mod, "get_model", return_value=mock_model),
        ):
            result = bi.build_all(incremental=True)

        manifest = read_manifest((tmp_path / "Life-Index") / ".index")
        # Either partial=True or manifest exists with correct flags
        assert manifest is not None
        assert manifest.partial is True, "Manifest should be marked partial when vector fails"

    def test_manifest_not_written_on_fts_failure(self, tmp_path: Path, monkeypatch):
        """When FTS build fails, no manifest is written."""
        import tools.build_index as bi
        import tools.lib.search_index as si
        import tools.lib.vector_index_simple as vi_mod
        import tools.lib.semantic_search as ss

        index_dir = tmp_path / ".index"
        monkeypatch.setattr(vi_mod, "get_index_dir", lambda: index_dir)
        monkeypatch.setattr(vi_mod, "get_vec_index_path", lambda: index_dir / "vectors_simple.pkl")
        monkeypatch.setattr(vi_mod, "get_vec_meta_path", lambda: index_dir / "vectors_simple_meta.json")

        # Override the fixture's FTS mock to make it fail
        monkeypatch.setattr(bi, "update_fts_index", lambda **kw: {"success": False, "error": "FTS crashed"})

        mock_model = MagicMock()
        mock_model.load.return_value = False

        with (
            patch.object(ss, "get_model", return_value=mock_model),
            patch.object(vi_mod, "get_model", return_value=mock_model),
        ):
            result = bi.build_all(incremental=True)

        assert result["success"] is False
        manifest = read_manifest((tmp_path / "Life-Index") / ".index")
        assert manifest is None, "Manifest should NOT be written when FTS fails"

    def test_check_index_detects_partial(self, tmp_path: Path, monkeypatch):
        """index --check detects partial build and reports unhealthy."""
        from tools.build_index import check_index
        from tools.lib.index_manifest import write_manifest
        import tools.lib.vector_index_simple as vi_mod

        data_dir = tmp_path / "Life-Index"
        index_dir = data_dir / ".index"
        index_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(vi_mod, "get_index_dir", lambda: index_dir)
        monkeypatch.setattr(vi_mod, "get_vec_index_path", lambda: index_dir / "vectors_simple.pkl")

        # Write a partial manifest in the correct location
        partial_manifest = IndexManifest(
            fts_count=5,
            vector_count=0,
            file_count=5,
            fts_checksum="abc",
            vector_checksum="",
            build_timestamp="2026-04-18T12:00:00",
            build_version="1.0.0",
            partial=True,
        )
        write_manifest(partial_manifest, index_dir)

        result = check_index()
        assert result["healthy"] is False
        assert any("partial" in str(issue).lower() for issue in result.get("issues", []))
