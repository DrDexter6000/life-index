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
CHANGELOG_POINTER = "CHANGELOG.md"
CANONICAL_SKILL_SLOT = "life-index"


def _diagnostic(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _skill_dir_candidates_from_home(home: Path) -> list[Path]:
    skills_dir = home.expanduser() / "skills"
    candidates = [skills_dir / CANONICAL_SKILL_SLOT]
    candidates.extend(sorted(skills_dir.glob(f"*/{CANONICAL_SKILL_SLOT}")))
    return candidates


def _is_canonical_skill_leaf(path: Path) -> bool:
    parts = path.expanduser().parts
    if len(parts) < 3 or parts[-1] != CANONICAL_SKILL_SLOT:
        return False
    if parts[-2] == "skills":
        return True
    return len(parts) >= 4 and parts[-3] == "skills"


def _normalize_host_skill_dir_parent(path: Path) -> tuple[Path, list[dict[str, str]]]:
    candidate = path.expanduser()
    if candidate.name != "skills":
        return candidate, []
    normalized = candidate / CANONICAL_SKILL_SLOT
    return normalized, [
        _diagnostic(
            "HOST_SKILL_DIR_PARENT_NORMALIZED",
            (
                "Host skill directory pointed at a skills parent; using canonical "
                f"Life Index skill slot {normalized}."
            ),
        )
    ]


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
        candidate, normalization_diagnostics = _normalize_host_skill_dir_parent(Path(explicit_dir))
        if candidate.is_dir():
            return candidate, [*diagnostics, *normalization_diagnostics]
        return None, [
            *normalization_diagnostics,
            _diagnostic(
                "HOST_SKILL_DIR_NOT_FOUND",
                f"Host skill directory does not exist: {candidate}",
            ),
        ]

    env_dir = os.environ.get(HOST_SKILL_DIR_ENV)
    if env_dir:
        candidate, normalization_diagnostics = _normalize_host_skill_dir_parent(Path(env_dir))
        if candidate.is_dir():
            return candidate, [*diagnostics, *normalization_diagnostics]
        return None, [
            *normalization_diagnostics,
            _diagnostic(
                "HOST_SKILL_DIR_NOT_FOUND",
                f"Host skill directory does not exist: {candidate}",
            ),
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
        converged = _autoconverge_managed_nested_duplicate(matches)
        if converged is not None:
            return converged
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


def _host_skill_candidates_from_default_homes() -> list[Path]:
    candidates: list[Path] = []
    for env_name in HOST_HOME_ENVS:
        host_home = os.environ.get(env_name)
        if host_home:
            candidates.extend(_skill_dir_candidates_from_home(Path(host_home)))

    home = Path.home()
    for dirname in DEFAULT_HOST_HOME_DIRS:
        candidates.extend(_skill_dir_candidates_from_home(home / dirname))
    return _dedupe_paths(candidates)


def install_target_from_host_home(host_home: str | Path) -> Path:
    """Resolve the canonical Life Index skill directory under a host home."""
    return Path(host_home).expanduser() / "skills" / CANONICAL_SKILL_SLOT


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


def _empty_dedupe() -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "nested_dir": None,
        "removed": [],
        "skipped": [],
    }


def _nested_duplicate_dir(target_dir: Path) -> Path:
    return target_dir / "life-index"


def _managed_nested_skill_tree_reason(path: Path) -> str | None:
    if not path.exists():
        return "not_found"
    if path.is_symlink():
        return "symlink_refused"
    if not path.is_dir():
        return "not_directory"
    if not (path / "SKILL.md").is_file():
        return "missing_skill"

    for child in path.iterdir():
        if child.name == "SKILL.md":
            continue
        if child.name == "references" and child.is_dir() and not child.is_symlink():
            continue
        return "extra_files_refused"
    return None


def _is_life_index_managed_skill_text(text: str) -> bool:
    frontmatter, _body = _split_frontmatter(text)
    if not frontmatter:
        return False
    try:
        parsed = yaml.safe_load("\n".join(frontmatter)) or {}
    except yaml.YAMLError:
        return False
    return parsed.get("name") == "life-index"


def _reference_source_files(source_root: Path) -> dict[Path, Path]:
    references_root = source_root / "references"
    if not references_root.is_dir():
        return {}
    return {
        path.relative_to(references_root): path
        for path in references_root.rglob("*")
        if path.is_file()
    }


def _parent_stray_artifact_status(
    source_root: Path,
    target_dir: Path,
) -> dict[str, Any]:
    parent_dir = target_dir.parent
    parent_skill = parent_dir / "SKILL.md"
    parent_references = parent_dir / "references"
    if not parent_skill.exists() and not parent_references.exists():
        return {"status": "not_applicable", "skill_text": None}

    if not parent_skill.is_file():
        return {"status": "preserved", "skill_text": None, "reason": "missing_managed_skill"}

    try:
        skill_text = parent_skill.read_text(encoding="utf-8")
    except OSError:
        return {"status": "preserved", "skill_text": None, "reason": "skill_unreadable"}
    if not _is_life_index_managed_skill_text(skill_text):
        return {"status": "preserved", "skill_text": None, "reason": "unmanaged_skill"}

    if parent_references.exists():
        if parent_references.is_symlink() or not parent_references.is_dir():
            return {"status": "preserved", "skill_text": None, "reason": "references_not_directory"}

        source_references = _reference_source_files(source_root)
        for stray_path in sorted(path for path in parent_references.rglob("*") if path.is_file()):
            relative_path = stray_path.relative_to(parent_references)
            source_path = source_references.get(relative_path)
            if source_path is None:
                return {"status": "preserved", "skill_text": None, "reason": "extra_reference"}
            try:
                if stray_path.read_bytes() != source_path.read_bytes():
                    return {
                        "status": "preserved",
                        "skill_text": None,
                        "reason": "changed_reference",
                    }
            except OSError:
                return {
                    "status": "preserved",
                    "skill_text": None,
                    "reason": "reference_unreadable",
                }

    return {
        "status": "managed",
        "skill_text": skill_text,
        "skill_path": parent_skill,
        "references_path": parent_references,
    }


def find_install_target_dir(
    source_root: Path,
    explicit_dir: str | Path | None = None,
) -> tuple[Path | None, list[dict[str, str]]]:
    """Resolve an install target without guessing a new host unless recovery is provable."""
    if explicit_dir:
        candidate, normalization_diagnostics = _normalize_host_skill_dir_parent(Path(explicit_dir))
        return candidate, normalization_diagnostics

    env_dir = os.environ.get(HOST_SKILL_DIR_ENV)
    if env_dir:
        candidate, normalization_diagnostics = _normalize_host_skill_dir_parent(Path(env_dir))
        return candidate, normalization_diagnostics

    candidates = _host_skill_candidates_from_default_homes()
    matches = [candidate for candidate in candidates if candidate.is_dir()]
    if len(matches) == 1:
        return matches[0], []
    if len(matches) > 1:
        converged = _autoconverge_managed_nested_duplicate(matches)
        if converged is not None:
            return converged
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

    recovery_targets: list[Path] = []
    for host_home in _default_host_homes():
        target = install_target_from_host_home(host_home)
        parent_stray = _parent_stray_artifact_status(source_root.resolve(), target)
        if parent_stray["status"] == "managed":
            recovery_targets.append(target)

    recovery_targets = _dedupe_paths(recovery_targets)
    if len(recovery_targets) == 1:
        target = recovery_targets[0]
        return target, [
            _diagnostic(
                "HOST_SKILL_DIR_PARENT_STRAY_RECOVERY_SELECTED",
                (
                    "Managed Life Index skill artifacts were found in the host skills "
                    f"parent; recovering the canonical skill slot {target}."
                ),
            )
        ]
    if len(recovery_targets) > 1:
        formatted = "; ".join(str(path) for path in recovery_targets)
        return None, [
            _diagnostic(
                "HOST_SKILL_DIR_AMBIGUOUS",
                (
                    "Multiple parent-level Life Index skill recovery targets were found; "
                    f"pass --host-skill-dir or --host-home explicitly. Matches: {formatted}"
                ),
            )
        ]

    checked = "; ".join(str(path) for path in candidates)
    return None, [
        _diagnostic(
            "HOST_SKILL_DIR_NOT_FOUND",
            (
                "No existing host skill directory or managed parent-level recovery "
                f"artifact was found; skill artifact sync was not delivered. Checked: {checked}"
            ),
        )
    ]


def _autoconverge_managed_nested_duplicate(
    matches: list[Path],
) -> tuple[Path, list[dict[str, str]]] | None:
    if len(matches) != 2:
        return None

    resolved_matches = {str(match.expanduser().resolve()): match for match in matches}
    for canonical in matches:
        if canonical.is_symlink():
            continue
        nested = _nested_duplicate_dir(canonical)
        nested_key = str(nested.expanduser().resolve())
        if nested_key not in resolved_matches:
            continue
        reason = _managed_nested_skill_tree_reason(nested)
        if reason is not None:
            return None
        canonical_resolved = str(canonical.expanduser().resolve())
        nested_resolved = str(nested.expanduser().resolve())
        return canonical, [
            _diagnostic(
                "HOST_SKILL_DIR_NESTED_DUPLICATE_AUTOCONVERGED",
                (
                    "Managed nested Life Index skill duplicate found; "
                    f"using canonical host skill directory {canonical_resolved} "
                    f"and converging nested duplicate {nested_resolved}."
                ),
            )
        ]
    return None


def _detect_nested_dedupe(target_dir: Path) -> dict[str, Any]:
    nested = _nested_duplicate_dir(target_dir)
    if not nested.exists():
        return _empty_dedupe()

    resolved = str(nested.resolve())
    reason = _managed_nested_skill_tree_reason(nested)
    if reason is not None:
        return {
            "status": "skipped",
            "nested_dir": resolved,
            "removed": [],
            "skipped": [{"path": resolved, "reason": reason}],
        }
    return {
        "status": "ready",
        "nested_dir": resolved,
        "removed": [],
        "skipped": [],
    }


def _merge_existing_skill_texts(source_text: str, existing_texts: list[str | None]) -> str:
    merged = source_text
    for existing_text in existing_texts:
        if existing_text:
            merged = _merge_skill_text(merged, existing_text)
    return merged


def sync_skill_artifacts(
    source_root: Path,
    target_dir: Path | None,
    *,
    install: bool = False,
    dry_run: bool = False,
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
                "playbook_status": "not_delivered",
                "changelog": CHANGELOG_POINTER,
                "dedupe": _empty_dedupe(),
                "diagnostics": diagnostics,
            },
        }

    target_dir = target_dir.expanduser().resolve()
    if not _is_canonical_skill_leaf(target_dir):
        diagnostics.append(
            _diagnostic(
                "HOST_SKILL_DIR_NOT_CANONICAL",
                (
                    "Refusing to sync into a non-canonical host skill directory; "
                    "target must be a life-index leaf such as "
                    "<host-home>/skills/life-index."
                ),
            )
        )
        return {
            "success": False,
            "schema_version": SYNC_SKILL_SCHEMA_VERSION,
            "command": "sync-skill",
            "data": {
                "status": "refused",
                "delivered": False,
                "target_dir": str(target_dir),
                "copied": [],
                "playbook_status": "not_delivered",
                "changelog": CHANGELOG_POINTER,
                "dedupe": _empty_dedupe(),
                "diagnostics": diagnostics,
            },
        }
    target_skill = target_dir / "SKILL.md"
    target_dir_exists = target_dir.is_dir()
    nested_duplicate_exists = _nested_duplicate_dir(target_dir).exists()
    target_preexisting = target_dir_exists and not (
        install and not target_skill.is_file() and nested_duplicate_exists
    )
    if not target_dir_exists:
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
                    "playbook_status": "not_delivered",
                    "changelog": CHANGELOG_POINTER,
                    "dedupe": _empty_dedupe(),
                    "diagnostics": diagnostics,
                },
            }
        if not dry_run:
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
                "playbook_status": "not_delivered",
                "changelog": CHANGELOG_POINTER,
                "dedupe": _empty_dedupe(),
                "diagnostics": [
                    _diagnostic("SOURCE_SKILL_NOT_FOUND", f"Missing source skill: {source_skill}")
                ],
            },
        }

    source_text = source_skill.read_text(encoding="utf-8")
    existing_text = target_skill.read_text(encoding="utf-8") if target_skill.is_file() else None
    parent_stray = _parent_stray_artifact_status(source_root, target_dir)
    if parent_stray["status"] == "preserved":
        diagnostics.append(
            _diagnostic(
                "HOST_SKILL_DIR_PARENT_STRAY_PRESERVED",
                (
                    "Found parent-level skill artifacts that cannot be proven to be "
                    "Life Index managed; leaving them untouched."
                ),
            )
        )
    dedupe = _detect_nested_dedupe(target_dir)
    nested_text: str | None = None
    nested_dir = _nested_duplicate_dir(target_dir)
    nested_skill = nested_dir / "SKILL.md"
    if dedupe["status"] == "ready" and nested_skill.is_file():
        nested_text = nested_skill.read_text(encoding="utf-8")

    parent_stray_text = parent_stray.get("skill_text")
    merged_text = _merge_existing_skill_texts(
        source_text,
        [existing_text, nested_text, parent_stray_text],
    )
    playbook_status = "unchanged" if existing_text == merged_text else "updated"
    if not target_preexisting:
        playbook_status = "would_install" if dry_run else "installed"
    elif dry_run and playbook_status == "updated":
        playbook_status = "would_update"

    if dry_run:
        if dedupe["status"] == "ready":
            dedupe = {**dedupe, "status": "would_remove"}
        return {
            "success": True,
            "schema_version": SYNC_SKILL_SCHEMA_VERSION,
            "command": "sync-skill",
            "data": {
                "status": "dry_run",
                "delivered": False,
                "target_dir": str(target_dir),
                "copied": [],
                "playbook_status": playbook_status,
                "changelog": CHANGELOG_POINTER,
                "dedupe": dedupe,
                "diagnostics": diagnostics,
            },
        }

    target_dir.mkdir(parents=True, exist_ok=True)
    target_skill.write_text(merged_text, encoding="utf-8")

    copied = ["SKILL.md", *_copy_references(source_root, target_dir)]
    if dedupe["status"] == "ready":
        shutil.rmtree(nested_dir)
        nested_resolved = str(nested_dir.resolve())
        dedupe = {
            **dedupe,
            "status": "removed",
            "removed": [nested_resolved],
        }
    if parent_stray["status"] == "managed":
        parent_skill = parent_stray["skill_path"]
        parent_references = parent_stray["references_path"]
        if parent_skill.exists():
            parent_skill.unlink()
        if parent_references.exists():
            shutil.rmtree(parent_references)
        diagnostics.append(
            _diagnostic(
                "HOST_SKILL_DIR_PARENT_STRAY_CLEANED",
                (
                    "Removed managed Life Index skill artifacts from the host skills "
                    "parent after installing the canonical skills/life-index slot."
                ),
            )
        )
    return {
        "success": True,
        "schema_version": SYNC_SKILL_SCHEMA_VERSION,
        "command": "sync-skill",
        "data": {
            "status": "synced" if target_preexisting else "installed",
            "delivered": True,
            "target_dir": str(target_dir),
            "copied": copied,
            "playbook_status": playbook_status,
            "changelog": CHANGELOG_POINTER,
            "dedupe": dedupe,
            "diagnostics": diagnostics,
        },
    }
