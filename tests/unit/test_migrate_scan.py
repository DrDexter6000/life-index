"""Tests for migrate --dry-run scan functionality."""

import json
import pytest
from pathlib import Path


class TestMigrateScan:
    def _create_journal(self, path: Path, schema_version: int, **extra) -> None:
        """Helper: create a test journal with specified schema_version."""
        fields: dict = {
            "schema_version": schema_version,
            "title": "test",
            "date": "2026-01-01",
            "topic": ["work"],
            **extra,
        }
        lines = ["---"]
        for k, v in fields.items():
            if isinstance(v, list):
                lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
            elif v is None:
                lines.append(f"{k}: null")
            else:
                lines.append(f"{k}: {v}")
        lines.append("---")
        lines.append("")
        lines.append("# Test content")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")

    def test_scan_finds_outdated_journals(self, tmp_path: Path):
        """--dry-run should detect journals with schema_version < CURRENT."""
        from tools.migrate import scan_journals
        from tools.lib.schema import SCHEMA_VERSION

        journals_dir = tmp_path / "Journals" / "2026" / "01"
        self._create_journal(
            journals_dir / "life-index_2026-01-01_001.md",
            schema_version=1,
        )
        self._create_journal(
            journals_dir / "life-index_2026-01-02_001.md",
            schema_version=SCHEMA_VERSION,
        )

        report = scan_journals(tmp_path / "Journals")
        assert report["total_scanned"] == 2
        assert report["version_distribution"]["1"] == 1
        assert report["version_distribution"][str(SCHEMA_VERSION)] == 1
        assert report["needs_migration"] == 1
        assert len(report["outdated_files"]) == 1

    def test_scan_empty_directory(self, tmp_path: Path):
        """Empty directory should return zero-count report."""
        from tools.migrate import scan_journals

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir()
        report = scan_journals(journals_dir)
        assert report["total_scanned"] == 0
        assert report["needs_migration"] == 0

    def test_scan_detects_missing_fields(self, tmp_path: Path):
        """Should detect missing recommended fields."""
        from tools.migrate import scan_journals

        journals_dir = tmp_path / "Journals" / "2026" / "01"
        self._create_journal(
            journals_dir / "life-index_2026-01-01_001.md",
            schema_version=1,
        )

        report = scan_journals(tmp_path / "Journals")
        assert len(report["outdated_files"]) == 1
        missing = report["outdated_files"][0]["missing_fields"]
        assert "sentiment_score" in missing

    def test_scan_ignores_index_files(self, tmp_path: Path):
        """Non-journal files (index, report) should be ignored."""
        from tools.migrate import scan_journals
        from tools.lib.schema import SCHEMA_VERSION

        journals_dir = tmp_path / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)

        (journals_dir / "index_2026-03.md").write_text("# 索引", encoding="utf-8")
        (journals_dir / "report_2026-03.md").write_text("# 报告", encoding="utf-8")
        self._create_journal(
            journals_dir / "life-index_2026-03-01_001.md",
            schema_version=SCHEMA_VERSION,
        )

        report = scan_journals(tmp_path / "Journals")
        assert report["total_scanned"] == 1

    def test_scan_output_structure(self, tmp_path: Path):
        """Scan report should contain all required keys."""
        from tools.migrate import scan_journals

        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir()
        report = scan_journals(journals_dir)

        required_keys = {
            "total_scanned",
            "version_distribution",
            "needs_migration",
            "outdated_files",
        }
        assert required_keys.issubset(set(report.keys()))
