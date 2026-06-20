"""Life Index bootstrap detection.

Read-only. This module never writes user data, checkouts, venvs, indexes, or
config.
"""

from __future__ import annotations

import os
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any, Literal

from tools.lib.journal_files import count_journal_files
from tools.lib.bootstrap_manifest import get_manifest_version
from tools.migrate import scan_journals

BOOTSTRAP_SCHEMA_VERSION = "m34.bootstrap.v0"
PIP_INSTALL_STEP = "pip install -e ."
MIGRATE_DRY_RUN_STEP = "life-index migrate --dry-run"
MIGRATE_APPLY_STEP = "life-index migrate --apply"
SEARCH_INDEX_REBUILD_STEP = "life-index index --rebuild"
INDEX_B_REBUILD_STEP = "life-index index-tree materialize --json"
INDEX_TREE_REBUILD_STEP = "life-index generate-index --all-months"
SYNC_SKILL_STEP = "life-index sync-skill"
HEALTH_STEP = "life-index health"

CheckoutOrigin = Literal["discovered", "host_managed", "user_designated"]

_DEV_PATH_TOKENS_LOWER = frozenset({"projects", "workspace", "repos"})
_DEV_TOOLS = frozenset({"pytest", "black", "mypy", "flake8", "isort", "playwright"})


def _resolve_data_dir(data_dir: str | None = None) -> Path:
    if data_dir:
        return Path(data_dir)
    return Path(
        os.environ.get("LIFE_INDEX_DATA_DIR", str(Path.home() / "Documents" / "Life-Index"))
    )


def _count_journals(data_dir: Path) -> int:
    return count_journal_files(data_dir / "Journals")


def _get_installed_version() -> str | None:
    try:
        return _pkg_version("life-index")
    except PackageNotFoundError:
        return None


def _get_manifest_version() -> str | None:
    return get_manifest_version()


def _check_migration(data_dir: Path) -> tuple[int | None, str | None]:
    journals_dir = data_dir / "Journals"
    if not journals_dir.exists():
        return 0, None
    try:
        result = scan_journals(journals_dir)
    except Exception as exc:
        return None, str(exc)
    needs = result.get("needs_migration", 0)
    return int(needs), None


def detect_data_state(data_dir: str | None = None) -> dict[str, Any]:
    """Probe data directory and installed-version state. Read-only."""
    ddir = _resolve_data_dir(data_dir)
    journal_count = _count_journals(ddir)
    installed = _get_installed_version()
    manifest = _get_manifest_version()
    install_in_sync: bool | None = None
    if installed is not None and manifest is not None:
        install_in_sync = installed == manifest
    migration_needed, migration_error = _check_migration(ddir)
    return {
        "has_user_data": journal_count > 0,
        "journal_count": journal_count,
        "data_dir": str(ddir),
        "installed_version": installed,
        "manifest_version": manifest,
        "install_in_sync": install_in_sync,
        "migration_needed": migration_needed,
        "migration_check_error": migration_error,
    }


def assess_checkout(path: Path, checkout_origin: CheckoutOrigin = "discovered") -> dict[str, Any]:
    """Assess whether a checkout can be adopted as install target.

    Adoption requires positive origin: host-managed or user-designated. A random
    discovered checkout is ambiguous even when it looks clean.
    """
    signals: list[str] = []
    strong_dev_signals: list[str] = []

    required = ["SKILL.md", "pyproject.toml", "bootstrap-manifest.json"]
    missing = [name for name in required if not (path / name).exists()]

    if (path / ".venv" / "Scripts" / "python.exe").exists() and sys.platform != "win32":
        signals.append("windows_venv_from_non_windows")
        strong_dev_signals.append("windows_venv_from_non_windows")
    if (path / ".venv" / "bin" / "python").exists() and sys.platform == "win32":
        signals.append("linux_venv_from_windows")
        strong_dev_signals.append("linux_venv_from_windows")

    lower_parts = {part.lower() for part in path.parts}
    has_dev_path_hint = bool(lower_parts & _DEV_PATH_TOKENS_LOWER)
    if has_dev_path_hint:
        signals.append("dev_path_hint")
        if (path / ".git").exists():
            signals.append("dev_path_with_git")
            strong_dev_signals.append("dev_path_with_git")

    bin_dir = path / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
    for tool in sorted(_DEV_TOOLS):
        if (bin_dir / tool).exists() or (bin_dir / f"{tool}.exe").exists():
            signal = f"dev_package_{tool}"
            signals.append(signal)
            strong_dev_signals.append(signal)
            break

    if missing:
        return {
            "path": str(path),
            "origin": checkout_origin,
            "verdict": "invalid",
            "signals": signals,
            "safe_to_adopt": False,
            "reason": f"Missing required files: {', '.join(missing)}",
        }

    if strong_dev_signals:
        return {
            "path": str(path),
            "origin": checkout_origin,
            "verdict": "dev_dir",
            "signals": signals,
            "safe_to_adopt": False,
            "reason": f"Development directory signals: {', '.join(strong_dev_signals)}",
        }

    if checkout_origin not in ("host_managed", "user_designated"):
        return {
            "path": str(path),
            "origin": checkout_origin,
            "verdict": "ambiguous",
            "signals": signals,
            "safe_to_adopt": False,
            "reason": "Checkout origin is not host-managed or user-designated",
        }

    return {
        "path": str(path),
        "origin": checkout_origin,
        "verdict": "adopt",
        "signals": signals,
        "safe_to_adopt": True,
        "reason": "Checkout has required files and positive adoption origin",
    }


def decide_route(
    data_state: dict[str, Any],
    checkout_assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Choose onboarding route and safe next steps without taking action."""
    needs_human: list[dict[str, str]] = []
    safe_next_steps: list[str] = []

    if checkout_assessment and not checkout_assessment.get("safe_to_adopt", False):
        verdict = checkout_assessment.get("verdict")
        if verdict == "ambiguous":
            needs_human.append(
                {
                    "code": "AMBIGUOUS_CHECKOUT",
                    "message": "Checkout is complete but lacks positive adoption authority.",
                    "suggested_action": (
                        "Use a host-managed skill path, ask the user to designate this "
                        "checkout, or clone fresh into an agent-managed target."
                    ),
                }
            )
        elif verdict == "dev_dir":
            needs_human.append(
                {
                    "code": "DEV_DIR_FOUND",
                    "message": "Checkout has development-directory signals.",
                    "suggested_action": (
                        "Do not adopt or repair this checkout from onboarding; use a "
                        "host-managed skill path or ask the user."
                    ),
                }
            )
        elif verdict == "invalid":
            needs_human.append(
                {
                    "code": "INVALID_CHECKOUT",
                    "message": "Checkout is missing required Life Index files.",
                    "suggested_action": (
                        "Delete and reclone only if the path is agent-managed; otherwise "
                        "ask the user before cleanup."
                    ),
                }
            )

    has_user_data = bool(data_state.get("has_user_data"))
    journal_count = int(data_state.get("journal_count", 0) or 0)
    data_dir = str(data_state.get("data_dir", ""))

    if has_user_data:
        route = "upgrade"
        route_reason = f"Found {journal_count} journal(s) in {data_dir}"
    else:
        route = "fresh_install"
        route_reason = "No existing journal data found"

    def add_step(step: str) -> None:
        if step not in safe_next_steps:
            safe_next_steps.append(step)

    if data_state.get("install_in_sync") is False:
        add_step(PIP_INSTALL_STEP)

    migration_needed = data_state.get("migration_needed")
    migration_error = data_state.get("migration_check_error")
    if migration_needed is None:
        needs_human.append(
            {
                "code": "MIGRATION_CHECK_FAILED",
                "message": f"Migration scan failed: {migration_error or 'unknown error'}",
                "suggested_action": (
                    "Run life-index migrate --dry-run manually and inspect output before "
                    "continuing."
                ),
            }
        )
        add_step(MIGRATE_DRY_RUN_STEP)
    elif migration_needed > 0:
        add_step(MIGRATE_DRY_RUN_STEP)
        add_step(MIGRATE_APPLY_STEP)

    if route == "upgrade":
        add_step(MIGRATE_DRY_RUN_STEP)
        add_step(SEARCH_INDEX_REBUILD_STEP)
        add_step(INDEX_B_REBUILD_STEP)
        add_step(INDEX_TREE_REBUILD_STEP)
        add_step(SYNC_SKILL_STEP)

    if route in ("upgrade", "fresh_install"):
        add_step(HEALTH_STEP)

    return {
        "route": route,
        "route_reason": route_reason,
        "needs_human": needs_human,
        "safe_next_steps": safe_next_steps,
    }


def build_bootstrap_result(
    data_dir: str | None = None,
    checkout_path: str | None = None,
    checkout_origin: CheckoutOrigin = "discovered",
) -> dict[str, Any]:
    """Build the public bootstrap JSON envelope. Read-only."""
    data_state = detect_data_state(data_dir=data_dir)
    checkout_assessment = None
    if checkout_path:
        checkout_assessment = assess_checkout(
            Path(checkout_path),
            checkout_origin=checkout_origin,
        )

    detected_state = dict(data_state)
    detected_state["checkout_assessment"] = checkout_assessment
    route = decide_route(data_state, checkout_assessment=checkout_assessment)

    return {
        "success": True,
        "schema_version": BOOTSTRAP_SCHEMA_VERSION,
        "command": "bootstrap",
        "detected_state": detected_state,
        **route,
    }
