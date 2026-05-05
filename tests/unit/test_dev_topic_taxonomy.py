#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


class TestTopicTaxonomyNormalizer:
    def test_reports_non_standard_topics_with_suggested_standard_mapping(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.normalize_topic_taxonomy import TopicTaxonomyNormalizer

        journals_dir = tmp_path / "Journals"
        journal_dir = journals_dir / "2026" / "03"
        journal_dir.mkdir(parents=True)
        (journal_dir / "life-index_2026-03-13_001.md").write_text(
            "---\n"
            'title: "Legacy Topic"\n'
            "date: 2026-03-13\n"
            'topic: ["learning", "general", "work"]\n'
            "---\n"
            "\n"
            "Content\n",
            encoding="utf-8",
        )

        result = TopicTaxonomyNormalizer(journals_dir=journals_dir).run()

        assert result.summary["non_standard_topics"] == 2
        suggestions = {issue.original_topic: issue.suggested_topic for issue in result.issues}
        assert suggestions["learning"] == "learn"
        assert suggestions["general"] == "life"

    def test_apply_mode_rewrites_safe_deterministic_topic_mappings(self, tmp_path: Path) -> None:
        from tools.dev.normalize_topic_taxonomy import TopicTaxonomyNormalizer

        journals_dir = tmp_path / "Journals"
        journal_dir = journals_dir / "2026" / "03"
        journal_dir.mkdir(parents=True)
        journal_file = journal_dir / "life-index_2026-03-13_001.md"
        journal_file.write_text(
            "---\n"
            'title: "Legacy Topic"\n'
            "date: 2026-03-13\n"
            'topic: ["learning", "AI", "work"]\n'
            "---\n"
            "\n"
            "Content\n",
            encoding="utf-8",
        )

        result = TopicTaxonomyNormalizer(journals_dir=journals_dir, dry_run=False).run()
        updated = journal_file.read_text(encoding="utf-8")

        assert result.summary["fixed_files"] == 1
        assert str(journal_file) in result.changed_files
        assert 'topic: ["learn", "think", "work"]' in updated

    def test_skips_unmapped_non_standard_topics_in_apply_mode(self, tmp_path: Path) -> None:
        from tools.dev.normalize_topic_taxonomy import TopicTaxonomyNormalizer

        journals_dir = tmp_path / "Journals"
        journal_dir = journals_dir / "2026" / "03"
        journal_dir.mkdir(parents=True)
        journal_file = journal_dir / "life-index_2026-03-13_001.md"
        journal_file.write_text(
            "---\n"
            'title: "Legacy Topic"\n'
            "date: 2026-03-13\n"
            'topic: ["milestone", "work"]\n'
            "---\n"
            "\n"
            "Content\n",
            encoding="utf-8",
        )

        result = TopicTaxonomyNormalizer(journals_dir=journals_dir, dry_run=False).run()
        updated = journal_file.read_text(encoding="utf-8")

        assert result.summary["fixed_files"] == 0
        assert result.summary["unmapped_topics"] == 1
        assert 'topic: ["milestone", "work"]' in updated

    def test_report_includes_standard_topic_set_and_rebuild_hint(self, tmp_path: Path) -> None:
        from tools.dev.normalize_topic_taxonomy import (
            TopicTaxonomyNormalizer,
            print_report,
        )

        journals_dir = tmp_path / "Journals"
        journal_dir = journals_dir / "2026" / "03"
        journal_dir.mkdir(parents=True)
        (journal_dir / "life-index_2026-03-13_001.md").write_text(
            '---\ntitle: "Legacy Topic"\ndate: 2026-03-13\ntopic: ["learning"]\n---\n\nContent\n',
            encoding="utf-8",
        )

        result = TopicTaxonomyNormalizer(journals_dir=journals_dir).run()

        from io import StringIO
        from contextlib import redirect_stdout

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(result, use_json=False)

        output = buffer.getvalue()
        # Match the actual sorted order of STANDARD_TOPICS rather than
        # hard-coding a fragile sequence.
        from tools.dev.normalize_topic_taxonomy import STANDARD_TOPICS

        assert ", ".join(STANDARD_TOPICS) in output
        assert "life-index index --rebuild" in output
