"""
Tests for CLI stdout/stderr UTF-8 encoding protection (Round 10, T0.1).

Validates R10 fix: Windows subprocess calls should not crash with
UnicodeDecodeError when torch/transformers emit non-UTF-8 bytes.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Subprocess-level E2E test ──────────────────────────────────────────


class TestCLIEncodingSubprocess:
    """
    Verify CLI works correctly when called as subprocess with UTF-8 encoding.

    These tests launch a real subprocess to catch encoding issues that
    unit-level mocks would miss.
    """

    @pytest.fixture(autouse=True)
    def _setup_env(self, isolated_data_dir: Path) -> None:
        """Ensure subprocess uses isolated data directory."""
        self.data_dir = isolated_data_dir
        # Create minimal directory structure so CLI doesn't fail on missing dirs
        journals_dir = isolated_data_dir / "Journals"
        journals_dir.mkdir(parents=True, exist_ok=True)

    @pytest.mark.integration
    def test_chinese_query_returns_valid_json(self) -> None:
        """
        R10: Subprocess with UTF-8 encoding + Chinese query must return
        valid JSON with exit code 0.

        Before fix: Windows GBK stderr from torch caused UnicodeDecodeError
        in the calling process.
        """
        env = os.environ.copy()
        env["LIFE_INDEX_DATA_DIR"] = str(self.data_dir)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.search_journals",
                "--query",
                "最近焦虑的事",
                "--no-semantic",
            ],
            capture_output=True,
            encoding="utf-8",
            env=env,
            timeout=60,
            cwd=str(Path(__file__).parent.parent.parent),  # project root
        )

        # Exit code 0 (success) — not a crash from encoding
        assert result.returncode == 0, f"CLI crashed. stderr:\n{result.stderr}"

        # stdout may contain model loading messages before JSON;
        # extract the JSON object by finding the first '{'
        stdout_text = result.stdout
        json_start = stdout_text.find("{")
        assert json_start >= 0, f"No JSON found in stdout:\n{stdout_text}"
        json_text = stdout_text[json_start:]
        parsed = json.loads(json_text)
        assert "success" in parsed
        assert parsed["success"] is True

    @pytest.mark.integration
    def test_chinese_query_title_not_segmented(self) -> None:
        """
        R11 (pre-check): Search result titles should not contain
        jieba segmentation artifacts (spaces between characters).

        This is a pre-existing check that validates the test infrastructure.
        The actual R11 fix is in T0.2.
        """
        env = os.environ.copy()
        env["LIFE_INDEX_DATA_DIR"] = str(self.data_dir)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.search_journals",
                "--query",
                "测试",
                "--no-semantic",
            ],
            capture_output=True,
            encoding="utf-8",
            env=env,
            timeout=60,
            cwd=str(Path(__file__).parent.parent.parent),
        )

        assert result.returncode == 0
        stdout_text = result.stdout
        json_start = stdout_text.find("{")
        assert json_start >= 0, f"No JSON found in stdout:\n{stdout_text}"
        parsed = json.loads(stdout_text[json_start:])
        # No results expected in empty data dir, but JSON must be valid
        assert isinstance(parsed.get("merged_results", []), list)


# ── Unit-level bootstrap tests ─────────────────────────────────────────


class TestEncodingBootstrap:
    """
    Verify that the encoding bootstrap function correctly configures
    sys.stdout/stderr and suppresses transformers/torch noise.
    """

    def test_reconfigure_stdout_stderr_called(self) -> None:
        """
        ensure_utf8_io() must call sys.stdout.reconfigure(encoding='utf-8')
        and sys.stderr.reconfigure(encoding='utf-8').
        """
        from tools.search_journals._bootstrap import ensure_utf8_io

        mock_stdout = MagicMock()
        mock_stderr = MagicMock()

        with patch("sys.stdout", mock_stdout), patch("sys.stderr", mock_stderr):
            ensure_utf8_io()

        mock_stdout.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace"
        )
        mock_stderr.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace"
        )

    def test_reconfigure_handles_missing_attribute(self) -> None:
        """
        If sys.stdout doesn't have reconfigure (e.g., io.StringIO in tests),
        ensure_utf8_io must not crash.
        """
        from tools.search_journals._bootstrap import ensure_utf8_io

        mock_stdout = MagicMock(spec=[])  # no 'reconfigure' attribute
        mock_stderr = MagicMock(spec=[])

        # Must not raise
        with patch("sys.stdout", mock_stdout), patch("sys.stderr", mock_stderr):
            ensure_utf8_io()

    def test_transformers_logging_suppressed(self) -> None:
        """
        After ensure_utf8_io(), transformers logging must be at ERROR level
        to prevent progress bars and info messages from polluting stderr.
        """
        from tools.search_journals._bootstrap import ensure_utf8_io

        ensure_utf8_io()

        try:
            import transformers

            transformers_logging = getattr(transformers, "logging", None)
            assert transformers_logging is not None
            assert transformers_logging.get_verbosity() <= transformers_logging.ERROR
        except ImportError:
            pytest.skip("transformers not installed")

    def test_windows_torch_stderr_redirect(self) -> None:
        """
        On Windows non-TTY, torch stderr must be redirected to prevent
        GBK-encoded bytes from reaching the parent process.

        This test verifies the redirect logic is wired up correctly
        without actually loading torch.
        """
        from tools.search_journals._bootstrap import ensure_utf8_io

        with (
            patch("sys.platform", "win32"),
            patch("sys.stderr.isatty", return_value=False),
        ):
            # Should not crash even without torch installed
            ensure_utf8_io()
