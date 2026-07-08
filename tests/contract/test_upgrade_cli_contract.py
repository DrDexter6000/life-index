from __future__ import annotations

import json
import subprocess
import sys


def test_upgrade_help_is_text_and_does_not_emit_json() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools", "upgrade", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
    assert "upgrade" in result.stdout
    try:
        json.loads(result.stdout)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("upgrade --help unexpectedly emitted JSON")


def test_upgrade_plan_json_stdout_is_parseable(monkeypatch, capsys) -> None:
    from tools.upgrade import __main__ as upgrade_cli
    from tools.upgrade.core import InstallContext, ReleaseInfo

    monkeypatch.setattr(
        upgrade_cli,
        "detect_install_context",
        lambda: InstallContext(
            package_version="1.4.4",
            manifest_version="1.4.4",
            install_type="package",
            repo_path=None,
        ),
    )
    monkeypatch.setattr(
        upgrade_cli,
        "PyPIReleaseProvider",
        lambda: type("Provider", (), {"fetch": lambda self: [ReleaseInfo(version="1.4.4")]})(),
    )

    exit_code = upgrade_cli.main(["--plan", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["command"] == "upgrade"
    assert payload["mode"] == "plan"
