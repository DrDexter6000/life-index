"""Tests for index_manifest module (Round 12 Phase 2 Task 2.1)."""

import json
from pathlib import Path

import pytest

from tools.lib.index_manifest import (
    IndexManifest,
    write_manifest,
    read_manifest,
    is_manifest_valid,
    compute_fts_checksum,
    compute_vector_checksum,
)


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".index"
    d.mkdir()
    return d


class TestIndexManifest:
    """Tests for IndexManifest dataclass and I/O."""

    def test_write_and_read_manifest(self, index_dir: Path):
        """write_manifest + read_manifest round-trips correctly."""
        manifest = IndexManifest(
            fts_count=10,
            vector_count=10,
            file_count=10,
            fts_checksum="abc123",
            vector_checksum="def456",
            build_timestamp="2026-04-18T12:00:00",
            build_version="1.0.0",
        )
        write_manifest(manifest, index_dir)

        result = read_manifest(index_dir)
        assert result is not None
        assert result.fts_count == 10
        assert result.vector_count == 10
        assert result.file_count == 10
        assert result.fts_checksum == "abc123"
        assert result.vector_checksum == "def456"
        assert result.build_timestamp == "2026-04-18T12:00:00"
        assert result.build_version == "1.0.0"

    def test_read_manifest_missing_file_returns_none(self, index_dir: Path):
        """read_manifest returns None when manifest doesn't exist."""
        result = read_manifest(index_dir)
        assert result is None

    def test_read_manifest_corrupt_json_returns_none(self, index_dir: Path):
        """read_manifest returns None for corrupt JSON."""
        (index_dir / "index_manifest.json").write_text("not valid json{{{", encoding="utf-8")
        result = read_manifest(index_dir)
        assert result is None

    def test_write_manifest_is_atomic(self, index_dir: Path):
        """Write uses temp file + rename — no partial writes visible."""
        manifest = IndexManifest(
            fts_count=5,
            vector_count=5,
            file_count=5,
            fts_checksum="x",
            vector_checksum="y",
            build_timestamp="2026-04-18T12:00:00",
            build_version="1.0.0",
        )
        write_manifest(manifest, index_dir)

        manifest_file = index_dir / "index_manifest.json"
        assert manifest_file.exists()
        # No temp files should remain
        tmp_files = list(index_dir.glob("index_manifest.json.tmp*"))
        assert tmp_files == []

    def test_manifest_json_structure(self, index_dir: Path):
        """Manifest file contains expected JSON fields."""
        manifest = IndexManifest(
            fts_count=3,
            vector_count=3,
            file_count=3,
            fts_checksum="sha_fts",
            vector_checksum="sha_vec",
            build_timestamp="2026-04-18T15:00:00",
            build_version="2.0.0",
        )
        write_manifest(manifest, index_dir)

        raw = json.loads((index_dir / "index_manifest.json").read_text(encoding="utf-8"))
        assert "fts_count" in raw
        assert "vector_count" in raw
        assert "file_count" in raw
        assert "fts_checksum" in raw
        assert "vector_checksum" in raw
        assert "build_timestamp" in raw
        assert "build_version" in raw

    def test_is_manifest_valid_when_counts_match(self, index_dir: Path):
        """is_manifest_valid returns True when all counts match."""
        manifest = IndexManifest(
            fts_count=10,
            vector_count=10,
            file_count=10,
            fts_checksum="a",
            vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00",
            build_version="1.0.0",
        )
        assert is_manifest_valid(manifest, actual_file_count=10) is True

    def test_is_manifest_valid_when_fts_count_mismatch(self, index_dir: Path):
        """is_manifest_valid returns False when fts_count != file_count."""
        manifest = IndexManifest(
            fts_count=8,
            vector_count=10,
            file_count=10,
            fts_checksum="a",
            vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00",
            build_version="1.0.0",
        )
        assert is_manifest_valid(manifest, actual_file_count=10) is False

    def test_is_manifest_valid_when_vector_count_mismatch(self, index_dir: Path):
        """is_manifest_valid returns False when vector_count != file_count."""
        manifest = IndexManifest(
            fts_count=10,
            vector_count=7,
            file_count=10,
            fts_checksum="a",
            vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00",
            build_version="1.0.0",
        )
        assert is_manifest_valid(manifest, actual_file_count=10) is False

    def test_is_manifest_valid_when_actual_file_count_mismatch(self, index_dir: Path):
        """is_manifest_valid returns False when actual_file_count != file_count."""
        manifest = IndexManifest(
            fts_count=10,
            vector_count=10,
            file_count=10,
            fts_checksum="a",
            vector_checksum="b",
            build_timestamp="2026-04-18T12:00:00",
            build_version="1.0.0",
        )
        assert is_manifest_valid(manifest, actual_file_count=5) is False


class TestChecksum:
    """Tests for FTS/vector checksum computation."""

    def test_compute_fts_checksum(self, tmp_path: Path):
        """compute_fts_checksum returns consistent MD5 hex."""
        fts_db = tmp_path / "test_fts.db"
        fts_db.write_bytes(b"hello world\n")
        result = compute_fts_checksum(fts_db)
        assert isinstance(result, str)
        assert len(result) == 32  # MD5 hex length
        # Same content = same checksum
        assert compute_fts_checksum(fts_db) == result

    def test_compute_vector_checksum(self, tmp_path: Path):
        """compute_vector_checksum returns consistent MD5 hex."""
        vec_pkl = tmp_path / "test_vec.pkl"
        vec_pkl.write_bytes(b"vector data\n")
        result = compute_vector_checksum(vec_pkl)
        assert isinstance(result, str)
        assert len(result) == 32

    def test_compute_fts_checksum_missing_file(self, tmp_path: Path):
        """compute_fts_checksum returns empty string for missing file."""
        result = compute_fts_checksum(tmp_path / "nonexistent.db")
        assert result == ""

    def test_compute_vector_checksum_missing_file(self, tmp_path: Path):
        """compute_vector_checksum returns empty string for missing file."""
        result = compute_vector_checksum(tmp_path / "nonexistent.pkl")
        assert result == ""
