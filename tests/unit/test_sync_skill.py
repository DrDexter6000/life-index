from __future__ import annotations

import json
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
    assert (target / "SKILL.md").exists()
