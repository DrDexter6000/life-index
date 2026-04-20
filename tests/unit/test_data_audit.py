"""Tests for data directory audit (Round 12 Phase 0 Task 0.3)."""

import json
import pytest
from pathlib import Path

from tools.lib.data_audit import (
    audit_data_directory,
    DataAuditReport,
    Anomaly,
)


@pytest.fixture
def fresh_data_dir(tmp_path: Path) -> Path:
    """Create a minimal data directory structure for testing."""
    data_dir = tmp_path / "Life-Index"
    journals_dir = data_dir / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True)
    return data_dir


def _create_journal(journals_dir: Path, name: str, title: str = "Test") -> Path:
    """Create a minimal journal file under the standard month structure."""
    month_dir = journals_dir / "2026" / "03"
    month_dir.mkdir(parents=True, exist_ok=True)
    p = month_dir / name
    p.write_text(
        f'---\ntitle: "{title}"\ndate: 2026-03-01\ntopic: [life]\n---\n# {title}\nBody',
        encoding="utf-8",
    )
    return p


class TestAnomaly:
    """Test Anomaly dataclass."""

    def test_anomaly_is_json_serializable(self):
        anomaly = Anomaly(
            type="naming",
            severity="warning",
            description="Non-standard file name",
            path="Journals/2026/03/weird.md",
        )
        d = anomaly.__dict__.copy()
        result = json.dumps(d)
        assert "naming" in result


class TestAuditDataDirectory:
    """Test audit_data_directory function."""

    def test_clean_directory_no_anomalies(self, fresh_data_dir: Path):
        """A clean directory with only properly-named journals returns no anomalies."""
        journals_dir = fresh_data_dir / "Journals"
        _create_journal(journals_dir, "life-index_2026-03-01_001.md")
        _create_journal(journals_dir, "life-index_2026-03-02_001.md")

        report = audit_data_directory(fresh_data_dir)
        assert report.anomalies == []
        assert report.file_count == 2

    def test_empty_directory_no_crash(self, fresh_data_dir: Path):
        """Empty directory doesn't crash."""
        report = audit_data_directory(fresh_data_dir)
        assert report.anomalies == []
        assert report.file_count == 0

    def test_detects_revision_files_in_journals(self, fresh_data_dir: Path):
        """Revision files (*.YYYYMMDD.HHMMSS*.md) loose in Journals/ are flagged."""
        journals_dir = fresh_data_dir / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True, exist_ok=True)
        # Create a revision file directly in the month dir (NOT inside .revisions/)
        (month_dir / "life-index_2026-03-01_001_20260418_120000_000000.md").write_text("---\n---")
        _create_journal(journals_dir, "life-index_2026-03-01_001.md")

        report = audit_data_directory(fresh_data_dir)
        assert len(report.anomalies) >= 1
        assert any(a.type == "revision_file" for a in report.anomalies)

    def test_detects_non_standard_naming(self, fresh_data_dir: Path):
        """Files not matching standard naming patterns are flagged."""
        journals_dir = fresh_data_dir / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True, exist_ok=True)
        (month_dir / "random_notes.md").write_text("# Random")
        (month_dir / "diary_2026.md").write_text("# Diary")
        _create_journal(journals_dir, "life-index_2026-03-01_001.md")

        report = audit_data_directory(fresh_data_dir)
        naming_anomalies = [a for a in report.anomalies if a.type == "naming"]
        assert len(naming_anomalies) >= 1

    def test_accepts_index_and_report_files(self, fresh_data_dir: Path):
        """Standard index_ and monthly_report_ files are NOT flagged."""
        journals_dir = fresh_data_dir / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True, exist_ok=True)
        (month_dir / "index_2026-03.md").write_text("# Index")
        (month_dir / "monthly_report_2026-03.md").write_text("# Report")
        _create_journal(journals_dir, "life-index_2026-03-01_001.md")

        report = audit_data_directory(fresh_data_dir)
        naming_anomalies = [a for a in report.anomalies if a.type == "naming"]
        assert len(naming_anomalies) == 0

    def test_detects_distribution_anomaly(self, fresh_data_dir: Path):
        """A month with >> 3x the average journal count is flagged."""
        journals_dir = fresh_data_dir / "Journals"
        # Create 2 journals in March (normal)
        for i in range(1, 3):
            _create_journal(journals_dir, f"life-index_2026-03-0{i}_001.md")
        # Create 2 journals in May (normal)
        may_dir = journals_dir / "2026" / "05"
        may_dir.mkdir(parents=True, exist_ok=True)
        for i in range(1, 3):
            (may_dir / f"life-index_2026-05-{i:02d}_001.md").write_text(
                f'---\ntitle: "Day {i}"\ndate: 2026-05-{i:02d}\ntopic: [life]\n---\n# Day {i}',
                encoding="utf-8",
            )
        # Create 50 journals in April (anomalous — avg=~18, threshold=~54, 50 < 54)
        # Need 3 months so avg is low enough. Let's use 1, 1, and 50.
        # Actually, let's use: Feb=1, Mar=1, Apr=50 → avg=17.3, threshold=52, 50<52
        # Use: Jan=1, Feb=1, Mar=1, Apr=100 → avg=25.75, threshold=77.25, 100>77 ✓
        jan_dir = journals_dir / "2026" / "01"
        jan_dir.mkdir(parents=True, exist_ok=True)
        (jan_dir / "life-index_2026-01-01_001.md").write_text("# Jan")
        feb_dir = journals_dir / "2026" / "02"
        feb_dir.mkdir(parents=True, exist_ok=True)
        (feb_dir / "life-index_2026-02-01_001.md").write_text("# Feb")
        # 100 journals in April
        apr_dir = journals_dir / "2026" / "04"
        apr_dir.mkdir(parents=True, exist_ok=True)
        for i in range(1, 101):
            (apr_dir / f"life-index_2026-04-{i:02d}_001.md").write_text(
                f'---\ntitle: "Day {i}"\ndate: 2026-04-{i:02d}\ntopic: [life]\n---\n# Day {i}',
                encoding="utf-8",
            )

        report = audit_data_directory(fresh_data_dir)
        dist_anomalies = [a for a in report.anomalies if a.type == "distribution"]
        assert len(dist_anomalies) >= 1

    def test_report_is_json_serializable(self, fresh_data_dir: Path):
        """Full report must be JSON-serializable."""
        journals_dir = fresh_data_dir / "Journals"
        _create_journal(journals_dir, "life-index_2026-03-01_001.md")

        report = audit_data_directory(fresh_data_dir)
        d = {
            "file_count": report.file_count,
            "anomalies": [a.__dict__ for a in report.anomalies],
            "distribution": report.distribution,
        }
        serialized = json.dumps(d, ensure_ascii=False)
        assert isinstance(serialized, str)
