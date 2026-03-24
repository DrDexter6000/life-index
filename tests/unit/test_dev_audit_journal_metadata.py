#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


class TestJournalMetadataAuditor:
    def test_reports_scalar_topic_and_tags_fields(self, tmp_path: Path) -> None:
        from tools.dev.audit_journal_metadata import JournalMetadataAuditor

        journals_dir = tmp_path / "Journals"
        journal_dir = journals_dir / "2026" / "03"
        journal_dir.mkdir(parents=True)
        (journal_dir / "life-index_2026-03-13_001.md").write_text(
            '---\ntitle: "Legacy"\ndate: 2026-03-13\ntopic: "think"\ntags: "OpenClaw"\n---\n\nContent\n',
            encoding="utf-8",
        )

        result = JournalMetadataAuditor(journals_dir=journals_dir).run()

        assert result.summary["total_journals"] == 1
        assert result.summary["journals_with_issues"] == 1
        assert result.summary["scalar_list_fields"] == 2
        fields = {issue.field for issue in result.issues}
        assert fields == {"topic", "tags"}

    def test_ignores_proper_list_fields(self, tmp_path: Path) -> None:
        from tools.dev.audit_journal_metadata import JournalMetadataAuditor

        journals_dir = tmp_path / "Journals"
        journal_dir = journals_dir / "2026" / "03"
        journal_dir.mkdir(parents=True)
        (journal_dir / "life-index_2026-03-13_001.md").write_text(
            '---\ntitle: "Modern"\ndate: 2026-03-13\ntopic: ["think"]\ntags: ["OpenClaw"]\nmood: ["专注"]\npeople: ["乐乐"]\n---\n\nContent\n',
            encoding="utf-8",
        )

        result = JournalMetadataAuditor(journals_dir=journals_dir).run()

        assert result.summary["total_journals"] == 1
        assert result.summary["issues"] == 0
        assert result.issues == []

    def test_fix_mode_rewrites_scalar_list_fields_to_lists(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.audit_journal_metadata import JournalMetadataAuditor

        journals_dir = tmp_path / "Journals"
        journal_dir = journals_dir / "2026" / "03"
        journal_dir.mkdir(parents=True)
        journal_file = journal_dir / "life-index_2026-03-13_001.md"
        journal_file.write_text(
            '---\ntitle: "Legacy"\ndate: 2026-03-13\ntopic: "think"\nmood: "专注"\n---\n\nContent\n',
            encoding="utf-8",
        )

        auditor = JournalMetadataAuditor(journals_dir=journals_dir, dry_run=False)
        result = auditor.run()
        updated = journal_file.read_text(encoding="utf-8")

        assert result.summary["fixed_files"] == 1
        assert str(journal_file) in result.changed_files
        assert 'topic: ["think"]' in updated
        assert 'mood: ["专注"]' in updated

    def test_report_includes_rebuild_guidance_when_issues_found(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.audit_journal_metadata import (
            JournalMetadataAuditor,
            print_report,
        )

        journals_dir = tmp_path / "Journals"
        journal_dir = journals_dir / "2026" / "03"
        journal_dir.mkdir(parents=True)
        (journal_dir / "life-index_2026-03-13_001.md").write_text(
            '---\ntitle: "Legacy"\ndate: 2026-03-13\ntopic: "think"\n---\n\nContent\n',
            encoding="utf-8",
        )

        result = JournalMetadataAuditor(journals_dir=journals_dir).run()

        from io import StringIO
        from contextlib import redirect_stdout

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(result, use_json=False)

        output = buffer.getvalue()
        assert "life-index index --rebuild" in output
