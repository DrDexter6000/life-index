"""Test that pyproject.toml version matches branch name."""

import tomllib  # Python 3.11+
from pathlib import Path


def test_pyproject_version_is_1_6_5():
    """pyproject.toml 版本必须为 1.6.5"""
    pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    assert data["project"]["version"] == "1.6.5", (
        f"Expected version '1.6.5', got '{data['project']['version']}'"
    )
