"""Tests for migrate --apply execution."""

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

    def test_apply_preserves_original_when_replace_fails(self, tmp_path: Path, monkeypatch):
        """Migration failure during replace should not delete the original file."""
        from tools.migrate import apply_migrations

        journal = tmp_path / "Journals" / "2025" / "06" / "life-index_2025-06-15_001.md"
        self._create_v1_journal(journal)
        original_content = journal.read_text(encoding="utf-8")

        def fail_replace(self, target):
            raise OSError("replace failed")

        def fail_rename(self, target):
            raise OSError("rename failed")

        monkeypatch.setattr(Path, "replace", fail_replace)
        monkeypatch.setattr(Path, "rename", fail_rename)

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 0
        assert result["failed_count"] == 1
        assert journal.exists(), "original file should still exist after replacement failure"
        assert journal.read_text(encoding="utf-8") == original_content


class TestUnreadableFrontmatterIsLeftUntouched:
    """D3: migrate never rewrites a file whose frontmatter it could not read."""

    UNREADABLE = {
        "list_root": "---\n- token\n---\n\nbody\n",
        "scalar_root": "---\njust a scalar\n---\n\nbody\n",
        "recursive_alias": "---\ntitle: T\ncustom: &a [*a]\n---\n\nbody\n",
        "invalid_yaml": "---\ntitle: [unterminated\ndate: 2026-03-04\n---\n\nbody\n",
        "false_root": "---\nfalse\n---\n\nbody\n",
        "zero_root": "---\n0\n---\n\nbody\n",
        "empty_list_root": "---\n[]\n---\n\nbody\n",
        "pairs_cycle": "---\ntitle: T\ncustom: &a !!pairs [x: *a]\n---\n\nbody\n",
    }

    @staticmethod
    def _journal(tmp_path: Path) -> Path:
        journal = tmp_path / "Journals" / "2025" / "06" / "life-index_2025-06-15_001.md"
        journal.parent.mkdir(parents=True, exist_ok=True)
        return journal

    @pytest.mark.parametrize("shape", sorted(UNREADABLE))
    def test_apply_leaves_the_bytes_unchanged(self, tmp_path: Path, shape):
        from tools.migrate import apply_migrations

        journal = self._journal(tmp_path)
        original = self.UNREADABLE[shape].encode()
        journal.write_bytes(original)

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 0
        assert result["failed_count"] == 1
        assert result["failed_files"][0]["path"] == str(journal)
        assert "unreadable" in result["failed_files"][0]["error"]
        assert journal.read_bytes() == original

    @pytest.mark.parametrize("shape", sorted(UNREADABLE))
    def test_scan_reports_the_file_as_unparseable(self, tmp_path: Path, shape):
        from tools.migrate import scan_journals

        journal = self._journal(tmp_path)
        journal.write_bytes(self.UNREADABLE[shape].encode())

        report = scan_journals(tmp_path / "Journals")

        assert report["total_scanned"] == 1
        assert report["version_distribution"] == {"unparseable": 1}
        assert report["needs_migration"] == 0

    def test_a_legacy_recoverable_file_still_migrates(self, tmp_path: Path):
        from tools.lib.frontmatter import parse_frontmatter
        from tools.lib.schema import SCHEMA_VERSION
        from tools.migrate import apply_migrations

        journal = self._journal(tmp_path)
        journal.write_text(
            '---\ntitle: "Legacy"\ndate: 2025-06-15\ncontent: "line one\nline two"\n'
            "---\n\n# body\n",
            encoding="utf-8",
        )

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 1
        assert result["failed_count"] == 0
        metadata, body = parse_frontmatter(journal.read_text(encoding="utf-8"))
        assert metadata["schema_version"] == SCHEMA_VERSION
        assert metadata["title"] == "Legacy"
        assert "line one" in body


class TestNotRoundTrippableFrontmatterIsLeftUntouched:
    """D3: migrate refuses to rewrite an outdated file the serializer cannot reproduce.

    Such a file is readable, so the scan reports its real version and that it
    needs a migration; ``--apply`` fails it alone and keeps its bytes. A file
    that is already current is never rewritten, so the guard does not concern it.
    """

    NOT_ROUND_TRIPPABLE = {
        "set_value": (
            "---\nschema_version: 1\ntitle: T\ndate: 2025-06-15\n"
            "tags: !!set {alpha: null, beta: null}\n---\n\nbody\n"
        ),
        "pairs_value": (
            "---\nschema_version: 1\ntitle: T\ndate: 2025-06-15\n"
            "custom: !!pairs [a: b, c: d]\n---\n\nbody\n"
        ),
    }

    @staticmethod
    def _journal(tmp_path: Path) -> Path:
        journal = tmp_path / "Journals" / "2025" / "06" / "life-index_2025-06-15_001.md"
        journal.parent.mkdir(parents=True, exist_ok=True)
        return journal

    @pytest.mark.parametrize("shape", sorted(NOT_ROUND_TRIPPABLE))
    def test_apply_leaves_the_bytes_unchanged(self, tmp_path: Path, shape):
        from tools.migrate import apply_migrations

        journal = self._journal(tmp_path)
        original = self.NOT_ROUND_TRIPPABLE[shape].encode()
        journal.write_bytes(original)

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 0
        assert result["failed_count"] == 1
        assert result["failed_files"][0]["path"] == str(journal)
        assert "not_round_trippable" in result["failed_files"][0]["error"]
        assert journal.read_bytes() == original

    @pytest.mark.parametrize("shape", sorted(NOT_ROUND_TRIPPABLE))
    def test_scan_reports_the_real_version_and_the_blocker(self, tmp_path: Path, shape):
        from tools.migrate import scan_journals

        journal = self._journal(tmp_path)
        journal.write_bytes(self.NOT_ROUND_TRIPPABLE[shape].encode())

        report = scan_journals(tmp_path / "Journals")

        assert report["total_scanned"] == 1
        assert report["version_distribution"] == {"1": 1}
        assert report["needs_migration"] == 1
        assert report["outdated_files"][0]["rewrite_blocker"] == "not_round_trippable"

    def test_scan_names_no_blocker_for_a_rewritable_outdated_file(self, tmp_path: Path):
        from tools.migrate import scan_journals

        journal = self._journal(tmp_path)
        journal.write_bytes(b"---\nschema_version: 1\ntitle: T\ndate: 2025-06-15\n---\n\nbody\n")

        report = scan_journals(tmp_path / "Journals")

        assert report["needs_migration"] == 1
        assert "rewrite_blocker" not in report["outdated_files"][0]

    @pytest.mark.parametrize("shape", sorted(NOT_ROUND_TRIPPABLE))
    def test_a_current_file_is_not_a_failure(self, tmp_path: Path, shape):
        from tools.lib.schema import SCHEMA_VERSION
        from tools.migrate import apply_migrations, scan_journals

        journal = self._journal(tmp_path)
        original = (
            self.NOT_ROUND_TRIPPABLE[shape]
            .replace("schema_version: 1", f"schema_version: {SCHEMA_VERSION}")
            .encode()
        )
        assert original != self.NOT_ROUND_TRIPPABLE[shape].encode()
        journal.write_bytes(original)

        report = scan_journals(tmp_path / "Journals")
        result = apply_migrations(tmp_path / "Journals")

        assert report["version_distribution"] == {str(SCHEMA_VERSION): 1}
        assert report["needs_migration"] == 0
        assert result["already_current"] == 1
        assert result["failed_count"] == 0
        assert result["migrated_count"] == 0
        assert journal.read_bytes() == original


class TestOneFileNeverAbortsTheRun:
    """A file the migration cannot compute fails alone; the run goes on."""

    BROKEN = {
        "non_string_key": "---\ntitle: T\ndate: 2025-06-14\n2024: x\n---\n\nbody\n",
        "schema_version_text": (
            "---\nschema_version: abc\ntitle: T\ndate: 2025-06-14\n---\n\nbody\n"
        ),
    }

    @staticmethod
    def _month(tmp_path: Path) -> Path:
        month = tmp_path / "Journals" / "2025" / "06"
        month.mkdir(parents=True, exist_ok=True)
        return month

    @pytest.mark.parametrize("shape", sorted(BROKEN))
    def test_apply_fails_that_file_and_migrates_the_next(self, tmp_path: Path, shape):
        from tools.lib.frontmatter import parse_frontmatter
        from tools.lib.schema import SCHEMA_VERSION
        from tools.migrate import apply_migrations

        month = self._month(tmp_path)
        broken = month / "life-index_2025-06-14_001.md"
        original = self.BROKEN[shape].encode()
        broken.write_bytes(original)
        good = month / "life-index_2025-06-15_001.md"
        good.write_text(
            "---\nschema_version: 1\ntitle: Good\ndate: 2025-06-15\n---\n\nbody\n",
            encoding="utf-8",
        )

        result = apply_migrations(tmp_path / "Journals")

        assert [item["path"] for item in result["failed_files"]] == [str(broken)]
        assert broken.read_bytes() == original
        assert result["migrated_count"] == 1
        metadata, _body = parse_frontmatter(good.read_text(encoding="utf-8"))
        assert metadata["schema_version"] == SCHEMA_VERSION

    @pytest.mark.parametrize("shape", sorted(BROKEN))
    def test_scan_does_not_raise(self, tmp_path: Path, shape):
        from tools.migrate import scan_journals

        (self._month(tmp_path) / "life-index_2025-06-14_001.md").write_bytes(
            self.BROKEN[shape].encode()
        )

        report = scan_journals(tmp_path / "Journals")

        assert report["total_scanned"] == 1


class TestRewriteKeepsWhatItRead:
    def test_a_content_key_that_is_not_text_survives_the_rewrite(self, tmp_path: Path):
        from tools.migrate import apply_migrations

        journal = tmp_path / "Journals" / "2025" / "06" / "life-index_2025-06-15_001.md"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(
            "---\ntitle: T\ndate: 2025-06-15\ncontent: [irreplaceabletoken]\n---\n\nbody\n",
            encoding="utf-8",
        )

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 1
        assert "irreplaceabletoken" in journal.read_text(encoding="utf-8")
