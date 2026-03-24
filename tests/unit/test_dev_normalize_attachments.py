#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


class TestAttachmentNormalizationGovernance:
    def test_classifies_legacy_attachment_patterns(self, tmp_path: Path) -> None:
        from tools.dev.normalize_attachments import AttachmentNormalizer

        journals_dir = tmp_path / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True, exist_ok=True)

        legacy = month_dir / "life-index_2026-03-08_001.md"
        legacy.write_text(
            "---\n"
            'title: "Legacy"\n'
            "date: 2026-03-08\n"
            'attachments: ["first_github_repo_v3.png"]\n'
            "---\n\n"
            "正文\n\n"
            "## Attachments\n"
            "- [first_github_repo_v3.png](../../../attachments/2026/03/first_github_repo_v3.png)\n",
            encoding="utf-8",
        )

        normalizer = AttachmentNormalizer(journals_dir=journals_dir, dry_run=True)
        result = normalizer.run()

        assert result.summary["total_journals"] == 1
        assert result.summary["migration_candidates"] == 1
        categories = {issue.category for issue in result.issues}
        assert "attachment_bare_filename" in categories
        assert "attachment_body_duplication" in categories

    def test_generates_normalized_preview_without_writing_files(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.normalize_attachments import AttachmentNormalizer

        journals_dir = tmp_path / "Journals"
        month_dir = journals_dir / "2026" / "01"
        month_dir.mkdir(parents=True, exist_ok=True)

        journal = month_dir / "life-index_2026-01-28_001.md"
        original_content = (
            "---\n"
            'title: "Legacy"\n'
            "date: 2026-01-28\n"
            'attachments: ["../../../attachments/2026/01/kimi_20260127.docx"]\n'
            "---\n\n"
            "正文\n"
        )
        journal.write_text(original_content, encoding="utf-8")

        normalizer = AttachmentNormalizer(journals_dir=journals_dir, dry_run=True)
        result = normalizer.run()

        assert journal.read_text(encoding="utf-8") == original_content
        assert len(result.previews) == 1
        preview = result.previews[0]
        assert preview["file"].endswith("life-index_2026-01-28_001.md")
        assert preview["normalized_attachments"] == [
            {
                "filename": "kimi_20260127.docx",
                "rel_path": "../../../attachments/2026/01/kimi_20260127.docx",
                "description": "",
                "source_url": None,
                "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "size": None,
            }
        ]
