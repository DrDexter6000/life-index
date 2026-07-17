from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


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
    from tools.upgrade import core
    from tools.upgrade.core import InstallContext, ReleaseInfo

    monkeypatch.setattr(
        core,
        "inventory_life_index_distributions",
        lambda: {
            "project": "life-index",
            "state": "single",
            "canonical_count": 1,
            "distributions": [],
        },
    )

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


def test_upgrade_cli_plan_conflict_emits_only_the_isolated_recovery_action(
    monkeypatch, capsys
) -> None:
    from tools.upgrade import __main__ as upgrade_cli
    from tools.upgrade import core
    from tools.upgrade.core import InstallContext

    inventory = {
        "project": "life-index",
        "state": "conflict",
        "canonical_count": 2,
        "distributions": [],
    }
    monkeypatch.setattr(
        upgrade_cli,
        "detect_install_context",
        lambda: InstallContext(
            package_version="1.5.1",
            manifest_version="1.5.1",
            install_type="editable",
            repo_path=REPO_ROOT,
        ),
    )
    monkeypatch.setattr(core, "inventory_life_index_distributions", lambda: inventory)
    monkeypatch.setattr(
        upgrade_cli,
        "PyPIReleaseProvider",
        lambda: type(
            "Provider",
            (),
            {"fetch": lambda self: (_ for _ in ()).throw(AssertionError("must not fetch"))},
        )(),
    )

    exit_code = upgrade_cli.main(["--plan", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert [action["id"] for action in payload["data"]["actions"]] == [
        "recover_install_distribution_conflict"
    ]
    action = payload["data"]["recommended_next_step"]
    assert action["safe_to_run"] is False
    assert action["requires_human"] is True
    assert " -I " in action["command"]


def test_mixed_install_recovery_contract_is_documented() -> None:
    """Public operator authority must point to the one isolated recovery path."""
    api = (REPO_ROOT / "docs" / "API.md").read_text(encoding="utf-8")
    onboarding = (REPO_ROOT / "AGENT_ONBOARDING.md").read_text(encoding="utf-8")

    for text in (api, onboarding):
        assert "INSTALL_DISTRIBUTION_CONFLICT" in text
        assert "install_integrity.py" in text
        assert "--source-root TRUSTED_CHECKOUT" in text
        assert " -I " in text
    assert "UPGRADE_INSTALL_DISTRIBUTION_CONFLICT" in api
    assert "INSTALL_RECOVERY_ORPHAN_SHADOW" in api
    assert "INSTALL_RECOVERY_BUILD_PREFLIGHT_FAILED" in api
    assert "INSTALL_RECOVERY_OWNERSHIP_CONFLICT" in api
    assert "m37.install_integrity.v0" in api
    assert '"recovery_strategy": "ask_user|retry"' in api
    assert "standard virtual environment" in api
    assert "standard virtual environment" in onboarding
    assert "isolated_no_site_explicit_target" in api
    assert "ownership conflict" in onboarding
    assert "tools/__init__.py" in api
    assert "tools.py" in api
    assert "tools/__init__.py" in onboarding
    assert "tools.py" in onboarding
    for text in (api, onboarding):
        assert "SOURCE_SUFFIXES" in text
        assert "BYTECODE_SUFFIXES" in text
        assert "EXTENSION_SUFFIXES" in text
