#!/usr/bin/env python3

from __future__ import annotations

import json
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def read_pyproject_version() -> str:
    with (REPO_ROOT / "pyproject.toml").open("rb") as f:
        data = tomllib.load(f)
    return str(data["project"]["version"])


class TestCliVersion:
    def test_read_bootstrap_manifest_returns_expected_fields(self) -> None:
        from tools.__main__ import read_bootstrap_manifest

        manifest = read_bootstrap_manifest()
        expected_version = read_pyproject_version()

        assert manifest["repo_version"] == expected_version
        assert manifest["onboarding_schema_version"]
        assert manifest["requires_checkout_sync"] is True
        assert "required_authority_docs" in manifest

    def test_version_info_exposes_package_and_manifest_versions(self) -> None:
        from tools.__main__ import get_version_info

        payload = get_version_info()
        expected_version = read_pyproject_version()

        assert payload["package_version"] == expected_version
        assert payload["bootstrap_manifest"]["repo_version"] == expected_version
        assert payload["bootstrap_manifest"]["requires_checkout_sync"] is True

    def test_version_command_prints_json_payload(self, capsys) -> None:
        from tools import __main__

        __main__.sys.argv = ["life-index", "--version"]
        __main__.main()

        out = capsys.readouterr().out
        payload = json.loads(out)
        expected_version = read_pyproject_version()
        assert payload["package_version"] == expected_version
        assert payload["bootstrap_manifest"]["repo_version"] == expected_version
