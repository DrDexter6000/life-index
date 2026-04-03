#!/usr/bin/env python3
"""
Unit tests for tools/edit_journal/__init__.py

Tests cover:
- Journal parsing
- Frontmatter updates
- Index operations
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestParseJournal:
    """Tests for parse_journal function"""

    def test_parse_valid_journal(self, tmp_path):
        """Parse a valid journal file"""
        from tools.edit_journal import parse_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            """---
title: Test Journal
date: 2026-03-14
location: Beijing
---

# Test Content
""",
            encoding="utf-8",
        )

        metadata, body = parse_journal(journal)

        assert metadata.get("title") == "Test Journal"
        assert "Test Content" in body

    def test_parse_nonexistent_file(self, tmp_path):
        """Parse nonexistent file"""
        from tools.edit_journal import parse_journal

        nonexistent = tmp_path / "nonexistent.md"
        metadata, body = parse_journal(nonexistent)

        assert "_error" in metadata or metadata.get("title") is None


class TestRemoveFromIndex:
    """Tests for remove_from_index function"""

    def test_remove_existing_entry(self, tmp_path):
        """Remove existing entry from index"""
        from tools.edit_journal import remove_from_index

        index_file = tmp_path / "index.md"
        index_file.write_text(
            """# 主题: work

- [2026-03-14] [Test](../../Journals/2026/03/test_001.md)
- [2026-03-15] [Other](../../Journals/2026/03/other_001.md)
""",
            encoding="utf-8",
        )

        result = remove_from_index(index_file, "test_001.md")

        assert result is True
        content = index_file.read_text(encoding="utf-8")
        assert "test_001.md" not in content
        assert "other_001.md" in content

    def test_remove_nonexistent_entry(self, tmp_path):
        """Remove nonexistent entry returns False"""
        from tools.edit_journal import remove_from_index

        index_file = tmp_path / "index.md"
        index_file.write_text(
            """# 主题: work

- [2026-03-14] [Test](../../Journals/2026/03/test_001.md)
""",
            encoding="utf-8",
        )

        result = remove_from_index(index_file, "nonexistent.md")

        assert result is False

    def test_remove_from_nonexistent_index(self, tmp_path):
        """Remove from nonexistent index returns False"""
        from tools.edit_journal import remove_from_index

        nonexistent = tmp_path / "nonexistent.md"
        result = remove_from_index(nonexistent, "test.md")

        assert result is False


class TestNormalizeToList:
    """Tests for _normalize_to_list helper"""

    def test_string_to_list(self):
        """String becomes list"""
        from tools.edit_journal import _normalize_to_list

        assert _normalize_to_list("work") == ["work"]

    def test_list_unchanged(self):
        """List stays as list"""
        from tools.edit_journal import _normalize_to_list

        assert _normalize_to_list(["work", "learn"]) == ["work", "learn"]

    def test_empty_returns_empty(self):
        """Empty returns empty list"""
        from tools.edit_journal import _normalize_to_list

        assert _normalize_to_list(None) == []
        assert _normalize_to_list("") == []
        assert _normalize_to_list([]) == []

    def test_non_string_non_list_returns_empty(self):
        """Non-string, non-list types return empty list"""
        from tools.edit_journal import _normalize_to_list

        assert _normalize_to_list(123) == []
        assert _normalize_to_list({"key": "value"}) == []
        assert _normalize_to_list(("tuple", "value")) == []


class TestAddToIndex:
    """Tests for add_to_index function"""

    def test_add_to_existing_index(self, tmp_path):
        """Add entry to existing index file"""
        from tools.edit_journal import add_to_index

        index_file = tmp_path / "主题_work.md"
        index_file.write_text(
            "# 主题：work\n\n- [2026-03-13] [Old](path/old.md)\n", encoding="utf-8"
        )

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test_001.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        data = {"date": "2026-03-14T10:00:00", "title": "Test Entry"}
        add_to_index(index_file, journal_path, data)

        content = index_file.read_text(encoding="utf-8")
        assert "Test Entry" in content
        assert "2026-03-14" in content

    def test_create_new_topic_index(self, tmp_path):
        """Create new index file with topic prefix"""
        from tools.edit_journal import add_to_index

        index_file = tmp_path / "主题_learn.md"
        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"date": "2026-03-14T10:00:00", "title": "Learning"}
        add_to_index(index_file, journal_path, data)

        content = index_file.read_text(encoding="utf-8")
        assert "# 主题：learn" in content
        assert "Learning" in content

    def test_create_new_project_index(self, tmp_path):
        """Create new index file with project prefix"""
        from tools.edit_journal import add_to_index

        index_file = tmp_path / "项目_MyProject.md"
        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"date": "2026-03-14T10:00:00", "title": "Project Update"}
        add_to_index(index_file, journal_path, data)

        content = index_file.read_text(encoding="utf-8")
        assert "# 项目：MyProject" in content

    def test_create_new_tag_index(self, tmp_path):
        """Create new index file with tag prefix"""
        from tools.edit_journal import add_to_index

        index_file = tmp_path / "标签_重要.md"
        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"date": "2026-03-14T10:00:00", "title": "Important Note"}
        add_to_index(index_file, journal_path, data)

        content = index_file.read_text(encoding="utf-8")
        assert "# 标签：重要" in content

    def test_create_new_generic_index(self, tmp_path):
        """Create new index file without special prefix"""
        from tools.edit_journal import add_to_index

        index_file = tmp_path / "custom_index.md"
        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"date": "2026-03-14T10:00:00", "title": "Custom Entry"}
        add_to_index(index_file, journal_path, data)

        content = index_file.read_text(encoding="utf-8")
        assert "# custom_index" in content
        assert "Custom Entry" in content

    def test_prevent_duplicate_entries(self, tmp_path):
        """Prevent duplicate entries in index"""
        from tools.edit_journal import add_to_index

        index_file = tmp_path / "主题_work.md"
        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"date": "2026-03-14T10:00:00", "title": "Test"}

        # Add twice
        add_to_index(index_file, journal_path, data)
        add_to_index(index_file, journal_path, data)

        content = index_file.read_text(encoding="utf-8")
        assert content.count("Test") == 1


class TestUpdateIndicesForChange:
    """Tests for update_indices_for_change function"""

    def test_topic_change(self, tmp_path):
        """Update indices when topic changes"""
        from tools.edit_journal import update_indices_for_change

        # Create old index
        old_index = tmp_path / "主题_work.md"
        old_index.write_text(
            "# 主题：work\n\n- [2026-03-14] [Test](path.md)\n", encoding="utf-8"
        )

        journal_path = tmp_path / "test.md"
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"topic": ["work"]}
        new_data = {"topic": ["learn"], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        assert len(updated) >= 1

    def test_topic_removal(self, tmp_path):
        """Remove topic from index when topic is removed"""
        from tools.edit_journal import update_indices_for_change

        # Create old index with entry
        old_index = tmp_path / "主题_work.md"
        old_index.write_text(
            "# 主题：work\n\n- [2026-03-14] [test.md](path/test.md)\n", encoding="utf-8"
        )

        journal_path = tmp_path / "test.md"
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"topic": ["work"]}
        new_data = {"topic": [], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        # Old index should be updated (entry removed)
        assert len(updated) >= 1

    def test_topic_addition(self, tmp_path):
        """Add topic to index when new topic is added"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"topic": []}
        new_data = {"topic": ["work"], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        # New index should be created
        assert len(updated) >= 1
        new_index = tmp_path / "主题_work.md"
        assert new_index.exists()

    def test_project_change(self, tmp_path):
        """Update indices when project changes"""
        from tools.edit_journal import update_indices_for_change

        old_index = tmp_path / "项目_OldProject.md"
        old_index.write_text(
            "# 项目：OldProject\n\n- [Test](path.md)\n", encoding="utf-8"
        )

        journal_path = tmp_path / "test.md"
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"project": "OldProject"}
        new_data = {"project": "NewProject", "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        assert len(updated) >= 1

    def test_project_removal(self, tmp_path):
        """Remove project from index when project is removed"""
        from tools.edit_journal import update_indices_for_change

        old_index = tmp_path / "项目_OldProject.md"
        old_index.write_text(
            "# 项目：OldProject\n\n- [2026-03-14] [test.md](path/test.md)\n",
            encoding="utf-8",
        )

        journal_path = tmp_path / "test.md"
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"project": "OldProject"}
        new_data = {"project": "", "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        assert len(updated) >= 1

    def test_project_addition(self, tmp_path):
        """Add project to index when new project is added"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"project": ""}
        new_data = {"project": "NewProject", "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        assert len(updated) >= 1
        new_index = tmp_path / "项目_NewProject.md"
        assert new_index.exists()

    def test_tags_change(self, tmp_path):
        """Update indices when tags change"""
        from tools.edit_journal import update_indices_for_change

        old_index = tmp_path / "标签_old.md"
        old_index.write_text("# 标签：old\n\n- [Test](path.md)\n", encoding="utf-8")

        journal_path = tmp_path / "test.md"
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"tags": ["old"]}
        new_data = {"tags": ["new"], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        assert len(updated) >= 1

    def test_tags_removal(self, tmp_path):
        """Remove tag from index when tag is removed"""
        from tools.edit_journal import update_indices_for_change

        old_index = tmp_path / "标签_oldtag.md"
        old_index.write_text(
            "# 标签：oldtag\n\n- [2026-03-14] [test.md](path/test.md)\n",
            encoding="utf-8",
        )

        journal_path = tmp_path / "test.md"
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"tags": ["oldtag"]}
        new_data = {"tags": [], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        assert len(updated) >= 1

    def test_tags_addition(self, tmp_path):
        """Add tag to index when new tag is added"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"tags": []}
        new_data = {"tags": ["newtag"], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        assert len(updated) >= 1
        new_index = tmp_path / "标签_newtag.md"
        assert new_index.exists()


class TestEditJournal:
    """Tests for edit_journal main function"""

    def test_edit_nonexistent_journal(self, tmp_path):
        """Edit nonexistent journal returns error"""
        from tools.edit_journal import edit_journal

        nonexistent = tmp_path / "nonexistent.md"
        result = edit_journal(nonexistent, {"weather": "Sunny"})

        assert result["success"] is False
        assert result["error"]["code"] == "E0500"

    def test_edit_no_changes_specified(self, tmp_path):
        """Edit with no changes returns error"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\n# Content\n", encoding="utf-8"
        )

        result = edit_journal(journal, {})

        assert result["success"] is False
        assert result["error"]["code"] == "E0503"

    def test_edit_with_dry_run(self, tmp_path):
        """Edit with dry_run doesn't modify file"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        original = "---\ntitle: Test\ndate: 2026-03-14\n---\n\n# Content\n"
        journal.write_text(original, encoding="utf-8")

        result = edit_journal(journal, {"weather": "Sunny"}, dry_run=True)

        assert result["success"] is True
        assert "preview" in result
        assert journal.read_text(encoding="utf-8") == original

    def test_edit_update_weather(self, tmp_path):
        """Edit updates weather field"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\n# Content\n", encoding="utf-8"
        )

        result = edit_journal(journal, {"weather": "Sunny"})

        assert result["success"] is True
        assert "weather" in result["changes"]

        content = journal.read_text(encoding="utf-8")
        assert "Sunny" in content

    def test_edit_location_without_weather_rejected(self, tmp_path):
        """Location changes must include weather"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        original = (
            "---\n"
            "title: Test\n"
            "date: 2026-03-14\n"
            "location: Chongqing, China\n"
            "weather: Sunny\n"
            "---\n\n"
            "# Content\n"
        )
        journal.write_text(original, encoding="utf-8")

        result = edit_journal(journal, {"location": "Beijing, China"})

        assert result["success"] is False
        assert result["error"]["code"] == "E0504"
        assert journal.read_text(encoding="utf-8") == original

    def test_edit_location_with_weather_succeeds(self, tmp_path):
        """Location and weather can be updated together"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\n"
            "title: Test\n"
            "date: 2026-03-14\n"
            "location: Chongqing, China\n"
            "weather: Sunny\n"
            "---\n\n"
            "# Content\n",
            encoding="utf-8",
        )

        result = edit_journal(
            journal,
            {"location": "Beijing, China", "weather": "Cloudy 18°C"},
        )

        assert result["success"] is True
        assert result["changes"]["location"]["new"] == "Beijing, China"
        assert result["changes"]["weather"]["new"] == "Cloudy 18°C"

        content = journal.read_text(encoding="utf-8")
        assert "Beijing, China" in content
        assert "Cloudy 18°C" in content

    def test_edit_append_content(self, tmp_path):
        """Edit appends content to body"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\n# Content\n", encoding="utf-8"
        )

        with patch(
            "tools.edit_journal.update_vector_index", return_value=False
        ) as mock_update:
            result = edit_journal(journal, {}, append_content="New paragraph")

        assert result["success"] is True
        assert result["content_modified"] is True
        mock_update.assert_called_once()

        content = journal.read_text(encoding="utf-8")
        assert "New paragraph" in content

    def test_edit_replace_content(self, tmp_path):
        """Edit replaces body content"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\n# Old Content\n",
            encoding="utf-8",
        )

        with patch(
            "tools.edit_journal.update_vector_index", return_value=False
        ) as mock_update:
            result = edit_journal(
                journal, {}, replace_content="# New Content\n\nReplaced."
            )

        assert result["success"] is True
        assert result["content_modified"] is True
        mock_update.assert_called_once()

        content = journal.read_text(encoding="utf-8")
        assert "Old Content" not in content
        assert "New Content" in content

    def test_edit_delete_field_with_empty_string(self, tmp_path):
        """Edit deletes field when value is empty string"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\nweather: Sunny\n---\n\n# Content\n",
            encoding="utf-8",
        )

        result = edit_journal(journal, {"weather": ""})

        assert result["success"] is True
        assert result["changes"]["weather"]["new"] is None

    def test_edit_delete_field_with_none(self, tmp_path):
        """Edit deletes field when value is None"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\nweather: Sunny\n---\n\n# Content\n",
            encoding="utf-8",
        )

        result = edit_journal(journal, {"weather": None})

        assert result["success"] is True
        assert result["changes"]["weather"]["new"] is None

    def test_edit_append_to_empty_body(self, tmp_path):
        """Edit appends content when body is empty"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\n",
            encoding="utf-8",
        )

        with patch("tools.edit_journal.update_vector_index", return_value=False):
            result = edit_journal(journal, {}, append_content="First content")

        assert result["success"] is True
        assert result["content_modified"] is True

        content = journal.read_text(encoding="utf-8")
        assert "First content" in content

    def test_edit_updates_indices_on_topic_change(self, tmp_path):
        """Edit updates indices when topic changes"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\ntopic: [work]\n---\n\n# Content\n",
            encoding="utf-8",
        )

        # Create old topic index
        old_index = tmp_path / "by-topic" / "主题_work.md"
        old_index.parent.mkdir(parents=True, exist_ok=True)
        old_index.write_text(
            "# 主题：work\n\n- [2026-03-14] [test.md](Journals/2026/03/test.md)\n",
            encoding="utf-8",
        )

        with patch("tools.edit_journal.JOURNALS_DIR", journal.parent.parent):
            with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path / "by-topic"):
                with patch(
                    "tools.edit_journal.update_vector_index", return_value=False
                ):
                    result = edit_journal(journal, {"topic": ["learn"]})

        assert result["success"] is True
        assert len(result["indices_updated"]) >= 1

    def test_edit_updates_indices_on_project_change(self, tmp_path):
        """Edit updates indices when project changes"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\nproject: OldProject\n---\n\n# Content\n",
            encoding="utf-8",
        )

        # Create old project index
        old_index = tmp_path / "by-topic" / "项目_OldProject.md"
        old_index.parent.mkdir(parents=True, exist_ok=True)
        old_index.write_text(
            "# 项目：OldProject\n\n- [2026-03-14] [test.md](Journals/2026/03/test.md)\n",
            encoding="utf-8",
        )

        with patch("tools.edit_journal.JOURNALS_DIR", journal.parent.parent):
            with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path / "by-topic"):
                with patch(
                    "tools.edit_journal.update_vector_index", return_value=False
                ):
                    result = edit_journal(journal, {"project": "NewProject"})

        assert result["success"] is True
        assert len(result["indices_updated"]) >= 1

    def test_edit_updates_indices_on_tags_change(self, tmp_path):
        """Edit updates indices when tags change"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\ntags: [old]\n---\n\n# Content\n",
            encoding="utf-8",
        )

        # Create old tag index
        old_index = tmp_path / "by-topic" / "标签_old.md"
        old_index.parent.mkdir(parents=True, exist_ok=True)
        old_index.write_text(
            "# 标签：old\n\n- [2026-03-14] [test.md](Journals/2026/03/test.md)\n",
            encoding="utf-8",
        )

        with patch("tools.edit_journal.JOURNALS_DIR", journal.parent.parent):
            with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path / "by-topic"):
                with patch(
                    "tools.edit_journal.update_vector_index", return_value=False
                ):
                    result = edit_journal(journal, {"tags": ["new"]})

        assert result["success"] is True
        assert len(result["indices_updated"]) >= 1

    def test_edit_vector_index_update_success(self, tmp_path):
        """Edit updates vector index successfully"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\n# Content\n",
            encoding="utf-8",
        )

        with patch(
            "tools.edit_journal.update_vector_index", return_value=True
        ) as mock_update:
            result = edit_journal(journal, {"title": "New Title"})

        assert result["success"] is True
        assert result.get("vector_index_updated") is True
        mock_update.assert_called_once()

    def test_edit_vector_index_update_failure_handled(self, tmp_path):
        """Edit handles vector index update failure gracefully"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\n# Content\n",
            encoding="utf-8",
        )

        with patch(
            "tools.edit_journal.update_vector_index",
            side_effect=Exception("Vector index error"),
        ) as mock_update:
            result = edit_journal(journal, {"title": "New Title"})

        assert result["success"] is True
        mock_update.assert_called_once()

    def test_edit_io_error_handling(self, tmp_path):
        """Edit handles IOError gracefully"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\n# Content\n",
            encoding="utf-8",
        )

        # Mock Path.write_text to raise IOError
        with patch("pathlib.Path.write_text", side_effect=IOError("Disk full")):
            result = edit_journal(journal, {"weather": "Sunny"})

        assert result["success"] is False
        assert result["error"]["code"] == "E0200"  # WRITE_FAILED

    def test_edit_os_error_handling(self, tmp_path):
        """Edit handles OSError gracefully"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\n# Content\n",
            encoding="utf-8",
        )

        # Mock Path.write_text to raise OSError
        with patch("pathlib.Path.write_text", side_effect=OSError("Permission denied")):
            result = edit_journal(journal, {"weather": "Sunny"})

        assert result["success"] is False
        assert result["error"]["code"] == "E0200"  # WRITE_FAILED

    def test_edit_field_update_same_value(self, tmp_path):
        """Edit doesn't record change when value is same"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\nweather: Sunny\n---\n\n# Content\n",
            encoding="utf-8",
        )

        result = edit_journal(journal, {"weather": "Sunny"})

        assert result["success"] is True
        # No change recorded since value is same
        assert "weather" not in result["changes"]

    def test_edit_location_with_empty_weather_rejected(self, tmp_path):
        """Location changes with empty weather string are rejected"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        original = (
            "---\n"
            "title: Test\n"
            "date: 2026-03-14\n"
            "location: Chongqing, China\n"
            "weather: Sunny\n"
            "---\n\n"
            "# Content\n"
        )
        journal.write_text(original, encoding="utf-8")

        result = edit_journal(journal, {"location": "Beijing, China", "weather": ""})

        assert result["success"] is False
        assert result["error"]["code"] == "E0504"

    def test_edit_delete_nonexistent_field(self, tmp_path):
        """Edit handles deletion of nonexistent field gracefully"""
        from tools.edit_journal import edit_journal

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\n# Content\n",
            encoding="utf-8",
        )

        # Try to delete a field that doesn't exist
        result = edit_journal(journal, {"nonexistent_field": ""})

        assert result["success"] is True
        # No change recorded since field didn't exist
        assert "nonexistent_field" not in result["changes"]

    def test_edit_preserves_structured_links_and_attachments_updates(self, tmp_path):
        """Edit should round-trip structured links and attachments without corruption."""
        from tools.edit_journal import edit_journal
        from tools.lib.frontmatter import parse_frontmatter

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\n"
            'title: "Test"\n'
            "date: 2026-03-14\n"
            'links: ["https://example.com/a"]\n'
            'attachments: [{"filename": "old.png", "rel_path": "../../../attachments/2026/03/old.png"}]\n'
            "---\n\n"
            "# Content\n",
            encoding="utf-8",
        )

        result = edit_journal(
            journal,
            {
                "links": ["https://example.com/b", "https://example.com/c"],
                "attachments": [
                    "../../../attachments/2026/03/new.png",
                    {
                        "filename": "deck.pdf",
                        "rel_path": "../../../attachments/2026/03/deck.pdf",
                    },
                ],
            },
        )

        assert result["success"] is True

        metadata, _body = parse_frontmatter(journal.read_text(encoding="utf-8"))
        assert metadata["links"] == [
            "https://example.com/b",
            "https://example.com/c",
        ]
        assert metadata["attachments"] == [
            "../../../attachments/2026/03/new.png",
            {
                "filename": "deck.pdf",
                "rel_path": "../../../attachments/2026/03/deck.pdf",
            },
        ]

    def test_edit_lock_timeout(self, tmp_path):
        """Edit handles lock timeout gracefully"""
        from tools.edit_journal import edit_journal
        from tools.lib.file_lock import LockTimeoutError

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\n# Content\n",
            encoding="utf-8",
        )

        # Mock FileLock to raise LockTimeoutError
        with patch("tools.edit_journal.FileLock") as mock_lock:
            mock_lock_instance = MagicMock()
            mock_lock_instance.__enter__ = MagicMock(
                side_effect=LockTimeoutError(str(journal), 30.0)
            )
            mock_lock_instance.__exit__ = MagicMock(return_value=False)
            mock_lock.return_value = mock_lock_instance

            result = edit_journal(journal, {"weather": "Sunny"})

        assert result["success"] is False
        assert result["error"]["code"] == "E0005"  # LOCK_TIMEOUT

    def test_edit_reloads_current_state_after_lock_acquisition(self, tmp_path):
        """Edit should merge updates with the latest on-disk state acquired under lock."""
        from tools.edit_journal import edit_journal
        from tools.lib.frontmatter import parse_journal_file

        journal = tmp_path / "test.md"
        journal.write_text(
            "---\n"
            'title: "Old Title"\n'
            "date: 2026-03-14\n"
            'weather: "Rainy"\n'
            "---\n\n"
            "# Content\n",
            encoding="utf-8",
        )

        external_content = (
            "---\n"
            'title: "External Title"\n'
            "date: 2026-03-14\n"
            'weather: "Rainy"\n'
            "---\n\n"
            "# Content\n"
        )

        class MutatingLock:
            def __enter__(self):
                journal.write_text(external_content, encoding="utf-8")
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("tools.edit_journal.FileLock", return_value=MutatingLock()):
            result = edit_journal(journal, {"weather": "Sunny"})

        assert result["success"] is True

        metadata = parse_journal_file(journal)
        assert metadata["title"] == "External Title"
        assert metadata["weather"] == "Sunny"

        revision_path = Path(result["revision_path"])
        assert revision_path.exists()
        revision_text = revision_path.read_text(encoding="utf-8")
        assert 'title: "External Title"' in revision_text

    def test_update_indices_topic_already_in_updated(self, tmp_path):
        """Test topic index already in updated_indices"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        # Create index file
        idx_file = tmp_path / "主题_work.md"
        idx_file.write_text("# 主题：work\n\n", encoding="utf-8")

        old_data = {"topic": []}
        new_data = {"topic": ["work"], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            # First call adds to updated_indices
            updated = update_indices_for_change(journal_path, old_data, new_data)
            # Second call should not add duplicate
            updated2 = update_indices_for_change(journal_path, old_data, new_data)

        assert str(idx_file) in updated

    def test_update_indices_project_already_in_updated(self, tmp_path):
        """Test project index already in updated_indices"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        # Create old project index with entry
        old_idx = tmp_path / "项目_OldProject.md"
        old_idx.write_text(
            "# 项目：OldProject\n\n- [2026-03-14] [test.md](path/test.md)\n",
            encoding="utf-8",
        )

        old_data = {"project": "OldProject"}
        new_data = {"project": "NewProject", "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        assert len(updated) >= 1

    def test_update_indices_tags_already_in_updated(self, tmp_path):
        """Test tag index already in updated_indices"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        # Create old tag index with entry
        old_idx = tmp_path / "标签_oldtag.md"
        old_idx.write_text(
            "# 标签：oldtag\n\n- [2026-03-14] [test.md](path/test.md)\n",
            encoding="utf-8",
        )

        old_data = {"tags": ["oldtag"]}
        new_data = {"tags": ["newtag"], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        assert len(updated) >= 1

    def test_update_indices_topic_in_both_old_and_new(self, tmp_path):
        """Test topic that exists in both old and new (no removal)"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"topic": ["work", "learn"]}
        new_data = {"topic": ["work", "create"], "date": "2026-03-14", "title": "Test"}

        # Create index for 'learn' (will be removed)
        learn_idx = tmp_path / "主题_learn.md"
        learn_idx.write_text(
            "# 主题：learn\n\n- [2026-03-14] [test.md](path/test.md)\n",
            encoding="utf-8",
        )

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        # 'work' should not be removed (it's in both), 'learn' should be removed
        assert len(updated) >= 1

    def test_update_indices_empty_topic_in_list(self, tmp_path):
        """Test handling of empty string in topic list"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"topic": []}
        new_data = {"topic": ["", "work"], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        # Only 'work' should be added, empty string should be skipped
        work_idx = tmp_path / "主题_work.md"
        assert work_idx.exists()

    def test_update_indices_empty_tag_in_list(self, tmp_path):
        """Test handling of empty string in tags set"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"tags": []}
        new_data = {"tags": ["", "important"], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        # Only 'important' should be added, empty string should be skipped
        tag_idx = tmp_path / "标签_important.md"
        assert tag_idx.exists()

    def test_update_indices_topic_index_already_in_updated(self, tmp_path):
        """Test topic index already in updated_indices when adding"""
        from tools.edit_journal import update_indices_for_change, add_to_index

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        # Create index file
        idx_file = tmp_path / "主题_work.md"
        idx_file.write_text("# 主题：work\n\n", encoding="utf-8")

        old_data = {"topic": ["work"]}  # work is already in old
        new_data = {"topic": ["work"], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            # First add the index to updated_indices via removal
            updated = update_indices_for_change(
                journal_path, {"topic": ["work", "learn"]}, new_data
            )

        # The index should be in updated_indices from the removal of 'learn'
        # and the addition of 'work' should not add duplicate

    def test_update_indices_project_remove_not_in_updated(self, tmp_path):
        """Test project removal when index not already in updated_indices"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        # Create old project index with entry
        old_idx = tmp_path / "项目_OldProject.md"
        old_idx.write_text(
            "# 项目：OldProject\n\n- [2026-03-14] [test.md](path/test.md)\n",
            encoding="utf-8",
        )

        old_data = {"project": "OldProject"}
        new_data = {"project": "", "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        # Index should be in updated_indices
        assert len(updated) >= 1

    def test_update_indices_tag_remove_not_in_updated(self, tmp_path):
        """Test tag removal when index not already in updated_indices"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        # Create old tag index with entry
        old_idx = tmp_path / "标签_oldtag.md"
        old_idx.write_text(
            "# 标签：oldtag\n\n- [2026-03-14] [test.md](path/test.md)\n",
            encoding="utf-8",
        )

        old_data = {"tags": ["oldtag"]}
        new_data = {"tags": [], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        # Index should be in updated_indices
        assert len(updated) >= 1

    def test_update_indices_tag_add_not_in_updated(self, tmp_path):
        """Test tag addition when index not already in updated_indices"""
        from tools.edit_journal import update_indices_for_change

        journal_path = tmp_path / "Journals" / "2026" / "03" / "test.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("# Test", encoding="utf-8")

        old_data = {"tags": []}
        new_data = {"tags": ["newtag"], "date": "2026-03-14", "title": "Test"}

        with patch("tools.edit_journal.BY_TOPIC_DIR", tmp_path):
            updated = update_indices_for_change(journal_path, old_data, new_data)

        # Index should be in updated_indices
        assert len(updated) >= 1
        assert tmp_path / "标签_newtag.md" in [Path(u) for u in updated]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
