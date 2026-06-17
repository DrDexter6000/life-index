from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _base_env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env.pop("LIFE_INDEX_DATA_DIR", None)
    env.pop("LIFE_INDEX_VALIDATION_MODE", None)
    return env


def _run_version(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools", "version"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )


def test_validation_mode_rejects_missing_data_dir(tmp_path: Path) -> None:
    env = _base_env(tmp_path)
    default_config = Path(env["HOME"]) / "Documents" / "Life-Index" / ".life-index"
    default_config.mkdir(parents=True)
    (default_config / "config.yaml").write_text("path_mappings: [", encoding="utf-8")
    env["LIFE_INDEX_VALIDATION_MODE"] = "1"

    result = _run_version(env)

    assert result.returncode != 0
    assert "LIFE_INDEX_VALIDATION_MODE=1" in result.stderr
    assert "LIFE_INDEX_DATA_DIR" in result.stderr
    assert "isolated sandbox" in result.stderr


def test_validation_mode_rejects_default_data_dir_even_when_explicit(tmp_path: Path) -> None:
    env = _base_env(tmp_path)
    default_data_dir = Path(env["HOME"]) / "Documents" / "Life-Index"
    env["LIFE_INDEX_VALIDATION_MODE"] = "1"
    env["LIFE_INDEX_DATA_DIR"] = str(default_data_dir)

    result = _run_version(env)

    assert result.returncode != 0
    assert "default user data directory" in result.stderr
    assert str(default_data_dir) in result.stderr


def test_validation_mode_allows_explicit_sandbox_data_dir(tmp_path: Path) -> None:
    env = _base_env(tmp_path)
    env["LIFE_INDEX_VALIDATION_MODE"] = "1"
    env["LIFE_INDEX_DATA_DIR"] = str(tmp_path / "sandbox" / "Life-Index")

    result = _run_version(env)

    assert result.returncode == 0
    assert result.stderr == ""
    assert '"package_version"' in result.stdout


def test_unset_validation_mode_allows_default_data_dir(tmp_path: Path) -> None:
    env = _base_env(tmp_path)

    result = _run_version(env)

    assert result.returncode == 0
    assert result.stderr == ""
    assert '"package_version"' in result.stdout
