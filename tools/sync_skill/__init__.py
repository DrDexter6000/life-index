"""Synchronize Life Index skill artifacts into a host agent skill directory."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import yaml

SYNC_SKILL_SCHEMA_VERSION = "m35.sync_skill.v0"
HOST_SKILL_DIR_ENV = "LIFE_INDEX_HOST_SKILL_DIR"


def _diagnostic(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def find_host_skill_dir(
    explicit_dir: str | Path | None = None,
) -> tuple[Path | None, list[dict[str, str]]]:
    """Find an existing host skill directory without creating one."""
    candidates: list[Path] = []
    diagnostics: list[dict[str, str]] = []

    if explicit_dir:
        candidate = Path(explicit_dir).expanduser()
        if candidate.is_dir():
            return candidate, diagnostics
        return None, [
            _diagnostic(
                "HOST_SKILL_DIR_NOT_FOUND",
                f"Host skill directory does not exist: {candidate}",
            )
        ]

    env_dir = os.environ.get(HOST_SKILL_DIR_ENV)
    if env_dir:
        candidates.append(Path(env_dir).expanduser())

    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        candidates.append(Path(codex_home).expanduser() / "skills" / "life-index")

    agents_home = os.environ.get("AGENTS_HOME")
    if agents_home:
        candidates.append(Path(agents_home).expanduser() / "skills" / "life-index")

    home = Path.home()
    candidates.extend(
        [
            home / ".codex" / "skills" / "life-index",
            home / ".agents" / "skills" / "life-index",
        ]
    )

    for candidate in candidates:
        if candidate.is_dir():
            return candidate, diagnostics

    return None, [
        _diagnostic(
            "HOST_SKILL_DIR_NOT_FOUND",
            "No existing host skill directory was found; skill artifact sync was skipped.",
        )
    ]


def _split_frontmatter(text: str) -> tuple[list[str], list[str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], lines
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index], lines[index + 1 :]
    return [], lines


def _triggers_from_text(text: str) -> list[str]:
    frontmatter, _body = _split_frontmatter(text)
    if not frontmatter:
        return []
    try:
        parsed = yaml.safe_load("\n".join(frontmatter)) or {}
    except yaml.YAMLError:
        return []
    raw_triggers = parsed.get("triggers")
    if not isinstance(raw_triggers, list):
        return []
    return [item for item in raw_triggers if isinstance(item, str)]


def _replace_triggers(text: str, triggers: list[str]) -> str:
    frontmatter, body = _split_frontmatter(text)
    if not frontmatter:
        return text

    trigger_start: int | None = None
    trigger_end: int | None = None
    for index, line in enumerate(frontmatter):
        if line == "triggers:":
            trigger_start = index
            trigger_end = index + 1
            while trigger_end < len(frontmatter):
                next_line = frontmatter[trigger_end]
                if next_line and not next_line.startswith((" ", "\t")):
                    break
                trigger_end += 1
            break

    trigger_block = ["triggers:"] + [
        f"  - {json.dumps(trigger, ensure_ascii=False)}" for trigger in triggers
    ]
    if trigger_start is None or trigger_end is None:
        frontmatter.extend(trigger_block)
    else:
        frontmatter = frontmatter[:trigger_start] + trigger_block + frontmatter[trigger_end:]

    rendered = ["---", *frontmatter, "---", *body]
    return "\n".join(rendered) + "\n"


def _merge_skill_text(source_text: str, existing_target_text: str | None) -> str:
    source_triggers = _triggers_from_text(source_text)
    existing_triggers = _triggers_from_text(existing_target_text or "")
    merged_triggers = list(source_triggers)
    for trigger in existing_triggers:
        if trigger not in merged_triggers:
            merged_triggers.append(trigger)
    if not merged_triggers:
        return source_text
    return _replace_triggers(source_text, merged_triggers)


def _copy_references(source_root: Path, target_dir: Path) -> list[str]:
    source_references = source_root / "references"
    if not source_references.is_dir():
        return []

    copied: list[str] = []
    target_references = target_dir / "references"
    for source_path in sorted(path for path in source_references.rglob("*") if path.is_file()):
        relative_path = source_path.relative_to(source_references)
        target_path = target_references / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied.append(str(Path("references") / relative_path).replace("\\", "/"))
    return copied


def sync_skill_artifacts(source_root: Path, target_dir: Path | None) -> dict[str, Any]:
    """Copy SKILL.md and references into an existing host skill directory."""
    source_root = source_root.resolve()
    diagnostics: list[dict[str, str]] = []

    if target_dir is None:
        diagnostics.append(
            _diagnostic(
                "HOST_SKILL_DIR_NOT_FOUND",
                "No existing host skill directory was found; skill artifact sync was skipped.",
            )
        )
        return {
            "success": True,
            "schema_version": SYNC_SKILL_SCHEMA_VERSION,
            "command": "sync-skill",
            "data": {
                "status": "skipped",
                "target_dir": None,
                "copied": [],
                "diagnostics": diagnostics,
            },
        }

    target_dir = target_dir.expanduser().resolve()
    if not target_dir.is_dir():
        diagnostics.append(
            _diagnostic(
                "HOST_SKILL_DIR_NOT_FOUND",
                f"Host skill directory does not exist: {target_dir}",
            )
        )
        return {
            "success": True,
            "schema_version": SYNC_SKILL_SCHEMA_VERSION,
            "command": "sync-skill",
            "data": {
                "status": "skipped",
                "target_dir": None,
                "copied": [],
                "diagnostics": diagnostics,
            },
        }

    source_skill = source_root / "SKILL.md"
    if not source_skill.is_file():
        return {
            "success": False,
            "schema_version": SYNC_SKILL_SCHEMA_VERSION,
            "command": "sync-skill",
            "data": {
                "status": "failed",
                "target_dir": str(target_dir),
                "copied": [],
                "diagnostics": [
                    _diagnostic("SOURCE_SKILL_NOT_FOUND", f"Missing source skill: {source_skill}")
                ],
            },
        }

    target_skill = target_dir / "SKILL.md"
    source_text = source_skill.read_text(encoding="utf-8")
    existing_text = target_skill.read_text(encoding="utf-8") if target_skill.is_file() else None
    target_skill.write_text(_merge_skill_text(source_text, existing_text), encoding="utf-8")

    copied = ["SKILL.md", *_copy_references(source_root, target_dir)]
    return {
        "success": True,
        "schema_version": SYNC_SKILL_SCHEMA_VERSION,
        "command": "sync-skill",
        "data": {
            "status": "synced",
            "target_dir": str(target_dir),
            "copied": copied,
            "diagnostics": diagnostics,
        },
    }
