"""Tests for index_freshness module (Round 12 Phase 3 Task 3.1)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.lib.index_freshness import check_full_freshness, FreshnessReport
from tools.lib.index_manifest import IndexManifest, write_manifest
from tools.lib.pending_writes import mark_pending, clear_pending


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    """Isolate paths and pending queue to tmp_path."""
    import tools.lib.pending_writes as pw_mod
    import tools.lib.config as cfg
    import tools.lib.paths as paths
    import tools.lib.vector_index_simple as vi_mod

    idx = tmp_path / ".index"
    idx.mkdir(parents=True)
    d = tmp_path / "Life-Index"
    (d / "Journals" / "2026" / "03").mkdir(parents=True)

    monkeypatch.setattr(pw_mod, "get_index_dir", lambda: idx)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(d))
    monkeypatch.setattr(vi_mod, "get_index_dir", lambda: idx)
    monkeypatch.setattr(vi_mod, "get_vec_index_path", lambda: idx / "vectors_simple.pkl")
    monkeypatch.setattr(vi_mod, "get_user_data_dir", lambda: d)


class TestFullFreshness:
    """Tests for check_full_freshness()."""

    def test_returns_freshness_report_structure(self, tmp_path: Path):
        """check_full_freshness returns a FreshnessReport with all fields."""
        index_dir = tmp_path / ".index"
        # Write a valid manifest
        write_manifest(IndexManifest(
            fts_count=5, vector_count=5, file_count=5,
            fts_checksum="a", vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00", build_version="1.0.0",
        ), index_dir)

        with (
            patch("tools.lib.index_freshness.get_fts_count", return_value=5),
            patch("tools.lib.index_freshness.get_vector_count", return_value=5),
        ):
            report = check_full_freshness(index_dir)

        assert isinstance(report, FreshnessReport)
        assert hasattr(report, "fts_fresh")
        assert hasattr(report, "vector_fresh")
        assert hasattr(report, "overall_fresh")
        assert hasattr(report, "issues")

    def test_fts_count_mismatch_marks_fts_stale(self, tmp_path: Path):
        """FTS count != manifest count → fts_fresh=False."""
        index_dir = tmp_path / ".index"
        write_manifest(IndexManifest(
            fts_count=10, vector_count=10, file_count=10,
            fts_checksum="a", vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00", build_version="1.0.0",
        ), index_dir)

        with (
            patch("tools.lib.index_freshness.get_fts_count", return_value=7),
            patch("tools.lib.index_freshness.get_vector_count", return_value=10),
        ):
            report = check_full_freshness(index_dir)

        assert report.fts_fresh is False
        assert report.vector_fresh is True
        assert report.overall_fresh is False

    def test_vector_count_mismatch_marks_vector_stale(self, tmp_path: Path):
        """Vector count != manifest count → vector_fresh=False."""
        index_dir = tmp_path / ".index"
        write_manifest(IndexManifest(
            fts_count=10, vector_count=10, file_count=10,
            fts_checksum="a", vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00", build_version="1.0.0",
        ), index_dir)

        with (
            patch("tools.lib.index_freshness.get_fts_count", return_value=10),
            patch("tools.lib.index_freshness.get_vector_count", return_value=3),
        ):
            report = check_full_freshness(index_dir)

        assert report.fts_fresh is True
        assert report.vector_fresh is False
        assert report.overall_fresh is False

    def test_no_manifest_marks_overall_stale(self, tmp_path: Path):
        """No manifest → overall_fresh=False (first install scenario)."""
        index_dir = tmp_path / ".index"
        # Don't write manifest

        report = check_full_freshness(index_dir)
        assert report.overall_fresh is False
        assert any("no_manifest" in str(i).lower() for i in report.issues)

    def test_both_match_overall_fresh(self, tmp_path: Path):
        """Both FTS and vector match manifest → overall_fresh=True."""
        index_dir = tmp_path / ".index"
        write_manifest(IndexManifest(
            fts_count=8, vector_count=8, file_count=8,
            fts_checksum="a", vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00", build_version="1.0.0",
        ), index_dir)

        with (
            patch("tools.lib.index_freshness.get_fts_count", return_value=8),
            patch("tools.lib.index_freshness.get_vector_count", return_value=8),
        ):
            report = check_full_freshness(index_dir)

        assert report.fts_fresh is True
        assert report.vector_fresh is True
        assert report.overall_fresh is True
        assert report.issues == []

    def test_pending_non_empty_marks_stale(self, tmp_path: Path):
        """Pending queue non-empty → overall_fresh=False."""
        index_dir = tmp_path / ".index"
        write_manifest(IndexManifest(
            fts_count=5, vector_count=5, file_count=5,
            fts_checksum="a", vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00", build_version="1.0.0",
        ), index_dir)

        mark_pending("Journals/2026/03/test.md")

        with (
            patch("tools.lib.index_freshness.get_fts_count", return_value=5),
            patch("tools.lib.index_freshness.get_vector_count", return_value=5),
        ):
            report = check_full_freshness(index_dir)

        assert report.overall_fresh is False
        assert any("pending" in str(i).lower() for i in report.issues)

    def test_partial_manifest_marks_stale(self, tmp_path: Path):
        """Partial manifest → overall_fresh=False."""
        index_dir = tmp_path / ".index"
        write_manifest(IndexManifest(
            fts_count=5, vector_count=0, file_count=5,
            fts_checksum="a", vector_checksum="",
            build_timestamp="2026-04-18T12:00:00", build_version="1.0.0",
            partial=True,
        ), index_dir)

        with (
            patch("tools.lib.index_freshness.get_fts_count", return_value=5),
            patch("tools.lib.index_freshness.get_vector_count", return_value=0),
        ):
            report = check_full_freshness(index_dir)

        assert report.overall_fresh is False
        assert any("partial" in str(i).lower() for i in report.issues)

    def test_report_is_json_serializable(self, tmp_path: Path):
        """FreshnessReport can be converted to dict for JSON output."""
        import json

        index_dir = tmp_path / ".index"
        write_manifest(IndexManifest(
            fts_count=3, vector_count=3, file_count=3,
            fts_checksum="x", vector_checksum="y",
            build_timestamp="2026-04-18T12:00:00", build_version="1.0.0",
        ), index_dir)

        with (
            patch("tools.lib.index_freshness.get_fts_count", return_value=3),
            patch("tools.lib.index_freshness.get_vector_count", return_value=3),
        ):
            report = check_full_freshness(index_dir)

        d = report.to_dict()
        json_str = json.dumps(d)
        assert "fts_fresh" in json_str
        assert "vector_fresh" in json_str
        assert "overall_fresh" in json_str
