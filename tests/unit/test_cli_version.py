#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


class TestCliVersion:
    def test_read_bootstrap_manifest_returns_expected_fields(self) -> None:
        from tools.__main__ import read_bootstrap_manifest

        manifest = read_bootstrap_manifest()

        assert manifest["repo_version"] == "1.5.0"
        assert manifest["onboarding_schema_version"]
        assert manifest["requires_checkout_sync"] is True
        assert "required_authority_docs" in manifest

    def test_version_info_exposes_package_and_manifest_versions(self) -> None:
        from tools.__main__ import get_version_info

        payload = get_version_info()

        assert payload["package_version"] == "1.5.0"
        assert payload["bootstrap_manifest"]["repo_version"] == "1.5.0"
        assert payload["bootstrap_manifest"]["requires_checkout_sync"] is True

    def test_version_command_prints_json_payload(self, capsys) -> None:
        from tools import __main__

        __main__.sys.argv = ["life-index", "--version"]
        __main__.main()

        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["package_version"] == "1.5.0"
        assert payload["bootstrap_manifest"]["repo_version"] == "1.5.0"
