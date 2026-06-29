from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _write_source(root: Path) -> None:
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text(
        """---
name: life-index
triggers:
  - "/life-index"
  - "记日志"
---

# Current Skill
""",
        encoding="utf-8",
    )
    (root / "references" / "WEATHER_FLOW.md").write_text("# Weather\n", encoding="utf-8")


def test_sync_skill_copies_skill_and_references_preserving_custom_triggers(tmp_path: Path) -> None:
    from tools.sync_skill import sync_skill_artifacts

    source_root = tmp_path / "checkout"
    target = tmp_path / "host" / "skills" / "life-index"
    source_root.mkdir()
    target.mkdir(parents=True)
    _write_source(source_root)
    (target / "SKILL.md").write_text(
        """---
name: life-index
triggers:
  - "/life-index"
  - "/life-index custom"
---

# Old Skill
""",
        encoding="utf-8",
    )

    payload = sync_skill_artifacts(source_root=source_root, target_dir=target)

    assert payload["success"] is True
    assert payload["data"]["status"] == "synced"
    assert payload["data"]["target_dir"] == str(target)
    assert payload["data"]["copied"] == ["SKILL.md", "references/WEATHER_FLOW.md"]
    synced_skill = (target / "SKILL.md").read_text(encoding="utf-8")
    assert "# Current Skill" in synced_skill
    assert '  - "/life-index custom"' in synced_skill
    assert (target / "references" / "WEATHER_FLOW.md").read_text(encoding="utf-8") == "# Weather\n"


def test_sync_skill_gracefully_skips_when_no_host_dir(tmp_path: Path) -> None:
    from tools.sync_skill import sync_skill_artifacts

    source_root = tmp_path / "checkout"
    source_root.mkdir()
    _write_source(source_root)

    payload = sync_skill_artifacts(source_root=source_root, target_dir=None)

    assert payload["success"] is True
    assert payload["data"]["status"] == "skipped"
    assert payload["data"]["target_dir"] is None
    assert payload["data"]["copied"] == []
    assert payload["data"]["diagnostics"][0]["code"] == "HOST_SKILL_DIR_NOT_FOUND"


def test_sync_skill_without_install_does_not_create_missing_target(tmp_path: Path) -> None:
    from tools.sync_skill import sync_skill_artifacts

    source_root = tmp_path / "checkout"
    target = tmp_path / "host" / "skills" / "life-index"
    source_root.mkdir()
    _write_source(source_root)

    payload = sync_skill_artifacts(source_root=source_root, target_dir=target)

    assert payload["success"] is True
    assert payload["data"]["status"] == "skipped"
    assert payload["data"]["delivered"] is False
    assert not target.exists()


def test_sync_skill_install_creates_host_home_target(tmp_path: Path) -> None:
    from tools.sync_skill import install_target_from_host_home, sync_skill_artifacts

    source_root = tmp_path / "checkout"
    host_home = tmp_path / ".hermes"
    target = install_target_from_host_home(host_home)
    source_root.mkdir()
    _write_source(source_root)

    payload = sync_skill_artifacts(source_root=source_root, target_dir=target, install=True)

    assert payload["success"] is True
    assert payload["data"]["status"] == "installed"
    assert payload["data"]["delivered"] is True
    assert payload["data"]["target_dir"] == str(target.resolve())
    assert payload["data"]["copied"] == ["SKILL.md", "references/WEATHER_FLOW.md"]
    assert (target / "SKILL.md").exists()
    assert (target / "references" / "WEATHER_FLOW.md").exists()


def test_sync_skill_cli_uses_host_skill_dir_env(tmp_path: Path, monkeypatch) -> None:
    source_root = tmp_path / "checkout"
    target = tmp_path / "host" / "skills" / "life-index"
    source_root.mkdir()
    target.mkdir(parents=True)
    _write_source(source_root)
    monkeypatch.setenv("LIFE_INDEX_HOST_SKILL_DIR", str(target))

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.sync_skill",
            "--source-root",
            str(source_root),
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["command"] == "sync-skill"
    assert payload["data"]["status"] == "synced"
    assert payload["data"]["delivered"] is True
    assert (target / "SKILL.md").exists()


def test_sync_skill_cli_install_host_home(tmp_path: Path) -> None:
    source_root = tmp_path / "checkout"
    host_home = tmp_path / ".codex"
    target = host_home / "skills" / "life-index"
    source_root.mkdir()
    _write_source(source_root)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools",
            "sync-skill",
            "--source-root",
            str(source_root),
            "--install",
            "--host-home",
            str(host_home),
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["command"] == "sync-skill"
    assert payload["data"]["status"] == "installed"
    assert payload["data"]["delivered"] is True
    assert payload["data"]["target_dir"] == str(target.resolve())
    assert (target / "SKILL.md").exists()


def test_find_host_skill_dir_detects_nested_hermes_skill_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import tools.sync_skill as sync_skill

    target = tmp_path / ".hermes" / "skills" / "productivity" / "life-index"
    target.mkdir(parents=True)
    monkeypatch.setattr(sync_skill.Path, "home", lambda: tmp_path)
    for name in (
        "LIFE_INDEX_HOST_SKILL_DIR",
        "CODEX_HOME",
        "AGENTS_HOME",
        "HERMES_HOME",
        "CLAUDE_HOME",
    ):
        monkeypatch.delenv(name, raising=False)

    found, diagnostics = sync_skill.find_host_skill_dir()

    assert found == target
    assert diagnostics == []


def test_find_host_skill_dir_reports_ambiguous_nested_matches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import tools.sync_skill as sync_skill

    first = tmp_path / ".hermes" / "skills" / "productivity" / "life-index"
    second = tmp_path / ".claude" / "skills" / "journaling" / "life-index"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    monkeypatch.setattr(sync_skill.Path, "home", lambda: tmp_path)
    for name in (
        "LIFE_INDEX_HOST_SKILL_DIR",
        "CODEX_HOME",
        "AGENTS_HOME",
        "HERMES_HOME",
        "CLAUDE_HOME",
    ):
        monkeypatch.delenv(name, raising=False)

    found, diagnostics = sync_skill.find_host_skill_dir()

    assert found is None
    assert diagnostics[0]["code"] == "HOST_SKILL_DIR_AMBIGUOUS"
    assert str(first) in diagnostics[0]["message"]
    assert str(second) in diagnostics[0]["message"]


def test_sync_skill_cli_loudly_reports_undelivered_when_no_host_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_root = tmp_path / "checkout"
    source_root.mkdir()
    _write_source(source_root)
    env = os.environ.copy()
    for name in (
        "LIFE_INDEX_HOST_SKILL_DIR",
        "CODEX_HOME",
        "AGENTS_HOME",
        "HERMES_HOME",
        "CLAUDE_HOME",
    ):
        env.pop(name, None)
    env["HOME"] = str(tmp_path)
    env["USERPROFILE"] = str(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.sync_skill",
            "--source-root",
            str(source_root),
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["data"]["status"] == "skipped"
    assert payload["data"]["delivered"] is False
    assert payload["data"]["diagnostics"][0]["code"] == "HOST_SKILL_DIR_NOT_FOUND"
