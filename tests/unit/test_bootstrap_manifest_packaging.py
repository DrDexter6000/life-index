"""Packaging contract for bootstrap manifest runtime availability."""

from __future__ import annotations

import importlib
import json
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _root_manifest() -> dict[str, object]:
    return json.loads((REPO_ROOT / "bootstrap-manifest.json").read_text(encoding="utf-8"))


def test_tools_package_contains_bootstrap_manifest_resource() -> None:
    """Wheel installs must carry a manifest inside the importable tools package."""
    tools_package = importlib.import_module("tools")
    package_dirs = [
        Path(raw_path) for raw_path in tools_package.__path__ if Path(raw_path).is_dir()
    ]
    resources = [package_dir / "bootstrap-manifest.json" for package_dir in package_dirs]
    resource = next((candidate for candidate in resources if candidate.is_file()), None)

    assert resource is not None
    packaged = json.loads(resource.read_text(encoding="utf-8"))
    assert packaged == _root_manifest()


def test_read_bootstrap_manifest_falls_back_to_packaged_resource(tmp_path, monkeypatch) -> None:
    """Installed wheels do not have the repo-root manifest path beside tools."""
    import tools.__main__ as cli_main

    monkeypatch.setattr(cli_main, "BOOTSTRAP_MANIFEST_PATH", tmp_path / "missing.json")

    assert cli_main.read_bootstrap_manifest() == _root_manifest()


def test_packaging_config_declares_bootstrap_manifest_data() -> None:
    """Setuptools config must include the package resource in built wheels."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    setuptools_config = pyproject["tool"]["setuptools"]
    package_data = setuptools_config["package-data"]

    assert setuptools_config["include-package-data"] is True
    assert "bootstrap-manifest.json" in package_data["tools"]


def test_manifest_in_includes_bootstrap_manifest_sources() -> None:
    """sdist inputs must include both the root authority file and package copy."""
    manifest_in = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    assert "include bootstrap-manifest.json" in manifest_in
    assert "include tools/bootstrap-manifest.json" in manifest_in
