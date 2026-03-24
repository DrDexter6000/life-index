#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestE2ERunnerIsolation:
    def test_write_journal_subprocess_receives_isolated_data_dir(
        self, tmp_path: Path
    ) -> None:
        from tests.e2e.runner import E2ETestRunner

        runner = E2ETestRunner(project_root=tmp_path)
        expected_root = runner.test_data_dir

        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = '{"success": true, "journal_path": "C:/tmp/test.md"}'
        completed.stderr = ""

        with patch(
            "tests.e2e.runner.subprocess.run", return_value=completed
        ) as mock_run:
            runner._test_write_journal({"data": {"title": "x", "content": "y"}}, {})

        env = mock_run.call_args.kwargs.get("env")
        assert env is not None
        assert env["LIFE_INDEX_DATA_DIR"] == str(expected_root)

    def test_cleanup_removes_created_journals_and_test_attachments_under_isolated_root(
        self, tmp_path: Path
    ) -> None:
        from tests.e2e.runner import E2ETestRunner

        runner = E2ETestRunner(project_root=tmp_path)
        journal = runner.test_data_dir / "Journals" / "2026" / "03" / "sample.md"
        attachment = runner.test_data_dir / "attachments" / "2026" / "03" / "sample.png"
        journal.parent.mkdir(parents=True, exist_ok=True)
        attachment.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text("demo", encoding="utf-8")
        attachment.write_text("demo", encoding="utf-8")

        runner.created_files = [journal]
        runner.created_attachments = [attachment]

        runner._cleanup()

        assert not journal.exists()
        assert not attachment.exists()
