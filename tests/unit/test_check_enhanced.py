"""Tests for enhanced index --check (Round 12 Phase 3 Task 3.3)."""

from pathlib import Path

import pytest

from tools.lib.index_manifest import IndexManifest, write_manifest


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    """Isolate paths to tmp_path."""
    d = tmp_path / "Life-Index"
    idx = d / ".index"
    (d / "Journals" / "2026" / "03").mkdir(parents=True)
    idx.mkdir(parents=True)

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(d))


class TestEnhancedCheckIndex:

    def test_check_includes_manifest_subfield(self, tmp_path: Path):
        """index --check output includes manifest subfield."""
        from tools.build_index import check_index

        data_dir = tmp_path / "Life-Index"
        index_dir = data_dir / ".index"

        write_manifest(
            IndexManifest(
                fts_count=5,
                vector_count=5,
                file_count=5,
                fts_checksum="a",
                vector_checksum="b",
                build_timestamp="2026-04-18T12:00:00",
                build_version="1.0.0",
            ),
            index_dir,
        )

        result = check_index()
        assert "manifest" in result
        manifest_info = result["manifest"]
        assert manifest_info.get("exists") is True

    def test_check_includes_freshness_subfield(self, tmp_path: Path):
        """index --check output includes freshness subfield."""
        from tools.build_index import check_index

        data_dir = tmp_path / "Life-Index"
        index_dir = data_dir / ".index"

        write_manifest(
            IndexManifest(
                fts_count=5,
                vector_count=5,
                file_count=5,
                fts_checksum="a",
                vector_checksum="b",
                build_timestamp="2026-04-18T12:00:00",
                build_version="1.0.0",
            ),
            index_dir,
        )

        result = check_index()
        assert "freshness" in result
        freshness = result["freshness"]
        assert "fts_fresh" in freshness
        assert "vector_fresh" in freshness
        assert "overall_fresh" in freshness

    def test_check_healthy_when_all_good(self, tmp_path: Path):
        """Everything normal (matching rows + signatures) → healthy=true."""
        from tools.build_index import check_index
        from tools.lib.search_index import update_index

        data_dir = tmp_path / "Life-Index"
        index_dir = data_dir / ".index"
        journal = data_dir / "Journals" / "2026" / "03" / "life-index_2026-03-01_001.md"
        journal.write_text(
            "---\ntitle: test\ndate: 2026-03-01\ntopic: [life]\n---\n\nBody\n",
            encoding="utf-8",
        )
        assert update_index(incremental=False)["success"] is True

        write_manifest(
            IndexManifest(
                fts_count=1,
                vector_count=0,
                file_count=1,
                fts_checksum="a",
                vector_checksum="",
                build_timestamp="2026-04-18T12:00:00",
                build_version="2.0.0",
            ),
            index_dir,
        )

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
