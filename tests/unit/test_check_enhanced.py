"""Tests for enhanced index --check (Round 12 Phase 3 Task 3.3)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.lib.index_manifest import IndexManifest, write_manifest


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    """Isolate paths to tmp_path."""
    import tools.lib.vector_index_simple as vi_mod

    d = tmp_path / "Life-Index"
    idx = d / ".index"
    (d / "Journals" / "2026" / "03").mkdir(parents=True)
    idx.mkdir(parents=True)

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(d))
    monkeypatch.setattr(vi_mod, "get_index_dir", lambda: idx)
    monkeypatch.setattr(vi_mod, "get_vec_index_path", lambda: idx / "vectors_simple.pkl")
    monkeypatch.setattr(vi_mod, "get_user_data_dir", lambda: d)


class TestEnhancedCheckIndex:

    def test_check_includes_manifest_subfield(self, tmp_path: Path):
        """index --check output includes manifest subfield."""
        from tools.build_index import check_index

        data_dir = tmp_path / "Life-Index"
        index_dir = data_dir / ".index"

        write_manifest(IndexManifest(
            fts_count=5, vector_count=5, file_count=5,
            fts_checksum="a", vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00", build_version="1.0.0",
        ), index_dir)

        result = check_index()
        assert "manifest" in result
        manifest_info = result["manifest"]
        assert manifest_info.get("exists") is True

    def test_check_includes_freshness_subfield(self, tmp_path: Path):
        """index --check output includes freshness subfield."""
        from tools.build_index import check_index

        data_dir = tmp_path / "Life-Index"
        index_dir = data_dir / ".index"

        write_manifest(IndexManifest(
            fts_count=5, vector_count=5, file_count=5,
            fts_checksum="a", vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00", build_version="1.0.0",
        ), index_dir)

        result = check_index()
        assert "freshness" in result
        freshness = result["freshness"]
        assert "fts_fresh" in freshness
        assert "vector_fresh" in freshness
        assert "overall_fresh" in freshness

    def test_check_healthy_when_all_good(self, tmp_path: Path):
        """Everything normal → healthy=true."""
        from tools.build_index import check_index

        data_dir = tmp_path / "Life-Index"
        index_dir = data_dir / ".index"

        write_manifest(IndexManifest(
            fts_count=5, vector_count=5, file_count=5,
            fts_checksum="a", vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00", build_version="1.0.0",
        ), index_dir)

        with (
            patch("tools.lib.index_freshness.get_fts_count", return_value=5),
            patch("tools.lib.index_freshness.get_vector_count", return_value=5),
        ):
            result = check_index()

        assert result["healthy"] is True
        assert result["issues"] == []

    def test_check_unhealthy_when_no_manifest(self, tmp_path: Path):
        """No manifest → healthy=false, suggests index --rebuild."""
        from tools.build_index import check_index

        result = check_index()
        assert result["healthy"] is False
        assert result["manifest"]["exists"] is False
        assert any("rebuild" in str(i).lower() for i in result.get("issues", []))
