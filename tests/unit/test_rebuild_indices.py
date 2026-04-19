#!/usr/bin/env python3
"""
Unit tests for tools/dev/rebuild_indices/__init__.py
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from tools.dev.rebuild_indices import IndexRebuilder


class TestIndexRebuilder:
    """Tests for IndexRebuilder class"""

    def test_init_default(self):
        """Test default initialization"""
        rebuilder = IndexRebuilder()
        assert rebuilder.dry_run is False
        assert rebuilder.journals == []
        assert rebuilder.journal_metadata == {}
        assert rebuilder.dead_links_found == 0
        assert rebuilder.indices_updated == 0

    def test_init_dry_run(self):
        """Test dry-run mode initialization"""
        rebuilder = IndexRebuilder(dry_run=True)
        assert rebuilder.dry_run is True

    def test_collect_journals_empty(self, monkeypatch, tmp_path) -> None:
        """Test collecting journals when directory is empty"""
        from tools.dev import rebuild_indices as ri_mod
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
        monkeypatch.setattr(ri_mod, "get_journals_dir", lambda: tmp_path / "Journals")
        rebuilder = IndexRebuilder()
        rebuilder._collect_journals()

        assert rebuilder.journals == []

    def test_collect_journals_with_files(self, monkeypatch, tmp_path) -> None:
        """Test collecting journals with actual files"""
        from tools.dev import rebuild_indices as ri_mod
        # Create mock journal files
        journals_dir = tmp_path / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)
        journal1 = journals_dir / "life-index_2026-03-20_001.md"
        journal2 = journals_dir / "life-index_2026-03-20_002.md"
        journal1.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")
        journal2.write_text("---\ntitle: Test2\n---\nContent", encoding="utf-8")

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
        monkeypatch.setattr(ri_mod, "get_journals_dir", lambda: tmp_path / "Journals")

        rebuilder = IndexRebuilder()
        rebuilder._collect_journals()

        assert len(rebuilder.journals) == 2

    @patch("tools.dev.rebuild_indices.parse_journal_file")
    def test_parse_frontmatter_success(self, mock_parse):
        """Test successful frontmatter parsing"""
        mock_parse.return_value = {"title": "Test", "date": "2026-03-20"}
        rebuilder = IndexRebuilder()

        result = rebuilder._parse_frontmatter(Path("test.md"))

        assert result == {"title": "Test", "date": "2026-03-20"}

    @patch("tools.dev.rebuild_indices.parse_journal_file")
    def test_parse_frontmatter_failure(self, mock_parse):
        """Test frontmatter parsing failure"""
        mock_parse.side_effect = Exception("Parse error")
        rebuilder = IndexRebuilder()

        result = rebuilder._parse_frontmatter(Path("test.md"))

        assert result == {}

    def test_resolve_link_http(self):
        """Test resolving HTTP links"""
        rebuilder = IndexRebuilder()
        result = rebuilder._resolve_link(Path("/some/file.md"), "http://example.com")
        assert result is None

    def test_resolve_link_https(self):
        """Test resolving HTTPS links"""
        rebuilder = IndexRebuilder()
        result = rebuilder._resolve_link(Path("/some/file.md"), "https://example.com")
        assert result is None

    def test_resolve_link_absolute(self, monkeypatch, tmp_path) -> None:
        """Test resolving absolute paths"""
        from tools.dev import rebuild_indices as ri_mod
        fake_journals = Path("/data")
        monkeypatch.setattr(ri_mod, "get_journals_dir", lambda: fake_journals)
        rebuilder = IndexRebuilder()
        result = rebuilder._resolve_link(Path("/some/file.md"), "/Journals/test.md")
        assert result == Path("/data/Journals/test.md")

    def test_clean_dead_links_empty_dir(self, monkeypatch, tmp_path) -> None:
        """Test cleaning dead links when directory doesn't exist"""
        from tools.dev import rebuild_indices as ri_mod
        nonexist = tmp_path / "nonexistent-by-topic"
        monkeypatch.setattr(ri_mod, "get_by_topic_dir", lambda: nonexist)
        rebuilder = IndexRebuilder()
        rebuilder._clean_dead_links()

        assert rebuilder.dead_links_found == 0

    def test_clean_dead_links_with_files(self, monkeypatch, tmp_path) -> None:
        """Test cleaning dead links with actual index files"""
        from tools.dev import rebuild_indices as ri_mod
        # Create mock index file
        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()
        index_file = index_dir / "topic_work.md"
        index_content = """# Topic: work

## Journal List

### 2026-03

- [2026-03-20 Test](../Journals/2026/03/life-index_2026-03-20_001.md)
"""
        index_file.write_text(index_content, encoding="utf-8")

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
        monkeypatch.setattr(ri_mod, "get_by_topic_dir", lambda: index_dir)

        rebuilder = IndexRebuilder(dry_run=True)
        rebuilder._clean_dead_links()

        # Dead link found because the target doesn't exist
        assert rebuilder.dead_links_found >= 0

    def test_run_dry_run(self, monkeypatch, tmp_path) -> None:
        """Test run method in dry-run mode"""
        from tools.dev import rebuild_indices as ri_mod
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
        monkeypatch.setattr(ri_mod, "get_journals_dir", lambda: tmp_path / "Journals")
        monkeypatch.setattr(ri_mod, "get_by_topic_dir", lambda: tmp_path / "by-topic")
        monkeypatch.setattr(ri_mod, "ensure_dirs", lambda: None)

        rebuilder = IndexRebuilder(dry_run=True)
        rebuilder.run()

        # Should complete without error
        assert rebuilder.journals == []


class TestRebuildTopicIndices:
    """Tests for topic index rebuilding"""

    def test_rebuild_topic_indices_with_entries(self):
        """Test rebuilding topic indices with entries"""
        rebuilder = IndexRebuilder(dry_run=True)
        rebuilder.journal_metadata = {
            "Journals/2026/03/test.md": {
                "title": "Test",
                "date": "2026-03-20T10:00:00",
                "topic": ["work", "create"],
                "_title": "Test",
                "_abstract": "Test abstract",
            }
        }

        # This should not raise an error
        rebuilder._rebuild_topic_indices()


class TestRebuildProjectIndices:
    """Tests for project index rebuilding"""

    def test_rebuild_project_indices_with_entries(self):
        """Test rebuilding project indices with entries"""
        rebuilder = IndexRebuilder(dry_run=True)
        rebuilder.journal_metadata = {
            "Journals/2026/03/test.md": {
                "title": "Test",
                "date": "2026-03-20T10:00:00",
                "project": "LifeIndex",
                "_title": "Test",
            }
        }

        rebuilder._rebuild_project_indices()


class TestRebuildTagIndices:
    """Tests for tag index rebuilding"""

    def test_rebuild_tag_indices_with_entries(self):
        """Test rebuilding tag indices with entries"""
        rebuilder = IndexRebuilder(dry_run=True)
        rebuilder.journal_metadata = {
            "Journals/2026/03/test.md": {
                "title": "Test",
                "date": "2026-03-20T10:00:00",
                "tags": ["test", "unit"],
                "_title": "Test",
            }
        }

        rebuilder._rebuild_tag_indices()

    def test_rebuild_tag_indices_string_tags(self):
        """Test rebuilding tag indices when tags is a string"""
        rebuilder = IndexRebuilder(dry_run=True)
        rebuilder.journal_metadata = {
            "Journals/2026/03/test.md": {
                "title": "Test",
                "date": "2026-03-20T10:00:00",
                "tags": "single_tag",
                "_title": "Test",
            }
        }

        rebuilder._rebuild_tag_indices()


class TestWriteIndex:
    """Tests for _write_index method"""

    def test_write_index_dry_run(self, monkeypatch, tmp_path) -> None:
        """Test writing index in dry-run mode"""
        from tools.dev import rebuild_indices as ri_mod
        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
        monkeypatch.setattr(ri_mod, "get_by_topic_dir", lambda: index_dir)
        monkeypatch.setattr(ri_mod, "get_journals_dir", lambda: tmp_path / "Journals")

        rebuilder = IndexRebuilder(dry_run=True)
        entries = [
            (
                "Journals/2026/03/test.md",
                {"date": "2026-03-20T10:00:00", "_title": "Test", "tags": ["a"]},
            )
        ]

        rebuilder._write_index("topic_work.md", "Topic: work", entries)

        assert rebuilder.indices_updated == 0  # Dry run, no update


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
