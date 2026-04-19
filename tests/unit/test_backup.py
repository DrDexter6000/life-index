#!/usr/bin/env python3
"""
Unit tests for tools/backup/__init__.py
"""

import hashlib
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

from tools.backup import (
    calculate_file_hash,
    load_backup_manifest,
    save_backup_manifest,
    create_backup,
    list_backups,
    restore_backup,
)


class TestCalculateFileHash:
    """Tests for calculate_file_hash function"""

    def test_calculate_hash_success(self, tmp_path):
        """Test successful hash calculation"""
        test_file = tmp_path / "test.txt"
        test_content = b"Hello, World!"
        test_file.write_bytes(test_content)

        result = calculate_file_hash(test_file)

        # Verify hash matches expected MD5
        expected = hashlib.md5(test_content).hexdigest()
        assert result == expected

    def test_calculate_hash_empty_file(self, tmp_path):
        """Test hash of empty file"""
        test_file = tmp_path / "empty.txt"
        test_file.touch()

        result = calculate_file_hash(test_file)

        expected = hashlib.md5(b"").hexdigest()
        assert result == expected

    def test_calculate_hash_file_not_found(self, tmp_path):
        """Test hash of non-existent file returns empty string"""
        non_existent = tmp_path / "nonexistent.txt"

        result = calculate_file_hash(non_existent)

        assert result == ""

    def test_calculate_hash_large_file(self, tmp_path):
        """Test hash of file larger than chunk size"""
        test_file = tmp_path / "large.bin"
        # Create file larger than 4096 bytes (chunk size)
        test_content = b"x" * 10000
        test_file.write_bytes(test_content)

        result = calculate_file_hash(test_file)

        expected = hashlib.md5(test_content).hexdigest()
        assert result == expected


class TestLoadBackupManifest:
    """Tests for load_backup_manifest function"""

    def test_load_existing_manifest(self, tmp_path):
        """Test loading an existing manifest file"""
        manifest_path = tmp_path / ".life-index-backup-manifest.json"
        manifest_data = {
            "backups": [{"timestamp": "20260320_120000", "type": "full"}],
            "files": {"test.txt": {"hash": "abc123"}},
        }
        manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

        result = load_backup_manifest(tmp_path)

        assert result == manifest_data

    def test_load_nonexistent_manifest(self, tmp_path):
        """Test loading when manifest doesn't exist"""
        result = load_backup_manifest(tmp_path)

        assert result == {"backups": [], "files": {}}

    def test_load_invalid_json(self, tmp_path):
        """Test loading when manifest has invalid JSON"""
        manifest_path = tmp_path / ".life-index-backup-manifest.json"
        manifest_path.write_text("not valid json", encoding="utf-8")

        result = load_backup_manifest(tmp_path)

        assert result == {"backups": [], "files": {}}


class TestSaveBackupManifest:
    """Tests for save_backup_manifest function"""

    def test_save_manifest_success(self, tmp_path):
        """Test saving manifest successfully"""
        manifest_data = {
            "backups": [{"timestamp": "20260320_120000"}],
            "files": {"test.txt": {"hash": "abc123"}},
        }

        save_backup_manifest(tmp_path, manifest_data)

        manifest_path = tmp_path / ".life-index-backup-manifest.json"
        assert manifest_path.exists()
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert loaded == manifest_data

    def test_save_manifest_creates_file(self, tmp_path):
        """Test that save creates the manifest file"""
        manifest_data = {"backups": [], "files": {}}

        save_backup_manifest(tmp_path, manifest_data)

        manifest_path = tmp_path / ".life-index-backup-manifest.json"
        assert manifest_path.exists()

    def test_save_manifest_io_error(self, tmp_path):
        """Test saving manifest when IOError occurs (lines 66-67)"""
        manifest_data = {"backups": [], "files": {}}
        manifest_path = tmp_path / ".life-index-backup-manifest.json"

        # Create a read-only directory to trigger IOError
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            # Should not raise, just log error
            save_backup_manifest(tmp_path, manifest_data)

        # Verify function completed without raising
        assert True


class TestCreateBackup:
    """Tests for create_backup function"""

    @patch("tools.backup.get_journals_dir")
    @patch("tools.backup.get_by_topic_dir")
    @patch("tools.backup.get_attachments_dir")
    def test_create_backup_dry_run(
        self, mock_attach, mock_topic, mock_journals, tmp_path
    ):
        """Test backup in dry-run mode"""
        # Setup mock directories
        mock_journals.exists.return_value = False
        mock_topic.exists.return_value = False
        mock_attach.exists.return_value = False

        result = create_backup(str(tmp_path), dry_run=True)

        assert result["success"] is True
        assert result["files_backed_up"] == 0
        assert result["files_skipped"] == 0

    @patch("tools.backup.get_journals_dir")
    @patch("tools.backup.get_by_topic_dir")
    @patch("tools.backup.get_attachments_dir")
    def test_create_backup_full_mode(
        self, mock_attach, mock_topic, mock_journals, tmp_path
    ):
        """Test full backup mode"""
        # Setup mock directories as non-existent
        mock_journals.exists.return_value = False
        mock_topic.exists.return_value = False
        mock_attach.exists.return_value = False

        result = create_backup(str(tmp_path), full=True, dry_run=True)

        assert result["success"] is True

    @patch("tools.backup.get_journals_dir")
    @patch("tools.backup.get_by_topic_dir")
    @patch("tools.backup.get_attachments_dir")
    def test_create_backup_with_exclude_patterns(
        self, mock_attach, mock_topic, mock_journals, tmp_path
    ):
        """Test backup with custom exclude patterns"""
        mock_journals.exists.return_value = False
        mock_topic.exists.return_value = False
        mock_attach.exists.return_value = False

        result = create_backup(
            str(tmp_path),
            dry_run=True,
            exclude_patterns=["*.log", "temp_*"],
        )

        assert result["success"] is True

    def test_create_backup_actual_files(self, tmp_path):
        """Test backup with actual files (lines 107, 113, 143-180)"""
        # Create real source directories with files
        journals_src = tmp_path / "Journals"
        journals_src.mkdir()
        (journals_src / "2026").mkdir()
        (journals_src / "2026" / "03").mkdir()
        test_file = journals_src / "2026" / "03" / "test.md"
        test_file.write_text("---\ntitle: Test\n---\nContent", encoding="utf-8")

        by_topic_src = tmp_path / "by-topic"
        by_topic_src.mkdir()

        attachments_src = tmp_path / "attachments"
        attachments_src.mkdir()

        backup_dest = tmp_path / "backup_dest"

        # Patch config to use our temp directories
        with (
            patch("tools.backup.get_journals_dir", return_value=journals_src),
            patch("tools.backup.get_by_topic_dir", return_value=by_topic_src),
            patch("tools.backup.get_attachments_dir", return_value=attachments_src),
        ):
            result = create_backup(str(backup_dest), dry_run=False)

        assert result["success"] is True
        assert result["files_backed_up"] >= 1
        assert result["backup_path"] != ""
        assert result["manifest_path"] != ""

    def test_create_backup_excludes_matching_files(self, tmp_path):
        """Test should_exclude function (lines 132-135)"""
        # Create source with files that should be excluded
        journals_src = tmp_path / "Journals"
        journals_src.mkdir()
        (journals_src / "2026").mkdir()
        (journals_src / "2026" / "03").mkdir()

        # Regular file
        regular_file = journals_src / "2026" / "03" / "regular.md"
        regular_file.write_text("content", encoding="utf-8")

        # File matching exclude pattern (substring match: ".tmp" in filename)
        # Note: The exclude pattern matching uses substring matching, not glob
        tmp_file = journals_src / "2026" / "03" / "test.tmp"
        tmp_file.write_text("temp content", encoding="utf-8")

        by_topic_src = tmp_path / "by-topic"
        by_topic_src.mkdir()

        attachments_src = tmp_path / "attachments"
        attachments_src.mkdir()

        backup_dest = tmp_path / "backup_dest"

        # Use custom exclude pattern that will match via substring
        with (
            patch("tools.backup.get_journals_dir", return_value=journals_src),
            patch("tools.backup.get_by_topic_dir", return_value=by_topic_src),
            patch("tools.backup.get_attachments_dir", return_value=attachments_src),
        ):
            result = create_backup(
                str(backup_dest), dry_run=False, exclude_patterns=[".tmp"]
            )

        # Only regular file should be backed up, .tmp excluded
        assert result["files_backed_up"] == 1

    def test_create_backup_incremental_skips_unchanged(self, tmp_path):
        """Test incremental backup skips unchanged files (lines 158-162)"""
        # Create source directory
        journals_src = tmp_path / "Journals"
        journals_src.mkdir()
        (journals_src / "2026").mkdir()
        (journals_src / "2026" / "03").mkdir()
        test_file = journals_src / "2026" / "03" / "test.md"
        test_file.write_text("unchanged content", encoding="utf-8")

        by_topic_src = tmp_path / "by-topic"
        by_topic_src.mkdir()

        attachments_src = tmp_path / "attachments"
        attachments_src.mkdir()

        backup_dest = tmp_path / "backup_dest"

        with (
            patch("tools.backup.get_journals_dir", return_value=journals_src),
            patch("tools.backup.get_by_topic_dir", return_value=by_topic_src),
            patch("tools.backup.get_attachments_dir", return_value=attachments_src),
        ):
            # First backup
            result1 = create_backup(str(backup_dest), dry_run=False)
            assert result1["files_backed_up"] == 1
            assert result1["files_skipped"] == 0

            # Second backup (incremental) - file unchanged
            result2 = create_backup(str(backup_dest), dry_run=False, full=False)
            assert result2["files_skipped"] >= 1  # Should skip unchanged file

    def test_create_backup_incremental_with_changed_file(self, tmp_path):
        """Test incremental backup copies changed files (line 160->164)"""
        journals_src = tmp_path / "Journals"
        journals_src.mkdir()
        (journals_src / "2026").mkdir()
        (journals_src / "2026" / "03").mkdir()
        test_file = journals_src / "2026" / "03" / "test.md"
        test_file.write_text("original content", encoding="utf-8")

        by_topic_src = tmp_path / "by-topic"
        by_topic_src.mkdir()

        attachments_src = tmp_path / "attachments"
        attachments_src.mkdir()

        backup_dest = tmp_path / "backup_dest"

        with (
            patch("tools.backup.get_journals_dir", return_value=journals_src),
            patch("tools.backup.get_by_topic_dir", return_value=by_topic_src),
            patch("tools.backup.get_attachments_dir", return_value=attachments_src),
        ):
            # First backup
            result1 = create_backup(str(backup_dest), dry_run=False)
            assert result1["files_backed_up"] == 1

            # Modify the file
            test_file.write_text("modified content", encoding="utf-8")

            # Second backup (incremental) - file changed
            result2 = create_backup(str(backup_dest), dry_run=False, full=False)
            assert result2["files_backed_up"] >= 1  # Should backup changed file

    def test_create_backup_dry_run_with_files(self, tmp_path):
        """Test dry_run mode with actual files (lines 144->147, 164->168)"""
        journals_src = tmp_path / "Journals"
        journals_src.mkdir()
        (journals_src / "2026").mkdir()
        (journals_src / "2026" / "03").mkdir()
        test_file = journals_src / "2026" / "03" / "test.md"
        test_file.write_text("content", encoding="utf-8")

        by_topic_src = tmp_path / "by-topic"
        by_topic_src.mkdir()

        attachments_src = tmp_path / "attachments"
        attachments_src.mkdir()

        backup_dest = tmp_path / "backup_dest"

        with (
            patch("tools.backup.get_journals_dir", return_value=journals_src),
            patch("tools.backup.get_by_topic_dir", return_value=by_topic_src),
            patch("tools.backup.get_attachments_dir", return_value=attachments_src),
        ):
            result = create_backup(str(backup_dest), dry_run=True)

        # In dry_run mode, files should be counted but not copied
        assert result["files_backed_up"] >= 1
        # No backup directory should be created
        assert not (backup_dest / "life-index-backup").exists()

    def test_create_backup_saves_manifest_with_records(self, tmp_path):
        """Test saving manifest with backup records (lines 194-206)"""
        journals_src = tmp_path / "Journals"
        journals_src.mkdir()
        (journals_src / "2026").mkdir()
        (journals_src / "2026" / "03").mkdir()
        test_file = journals_src / "2026" / "03" / "test.md"
        test_file.write_text("content", encoding="utf-8")

        by_topic_src = tmp_path / "by-topic"
        by_topic_src.mkdir()

        attachments_src = tmp_path / "attachments"
        attachments_src.mkdir()

        backup_dest = tmp_path / "backup_dest"

        with (
            patch("tools.backup.get_journals_dir", return_value=journals_src),
            patch("tools.backup.get_by_topic_dir", return_value=by_topic_src),
            patch("tools.backup.get_attachments_dir", return_value=attachments_src),
        ):
            result = create_backup(str(backup_dest), dry_run=False)

        # Verify manifest was saved with backup record
        manifest_path = backup_dest / ".life-index-backup-manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert len(manifest["backups"]) == 1
        assert manifest["backups"][0]["type"] == "incremental"
        assert manifest["backups"][0]["files_backed_up"] == 1

    def test_create_backup_manifest_without_backups_key(self, tmp_path):
        """Test manifest initialization when 'backups' key is missing (line 202)"""
        journals_src = tmp_path / "Journals"
        journals_src.mkdir()
        (journals_src / "2026").mkdir()
        (journals_src / "2026" / "03").mkdir()
        test_file = journals_src / "2026" / "03" / "test.md"
        test_file.write_text("content", encoding="utf-8")

        by_topic_src = tmp_path / "by-topic"
        by_topic_src.mkdir()

        attachments_src = tmp_path / "attachments"
        attachments_src.mkdir()

        backup_dest = tmp_path / "backup_dest"
        backup_dest.mkdir()

        # Create a manifest without 'backups' key
        manifest_path = backup_dest / ".life-index-backup-manifest.json"
        manifest_path.write_text('{"files": {}}', encoding="utf-8")

        with (
            patch("tools.backup.get_journals_dir", return_value=journals_src),
            patch("tools.backup.get_by_topic_dir", return_value=by_topic_src),
            patch("tools.backup.get_attachments_dir", return_value=attachments_src),
        ):
            result = create_backup(str(backup_dest), dry_run=False)

        # Verify manifest was updated with backups key
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "backups" in manifest
        assert len(manifest["backups"]) == 1

    def test_create_backup_error_handling(self, tmp_path):
        """Test error handling in backup_directory (lines 177-180)"""
        journals_src = tmp_path / "Journals"
        journals_src.mkdir()
        (journals_src / "2026").mkdir()
        (journals_src / "2026" / "03").mkdir()
        test_file = journals_src / "2026" / "03" / "test.md"
        test_file.write_text("content", encoding="utf-8")

        by_topic_src = tmp_path / "by-topic"
        by_topic_src.mkdir()

        attachments_src = tmp_path / "attachments"
        attachments_src.mkdir()

        backup_dest = tmp_path / "backup_dest"

        with (
            patch("tools.backup.get_journals_dir", return_value=journals_src),
            patch("tools.backup.get_by_topic_dir", return_value=by_topic_src),
            patch("tools.backup.get_attachments_dir", return_value=attachments_src),
            patch("tools.backup.shutil.copy2", side_effect=IOError("Disk full")),
        ):
            result = create_backup(str(backup_dest), dry_run=False)

        assert len(result["errors"]) > 0
        assert "Disk full" in result["errors"][0]

    def test_create_backup_outer_error_handling(self, tmp_path):
        """Test outer error handling in create_backup (lines 215-218)"""
        journals_src = tmp_path / "Journals"
        journals_src.mkdir()

        by_topic_src = tmp_path / "by-topic"
        by_topic_src.mkdir()

        attachments_src = tmp_path / "attachments"
        attachments_src.mkdir()

        backup_dest = tmp_path / "backup_dest"

        # Make Path.mkdir raise an error
        original_mkdir = Path.mkdir

        def raise_oserror(self, *args, **kwargs):
            raise OSError("System error")

        with patch.object(Path, "mkdir", raise_oserror):
            result = create_backup(str(backup_dest), dry_run=False)

        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert "System error" in result["errors"][0]

    def test_restore_backup_outer_error_handling(self, tmp_path):
        """Test outer error handling in restore_backup (lines 286-289)"""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        dest_dir = tmp_path / "restore_dest"
        dest_dir.mkdir()

        # Mock Path.exists to raise error
        with patch("pathlib.Path.exists", side_effect=OSError("System error")):
            result = restore_backup(
                str(backup_dir), dest_path=str(dest_dir), dry_run=False
            )

        assert result["success"] is False
        assert len(result["errors"]) > 0


class TestListBackups:
    """Tests for list_backups function"""

    def test_list_backups_empty(self, tmp_path):
        """list_backups should return empty list when manifest missing"""
        result = list_backups(tmp_path)

        assert result == []

    def test_list_backups_with_records(self, tmp_path):
        """list_backups should return backup records from manifest"""
        manifest_path = tmp_path / ".life-index-backup-manifest.json"
        manifest_data = {
            "backups": [
                {"timestamp": "20260320_120000", "type": "full"},
                {"timestamp": "20260320_130000", "type": "incremental"},
            ],
            "files": {},
        }
        manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

        result = list_backups(tmp_path)

        assert len(result) == 2
        assert result[0]["type"] == "full"
        assert result[1]["type"] == "incremental"


class TestRestoreBackup:
    """Tests for restore_backup function"""

    def test_restore_backup_missing_directory(self, tmp_path):
        """restore_backup should report missing backup directory"""
        result = restore_backup(str(tmp_path / "missing"), dry_run=False)

        assert result["success"] is False
        assert result["files_restored"] == 0
        assert result["errors"]

    def test_restore_backup_with_files(self, tmp_path):
        """restore_backup should copy files from Journals/by-topic/attachments"""
        backup_dir = tmp_path / "backup"
        journals_dir = backup_dir / "Journals" / "2026" / "03"
        topic_dir = backup_dir / "by-topic"
        attachments_dir = backup_dir / "attachments" / "2026" / "03"
        journals_dir.mkdir(parents=True)
        topic_dir.mkdir(parents=True)
        attachments_dir.mkdir(parents=True)

        (journals_dir / "life-index_2026-03-20_001.md").write_text(
            "journal", encoding="utf-8"
        )
        (topic_dir / "主题_work.md").write_text("index", encoding="utf-8")
        (attachments_dir / "img.png").write_text("attachment", encoding="utf-8")

        dest_dir = tmp_path / "restored"

        result = restore_backup(str(backup_dir), dest_path=str(dest_dir), dry_run=False)

        assert result["success"] is True
        assert result["files_restored"] == 3
        assert (
            dest_dir / "Journals" / "2026" / "03" / "life-index_2026-03-20_001.md"
        ).exists()
        assert (dest_dir / "by-topic" / "主题_work.md").exists()
        assert (dest_dir / "attachments" / "2026" / "03" / "img.png").exists()

    def test_restore_backup_dry_run_counts_without_copying(self, tmp_path):
        """restore_backup dry run should count files without creating output"""
        backup_dir = tmp_path / "backup"
        journals_dir = backup_dir / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)
        (journals_dir / "life-index_2026-03-20_001.md").write_text(
            "journal", encoding="utf-8"
        )

        dest_dir = tmp_path / "restored"
        result = restore_backup(str(backup_dir), dest_path=str(dest_dir), dry_run=True)

        assert result["success"] is True
        assert result["files_restored"] == 1
        assert not dest_dir.exists()

    def test_restore_backup_file_copy_error(self, tmp_path):
        """restore_backup should collect per-file copy errors"""
        backup_dir = tmp_path / "backup"
        journals_dir = backup_dir / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True)
        source_file = journals_dir / "life-index_2026-03-20_001.md"
        source_file.write_text("journal", encoding="utf-8")

        dest_dir = tmp_path / "restored"

        with patch("tools.backup.shutil.copy2", side_effect=IOError("copy failed")):
            result = restore_backup(
                str(backup_dir), dest_path=str(dest_dir), dry_run=False
            )

        assert result["success"] is False
        assert result["files_restored"] == 0
        assert any("copy failed" in err for err in result["errors"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
