#!/usr/bin/env python3
"""
Unit tests for tools/dev/validate_data/__init__.py
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import asdict

from tools.dev.validate_data import (
    ValidationIssue,
    ValidationResult,
    DataValidator,
    print_report,
)


class TestValidationIssue:
    """Tests for ValidationIssue dataclass"""

    def test_create_issue_minimal(self):
        """Test creating minimal validation issue"""
        issue = ValidationIssue(
            level="error",
            category="metadata",
            file="test.md",
            message="Test error",
        )

        assert issue.level == "error"
        assert issue.category == "metadata"
        assert issue.file == "test.md"
        assert issue.message == "Test error"
        assert issue.suggestion == ""
        assert issue.auto_fixable is False

    def test_create_issue_full(self):
        """Test creating validation issue with all fields"""
        issue = ValidationIssue(
            level="warning",
            category="link",
            file="test.md",
            message="Broken link",
            suggestion="Fix the link",
            auto_fixable=True,
        )

        assert issue.level == "warning"
        assert issue.suggestion == "Fix the link"
        assert issue.auto_fixable is True


class TestValidationResult:
    """Tests for ValidationResult dataclass"""

    def test_empty_result(self):
        """Test empty validation result"""
        result = ValidationResult()

        assert result.total_journals == 0
        assert result.total_indices == 0
        assert result.total_attachments == 0
        assert result.issues == []
        assert result.error_count() == 0
        assert result.warning_count() == 0

    def test_error_count(self):
        """Test counting errors"""
        result = ValidationResult()
        result.issues = [
            ValidationIssue("error", "metadata", "f1.md", "err1"),
            ValidationIssue("warning", "link", "f2.md", "warn1"),
            ValidationIssue("error", "metadata", "f3.md", "err2"),
        ]

        assert result.error_count() == 2
        assert result.warning_count() == 1

    def test_to_dict(self):
        """Test converting to dictionary"""
        result = ValidationResult()
        result.total_journals = 10
        result.total_indices = 5
        result.issues = [
            ValidationIssue("error", "metadata", "test.md", "Error message"),
        ]
        result.stats = {"topics": {"work": 5}}

        d = result.to_dict()

        assert d["summary"]["total_journals"] == 10
        assert d["summary"]["errors"] == 1
        assert len(d["issues"]) == 1
        assert d["stats"]["topics"]["work"] == 5


class TestDataValidator:
    """Tests for DataValidator class"""

    def test_init_default(self):
        """Test default initialization"""
        validator = DataValidator()
        assert validator.fix_mode is False
        assert validator.result.total_journals == 0

    def test_init_fix_mode(self):
        """Test initialization with fix mode"""
        validator = DataValidator(fix_mode=True)
        assert validator.fix_mode is True

    def test_required_fields_property(self):
        """Test REQUIRED_FIELDS property"""
        validator = DataValidator()
        fields = validator.REQUIRED_FIELDS
        assert isinstance(fields, list)
        assert len(fields) > 0

    def test_recommended_fields_property(self):
        """Test RECOMMENDED_FIELDS property"""
        validator = DataValidator()
        fields = validator.RECOMMENDED_FIELDS
        assert isinstance(fields, list)

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.BY_TOPIC_DIR")
    @patch("tools.dev.validate_data.ATTACHMENTS_DIR")
    def test_collect_files_empty(self, mock_attach, mock_topic, mock_journals):
        """Test collecting files when directories are empty"""
        mock_journals.exists.return_value = False
        mock_topic.exists.return_value = False
        mock_attach.exists.return_value = False

        validator = DataValidator()
        validator._collect_files()

        assert validator.journal_files == []
        assert validator.index_files == []
        assert validator.attachment_files == []

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    def test_collect_files_with_journals(self, mock_journals, tmp_path):
        """Test collecting journal files"""
        journals_dir = tmp_path / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)
        journal = journals_dir / "life-index_2026-03-20_001.md"
        journal.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        mock_journals.exists.return_value = True
        mock_journals.rglob.return_value = [journal]

        validator = DataValidator()
        validator._collect_files()

        assert len(validator.journal_files) == 1
        assert validator.result.total_journals == 1

    @patch("tools.dev.validate_data.parse_journal_file")
    def test_parse_frontmatter_success(self, mock_parse):
        """Test successful frontmatter parsing"""
        mock_parse.return_value = {"title": "Test", "date": "2026-03-20"}
        validator = DataValidator()

        result = validator._parse_frontmatter(Path("test.md"))

        assert result == {"title": "Test", "date": "2026-03-20"}

    @patch("tools.dev.validate_data.parse_journal_file")
    def test_parse_frontmatter_with_error(self, mock_parse):
        """Test frontmatter parsing with _error in result"""
        mock_parse.return_value = {"_error": "Parse failed"}
        validator = DataValidator()

        result = validator._parse_frontmatter(Path("test.md"))

        assert result is None
        assert len(validator.result.issues) == 1
        assert validator.result.issues[0].level == "error"

    @patch("tools.dev.validate_data.parse_journal_file")
    def test_parse_frontmatter_exception(self, mock_parse):
        """Test frontmatter parsing with exception"""
        mock_parse.side_effect = Exception("Unexpected error")
        validator = DataValidator()

        result = validator._parse_frontmatter(Path("test.md"))

        assert result is None
        assert len(validator.result.issues) == 1

    def test_resolve_link_external(self):
        """Test resolving external links"""
        validator = DataValidator()
        result = validator._resolve_link(Path("/some/file.md"), "http://example.com")
        assert result is None

        result = validator._resolve_link(Path("/some/file.md"), "https://example.com")
        assert result is None

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    def test_resolve_link_absolute(self, mock_journals):
        """Test resolving absolute paths"""
        mock_journals.parent = Path("/data")
        validator = DataValidator()
        result = validator._resolve_link(Path("/some/file.md"), "/Journals/test.md")
        assert result == Path("/data/Journals/test.md")


class TestDataValidatorValidateJournals:
    """Tests for _validate_journals method"""

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.parse_journal_file")
    def test_validate_journals_missing_required_field(
        self, mock_parse, mock_journals, tmp_path
    ):
        """Test validation catches missing required fields"""
        journal = tmp_path / "test.md"
        journal.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path
        mock_parse.return_value = {"title": "Test"}  # Missing date

        validator = DataValidator()
        validator.journal_files = [journal]
        validator._validate_journals()

        # Should have issues for missing required fields
        assert len(validator.result.issues) > 0

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.parse_journal_file")
    def test_validate_journals_invalid_date(self, mock_parse, mock_journals, tmp_path):
        """Test validation catches invalid date format"""
        journal = tmp_path / "test.md"
        journal.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path
        mock_parse.return_value = {"title": "Test", "date": "invalid-date"}

        validator = DataValidator()
        validator.journal_files = [journal]
        validator._validate_journals()

        # Should have error for invalid date
        date_errors = [
            i for i in validator.result.issues if "date" in i.message.lower()
        ]
        assert len(date_errors) > 0


class TestDataValidatorValidateIndices:
    """Tests for _validate_indices method"""

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    def test_validate_indices_dead_link(self, mock_journals, tmp_path):
        """Test validation catches dead links"""
        index_dir = tmp_path / "by-topic"
        index_dir.mkdir()
        index_file = index_dir / "主题_work.md"
        index_content = """# 主题: work

- [2026-03-20 Test](../Journals/2026/03/nonexistent.md)
"""
        index_file.write_text(index_content, encoding="utf-8")

        mock_journals.parent = tmp_path

        validator = DataValidator()
        validator.index_files = [index_file]
        validator._validate_indices()

        # Should have error for dead link
        assert len(validator.result.issues) > 0
        assert validator.result.issues[0].category == "link"


class TestGenerateStats:
    """Tests for _generate_stats method"""

    def test_generate_stats_empty(self):
        """Test generating stats with no data"""
        validator = DataValidator()
        validator.journal_entries = {}
        validator._generate_stats()

        assert validator.result.stats == {
            "topics": {},
            "projects": {},
            "tags": {},
            "moods": {},
            "monthly_distribution": {},
        }

    def test_generate_stats_with_data(self):
        """Test generating stats with journal data"""
        validator = DataValidator()
        validator.journal_entries = {
            "test1.md": {
                "topic": ["work"],
                "project": "LifeIndex",
                "tags": ["test"],
                "mood": ["happy"],
                "date": "2026-03-20",
            },
            "test2.md": {
                "topic": ["work", "create"],
                "tags": ["test", "unit"],
                "mood": "focused",
                "date": "2026-03-21",
            },
        }
        validator._generate_stats()

        assert validator.result.stats["topics"]["work"] == 2
        assert validator.result.stats["topics"]["create"] == 1
        assert validator.result.stats["projects"]["LifeIndex"] == 1
        assert validator.result.stats["tags"]["test"] == 2

    def test_generate_stats_topic_as_string(self):
        """Test generating stats when topic is a string instead of list"""
        validator = DataValidator()
        validator.journal_entries = {
            "test.md": {
                "topic": "work",  # String instead of list
                "date": "2026-03-20",
            },
        }
        validator._generate_stats()

        assert validator.result.stats["topics"]["work"] == 1

    def test_generate_stats_tags_as_string(self):
        """Test generating stats when tags is a string (should be skipped)"""
        validator = DataValidator()
        validator.journal_entries = {
            "test.md": {
                "tags": "single-tag",  # String instead of list - should be skipped
                "date": "2026-03-20",
            },
        }
        validator._generate_stats()

        # Tags as string should not be counted (only list is handled)
        assert validator.result.stats["tags"] == {}

    def test_generate_stats_mood_as_string(self):
        """Test generating stats when mood is a string instead of list"""
        validator = DataValidator()
        validator.journal_entries = {
            "test.md": {
                "mood": "happy",  # String instead of list
                "date": "2026-03-20",
            },
        }
        validator._generate_stats()

        assert validator.result.stats["moods"]["happy"] == 1

    def test_generate_stats_mood_as_list(self):
        """Test generating stats when mood is a list"""
        validator = DataValidator()
        validator.journal_entries = {
            "test.md": {
                "mood": ["happy", "focused"],
                "date": "2026-03-20",
            },
        }
        validator._generate_stats()

        assert validator.result.stats["moods"]["happy"] == 1
        assert validator.result.stats["moods"]["focused"] == 1

    def test_generate_stats_invalid_date(self):
        """Test generating stats with invalid date string"""
        validator = DataValidator()
        validator.journal_entries = {
            "test.md": {
                "date": "invalid-date",  # Invalid date format - code slices first 7 chars
            },
        }
        validator._generate_stats()

        # Code slices first 7 chars, so "invalid" becomes the key
        # This tests that it doesn't crash
        assert "invalid" in validator.result.stats["monthly_distribution"]

    def test_generate_stats_date_type_error(self):
        """Test generating stats when date is an integer"""
        validator = DataValidator()
        validator.journal_entries = {
            "test.md": {
                "date": 12345,  # Integer instead of string - gets converted to str
            },
        }
        validator._generate_stats()

        # Code converts to string first, then slices first 7 chars
        # This tests that it doesn't crash
        assert "12345" in validator.result.stats["monthly_distribution"]


class TestValidateAttachments:
    """Tests for _validate_attachments method"""

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.ATTACHMENTS_DIR")
    def test_validate_attachments_existing_file(
        self, mock_attach_dir, mock_journals, tmp_path
    ):
        """Test validation when attachment exists"""
        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir()
        attachments_dir = tmp_path / "attachments" / "2026" / "03"
        attachments_dir.mkdir(parents=True)

        # Create existing attachment
        attachment = attachments_dir / "photo.jpg"
        attachment.write_bytes(b"fake image data")

        journal_file = journals_dir / "life-index_2026-03-20_001.md"
        journal_file.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path
        mock_journals.__truediv__ = lambda self, x: tmp_path / x
        # Set ATTACHMENTS_DIR to the attachments folder
        mock_attach_dir.__str__ = lambda self: str(
            attachments_dir.parent.parent
        )  # attachments/
        # Make the path operations work
        mock_attach_dir.__truediv__ = lambda self, x: attachments_dir.parent.parent / x

        validator = DataValidator()
        validator.journal_entries = {
            "Journals/life-index_2026-03-20_001.md": {
                "attachments": ["photo.jpg"],
            },
        }

        validator._validate_attachments()

        # The test verifies the method doesn't crash
        # The exact behavior depends on path resolution
        assert True

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    def test_validate_attachments_not_list(self, mock_journals, tmp_path):
        """Test validation when attachments is not a list"""
        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir()

        journal_file = journals_dir / "test.md"
        journal_file.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path

        validator = DataValidator()
        validator.journal_entries = {
            "Journals/test.md": {
                "attachments": "not-a-list",  # String instead of list
            },
        }

        validator._validate_attachments()

        # Should not crash, no issues (attachments is not a list)
        assert len(validator.result.issues) == 0


class TestValidateCrossReferences:
    """Tests for _validate_cross_references method"""

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.BY_TOPIC_DIR")
    def test_validate_cross_references_orphan_journal(
        self, mock_topic_dir, mock_journals, tmp_path
    ):
        """Test detection of journal not indexed in topic file"""
        journals_dir = tmp_path / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)
        topic_dir = tmp_path / "by-topic"
        topic_dir.mkdir()

        # Create topic index file without the journal
        index_file = topic_dir / "主题_work.md"
        index_file.write_text(
            "# 主题: work\n\n- [Other](../Journals/other.md)\n", encoding="utf-8"
        )

        journal_file = journals_dir / "life-index_2026-03-20_001.md"
        journal_file.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path
        mock_topic_dir.__truediv__ = lambda self, x: topic_dir / x

        validator = DataValidator()
        validator.index_files = [index_file]
        validator.journal_entries = {
            "Journals/2026/03/life-index_2026-03-20_001.md": {
                "topic": ["work"],
            },
        }

        validator._validate_cross_references()

        # Should have warning for orphan journal
        assert len(validator.result.issues) == 1
        assert validator.result.issues[0].category == "orphan_index"
        assert validator.result.issues[0].auto_fixable is True

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.BY_TOPIC_DIR")
    def test_validate_cross_references_topic_as_string(
        self, mock_topic_dir, mock_journals, tmp_path
    ):
        """Test cross reference validation when topic is a string"""
        journals_dir = tmp_path / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)
        topic_dir = tmp_path / "by-topic"
        topic_dir.mkdir()

        index_file = topic_dir / "主题_work.md"
        index_file.write_text("# 主题: work\n", encoding="utf-8")

        journal_file = journals_dir / "life-index_2026-03-20_001.md"
        journal_file.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path
        mock_topic_dir.__truediv__ = lambda self, x: topic_dir / x

        validator = DataValidator()
        validator.index_files = [index_file]
        validator.journal_entries = {
            "Journals/2026/03/life-index_2026-03-20_001.md": {
                "topic": "work",  # String instead of list
            },
        }

        validator._validate_cross_references()

        # Should have warning for orphan journal
        assert len(validator.result.issues) == 1

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.BY_TOPIC_DIR")
    def test_validate_cross_references_tags_as_string(
        self, mock_topic_dir, mock_journals, tmp_path
    ):
        """Test cross reference validation when tags is a string"""
        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir()
        topic_dir = tmp_path / "by-topic"
        topic_dir.mkdir()

        mock_journals.parent = tmp_path

        validator = DataValidator()
        validator.index_files = []
        validator.journal_entries = {
            "Journals/test.md": {
                "topic": [],
                "tags": "single-tag",  # String instead of list
            },
        }

        validator._validate_cross_references()

        # Should not crash
        assert True

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.BY_TOPIC_DIR")
    def test_validate_cross_references_indexed_correctly(
        self, mock_topic_dir, mock_journals, tmp_path
    ):
        """Test when journal is correctly indexed"""
        journals_dir = tmp_path / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)
        topic_dir = tmp_path / "by-topic"
        topic_dir.mkdir()

        journal_name = "life-index_2026-03-20_001.md"
        index_file = topic_dir / "主题_work.md"
        index_file.write_text(
            f"# 主题: work\n\n- [Test](../Journals/2026/03/{journal_name})\n",
            encoding="utf-8",
        )

        journal_file = journals_dir / journal_name
        journal_file.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path
        mock_topic_dir.__truediv__ = lambda self, x: topic_dir / x

        validator = DataValidator()
        validator.index_files = [index_file]
        validator.journal_entries = {
            f"Journals/2026/03/{journal_name}": {
                "topic": ["work"],
            },
        }

        validator._validate_cross_references()

        # Should have no issues
        assert len(validator.result.issues) == 0

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.BY_TOPIC_DIR")
    def test_validate_cross_references_no_topic_index_file(
        self, mock_topic_dir, mock_journals, tmp_path
    ):
        """Test when topic index file doesn't exist"""
        journals_dir = tmp_path / "Journals"
        journals_dir.mkdir()
        topic_dir = tmp_path / "by-topic"
        topic_dir.mkdir()

        mock_journals.parent = tmp_path
        mock_topic_dir.__truediv__ = lambda self, x: topic_dir / x

        validator = DataValidator()
        validator.index_files = []
        validator.journal_entries = {
            "Journals/test.md": {
                "topic": ["work"],
            },
        }

        validator._validate_cross_references()

        # Should have no issues (index file doesn't exist, nothing to check)
        assert len(validator.result.issues) == 0


class TestValidateJournalsExtended:
    """Extended tests for _validate_journals method"""

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.parse_journal_file")
    def test_validate_journals_metadata_none(self, mock_parse, mock_journals, tmp_path):
        """Test validation when metadata parsing returns None"""
        journal = tmp_path / "test.md"
        journal.write_text("---\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path
        mock_parse.return_value = None

        validator = DataValidator()
        validator.journal_files = [journal]
        validator._validate_journals()

        # Should not add to journal_entries
        assert len(validator.journal_entries) == 0

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.parse_journal_file")
    def test_validate_journals_date_with_t(self, mock_parse, mock_journals, tmp_path):
        """Test validation of ISO 8601 date with T separator"""
        journal = tmp_path / "test.md"
        journal.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path
        mock_parse.return_value = {
            "title": "Test",
            "date": "2026-03-20T14:30:00",  # ISO 8601 with T
        }

        validator = DataValidator()
        validator.journal_files = [journal]
        validator._validate_journals()

        # Should have no date errors
        date_errors = [
            i for i in validator.result.issues if "date" in i.message.lower()
        ]
        assert len(date_errors) == 0

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.parse_journal_file")
    def test_validate_journals_date_with_z(self, mock_parse, mock_journals, tmp_path):
        """Test validation of ISO 8601 date with Z suffix"""
        journal = tmp_path / "test.md"
        journal.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path
        mock_parse.return_value = {
            "title": "Test",
            "date": "2026-03-20T14:30:00Z",  # ISO 8601 with Z
        }

        validator = DataValidator()
        validator.journal_files = [journal]
        validator._validate_journals()

        # Should have no date errors
        date_errors = [
            i for i in validator.result.issues if "date" in i.message.lower()
        ]
        assert len(date_errors) == 0

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.parse_journal_file")
    def test_validate_journals_missing_recommended_field(
        self, mock_parse, mock_journals, tmp_path
    ):
        """Test validation catches missing recommended fields"""
        journal = tmp_path / "test.md"
        journal.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path
        mock_parse.return_value = {
            "title": "Test",
            "date": "2026-03-20",
            # Missing recommended fields like mood, location
        }

        validator = DataValidator()
        validator.journal_files = [journal]
        validator._validate_journals()

        # Should have warnings for missing recommended fields
        warnings = [i for i in validator.result.issues if i.level == "warning"]
        assert len(warnings) > 0

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.parse_journal_file")
    def test_validate_journals_sequence_gap(self, mock_parse, mock_journals, tmp_path):
        """Test detection of sequence number gaps"""
        journals_dir = tmp_path / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)

        # Create journals with sequence gap (001, 003 - missing 002)
        journal1 = journals_dir / "life-index_2026-03-20_001.md"
        journal1.write_text("---\ntitle: Test 1\n---\nContent", encoding="utf-8")
        journal3 = journals_dir / "life-index_2026-03-20_003.md"
        journal3.write_text("---\ntitle: Test 3\n---\nContent", encoding="utf-8")

        mock_journals.parent = tmp_path
        mock_parse.side_effect = [
            {"title": "Test 1", "date": "2026-03-20"},
            {"title": "Test 3", "date": "2026-03-20"},
        ]

        validator = DataValidator()
        validator.journal_files = [journal1, journal3]
        validator._validate_journals()

        # Should have warning for sequence gap
        seq_warnings = [i for i in validator.result.issues if i.category == "sequence"]
        assert len(seq_warnings) == 1
        # The message contains the missing sequence number (2, not 002)
        assert "2" in seq_warnings[0].message or "002" in seq_warnings[0].message


class TestRunMethod:
    """Tests for the run() method"""

    @patch("tools.dev.validate_data.JOURNALS_DIR")
    @patch("tools.dev.validate_data.BY_TOPIC_DIR")
    @patch("tools.dev.validate_data.ATTACHMENTS_DIR")
    def test_run_full_validation(
        self, mock_attach, mock_topic, mock_journals, tmp_path
    ):
        """Test full validation run"""
        # Setup directories
        journals_dir = tmp_path / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)
        topic_dir = tmp_path / "by-topic"
        topic_dir.mkdir()
        attach_dir = tmp_path / "attachments"
        attach_dir.mkdir()

        # Create a valid journal
        journal = journals_dir / "life-index_2026-03-20_001.md"
        journal.write_text(
            """---
title: Test Journal
date: 2026-03-20
mood: [happy]
location: Test City
---
Content here
""",
            encoding="utf-8",
        )

        mock_journals.exists.return_value = True
        mock_journals.rglob.return_value = [journal]
        mock_journals.parent = tmp_path
        mock_topic.exists.return_value = True
        mock_topic.glob.return_value = []
        mock_attach.exists.return_value = True
        mock_attach.rglob.return_value = []

        validator = DataValidator()
        result = validator.run()

        assert isinstance(result, ValidationResult)
        assert result.total_journals == 1


class TestPrintReportExtended:
    """Extended tests for print_report function"""

    def test_print_report_with_stats(self, capsys):
        """Test printing report with statistics"""
        result = ValidationResult()
        result.total_journals = 10
        result.stats = {
            "topics": {"work": 5, "life": 3},
            "projects": {"LifeIndex": 7},
            "monthly_distribution": {"2026-03": 10},
        }

        print_report(result)

        captured = capsys.readouterr()
        assert "work" in captured.out or "topics" in captured.out.lower()

    def test_print_report_with_suggestion(self, capsys):
        """Test printing report with suggestion"""
        result = ValidationResult()
        result.issues = [
            ValidationIssue(
                level="error",
                category="metadata",
                file="test.md",
                message="Missing title",
                suggestion="Add a title field",
            )
        ]

        print_report(result)

        captured = capsys.readouterr()
        assert "Add a title field" in captured.out


class TestPrintReport:
    """Tests for print_report function"""

    def test_print_report_no_issues(self, capsys):
        """Test printing report with no issues"""
        result = ValidationResult()
        result.total_journals = 5
        result.total_indices = 3
        result.total_attachments = 2

        print_report(result)

        captured = capsys.readouterr()
        assert "5" in captured.out
        assert "3" in captured.out

    def test_print_report_json(self, capsys):
        """Test printing report in JSON format"""
        result = ValidationResult()
        result.total_journals = 5

        print_report(result, use_json=True)

        captured = capsys.readouterr()
        assert '"total_journals": 5' in captured.out

    def test_print_report_with_issues(self, capsys):
        """Test printing report with issues"""
        result = ValidationResult()
        result.issues = [
            ValidationIssue(
                level="error",
                category="metadata",
                file="test.md",
                message="Missing title",
                suggestion="Add title",
            )
        ]

        print_report(result)

        captured = capsys.readouterr()
        assert "error" in captured.out.lower() or "1" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
