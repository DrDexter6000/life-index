"""Tests for index consistency diagnostics (Round 12 Phase 0 Task 0.1)."""

import json
import pickle
import sqlite3
import pytest
from pathlib import Path
from dataclasses import asdict

from tools.build_index.diagnostics import (
    check_index_health,
    IndexHealthReport,
    _scan_actual_journals,
    _read_fts_paths,
    _read_vector_paths,
)


@pytest.fixture
def fresh_data_dir(tmp_path: Path) -> Path:
    """Create a minimal data directory structure for testing."""
    data_dir = tmp_path / "Life-Index"
    journals_dir = data_dir / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True)
    index_dir = data_dir / ".index"
    index_dir.mkdir()
    return data_dir


def _create_journal(journals_dir: Path, name: str, title: str = "Test") -> Path:
    """Create a minimal journal file."""
    month_dir = journals_dir / "2026" / "03"
    month_dir.mkdir(parents=True, exist_ok=True)
    p = month_dir / name
    p.write_text(f"---\ntitle: \"{title}\"\ndate: 2026-03-01\ntopic: [life]\n---\n# {title}\nBody", encoding="utf-8")
    return p


def _create_fts_db(index_dir: Path, paths: list[str]) -> Path:
    """Create a minimal FTS database with given paths."""
    db_path = index_dir / "journals_fts.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS journals (
            path TEXT PRIMARY KEY, title TEXT, content TEXT,
            date TEXT, location TEXT, weather TEXT, topic TEXT,
            project TEXT, tags TEXT, mood TEXT, people TEXT,
            file_hash TEXT, modified_time TEXT, title_segmented TEXT
        )
    """)
    for p in paths:
        conn.execute(
            "INSERT OR REPLACE INTO journals (path, title, date, file_hash) VALUES (?, ?, ?, ?)",
            (p, "Test", "2026-03-01", "abc123"),
        )
    conn.commit()
    conn.close()
    return db_path


def _create_vector_pickle(index_dir: Path, paths: list[str]) -> Path:
    """Create a minimal vector pickle with given paths."""
    import numpy as np

    pkl_path = index_dir / "vectors_simple.pkl"
    vectors = {}
    for p in paths:
        vectors[p] = {
            "embedding": np.random.rand(10).tolist(),
            "date": "2026-03-01",
            "hash": "abc123",
        }
    with open(pkl_path, "wb") as f:
        pickle.dump(vectors, f)
    return pkl_path


# --- Tests ---


class TestIndexHealthReport:
    """Test IndexHealthReport dataclass."""

    def test_report_is_json_serializable(self):
        report = IndexHealthReport(
            fts_count=10, vector_count=10, file_count=10,
            fts_orphans=set(), fts_missing=set(),
            vec_orphans=set(), vec_missing=set(),
            issues=[],
        )
        d = asdict(report)
        d["fts_orphans"] = list(d["fts_orphans"])
        d["fts_missing"] = list(d["fts_missing"])
        d["vec_orphans"] = list(d["vec_orphans"])
        d["vec_missing"] = list(d["vec_missing"])
        json.dumps(d)  # Should not raise


class TestScanActualJournals:
    """Test _scan_actual_journals helper."""

    def test_empty_directory(self, fresh_data_dir: Path):
        paths = _scan_actual_journals(fresh_data_dir)
        assert paths == set()

    def test_finds_life_index_files(self, fresh_data_dir: Path):
        journals_dir = fresh_data_dir / "Journals"
        _create_journal(journals_dir, "life-index_2026-03-01_001.md")
        _create_journal(journals_dir, "life-index_2026-03-01_002.md")
        paths = _scan_actual_journals(fresh_data_dir)
        assert len(paths) == 2

    def test_ignores_non_journal_files(self, fresh_data_dir: Path):
        journals_dir = fresh_data_dir / "Journals"
        month = journals_dir / "2026" / "03"
        month.mkdir(parents=True, exist_ok=True)
        (month / "index_2026-03.md").write_text("# Index")
        (month / "monthly_report_2026-03.md").write_text("# Report")
        (month / "life-index_2026-03-01_001.md").write_text("---\ntitle: T\n---\n# T")
        paths = _scan_actual_journals(fresh_data_dir)
        assert len(paths) == 1

    def test_ignores_revisions_directory(self, fresh_data_dir: Path):
        journals_dir = fresh_data_dir / "Journals"
        month = journals_dir / "2026" / "03"
        month.mkdir(parents=True, exist_ok=True)
        rev_dir = month / ".revisions"
        rev_dir.mkdir()
        (rev_dir / "life-index_2026-03-01_001_20260418_120000_000000.md").write_text("---\n---")
        (month / "life-index_2026-03-01_001.md").write_text("---\ntitle: T\n---\n# T")
        paths = _scan_actual_journals(fresh_data_dir)
        assert len(paths) == 1


class TestReadFtsPaths:
    """Test _read_fts_paths helper."""

    def test_no_db(self, fresh_data_dir: Path):
        paths = _read_fts_paths(fresh_data_dir / ".index")
        assert paths == set()

    def test_reads_paths_from_db(self, fresh_data_dir: Path):
        index_dir = fresh_data_dir / ".index"
        _create_fts_db(index_dir, ["Journals/2026/03/a.md", "Journals/2026/03/b.md"])
        paths = _read_fts_paths(index_dir)
        assert paths == {"Journals/2026/03/a.md", "Journals/2026/03/b.md"}


class TestReadVectorPaths:
    """Test _read_vector_paths helper."""

    def test_no_pickle(self, fresh_data_dir: Path):
        paths = _read_vector_paths(fresh_data_dir / ".index")
        assert paths == set()

    def test_reads_paths_from_pickle(self, fresh_data_dir: Path):
        index_dir = fresh_data_dir / ".index"
        _create_vector_pickle(index_dir, ["Journals/2026/03/a.md", "Journals/2026/03/b.md"])
        paths = _read_vector_paths(index_dir)
        assert paths == {"Journals/2026/03/a.md", "Journals/2026/03/b.md"}


class TestCheckIndexHealth:
    """Test main check_index_health function."""

    def test_empty_directory_no_crash(self, fresh_data_dir: Path):
        report = check_index_health(fresh_data_dir)
        assert report.file_count == 0
        assert report.fts_count == 0
        assert report.vector_count == 0
        assert report.consistency_ok is True
        assert report.issues == []

    def test_all_three_consistent(self, fresh_data_dir: Path):
        journals_dir = fresh_data_dir / "Journals"
        index_dir = fresh_data_dir / ".index"
        paths = ["Journals/2026/03/life-index_2026-03-01_001.md"]
        _create_journal(journals_dir, "life-index_2026-03-01_001.md")
        _create_fts_db(index_dir, paths)
        _create_vector_pickle(index_dir, paths)

        report = check_index_health(fresh_data_dir)
        assert report.file_count == 1
        assert report.fts_count == 1
        assert report.vector_count == 1
        assert report.consistency_ok is True
        assert report.fts_ok is True
        assert report.vector_ok is True

    def test_fts_missing_entries(self, fresh_data_dir: Path):
        """File exists on disk but not in FTS."""
        journals_dir = fresh_data_dir / "Journals"
        index_dir = fresh_data_dir / ".index"
        _create_journal(journals_dir, "life-index_2026-03-01_001.md")
        _create_journal(journals_dir, "life-index_2026-03-01_002.md")
        _create_fts_db(index_dir, ["Journals/2026/03/life-index_2026-03-01_001.md"])
        _create_vector_pickle(index_dir, ["Journals/2026/03/life-index_2026-03-01_001.md"])

        report = check_index_health(fresh_data_dir)
        assert report.fts_ok is False
        assert len(report.fts_missing) == 1
        assert report.vector_ok is False
        assert len(report.issues) > 0

    def test_fts_stale_entries(self, fresh_data_dir: Path):
        """FTS has entry but file doesn't exist on disk."""
        journals_dir = fresh_data_dir / "Journals"
        index_dir = fresh_data_dir / ".index"
        _create_journal(journals_dir, "life-index_2026-03-01_001.md")
        _create_fts_db(index_dir, [
            "Journals/2026/03/life-index_2026-03-01_001.md",
            "Journals/2026/03/life-index_2026-03-01_999.md",  # stale
        ])
        _create_vector_pickle(index_dir, ["Journals/2026/03/life-index_2026-03-01_001.md"])

        report = check_index_health(fresh_data_dir)
        assert report.fts_ok is False
        assert len(report.fts_orphans) == 1
        assert any("stale" in issue.lower() or "orphan" in issue.lower() for issue in report.issues)

    def test_vector_missing_entries(self, fresh_data_dir: Path):
        """File exists but not in vector index."""
        journals_dir = fresh_data_dir / "Journals"
        index_dir = fresh_data_dir / ".index"
        path1 = "Journals/2026/03/life-index_2026-03-01_001.md"
        path2 = "Journals/2026/03/life-index_2026-03-01_002.md"
        _create_journal(journals_dir, "life-index_2026-03-01_001.md")
        _create_journal(journals_dir, "life-index_2026-03-01_002.md")
        _create_fts_db(index_dir, [path1, path2])
        _create_vector_pickle(index_dir, [path1])  # missing path2

        report = check_index_health(fresh_data_dir)
        assert report.vector_ok is False
        assert len(report.vec_missing) == 1

    def test_no_index_dir(self, tmp_path: Path):
        """data_dir exists but .index dir doesn't."""
        data_dir = tmp_path / "Life-Index"
        data_dir.mkdir()
        report = check_index_health(data_dir)
        assert report.fts_count == 0
        assert report.vector_count == 0
        assert report.file_count == 0
