"""Tests for migration edge cases and idempotency."""

from pathlib import Path


class TestMigrateEdgeCases:
    def test_missing_schema_version_treated_as_v1(self, tmp_path: Path):
        """Journals without schema_version field should be treated as v1."""
        from tools.migrate import apply_migrations

        journal = tmp_path / "Journals" / "2025" / "01" / "life-index_2025-01-01_001.md"
        journal.parent.mkdir(parents=True)
        journal.write_text(
            "---\ntitle: 无版本号\ndate: 2025-01-01\n---\n\n# 正文\n",
            encoding="utf-8",
        )
        result = apply_migrations(tmp_path / "Journals")
        assert result["migrated_count"] == 1

    def test_corrupted_frontmatter_skipped(self, tmp_path: Path):
        """A file without a frontmatter block is refused, not wrapped.

        Wrapping the whole file in new frontmatter would change every byte
        after the (absent) block, so the lossless rewrite rule refuses it;
        the good file next to it still migrates.
        """
        from tools.migrate import apply_migrations

        journals_dir = tmp_path / "Journals" / "2025" / "01"
        journals_dir.mkdir(parents=True)

        # Good file
        good = journals_dir / "life-index_2025-01-01_001.md"
        good.write_text(
            "---\nschema_version: 1\ntitle: 好的\ndate: 2025-01-01\n"
            'topic: ["work"]\n---\n\n# 好的\n',
            encoding="utf-8",
        )
        # File without frontmatter — refused, bytes kept
        bare = journals_dir / "life-index_2025-01-02_001.md"
        bare_bytes = "这不是有效的 YAML frontmatter".encode("utf-8")
        bare.write_bytes(bare_bytes)

        result = apply_migrations(tmp_path / "Journals")
        assert result["migrated_count"] == 1
        assert result["failed_count"] == 1
        assert result["failed_files"][0]["path"] == str(bare)
        assert "no_frontmatter_block" in result["failed_files"][0]["error"]
        assert bare.read_bytes() == bare_bytes

    def test_non_journal_files_ignored(self, tmp_path: Path):
        """Non-journal files (index, report) should be ignored."""
        from tools.migrate import scan_journals
        from tools.lib.schema import SCHEMA_VERSION

        journals_dir = tmp_path / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)

        (journals_dir / "index_2026-03.md").write_text("# 索引", encoding="utf-8")
        (journals_dir / "report_2026-03.md").write_text("# 报告", encoding="utf-8")
        (journals_dir / "life-index_2026-03-01_001.md").write_text(
            f"---\nschema_version: {SCHEMA_VERSION}\ntitle: 日志\ndate: 2026-03-01\n"
            'topic: ["work"]\n---\n\n# 正文\n',
            encoding="utf-8",
        )

        report = scan_journals(tmp_path / "Journals")
        assert report["total_scanned"] == 1  # Only life-index_*.md

    def test_large_batch_migration(self, tmp_path: Path):
        """50 journal files batch migration should complete normally."""
        from tools.migrate import apply_migrations

        for i in range(50):
            day = f"{(i % 28) + 1:02d}"
            month = f"{(i // 28) + 1:02d}"
            journal = (
                tmp_path / "Journals" / "2025" / month / f"life-index_2025-{month}-{day}_001.md"
            )
            journal.parent.mkdir(parents=True, exist_ok=True)
            journal.write_text(
                f"---\nschema_version: 1\ntitle: 日志{i}\ndate: 2025-{month}-{day}\n"
                f'topic: ["work"]\n---\n\n# 正文{i}\n',
                encoding="utf-8",
            )

        result = apply_migrations(tmp_path / "Journals")
        assert result["migrated_count"] == 50
        assert result["failed_count"] == 0

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
