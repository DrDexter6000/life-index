"""Tests for migrate --apply execution."""

import json
import pytest
from pathlib import Path


class TestMigrateApply:
    def _create_v1_journal(self, path: Path) -> None:
        content = (
            "---\n"
            "schema_version: 1\n"
            "title: 旧日志\n"
            "date: 2025-06-15\n"
            'mood: ["开心"]\n'
            'tags: ["测试"]\n'
            'topic: ["life"]\n'
            "abstract: 这是一篇旧日志\n"
            "---\n\n"
            "# 旧日志正文\n\n今天很开心。\n"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_apply_upgrades_schema_version(self, tmp_path: Path):
        """--apply should upgrade schema_version to latest."""
        from tools.migrate import apply_migrations
        from tools.lib.schema import SCHEMA_VERSION

        journal = tmp_path / "Journals" / "2025" / "06" / "life-index_2025-06-15_001.md"
        self._create_v1_journal(journal)

        result = apply_migrations(tmp_path / "Journals")
        assert result["migrated_count"] == 1
        assert result["failed_count"] == 0

        # Verify file was modified
        from tools.lib.frontmatter import parse_frontmatter

        file_content = journal.read_text(encoding="utf-8")
        meta, _body = parse_frontmatter(file_content)
        assert meta["schema_version"] == SCHEMA_VERSION
        assert "entities" in meta
        assert "sentiment_score" not in meta
        assert "themes" not in meta

    def test_apply_preserves_existing_content(self, tmp_path: Path):
        """Migration should not modify body content."""
        from tools.migrate import apply_migrations

        journal = tmp_path / "Journals" / "2025" / "06" / "life-index_2025-06-15_001.md"
        self._create_v1_journal(journal)

        apply_migrations(tmp_path / "Journals")

        content = journal.read_text(encoding="utf-8")
        assert "今天很开心。" in content
        assert "旧日志正文" in content

    def test_apply_idempotent(self, tmp_path: Path):
        """Repeated --apply should produce no changes."""
        from tools.migrate import apply_migrations

        journal = tmp_path / "Journals" / "2025" / "06" / "life-index_2025-06-15_001.md"
        self._create_v1_journal(journal)

        result1 = apply_migrations(tmp_path / "Journals")
        assert result1["migrated_count"] == 1

        result2 = apply_migrations(tmp_path / "Journals")
        assert result2["migrated_count"] == 0
        assert result2["already_current"] == 1

    def test_apply_preserves_existing_fields(self, tmp_path: Path):
        """Existing field values should not be overwritten."""
        from tools.migrate import apply_migrations

        journal = tmp_path / "Journals" / "2025" / "06" / "life-index_2025-06-15_001.md"
        self._create_v1_journal(journal)

        apply_migrations(tmp_path / "Journals")

        from tools.lib.frontmatter import parse_frontmatter

        file_content = journal.read_text(encoding="utf-8")
        meta, _body = parse_frontmatter(file_content)
        assert meta["title"] == "旧日志"
        assert meta["abstract"] == "这是一篇旧日志"
        assert meta["mood"] == ["开心"]

    def test_apply_output_json_format(self, tmp_path: Path):
        """--apply output should contain all required fields."""
        from tools.migrate import apply_migrations

        journal = tmp_path / "Journals" / "2025" / "01" / "life-index_2025-01-01_001.md"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(
            "---\nschema_version: 1\ntitle: 测试\ndate: 2025-01-01\n"
            'topic: ["work"]\n---\n\n# 正文\n',
            encoding="utf-8",
        )

        result = apply_migrations(tmp_path / "Journals")
        required_keys = {
            "migrated_count",
            "already_current",
            "failed_count",
            "failed_files",
            "needs_agent",
            "deterministic_changes",
        }
        assert required_keys.issubset(set(result.keys()))
