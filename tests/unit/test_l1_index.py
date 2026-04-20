#!/usr/bin/env python3
"""
Unit tests for tools/search_journals/l1_index.py

Tests cover:
- L1 index scanning
- Topic/project/tag search
"""

import pytest
from unittest.mock import patch


class TestSearchL1Index:
    """Tests for search_l1_index function"""

    def test_search_topic(self, tmp_path):
        """Search by topic"""
        from tools.search_journals import l1_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir(parents=True)

        index_file = index_dir / "主题_work.md"
        index_file.write_text(
            """# 主题: work

- [2026-03-14] [Test Journal](../../Journals/2026/03/test.md)
""",
            encoding="utf-8",
        )

        with patch.object(l1_index, "get_by_topic_dir", return_value=index_dir):
            results = l1_index.search_l1_index("topic", "work")

        assert len(results) >= 1

    def test_search_project(self, tmp_path):
        """Search by project"""
        from tools.search_journals import l1_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir(parents=True)

        index_file = index_dir / "项目_Life-Index.md"
        index_file.write_text(
            """# 项目: Life-Index

- [2026-03-14] [Project Update](../../Journals/2026/03/update.md)
""",
            encoding="utf-8",
        )

        with patch.object(l1_index, "get_by_topic_dir", return_value=index_dir):
            results = l1_index.search_l1_index("project", "Life-Index")

        assert len(results) >= 1

    def test_search_tag(self, tmp_path):
        """Search by tag"""
        from tools.search_journals import l1_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir(parents=True)

        index_file = index_dir / "标签_python.md"
        index_file.write_text(
            """# 标签: python

- [2026-03-14] [Python Tips](../../Journals/2026/03/tips.md)
""",
            encoding="utf-8",
        )

        with patch.object(l1_index, "get_by_topic_dir", return_value=index_dir):
            results = l1_index.search_l1_index("tag", "python")

        assert len(results) >= 1

    def test_search_tag_uses_sanitized_filename(self, tmp_path):
        """Tag search should use the same sanitized filename logic as write-time index updates."""
        from tools.search_journals import l1_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir(parents=True)

        index_file = index_dir / "标签_UI_UX设计.md"
        index_file.write_text(
            """# 标签: UI/UX设计

- [2026-03-14] [Design Notes](../../Journals/2026/03/design.md)
""",
            encoding="utf-8",
        )

        with patch.object(l1_index, "get_by_topic_dir", return_value=index_dir):
            results = l1_index.search_l1_index("tag", "UI/UX设计")

        assert len(results) >= 1

    def test_search_nonexistent(self, tmp_path):
        """Search for nonexistent returns empty"""
        from tools.search_journals import l1_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir(parents=True)

        with patch.object(l1_index, "get_by_topic_dir", return_value=index_dir):
            results = l1_index.search_l1_index("topic", "nonexistent")

        assert results == []


class TestScanAllIndices:
    """Tests for scan_all_indices function"""

    def test_scan_multiple(self, tmp_path):
        """Scan multiple index files"""
        from tools.search_journals import l1_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir(parents=True)

        (index_dir / "主题_work.md").write_text("- [2026-03-14] [A](path/a.md)", encoding="utf-8")
        (index_dir / "主题_learn.md").write_text("- [2026-03-14] [B](path/b.md)", encoding="utf-8")

        with patch.object(l1_index, "get_by_topic_dir", return_value=index_dir):
            results = l1_index.scan_all_indices()

        assert len(results) >= 1

    def test_scan_empty(self, tmp_path):
        """Scan empty directory returns empty"""
        from tools.search_journals import l1_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir(parents=True)

        with patch.object(l1_index, "get_by_topic_dir", return_value=index_dir):
            results = l1_index.scan_all_indices()

        assert results == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
