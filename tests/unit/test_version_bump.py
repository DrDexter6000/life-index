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
    """bootstrap-manifest repo_version is a derived release surface."""
    pyproject = REPO_ROOT / "pyproject.toml"
    with pyproject.open("rb") as f:
        project_data = tomllib.load(f)
    manifest = json.loads((REPO_ROOT / "bootstrap-manifest.json").read_text())

    assert manifest["repo_version"] == project_data["project"]["version"]
