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
        """Ensure subprocess uses isolated data directory with fresh manifest."""
        self.data_dir = isolated_data_dir
        journals_dir = isolated_data_dir / "Journals"
        journals_dir.mkdir(parents=True, exist_ok=True)

        index_dir = isolated_data_dir / ".index"
        index_dir.mkdir(parents=True, exist_ok=True)
        from tools.lib.index_manifest import IndexManifest, write_manifest

        write_manifest(
            IndexManifest(
                fts_count=0,
                vector_count=0,
                file_count=0,
                fts_checksum="",
                vector_checksum="",
                build_timestamp="2026-01-01T00:00:00",
                build_version="2.0.0",
                partial=False,
            ),
            index_dir,
        )

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

        parsed = json.loads(result.stdout)
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
        parsed = json.loads(result.stdout)
        # No results expected in empty data dir, but JSON must be valid
        assert isinstance(parsed.get("merged_results", []), list)


# ── No ML imports at startup (subprocess, stub packages) ───────────────


class TestNoMLImportsAtStartup:
    """
    Starting the search CLI (or calling ensure_utf8_io() directly) must
    never import transformers / torch / sentence_transformers.

    The retired semantic-search guards used to import them unconditionally;
    on machines where they are installed this costs seconds of startup and
    hundreds of MB of RSS per search invocation. Noise-suppression guards
    may only act when an embedding host imported the library first.
    """

    STUB_PACKAGES = ("transformers", "torch", "sentence_transformers")

    def _make_stub_env(self, tmp_path: Path) -> tuple[dict[str, str], Path]:
        """Build PYTHONPATH stub packages that write a marker when imported.

        The stubs shadow any real installation, so a marker file proves the
        child process performed the import (not merely that the library is
        installed).
        """
        stub_dir = tmp_path / "ml_stubs"
        marker_dir = tmp_path / "ml_import_markers"
        marker_dir.mkdir(parents=True)
        for name in self.STUB_PACKAGES:
            pkg_dir = stub_dir / name
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "__init__.py").write_text(
                "import os\n"
                "from pathlib import Path\n"
                f"Path(os.environ['LI_TEST_ML_MARKER_DIR'], {name!r}).touch()\n",
                encoding="utf-8",
            )
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [str(stub_dir)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )
        env["LI_TEST_ML_MARKER_DIR"] = str(marker_dir)
        # Belt-and-braces: the child must never touch the real data dir even
        # if a future change makes --help reach data code paths.
        env["LIFE_INDEX_DATA_DIR"] = str(tmp_path / "isolated_data")
        return env, marker_dir

    def _assert_no_ml_imports(self, args: list[str], tmp_path: Path) -> None:
        env, marker_dir = self._make_stub_env(tmp_path)
        # capture_output pipes stderr (not a TTY) — exactly the condition that
        # used to trigger the Windows torch import in _bootstrap.
        result = subprocess.run(
            [sys.executable, *args],
            capture_output=True,
            env=env,
            timeout=120,
            cwd=str(Path(__file__).parent.parent.parent),  # project root
        )
        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
        imported = sorted(p.name for p in marker_dir.iterdir())
        assert imported == [], f"startup imported ML libraries: {imported}"

    def test_ensure_utf8_io_does_not_import_ml_libraries(self, tmp_path: Path) -> None:
        """Direct ensure_utf8_io() call must not import any ML library."""
        self._assert_no_ml_imports(
            [
                "-c",
                "from tools.search_journals._bootstrap import ensure_utf8_io; " "ensure_utf8_io()",
            ],
            tmp_path,
        )

    def test_cli_help_does_not_import_ml_libraries(self, tmp_path: Path) -> None:
        """`python -m tools.search_journals --help` must not import any ML library."""
        self._assert_no_ml_imports(["-m", "tools.search_journals", "--help"], tmp_path)


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

        mock_stdout.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
        mock_stderr.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")

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

    def test_transformers_logging_suppressed_when_already_imported(self) -> None:
        """
        When an embedding host has ALREADY imported transformers,
        ensure_utf8_io() must set its logging to ERROR level to prevent
        progress bars and info messages from polluting stderr.
        """
        try:
            import transformers
        except ImportError:
            pytest.skip("transformers not installed")

        from tools.search_journals._bootstrap import ensure_utf8_io

        transformers_logging = getattr(transformers, "logging", None)
        if transformers_logging is None:
            pytest.skip("transformers installed without logging module")

        original_verbosity = transformers_logging.get_verbosity()
        try:
            # Start from a verbosity ABOVE ERROR so the assertion below can
            # only pass if ensure_utf8_io() actually suppressed it.
            transformers_logging.set_verbosity(transformers_logging.INFO)
            ensure_utf8_io()
            assert transformers_logging.get_verbosity() <= transformers_logging.ERROR
        finally:
            transformers_logging.set_verbosity(original_verbosity)

    def test_windows_torch_stderr_redirect(self) -> None:
        """
        On Windows non-TTY with torch ALREADY imported by an embedding
        host, torch stderr must be redirected to prevent GBK-encoded
        bytes from reaching the parent process. Without torch imported,
        stderr must be left untouched (no import, no swap).
        """
        import types

        from tools.search_journals._bootstrap import ensure_utf8_io

        mock_stderr = MagicMock()
        mock_stderr.isatty.return_value = False

        # Without torch in sys.modules: no redirect, stderr untouched.
        with (
            patch("sys.platform", "win32"),
            patch("sys.stderr", mock_stderr),
            patch.dict(sys.modules),
        ):
            sys.modules.pop("torch", None)
            ensure_utf8_io()
            assert sys.stderr is mock_stderr

        # With a fake torch already imported (has _C like a real install):
        # the redirect swaps stderr away from the mock.
        fake_torch = types.ModuleType("torch")
        fake_torch._C = types.SimpleNamespace()  # type: ignore[attr-defined]
        with (
            patch("sys.platform", "win32"),
            patch("sys.stderr", mock_stderr),
            patch.dict(sys.modules, {"torch": fake_torch}),
        ):
            ensure_utf8_io()
            assert sys.stderr is not mock_stderr
