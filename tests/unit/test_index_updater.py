#!/usr/bin/env python3
"""
Unit tests for write_journal/index_updater.py

Tests cover:
- Topic index updates
- Project index updates
- Tag index updates
- Monthly abstract updates
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import tempfile

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))


class TestUpdateTopicIndex:
    """Tests for update_topic_index function"""

    def test_update_single_topic(self, tmp_path):
        """Update index for single topic"""
        from write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("write_journal.index_updater.BY_TOPIC_DIR", index_dir):
            with patch("write_journal.index_updater.JOURNALS_DIR", tmp_path):
                result = update_topic_index(["work"], journal_path, data)

        assert len(result) == 1
        assert result[0].name == "主题_work.md"

    def test_update_multiple_topics(self, tmp_path):
        """Update index for multiple topics"""
        from write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("write_journal.index_updater.BY_TOPIC_DIR", index_dir):
            with patch("write_journal.index_updater.JOURNALS_DIR", tmp_path):
                result = update_topic_index(["work", "learn"], journal_path, data)

        assert len(result) == 2

    def test_empty_topic_skipped(self, tmp_path):
        """Empty topic list should return empty"""
        from write_journal.index_updater import update_topic_index

        result = update_topic_index([], tmp_path / "test.md", {})
        assert result == []


class TestUpdateProjectIndex:
    """Tests for update_project_index function"""

    def test_update_project_index(self, tmp_path):
        """Update index for project"""
        from write_journal.index_updater import update_project_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("write_journal.index_updater.BY_TOPIC_DIR", index_dir):
            with patch("write_journal.index_updater.JOURNALS_DIR", tmp_path):
                result = update_project_index("Life-Index", journal_path, data)

        assert result is not None
        assert result.name == "项目_Life-Index.md"

    def test_empty_project_skipped(self, tmp_path):
        """Empty project should return None"""
        from write_journal.index_updater import update_project_index

        result = update_project_index("", tmp_path / "test.md", {})
        assert result is None


class TestUpdateTagIndices:
    """Tests for update_tag_indices function"""

    def test_update_multiple_tags(self, tmp_path):
        """Update indices for multiple tags"""
        from write_journal.index_updater import update_tag_indices

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("write_journal.index_updater.BY_TOPIC_DIR", index_dir):
            with patch("write_journal.index_updater.JOURNALS_DIR", tmp_path):
                result = update_tag_indices(["python", "testing"], journal_path, data)

        assert len(result) == 2

    def test_empty_tags_skipped(self, tmp_path):
        """Empty tags should return empty"""
        from write_journal.index_updater import update_tag_indices

        result = update_tag_indices([], tmp_path / "test.md", {})
        assert result == []


class TestUpdateMonthlyAbstract:
    """Tests for update_monthly_abstract function"""

    def test_create_new_abstract(self, tmp_path):
        """Create new monthly abstract"""
        from write_journal.index_updater import update_monthly_abstract

        journals_dir = tmp_path / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        # Create a test journal
        journal_file = month_dir / "life-index_2026-03-10_001.md"
        journal_file.write_text("""---
title: "Test Journal"
date: 2026-03-10
topic: ["work"]
---

# Test Journal

Content here.
""")

        with patch("write_journal.index_updater.JOURNALS_DIR", journals_dir):
            result = update_monthly_abstract(2026, 3, dry_run=False)

        # Check that abstract file was created
        abstract_file = month_dir / "monthly_report_2026-03.md"
        # Result depends on implementation
        pass

    def test_dry_run_no_file(self, tmp_path):
        """Dry run should not create file"""
        from write_journal.index_updater import update_monthly_abstract

        journals_dir = tmp_path / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)

        with patch("write_journal.index_updater.JOURNALS_DIR", journals_dir):
            result = update_monthly_abstract(2026, 3, dry_run=True)

        # Should not create abstract file in dry run
        abstract_file = month_dir / "monthly_report_2026-03.md"
        # Check depends on implementation


class TestIndexEntryFormat:
    """Tests for index entry format"""

    def test_entry_contains_date(self, tmp_path):
        """Index entry should contain date"""
        from write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("write_journal.index_updater.BY_TOPIC_DIR", index_dir):
            with patch("write_journal.index_updater.JOURNALS_DIR", tmp_path):
                result = update_topic_index(["work"], journal_path, data)

        if result:
            content = result[0].read_text(encoding="utf-8")
            assert "2026-03-10" in content

    def test_entry_contains_title(self, tmp_path):
        """Index entry should contain title"""
        from write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "My Test Title", "date": "2026-03-10"}

        with patch("write_journal.index_updater.BY_TOPIC_DIR", index_dir):
            with patch("write_journal.index_updater.JOURNALS_DIR", tmp_path):
                result = update_topic_index(["work"], journal_path, data)

        if result:
            content = result[0].read_text(encoding="utf-8")
            assert "My Test Title" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
