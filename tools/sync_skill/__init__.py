"""Synchronize Life Index skill artifacts into a host agent skill directory."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

SYNC_SKILL_SCHEMA_VERSION = "m35.sync_skill.v0"
HOST_SKILL_DIR_ENV = "LIFE_INDEX_HOST_SKILL_DIR"
HOST_HOME_ENVS = ("CODEX_HOME", "AGENTS_HOME", "HERMES_HOME", "CLAUDE_HOME")
DEFAULT_HOST_HOME_DIRS = (".codex", ".agents", ".hermes", ".claude")


def _diagnostic(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _skill_dir_candidates_from_home(home: Path) -> list[Path]:
    skills_dir = home.expanduser() / "skills"
    candidates = [skills_dir / "life-index"]
    candidates.extend(sorted(skills_dir.glob("*/life-index")))
    return candidates


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    deduped: list[Path] = []
    for path in paths:
        key = str(path.expanduser())
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


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
        candidate = Path(env_dir).expanduser()
        if candidate.is_dir():
            return candidate, diagnostics
        return None, [
            _diagnostic(
                "HOST_SKILL_DIR_NOT_FOUND",
                f"Host skill directory does not exist: {candidate}",
            )
        ]

    for env_name in HOST_HOME_ENVS:
        host_home = os.environ.get(env_name)
        if host_home:
            candidates.extend(_skill_dir_candidates_from_home(Path(host_home)))

    home = Path.home()
    for dirname in DEFAULT_HOST_HOME_DIRS:
        candidates.extend(_skill_dir_candidates_from_home(home / dirname))

    candidates = _dedupe_paths(candidates)
    matches = [candidate for candidate in candidates if candidate.is_dir()]
    if len(matches) == 1:
        return matches[0], diagnostics
    if len(matches) > 1:
        formatted = "; ".join(str(path) for path in matches)
        return None, [
            _diagnostic(
                "HOST_SKILL_DIR_AMBIGUOUS",
                (
                    "Multiple existing host skill directories were found; "
                    f"pass --host-skill-dir explicitly. Matches: {formatted}"
                ),
            )
        ]

    checked = "; ".join(str(path) for path in candidates)
    return None, [
        _diagnostic(
            "HOST_SKILL_DIR_NOT_FOUND",
            (
                "No existing host skill directory was found; skill artifact sync was "
                f"not delivered. Checked: {checked}"
            ),
        )
    ]


def install_target_from_host_home(host_home: str | Path) -> Path:
    """Resolve the canonical Life Index skill directory under a host home."""
    return Path(host_home).expanduser() / "skills" / "life-index"


def _default_host_homes() -> list[Path]:
    homes: list[Path] = []
    for env_name in HOST_HOME_ENVS:
        host_home = os.environ.get(env_name)
        if host_home:
            homes.append(Path(host_home))

    home = Path.home()
    homes.extend(home / dirname for dirname in DEFAULT_HOST_HOME_DIRS)
    return _dedupe_paths(homes)


def _managed_skill_dir_reason(path: Path, host_home: Path) -> str | None:
    """Return None when path is a managed LI skill dir under host_home."""
    try:
        resolved_home = host_home.expanduser().resolve()
        resolved_path = path.expanduser().resolve()
        relative_parts = resolved_path.relative_to(resolved_home).parts
    except ValueError:
        return "outside_host_home"

    if len(relative_parts) == 2 and relative_parts == ("skills", "life-index"):
        return None
    if (
        len(relative_parts) == 3
        and relative_parts[0] == "skills"
        and relative_parts[2] == "life-index"
    ):
        return None
    return "unmanaged_path"


def list_host_skill_dirs(
    host_homes: Sequence[str | Path] | None = None,
) -> dict[str, Any]:
    """List existing managed Life Index host skill directories without mutation."""
    homes = [Path(home) for home in host_homes] if host_homes is not None else _default_host_homes()
    discovered: list[str] = []
    skipped: list[dict[str, str]] = []

    for host_home in _dedupe_paths(homes):
        for candidate in _dedupe_paths(_skill_dir_candidates_from_home(host_home)):
            if not candidate.exists():
                continue
            reason = _managed_skill_dir_reason(candidate, host_home)
            resolved = str(candidate.expanduser().resolve())
            if reason is not None:
                skipped.append({"path": resolved, "reason": reason})
                continue
            if candidate.is_symlink():
                skipped.append({"path": resolved, "reason": "symlink_refused"})
                continue
            if candidate.is_dir():
                discovered.append(resolved)

    return {
        "success": True,
        "schema_version": SYNC_SKILL_SCHEMA_VERSION,
        "command": "sync-skill",
        "data": {
            "status": "listed",
            "action": "list",
            "discovered": sorted(set(discovered)),
            "removed": [],
            "skipped": skipped,
            "diagnostics": [],
        },
    }


def uninstall_skill_artifacts(
    *,
    host_home: str | Path | None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Remove managed Life Index host skill directories under an explicit host home."""
    if host_home is None:
        return {
            "success": False,
            "schema_version": SYNC_SKILL_SCHEMA_VERSION,
            "command": "sync-skill",
            "data": {
                "status": "refused",
                "action": "uninstall",
                "host_home": None,
                "dry_run": dry_run,
                "removed": [],
                "skipped": [],
                "diagnostics": [
                    _diagnostic(
                        "UNINSTALL_REQUIRES_HOST_HOME",
                        (
                            "--uninstall requires explicit --host-home; no data, "
                            "clone, or package paths are inferred."
                        ),
                    )
                ],
            },
        }

    host_home_path = Path(host_home).expanduser()
    removed: list[str] = []
    skipped: list[dict[str, str]] = []
    for candidate in _dedupe_paths(_skill_dir_candidates_from_home(host_home_path)):
        resolved = str(candidate.expanduser().resolve())
        reason = _managed_skill_dir_reason(candidate, host_home_path)
        if reason is not None:
            skipped.append({"path": resolved, "reason": reason})
            continue
        if not candidate.exists():
            skipped.append({"path": resolved, "reason": "not_found"})
            continue
        if candidate.is_symlink():
            skipped.append({"path": resolved, "reason": "symlink_refused"})
            continue
        if not candidate.is_dir():
            skipped.append({"path": resolved, "reason": "not_directory"})
            continue
        if dry_run:
            skipped.append({"path": resolved, "reason": "dry_run"})
            continue

        shutil.rmtree(candidate)
        removed.append(resolved)

    status = (
        "dry_run" if dry_run and any(item["reason"] == "dry_run" for item in skipped) else "skipped"
    )
    if removed:
        status = "uninstalled"

    return {
        "success": True,
        "schema_version": SYNC_SKILL_SCHEMA_VERSION,
        "command": "sync-skill",
        "data": {
            "status": status,
            "action": "uninstall",
            "host_home": str(host_home_path.resolve()),
            "dry_run": dry_run,
            "removed": removed,
            "skipped": skipped,
            "diagnostics": [],
        },
    }


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


def sync_skill_artifacts(
    source_root: Path,
    target_dir: Path | None,
    *,
    install: bool = False,
) -> dict[str, Any]:
    """Copy SKILL.md and references into a host skill directory."""
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
                "delivered": False,
                "target_dir": None,
                "copied": [],
                "diagnostics": diagnostics,
            },
        }

    target_dir = target_dir.expanduser().resolve()
    target_preexisting = target_dir.is_dir()
    if not target_preexisting:
        if not install:
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
                    "delivered": False,
                    "target_dir": None,
                    "copied": [],
                    "diagnostics": diagnostics,
                },
            }
        target_dir.mkdir(parents=True, exist_ok=True)

    source_skill = source_root / "SKILL.md"
    if not source_skill.is_file():
        return {
            "success": False,
            "schema_version": SYNC_SKILL_SCHEMA_VERSION,
            "command": "sync-skill",
            "data": {
                "status": "failed",
                "delivered": False,
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
            "status": "synced" if target_preexisting else "installed",
            "delivered": True,
            "target_dir": str(target_dir),
            "copied": copied,
            "diagnostics": diagnostics,
        },
    }
