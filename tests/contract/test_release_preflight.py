"""Release-candidate guards for the manual PyPI workflow."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = REPO_ROOT / "scripts" / "release_preflight.py"


def _load_preflight_module():
    spec = importlib.util.spec_from_file_location("release_preflight", PREFLIGHT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_release_fixture(tmp_path: Path, *, version: str = "1.5.2") -> Path:
    root = tmp_path / "release-fixture"
    (root / "tools").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "pyproject.toml").write_text(
        "[project]\nname = 'life-index'\nversion = '" + version + "'\n",
        encoding="utf-8",
    )
    manifest = {"repo_version": version}
    (root / "bootstrap-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "tools" / "bootstrap-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "docs" / "VERSIONING.md").write_text(
        "Known PyPI-used versions:\n\n```text\n1.5.0\n```\n",
        encoding="utf-8",
    )
    return root


def test_release_preflight_selects_1_5_2_when_history_allows_and_mocked_pypi_omits_it(
    tmp_path: Path,
) -> None:
    preflight = _load_preflight_module()
    root = _write_release_fixture(tmp_path)

    assert preflight.validate_version_surfaces(root) == "1.5.2"
    assert (
        preflight.validate_release_candidate(
            root,
            fetch_pypi_payload=lambda: {"releases": {}},
        )
        == "1.5.2"
    )


def test_release_preflight_forbids_known_used_1_5_0_even_when_mocked_pypi_omits_it(
    tmp_path: Path,
) -> None:
    preflight = _load_preflight_module()
    root = _write_release_fixture(tmp_path, version="1.5.0")

    with pytest.raises(preflight.ReleasePreflightError, match="known-used"):
        preflight.validate_release_candidate(root, fetch_pypi_payload=lambda: {"releases": {}})


def test_release_preflight_rejects_any_of_the_three_version_surfaces_drifting(
    tmp_path: Path,
) -> None:
    preflight = _load_preflight_module()
    root = _write_release_fixture(tmp_path)
    (root / "tools" / "bootstrap-manifest.json").write_text(
        json.dumps({"repo_version": "1.4.5"}), encoding="utf-8"
    )

    with pytest.raises(preflight.ReleasePreflightError, match="version surfaces disagree"):
        preflight.validate_version_surfaces(root)


def test_release_candidate_1_5_2_is_aligned_and_absent_from_known_used_history() -> None:
    preflight = _load_preflight_module()

    assert preflight.validate_version_surfaces(REPO_ROOT) == "1.5.2"
    known_used = preflight.known_used_versions(REPO_ROOT)
    assert "1.5.0" in known_used
    assert "1.5.1" in known_used
    assert "1.5.2" not in known_used
    assert (
        preflight.validate_release_candidate(
            REPO_ROOT,
            fetch_pypi_payload=lambda: {"releases": {}},
        )
        == "1.5.2"
    )


def test_manual_release_workflow_proves_exact_wheel_before_upload() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "Sync bootstrap-manifest.json version" not in workflow
    assert "json.dump" not in workflow
    assert workflow.index("Validate immutable release version") < workflow.index(
        "- name: Build distribution"
    )
    assert workflow.index("- name: Build distribution") < workflow.index(
        "Install exact wheel with MCP extra"
    )
    assert workflow.index("Install exact wheel with MCP extra") < workflow.index(
        "Run isolated sync-skill and health smoke"
    )
    assert 'metadata.version("mcp") == "1.27.2"' in workflow
    assert "life-index[mcp]" in workflow
    assert "installed CLI/repo version mismatch" in workflow
    assert 'VENV_PYTHON="$(pwd)/$VENV_PYTHON"' in workflow
    assert 'VENV_PYTHON="$(realpath "$VENV_PYTHON")"' not in workflow
    assert "Validate target availability immediately before publish" in workflow
    assert workflow.index(
        "Validate target availability immediately before publish"
    ) < workflow.index("pypa/gh-action-pypi-publish@release/v1")
