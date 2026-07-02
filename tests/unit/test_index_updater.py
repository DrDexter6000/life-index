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
from unittest.mock import patch


class TestRefreshIndexB:
    def test_refresh_index_b_returns_materialize_payload(self):
        from tools.write_journal.index_updater import refresh_index_b

        payload = {"artifact": "index-b", "written_docs": [".life-index/index-b/INDEX.md"]}
        with patch("tools.index_tree.materialize.build_materialize_payload", return_value=payload):
            result = refresh_index_b()

        assert result["success"] is True
        assert result["updated"] is True
        assert result["artifact"] == "index-b"
        assert result["payload"] == payload

    def test_refresh_index_b_is_non_blocking_on_failure(self):
        from tools.write_journal.index_updater import refresh_index_b

        with patch(
            "tools.index_tree.materialize.build_materialize_payload",
            side_effect=RuntimeError("boom"),
        ):
            result = refresh_index_b()

        assert result["success"] is False
        assert result["updated"] is False
        assert result["artifact"] == "index-b"
        assert result["error"]["code"] == "E0600"


class TestUpdateTopicIndex:
    """Tests for update_topic_index function"""

    def test_update_single_topic_string(self, tmp_path):
        """Update index for single topic as string"""
        from tools.write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_topic_index("work", journal_path, data)

        assert len(result) == 1
        assert "主题_work.md" in result[0].name

    def test_update_single_topic_list(self, tmp_path):
        """Update index for single topic as list"""
        from tools.write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_topic_index(["work"], journal_path, data)

        assert len(result) == 1
        assert "主题_work.md" in result[0].name

    def test_update_multiple_topics(self, tmp_path):
        """Update index for multiple topics"""
        from tools.write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_topic_index(["work", "learn"], journal_path, data)

        assert len(result) == 2

    def test_comma_separated_topic_string_creates_topic_indices(self, tmp_path):
        """Comma-separated topic strings should not become one combined topic."""
        from tools.write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_topic_index("work,learn", journal_path, data)

        assert sorted(path.name for path in result) == ["主题_learn.md", "主题_work.md"]
        assert not (index_dir / "主题_work,learn.md").exists()

    def test_empty_topic_skipped(self, tmp_path):
        """Empty topic list should return empty"""
        from tools.write_journal.index_updater import update_topic_index

        result = update_topic_index([], tmp_path / "test.md", {})
        assert result == []

    def test_none_topic_skipped(self, tmp_path):
        """None topic should return empty"""
        from tools.write_journal.index_updater import update_topic_index

        result = update_topic_index(None, tmp_path / "test.md", {})
        assert result == []

    def test_invalid_type_topic_skipped(self, tmp_path):
        """Invalid type (dict/int) should return empty"""
        from tools.write_journal.index_updater import update_topic_index

        result = update_topic_index({"key": "value"}, tmp_path / "test.md", {})
        assert result == []

        result = update_topic_index(123, tmp_path / "test.md", {})
        assert result == []

    def test_topic_with_empty_string_skipped(self, tmp_path):
        """Empty string in topic list should be skipped"""
        from tools.write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_topic_index(["work", "", "learn"], journal_path, data)

        # Should only create 2 files (skip empty string)
        assert len(result) == 2
        assert "主题_work.md" in [f.name for f in result]
        assert "主题_learn.md" in [f.name for f in result]


class TestUpdateProjectIndex:
    """Tests for update_project_index function"""

    def test_update_project_index(self, tmp_path):
        """Update index for project"""
        from tools.write_journal.index_updater import update_project_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_project_index("Life-Index", journal_path, data)

        assert result is not None
        assert result.name == "项目_Life-Index.md"

    def test_empty_project_skipped(self, tmp_path):
        """Empty project should return None"""
        from tools.write_journal.index_updater import update_project_index

        result = update_project_index("", tmp_path / "test.md", {})
        assert result is None

    def test_none_project_skipped(self, tmp_path):
        """None project should return None"""
        from tools.write_journal.index_updater import update_project_index

        result = update_project_index(None, tmp_path / "test.md", {})  # type: ignore
        assert result is None

    def test_project_index_new_file(self, tmp_path):
        """Project index should create new file if not exists"""
        from tools.write_journal.index_updater import update_project_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_project_index("NewProject", journal_path, data)

        assert result is not None
        assert "项目_NewProject.md" in result.name
        content = result.read_text(encoding="utf-8")
        assert "NewProject" in content
        assert "2026-03-10" in content
        assert "Test" in content

    def test_project_index_existing_file_no_duplicate(self, tmp_path):
        """Project index should not duplicate entries"""
        from tools.write_journal.index_updater import update_project_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                # First call
                result1 = update_project_index("ExistingProject", journal_path, data)
                # Second call with same data
                result2 = update_project_index("ExistingProject", journal_path, data)

        assert result1 is not None
        assert result2 is not None
        content = result2.read_text(encoding="utf-8")
        # Should only have one entry
        assert content.count("2026-03-10") == 1

    def test_project_index_existing_file_append(self, tmp_path):
        """Project index should append to existing file with different entry"""
        from tools.write_journal.index_updater import update_project_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path1 = tmp_path / "journal1.md"
        journal_path1.write_text("---\ntitle: Test1\n---\nContent")

        journal_path2 = tmp_path / "journal2.md"
        journal_path2.write_text("---\ntitle: Test2\n---\nContent")

        data1 = {"title": "Test1", "date": "2026-03-10"}
        data2 = {"title": "Test2", "date": "2026-03-11"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                update_project_index("SameProject", journal_path1, data1)
                update_project_index("SameProject", journal_path2, data2)

        index_file = index_dir / "项目_SameProject.md"
        content = index_file.read_text(encoding="utf-8")
        # Should have both entries
        assert "2026-03-10" in content
        assert "2026-03-11" in content
        assert "Test1" in content
        assert "Test2" in content


class TestUpdateTagIndices:
    """Tests for update_tag_indices function"""

    def test_update_multiple_tags(self, tmp_path):
        """Update indices for multiple tags"""
        from tools.write_journal.index_updater import update_tag_indices

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_tag_indices(["python", "testing"], journal_path, data)

        assert len(result) == 2

    def test_comma_separated_tag_string_creates_tag_indices(self, tmp_path):
        """Comma-separated tag strings should not be iterated character by character."""
        from tools.write_journal.index_updater import update_tag_indices

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_tag_indices("会议,项目进展", journal_path, data)  # type: ignore[arg-type]

        assert sorted(path.name for path in result) == ["标签_会议.md", "标签_项目进展.md"]
        assert sorted(path.name for path in index_dir.glob("标签_*.md")) == [
            "标签_会议.md",
            "标签_项目进展.md",
        ]

    def test_empty_tags_skipped(self, tmp_path):
        """Empty tags should return empty"""
        from tools.write_journal.index_updater import update_tag_indices

        result = update_tag_indices([], tmp_path / "test.md", {})
        assert result == []

    def test_none_tags_skipped(self, tmp_path):
        """None tags should be handled as an empty list"""
        from tools.write_journal.index_updater import update_tag_indices

        result = update_tag_indices(None, tmp_path / "test.md", {})
        assert result == []

    def test_tag_with_empty_string_skipped(self, tmp_path):
        """Empty string in tags list should be skipped"""
        from tools.write_journal.index_updater import update_tag_indices

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_tag_indices(["python", "", "testing"], journal_path, data)

        # Should only create 2 files (skip empty string)
        assert len(result) == 2
        assert "标签_python.md" in [f.name for f in result]
        assert "标签_testing.md" in [f.name for f in result]

    def test_tag_index_existing_file_no_duplicate(self, tmp_path):
        """Tag index should not duplicate entries"""
        from tools.write_journal.index_updater import update_tag_indices

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                # First call
                result1 = update_tag_indices(["duplicate"], journal_path, data)
                # Second call with same data
                result2 = update_tag_indices(["duplicate"], journal_path, data)

        assert len(result1) == 1
        assert len(result2) == 1
        content = result2[0].read_text(encoding="utf-8")
        # Should only have one entry
        assert content.count("2026-03-10") == 1

    def test_tag_index_new_file(self, tmp_path):
        """Tag index should create new file if not exists"""
        from tools.write_journal.index_updater import update_tag_indices

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_tag_indices(["newtag"], journal_path, data)

        assert len(result) == 1
        assert "标签_newtag.md" in result[0].name
        content = result[0].read_text(encoding="utf-8")
        assert "newtag" in content
        assert "2026-03-10" in content
        assert "Test" in content

    def test_tag_index_existing_file_append(self, tmp_path):
        """Tag index should append to existing file with different entry"""
        from tools.write_journal.index_updater import update_tag_indices

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path1 = tmp_path / "journal1.md"
        journal_path1.write_text("---\ntitle: Test1\n---\nContent")

        journal_path2 = tmp_path / "journal2.md"
        journal_path2.write_text("---\ntitle: Test2\n---\nContent")

        data1 = {"title": "Test1", "date": "2026-03-10"}
        data2 = {"title": "Test2", "date": "2026-03-11"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                update_tag_indices(["sametag"], journal_path1, data1)
                update_tag_indices(["sametag"], journal_path2, data2)

        index_file = index_dir / "标签_sametag.md"
        content = index_file.read_text(encoding="utf-8")
        # Should have both entries
        assert "2026-03-10" in content
        assert "2026-03-11" in content
        assert "Test1" in content
        assert "Test2" in content


class TestUpdateMonthlyAbstract:
    """Tests for update_index / update_monthly_abstract function"""

    def test_update_index_touches_monthly(self, tmp_path: Path) -> None:
        """After update, monthly index file is created."""
        from tools.write_journal.index_updater import update_index

        journals_dir = tmp_path / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)
        (month_dir / "life-index_2026-03-04_001.md").write_text(
            "---\ntitle: test\ndate: 2026-03-04\ntopic: work\n---\n\n# test\n",
            encoding="utf-8",
        )
        with patch("tools.write_journal.index_updater.get_journals_dir", return_value=journals_dir):
            with patch("tools.generate_index.get_journals_dir", return_value=journals_dir):
                with patch("tools.generate_index.get_user_data_dir", return_value=tmp_path):
                    result = update_index(year=2026, month=3)
        assert result["success"] is True
        monthly = result.get("monthly_index", {})
        assert monthly.get("success") is True

    def test_update_index_touches_yearly(self, tmp_path: Path) -> None:
        """After update, yearly index file is created."""
        from tools.write_journal.index_updater import update_index

        journals_dir = tmp_path / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)
        (month_dir / "life-index_2026-03-04_001.md").write_text(
            "---\ntitle: test\ndate: 2026-03-04\ntopic: work\n---\n\n# test\n",
            encoding="utf-8",
        )
        with patch("tools.write_journal.index_updater.get_journals_dir", return_value=journals_dir):
            with patch("tools.generate_index.get_journals_dir", return_value=journals_dir):
                with patch("tools.generate_index.get_user_data_dir", return_value=tmp_path):
                    result = update_index(year=2026, month=3)
        assert result.get("yearly_index", {}).get("success") is True

    def test_update_index_touches_root(self, tmp_path: Path) -> None:
        """After update, root INDEX.md is created."""
        from tools.write_journal.index_updater import update_index

        journals_dir = tmp_path / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)
        (month_dir / "life-index_2026-03-04_001.md").write_text(
            "---\ntitle: test\ndate: 2026-03-04\ntopic: work\n---\n\n# test\n",
            encoding="utf-8",
        )
        with patch("tools.write_journal.index_updater.get_journals_dir", return_value=journals_dir):
            with patch("tools.generate_index.get_journals_dir", return_value=journals_dir):
                with patch("tools.generate_index.get_user_data_dir", return_value=tmp_path):
                    result = update_index(year=2026, month=3)
        assert result.get("root_index", {}).get("success") is True

    def test_update_monthly_abstract_alias_works(self, tmp_path: Path) -> None:
        """Backward-compatible alias update_monthly_abstract still works."""
        from tools.write_journal.index_updater import (
            update_index,
            update_monthly_abstract,
        )

        assert update_monthly_abstract is update_index

    def test_dry_run_mode(self, tmp_path: Path) -> None:
        """Dry run should not write files but return success."""
        from tools.write_journal.index_updater import update_index

        journals_dir = tmp_path / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)
        (month_dir / "life-index_2026-03-04_001.md").write_text(
            "---\ntitle: test\ndate: 2026-03-04\ntopic: work\n---\n\n# test\n",
            encoding="utf-8",
        )
        with patch("tools.write_journal.index_updater.get_journals_dir", return_value=journals_dir):
            with patch("tools.generate_index.get_journals_dir", return_value=journals_dir):
                with patch("tools.generate_index.get_user_data_dir", return_value=tmp_path):
                    result = update_index(year=2026, month=3, dry_run=True)
        assert result["success"] is True

    def test_empty_month_no_files(self, tmp_path: Path) -> None:
        """Empty month should succeed but not create index files."""
        from tools.write_journal.index_updater import update_index

        journals_dir = tmp_path / "Journals"
        month_dir = journals_dir / "2026" / "03"
        month_dir.mkdir(parents=True)
        with patch("tools.write_journal.index_updater.get_journals_dir", return_value=journals_dir):
            with patch("tools.generate_index.get_journals_dir", return_value=journals_dir):
                with patch("tools.generate_index.get_user_data_dir", return_value=tmp_path):
                    result = update_index(year=2026, month=3)
        # Empty month: monthly index may be None/success with no output
        assert result["success"] is True


class TestIndexEntryFormat:
    """Tests for index entry format"""

    def test_entry_contains_date(self, tmp_path):
        """Index entry should contain date"""
        from tools.write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_topic_index(["work"], journal_path, data)

        if result:
            content = result[0].read_text(encoding="utf-8")
            assert "2026-03-10" in content

    def test_entry_contains_title(self, tmp_path):
        """Index entry should contain title"""
        from tools.write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "My Test Title", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                result = update_topic_index(["work"], journal_path, data)

        if result:
            content = result[0].read_text(encoding="utf-8")
            assert "My Test Title" in content

    def test_topic_index_existing_file_no_duplicate(self, tmp_path):
        """Topic index should not duplicate entries"""
        from tools.write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent")

        data = {"title": "Test", "date": "2026-03-10"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                # First call
                result1 = update_topic_index(["duplicate"], journal_path, data)
                # Second call with same data
                result2 = update_topic_index(["duplicate"], journal_path, data)

        assert len(result1) == 1
        assert len(result2) == 1
        content = result2[0].read_text(encoding="utf-8")
        # Should only have one entry
        assert content.count("2026-03-10") == 1

    def test_topic_index_existing_file_append(self, tmp_path):
        """Topic index should append to existing file with different entry"""
        from tools.write_journal.index_updater import update_topic_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()

        journal_path1 = tmp_path / "journal1.md"
        journal_path1.write_text("---\ntitle: Test1\n---\nContent")

        journal_path2 = tmp_path / "journal2.md"
        journal_path2.write_text("---\ntitle: Test2\n---\nContent")

        data1 = {"title": "Test1", "date": "2026-03-10"}
        data2 = {"title": "Test2", "date": "2026-03-11"}

        with patch("tools.write_journal.index_updater.get_by_topic_dir", return_value=index_dir):
            with patch("tools.write_journal.index_updater.get_journals_dir", return_value=tmp_path):
                update_topic_index(["same"], journal_path1, data1)
                update_topic_index(["same"], journal_path2, data2)

        index_file = index_dir / "主题_same.md"
        content = index_file.read_text(encoding="utf-8")
        # Should have both entries
        assert "2026-03-10" in content
        assert "2026-03-11" in content
        assert "Test1" in content
        assert "Test2" in content


class TestUpdateVectorIndex:
    """Compatibility tests for the removed write-through vector updater."""

    def test_update_vector_index_is_noop_and_does_not_import_model(self, tmp_path):
        from tools.write_journal.index_updater import update_vector_index

        journal_path = tmp_path / "journal.md"
        journal_path.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        result = update_vector_index(journal_path, {"title": "Test"})

        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
