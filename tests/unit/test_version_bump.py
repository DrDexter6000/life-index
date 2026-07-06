"""Tests for release version metadata alignment."""

import json
import re
import tomllib  # Python 3.11+
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_version_is_semver():
    """pyproject.toml must expose a SemVer package version."""
    pyproject = REPO_ROOT / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    version = data["project"]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version


def test_pyproject_and_bootstrap_versions_are_aligned():
    """All public release version surfaces must agree."""
    pyproject = REPO_ROOT / "pyproject.toml"
    with pyproject.open("rb") as f:
        project_data = tomllib.load(f)
    root_manifest = json.loads((REPO_ROOT / "bootstrap-manifest.json").read_text(encoding="utf-8"))
    packaged_manifest = json.loads(
        (REPO_ROOT / "tools" / "bootstrap-manifest.json").read_text(encoding="utf-8")
    )

    expected = project_data["project"]["version"]
    assert root_manifest["repo_version"] == expected
    assert packaged_manifest["repo_version"] == expected
    assert packaged_manifest == root_manifest
