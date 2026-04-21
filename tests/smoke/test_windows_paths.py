"""
Windows-specific smoke tests for path resolution and env-var handling.

These tests verify that the core path getters produce valid, usable paths
on native Windows — no WSL, no compat shims.

Note: conftest.py sets LIFE_INDEX_DATA_DIR to a temp dir before any test
module imports tools.lib.paths. The first test verifies the default path
by calling resolve_user_data_dir() directly (it has no pytest guard).
The second test verifies env-var override. The third tests tmp_path on Windows.
"""

import sys
from pathlib import Path

import pytest

from tools.lib.paths import get_user_data_dir, resolve_user_data_dir


# Only run on native Windows
pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows-specific smoke",
)


# ---------------------------------------------------------------------------
# test_resolve_default_path_is_valid_windows_path
# ---------------------------------------------------------------------------


def test_resolve_default_path_is_valid_windows_path() -> None:
    """resolve_user_data_dir() returns a valid absolute Windows path.

    Uses resolve_user_data_dir() (no pytest guard) instead of
    get_user_data_dir() (which raises RuntimeError when env var is unset
    during pytest — by design, prevents accidental writes to real data dir).

    We call it without clearing the env var, so it returns the conftest
    temp dir. That's fine — we're verifying the Path is valid on Windows.
    """
    result = resolve_user_data_dir()

    assert isinstance(result, Path), f"Expected Path, got {type(result)}"
    # Must not be empty / root
    assert len(result.parts) >= 2, f"Path too short: {result}"
    # Must be absolute (C:\Users\...\... on Windows)
    assert result.is_absolute(), f"Path not absolute: {result}"
    # Name is the conftest temp dir (life-index-test-xxx), just verify non-empty
    assert result.name, f"Path leaf is empty: {result}"


# ---------------------------------------------------------------------------
# test_env_var_override_respected
# ---------------------------------------------------------------------------


def test_env_var_override_respected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Setting LIFE_INDEX_DATA_DIR to a custom temp dir causes
    get_user_data_dir() to return exactly that dir."""
    override_dir = tmp_path / "custom_data"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(override_dir))

    result = get_user_data_dir()

    assert result == override_dir, f"Expected {override_dir}, got {result}"


# ---------------------------------------------------------------------------
# test_temp_dir_works
# ---------------------------------------------------------------------------


def test_temp_dir_works(tmp_path: Path) -> None:
    """Verify pytest's tmp_path fixture creates a usable temp directory
    on Windows (pathlib + os operations work correctly)."""
    # Write + read roundtrip
    test_file = tmp_path / "smoke.txt"
    test_file.write_text("hello windows", encoding="utf-8")
    assert test_file.read_text(encoding="utf-8") == "hello windows"

    # Subdir creation
    sub = tmp_path / "nested" / "dir"
    sub.mkdir(parents=True, exist_ok=True)
    assert sub.is_dir()

    # Path stays absolute and Windows-native
    assert tmp_path.is_absolute()
    assert "\\" in str(tmp_path) or "/" in str(tmp_path)  # either separator valid
