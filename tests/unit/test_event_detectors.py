"""Tests for built-in event detectors."""

import os
import time
import pytest
from pathlib import Path


class TestNoJournalStreakDetector:
    def test_detects_7_day_gap(self, tmp_path: Path):
        """7+ days without a journal should trigger an event."""
        from tools.lib.event_detectors import check_no_journal_streak

        journals_dir = tmp_path / "Journals"
        old_month = journals_dir / "2026" / "03"
        old_month.mkdir(parents=True)
        old_file = old_month / "life-index_2026-03-28_001.md"
        old_file.write_text("---\ntitle: old\n---\n", encoding="utf-8")
        # Set mtime to 10 days ago
        old_time = time.time() - 10 * 86400
        os.utime(old_file, (old_time, old_time))

        events = check_no_journal_streak({"journals_dir": journals_dir})
        assert len(events) == 1
        assert events[0].type == "no_journal_streak"

    def test_no_event_if_recent_journal(self, tmp_path: Path):
        """Recent journal should not trigger streak event."""
        from tools.lib.event_detectors import check_no_journal_streak

        journals_dir = tmp_path / "Journals" / "2026" / "04"
        journals_dir.mkdir(parents=True)
        (journals_dir / "life-index_2026-04-08_001.md").write_text(
            "---\ntitle: today\n---\n", encoding="utf-8"
        )

        events = check_no_journal_streak({"journals_dir": journals_dir})
        assert len(events) == 0

    def test_no_crash_if_no_journals_dir(self):
        """Missing journals_dir should return empty list."""
        from tools.lib.event_detectors import check_no_journal_streak

        events = check_no_journal_streak({"journals_dir": None})
        assert events == []


class TestMonthlyReviewDueDetector:
    def test_detects_missing_review(self, tmp_path: Path):
        """Last month without report file should trigger event."""
        from tools.lib.event_detectors import check_monthly_review_due

        journals_dir = tmp_path / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)
        (journals_dir / "life-index_2026-03-15_001.md").write_text(
            "---\ntitle: test\n---\n", encoding="utf-8"
        )

        events = check_monthly_review_due({"journals_dir": tmp_path / "Journals"})
        has_review_due = any(e.type == "monthly_review_due" for e in events)
        assert has_review_due

    def test_no_event_if_report_exists(self, tmp_path: Path):
        """Existing report file should not trigger event."""
        from tools.lib.event_detectors import check_monthly_review_due

        journals_dir = tmp_path / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)
        (journals_dir / "report_2026-03.md").write_text("# Report", encoding="utf-8")

        events = check_monthly_review_due({"journals_dir": tmp_path / "Journals"})
        review_events = [
            e
            for e in events
            if e.type == "monthly_review_due" and "2026-03" in e.data.get("month", "")
        ]
        assert len(review_events) == 0


class TestEntityAuditDueDetector:
    def test_detects_stale_entity_graph(self, tmp_path: Path):
        """entity_graph.yaml > 30 days unmodified should trigger."""
        from tools.lib.event_detectors import check_entity_audit_due

        graph_file = tmp_path / "entity_graph.yaml"
        graph_file.write_text("entities: []", encoding="utf-8")
        old_time = time.time() - 35 * 86400
        os.utime(graph_file, (old_time, old_time))

        events = check_entity_audit_due({"data_dir": tmp_path})
        assert len(events) == 1
        assert events[0].type == "entity_audit_due"

    def test_no_event_if_recently_modified(self, tmp_path: Path):
        """Recently modified entity_graph.yaml should not trigger."""
        from tools.lib.event_detectors import check_entity_audit_due

        graph_file = tmp_path / "entity_graph.yaml"
        graph_file.write_text("entities: []", encoding="utf-8")

        events = check_entity_audit_due({"data_dir": tmp_path})
        assert len(events) == 0

    def test_no_crash_if_no_entity_graph(self, tmp_path: Path):
        """Missing entity_graph.yaml should return empty list."""
        from tools.lib.event_detectors import check_entity_audit_due

        events = check_entity_audit_due({"data_dir": tmp_path})
        assert events == []


class TestSchemaMigrationAvailableDetector:
    def test_detects_outdated_schema(self, tmp_path: Path):
        """Journals with old schema version should trigger event."""
        from tools.lib.event_detectors import check_schema_migration_available

        journals_dir = tmp_path / "Journals" / "2025" / "01"
        journals_dir.mkdir(parents=True)
        (journals_dir / "life-index_2025-01-01_001.md").write_text(
            "---\nschema_version: 1\ntitle: old\ndate: 2025-01-01\n---\n",
            encoding="utf-8",
        )

        events = check_schema_migration_available(
            {"journals_dir": tmp_path / "Journals"}
        )
        assert len(events) == 1
        assert events[0].type == "schema_migration_available"


class TestIndexStaleDetector:
    def test_detects_stale_index(self, tmp_path: Path):
        """Journal mtime > index mtime should trigger event."""
        from tools.lib.event_detectors import check_index_stale

        journals_dir = tmp_path / "Journals" / "2026" / "04"
        journals_dir.mkdir(parents=True)
        index_dir = tmp_path / ".index"
        index_dir.mkdir()

        journal = journals_dir / "life-index_2026-04-08_001.md"
        journal.write_text("---\ntitle: new\n---\n", encoding="utf-8")

        fts_db = index_dir / "journals_fts.db"
        fts_db.write_text("", encoding="utf-8")
        old_time = time.time() - 3600
        os.utime(fts_db, (old_time, old_time))

        events = check_index_stale(
            {"data_dir": tmp_path, "journals_dir": tmp_path / "Journals"}
        )
        assert any(e.type == "index_stale" for e in events)

    def test_no_event_if_index_fresh(self, tmp_path: Path):
        """Index newer than journals should not trigger."""
        from tools.lib.event_detectors import check_index_stale

        journals_dir = tmp_path / "Journals" / "2026" / "04"
        journals_dir.mkdir(parents=True)
        index_dir = tmp_path / ".index"
        index_dir.mkdir()

        journal = journals_dir / "life-index_2026-04-08_001.md"
        journal.write_text("---\ntitle: old\n---\n", encoding="utf-8")
        old_time = time.time() - 3600
        os.utime(journal, (old_time, old_time))

        fts_db = index_dir / "journals_fts.db"
        fts_db.write_text("", encoding="utf-8")
        # Index is newer (current time)
        os.utime(fts_db, None)

        events = check_index_stale(
            {"data_dir": tmp_path, "journals_dir": tmp_path / "Journals"}
        )
        assert not any(e.type == "index_stale" for e in events)
