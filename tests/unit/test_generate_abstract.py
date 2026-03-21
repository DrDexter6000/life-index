#!/usr/bin/env python3
"""
Unit tests for tools/generate_abstract/__init__.py
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.generate_abstract import (
    parse_frontmatter,
    collect_month_journals,
    collect_year_journals,
    generate_monthly_abstract_content,
    generate_yearly_abstract_content,
    generate_monthly_abstract,
    generate_yearly_abstract,
)


class TestParseFrontmatter:
    """Tests for parse_frontmatter function"""

    def test_parse_valid_journal(self, tmp_path):
        """Parse valid journal returns metadata"""
        journal = tmp_path / "test.md"
        journal.write_text(
            """---
title: Test
date: 2026-03-14
---
# Content
""",
            encoding="utf-8",
        )

        result = parse_frontmatter(journal)

        assert result.get("title") == "Test"
        assert result.get("date") == "2026-03-14"

    def test_parse_invalid_journal(self, tmp_path):
        """Parse invalid journal returns dict with _error"""
        journal = tmp_path / "invalid.md"
        journal.write_text("# No frontmatter", encoding="utf-8")

        result = parse_frontmatter(journal)

        # Invalid frontmatter returns dict with _error key
        assert "_error" in result or result.get("title") is None

    def test_parse_returns_empty_dict_on_error(self, tmp_path):
        """Parse with _error returns empty dict (line 36)"""
        # Create a file that will cause UnicodeDecodeError
        journal = tmp_path / "broken.md"
        journal.write_bytes(b"\xff\xfe Invalid UTF-8 \x00\x00")

        result = parse_frontmatter(journal)

        # When _error is in result (from IOError/OSError/UnicodeDecodeError), function returns {}
        assert result == {}


class TestCollectMonthJournals:
    """Tests for collect_month_journals function"""

    def test_collect_from_empty_directory(self, tmp_path):
        """Collect from non-existent directory returns empty list"""
        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = collect_month_journals(2026, 3)
            assert result == []

    def test_collect_from_directory_with_journals(self, tmp_path):
        """Collect journals from directory"""
        month_dir = tmp_path / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)

        journal = month_dir / "life-index_2026-03-14_001.md"
        journal.write_text(
            """---
title: Test Journal
date: 2026-03-14T10:00:00
topic: ["work"]
---
# Content
""",
            encoding="utf-8",
        )

        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = collect_month_journals(2026, 3)

        assert len(result) == 1
        assert result[0]["title"] == "Test Journal"
        assert result[0]["file"] == "life-index_2026-03-14_001.md"

    def test_collect_skips_invalid_frontmatter(self, tmp_path):
        """Journals with invalid frontmatter (returns empty dict) are skipped (line 52->50)"""
        month_dir = tmp_path / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)

        # Valid journal
        valid = month_dir / "life-index_2026-03-14_001.md"
        valid.write_text(
            "---\ntitle: Valid\ndate: 2026-03-14\n---\n# Content", encoding="utf-8"
        )

        # Invalid journal (will cause UnicodeDecodeError when read as UTF-8)
        invalid = month_dir / "life-index_2026-03-15_002.md"
        invalid.write_bytes(b"\xff\xfe Invalid UTF-8 \x00\x00")

        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = collect_month_journals(2026, 3)

        # Only valid journal should be collected
        assert len(result) == 1
        assert result[0]["title"] == "Valid"


class TestCollectYearJournals:
    """Tests for collect_year_journals function"""

    def test_collect_from_empty_year(self, tmp_path):
        """Collect from non-existent year returns empty list"""
        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = collect_year_journals(2026)
            assert result == []

    def test_collect_from_year_with_multiple_months(self, tmp_path):
        """Collect journals from multiple months"""
        for month in ["01", "02"]:
            month_dir = tmp_path / "Journals" / "2026" / month
            month_dir.mkdir(parents=True)

            journal = month_dir / f"life-index_2026-{month}-15_001.md"
            journal.write_text(
                f"---\ntitle: Month {month}\ndate: 2026-{month}-15\n---\n# Content",
                encoding="utf-8",
            )

        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = collect_year_journals(2026)

        assert len(result) == 2

    def test_collect_skips_non_directory_entries(self, tmp_path):
        """Non-directory entries in year dir are skipped (line 84)"""
        year_dir = tmp_path / "Journals" / "2026"
        year_dir.mkdir(parents=True)

        # Create a file (not a directory) in year dir
        (year_dir / "some_file.txt").write_text("not a directory", encoding="utf-8")

        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = collect_year_journals(2026)

        assert result == []

    def test_collect_skips_invalid_frontmatter(self, tmp_path):
        """Journals with invalid frontmatter (returns empty dict) are skipped (line 89->87)"""
        month_dir = tmp_path / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)

        # Valid journal
        valid = month_dir / "life-index_2026-03-14_001.md"
        valid.write_text(
            "---\ntitle: Valid\ndate: 2026-03-14\n---\n# Content", encoding="utf-8"
        )

        # Invalid journal (will cause UnicodeDecodeError when read as UTF-8)
        invalid = month_dir / "life-index_2026-03-15_002.md"
        invalid.write_bytes(b"\xff\xfe Invalid UTF-8 \x00\x00")

        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = collect_year_journals(2026)

        # Only valid journal should be collected
        assert len(result) == 1
        assert result[0]["title"] == "Valid"


class TestGenerateMonthlyAbstractContent:
    """Tests for generate_monthly_abstract_content function"""

    def test_generate_with_journals(self):
        """Generate content with journals"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./test_001.md",
                "date": "2026-03-14T10:00:00",
                "title": "Test Entry",
                "tags": ["test"],
                "project": "TestProject",
                "topic": ["work"],
                "mood": ["happy"],
                "people": ["Alice"],
                "abstract": "Test abstract",
            }
        ]

        content = generate_monthly_abstract_content(2026, 3, journals)

        assert "2026" in content
        assert "Test Entry" in content

    def test_generate_empty_journals(self):
        """Generate content with no journals"""
        content = generate_monthly_abstract_content(2026, 3, [])

        assert "0" in content

    def test_generate_with_invalid_date(self):
        """Handle invalid date strings (line 134)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./test_001.md",
                "date": None,  # Invalid date
                "title": "No Date Entry",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_monthly_abstract_content(2026, 3, journals)

        assert "未知日期" in content

    def test_generate_with_string_tags(self):
        """Handle string tags instead of list (lines 161-162)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./test_001.md",
                "date": "2026-03-14",
                "title": "String Tags",
                "tags": "single-tag",  # String instead of list
                "project": "",
                "topic": [],
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_monthly_abstract_content(2026, 3, journals)

        assert "single-tag" in content

    def test_generate_with_string_topics(self):
        """Handle string topics instead of list (lines 170-171)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./test_001.md",
                "date": "2026-03-14",
                "title": "String Topics",
                "tags": [],
                "project": "",
                "topic": "work",  # String instead of list
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_monthly_abstract_content(2026, 3, journals)

        assert "work" in content

    def test_generate_multiple_journals_same_date(self):
        """Handle multiple journals on same date (line 136->138)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./test_001.md",
                "date": "2026-03-14T10:00:00",
                "title": "First Entry",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": [],
                "people": [],
                "abstract": "",
            },
            {
                "file": "test_002.md",
                "path": "./test_002.md",
                "date": "2026-03-14T15:00:00",  # Same date, different time
                "title": "Second Entry",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": [],
                "people": [],
                "abstract": "",
            },
        ]

        content = generate_monthly_abstract_content(2026, 3, journals)

        assert "First Entry" in content
        assert "Second Entry" in content

    def test_generate_with_none_tags(self):
        """Handle None tags (branch 161->164)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./test_001.md",
                "date": "2026-03-14",
                "title": "None Tags",
                "tags": None,  # Neither list nor string
                "project": "",
                "topic": [],
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_monthly_abstract_content(2026, 3, journals)

        assert "None Tags" in content

    def test_generate_with_none_topics(self):
        """Handle None topics (branch 170->157)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./test_001.md",
                "date": "2026-03-14",
                "title": "None Topics",
                "tags": [],
                "project": "",
                "topic": None,  # Neither list nor string
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_monthly_abstract_content(2026, 3, journals)

        assert "None Topics" in content


class TestGenerateYearlyAbstractContent:
    """Tests for generate_yearly_abstract_content function"""

    def test_generate_with_journals(self):
        """Generate yearly content"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": ["test"],
                "project": "",
                "topic": ["work"],
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)

        assert "2026" in content

    def test_generate_with_string_tags(self):
        """Handle string tags instead of list (lines 240-241)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": "single-tag",  # String instead of list
                "project": "",
                "topic": [],
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)

        assert "single-tag" in content

    def test_generate_with_project(self):
        """Include project distribution (lines 244, 275-280)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": [],
                "project": "MyProject",  # Has project
                "topic": [],
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)

        assert "项目分布" in content
        assert "MyProject" in content

    def test_generate_with_string_topics(self):
        """Handle string topics instead of list (lines 249-250)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": [],
                "project": "",
                "topic": "work",  # String instead of list
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)

        assert "work" in content

    def test_generate_with_string_moods(self):
        """Handle string moods instead of list (lines 255-256)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": "happy",  # String instead of list
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)

        assert "心情分布" in content
        assert "happy" in content

    def test_generate_with_moods_list(self):
        """Include mood distribution (lines 293-298)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": ["happy", "focused"],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)

        assert "心情分布" in content
        assert "happy" in content

    def test_generate_with_string_people(self):
        """Handle string people instead of list (lines 261-262)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": [],
                "people": "Alice",  # String instead of list
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)

        assert "相关人物" in content
        assert "Alice" in content

    def test_generate_with_people_list(self):
        """Include people distribution (lines 302-307)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": [],
                "people": ["Alice", "Bob"],
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)

        assert "相关人物" in content
        assert "Alice" in content

    def test_generate_with_invalid_date(self):
        """Handle invalid date in yearly index (line 329)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": None,  # Invalid date
                "title": "No Date",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)

        assert "??" in content  # Day shows as ??

    def test_generate_multiple_journals_same_month(self):
        """Handle multiple journals in same month (line 317->319)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "First Entry",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": [],
                "people": [],
                "abstract": "",
            },
            {
                "file": "test_002.md",
                "path": "./03/test_002.md",
                "month": "03",  # Same month
                "date": "2026-03-15",
                "title": "Second Entry",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": [],
                "people": [],
                "abstract": "",
            },
        ]

        content = generate_yearly_abstract_content(2026, journals)

        assert "First Entry" in content
        assert "Second Entry" in content

    def test_generate_with_none_tags(self):
        """Handle None tags (branch 240->243)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": None,  # Neither list nor string
                "project": "",
                "topic": [],
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)
        assert "Test" in content

    def test_generate_with_none_topics(self):
        """Handle None topics (branch 249->252)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": [],
                "project": "",
                "topic": None,  # Neither list nor string
                "mood": [],
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)
        assert "Test" in content

    def test_generate_with_none_moods(self):
        """Handle None moods (branch 255->258)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": None,  # Neither list nor string
                "people": [],
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)
        assert "Test" in content

    def test_generate_with_none_people(self):
        """Handle None people (branch 261->236)"""
        journals = [
            {
                "file": "test_001.md",
                "path": "./03/test_001.md",
                "month": "03",
                "date": "2026-03-14",
                "title": "Test",
                "tags": [],
                "project": "",
                "topic": [],
                "mood": [],
                "people": None,  # Neither list nor string
                "abstract": "",
            }
        ]

        content = generate_yearly_abstract_content(2026, journals)
        assert "Test" in content


class TestGenerateMonthlyAbstract:
    """Tests for generate_monthly_abstract function"""

    def test_generate_for_empty_month(self, tmp_path):
        """Generate for month with no journals"""
        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = generate_monthly_abstract(2026, 3)

        assert result["success"] is True
        assert result["journal_count"] == 0

    def test_generate_with_journals(self, tmp_path):
        """Generate abstract for month with journals"""
        month_dir = tmp_path / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)

        journal = month_dir / "life-index_2026-03-14_001.md"
        journal.write_text(
            """---
title: Test
date: 2026-03-14T10:00:00
topic: ["work"]
---
# Content
""",
            encoding="utf-8",
        )

        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = generate_monthly_abstract(2026, 3)

        assert result["success"] is True
        assert result["journal_count"] == 1
        assert result["updated"] is True

    def test_dry_run(self, tmp_path):
        """Dry run doesn't write file"""
        month_dir = tmp_path / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)

        journal = month_dir / "life-index_2026-03-14_001.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n# Content", encoding="utf-8"
        )

        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = generate_monthly_abstract(2026, 3, dry_run=True)

        assert result["success"] is True
        assert result["updated"] is False


class TestGenerateYearlyAbstract:
    """Tests for generate_yearly_abstract function"""

    def test_generate_for_empty_year(self, tmp_path):
        """Generate for year with no journals"""
        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = generate_yearly_abstract(2026)

        assert result["success"] is True
        assert result["journal_count"] == 0

    def test_generate_with_journals(self, tmp_path):
        """Generate abstract for year with journals"""
        month_dir = tmp_path / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)

        journal = month_dir / "life-index_2026-03-14_001.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n# Content", encoding="utf-8"
        )

        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = generate_yearly_abstract(2026)

        assert result["success"] is True
        assert result["journal_count"] == 1
        assert result["updated"] is True

    def test_dry_run(self, tmp_path):
        """Dry run doesn't write file (lines 431-434)"""
        month_dir = tmp_path / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)

        journal = month_dir / "life-index_2026-03-14_001.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n# Content", encoding="utf-8"
        )

        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            result = generate_yearly_abstract(2026, dry_run=True)

        assert result["success"] is True
        assert result["updated"] is False
        assert "预览" in result["message"]

    def test_io_error_handling(self, tmp_path):
        """Handle IOError/OSError when writing (lines 449-451)"""
        month_dir = tmp_path / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)

        journal = month_dir / "life-index_2026-03-14_001.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n# Content", encoding="utf-8"
        )

        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            with patch("builtins.open", side_effect=IOError("Disk full")):
                result = generate_yearly_abstract(2026)

        assert result["success"] is False
        assert "error" in result


class TestGenerateMonthlyAbstractErrors:
    """Tests for error handling in generate_monthly_abstract"""

    def test_io_error_handling(self, tmp_path):
        """Handle IOError/OSError when writing (lines 389-391)"""
        month_dir = tmp_path / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)

        journal = month_dir / "life-index_2026-03-14_001.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n# Content", encoding="utf-8"
        )

        with patch("tools.generate_abstract.JOURNALS_DIR", tmp_path / "Journals"):
            with patch("builtins.open", side_effect=OSError("Permission denied")):
                result = generate_monthly_abstract(2026, 3)

        assert result["success"] is False
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
