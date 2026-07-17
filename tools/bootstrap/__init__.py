"""Life Index bootstrap detection.

Read-only. This module never writes user data, checkouts, venvs, indexes, or
config.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import distribution as _pkg_distribution
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from tools.lib.journal_files import count_journal_files
from tools.lib.bootstrap_manifest import get_manifest_version
from tools.migrate import scan_journals
from tools.upgrade.install_integrity import inventory_life_index_distributions

BOOTSTRAP_SCHEMA_VERSION = "m34.bootstrap.v0"
PYPI_JSON_URL = "https://pypi.org/pypi/life-index/json"
PYPI_TIMEOUT_SECONDS = 2.0
GIT_TIMEOUT_SECONDS = 15.0
EDITABLE_REFRESH_STEP = "git pull --ff-only && pip install -e ."
PACKAGE_REFRESH_STEP = "pip install -U life-index"
MIGRATE_DRY_RUN_STEP = "life-index migrate --dry-run"
MIGRATE_APPLY_STEP = "life-index migrate --apply"
SEARCH_INDEX_REBUILD_STEP = "life-index index --rebuild"
INDEX_B_REBUILD_STEP = "life-index index-tree materialize --json"
INDEX_TREE_REBUILD_STEP = "life-index generate-index --all-months"
SYNC_SKILL_STEP = "life-index sync-skill"
HEALTH_STEP = "life-index health"

CheckoutOrigin = Literal["discovered", "host_managed", "user_designated"]
InstallType = Literal["editable", "package", "unknown"]

_DEV_PATH_TOKENS_LOWER = frozenset({"projects", "workspace", "repos"})
_DEV_TOOLS = frozenset({"pytest", "black", "mypy", "flake8", "isort", "playwright"})
EXECUTION_POLICY = {
    "needs_human": "relay_items_and_stop",
    "safe_next_steps": "run_in_order_without_additions",
    "uncertain_or_failed_step": "stop_and_report_exact_output",
    "data_safety": "never_delete_or_overwrite_user_data",
    "default_recovery": "refresh_or_reinstall_code_only_then_rerun_bootstrap",
}


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


def _version_tuple(version: str | None) -> tuple[int, ...] | None:
    if not version:
        return None
    public = version.split("+", 1)[0].split("-", 1)[0]
    parts: list[int] = []
    for piece in public.split("."):
        if not piece.isdigit():
            return None
        parts.append(int(piece))
    return tuple(parts)


def _is_newer_version(candidate: str | None, current: str | None) -> bool:
    candidate_parts = _version_tuple(candidate)
    current_parts = _version_tuple(current)
    if candidate_parts is None or current_parts is None:
        return False
    width = max(len(candidate_parts), len(current_parts))
    candidate_padded = candidate_parts + (0,) * (width - len(candidate_parts))
    current_padded = current_parts + (0,) * (width - len(current_parts))
    return candidate_padded > current_padded


def _query_latest_release() -> str:
    request = Request(PYPI_JSON_URL, headers={"Accept": "application/json"})
    with urlopen(request, timeout=PYPI_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))
    version = payload.get("info", {}).get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("PyPI response did not include info.version")
    return version


def _path_from_file_url(url: str) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    path = unquote(parsed.path)
    if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
        path = path[1:]
    return Path(path)


def _detect_editable_checkout_path() -> Path | None:
    try:
        dist = _pkg_distribution("life-index")
    except PackageNotFoundError:
        return None

    direct_url_text = dist.read_text("direct_url.json")
    if not direct_url_text:
        return None
    try:
        direct_url = json.loads(direct_url_text)
    except json.JSONDecodeError:
        return None
    dir_info = direct_url.get("dir_info")
    if not isinstance(dir_info, dict) or dir_info.get("editable") is not True:
        return None
    url = direct_url.get("url")
    if not isinstance(url, str):
        return None
    return _path_from_file_url(url)


def _detect_git_checkout_path(install_type: InstallType) -> Path | None:
    checkout_root = Path(__file__).resolve().parents[2]
    if (checkout_root / ".git").exists():
        return checkout_root

    if install_type == "editable":
        editable_path = _detect_editable_checkout_path()
        if editable_path and (editable_path / ".git").exists():
            return editable_path

    return None


def _run_git(checkout: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(checkout),
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )


def _git_ref_exists(checkout: Path, ref: str) -> bool:
    result = _run_git(checkout, ["rev-parse", "--verify", "--quiet", ref])
    return result.returncode == 0


def _detect_git_freshness(checkout: Path | None) -> dict[str, Any]:
    if checkout is None:
        return {
            "git_freshness": "not_applicable",
            "git_upstream": None,
            "git_behind_count": None,
            "git_ahead_count": None,
            "git_error": None,
        }

    if os.environ.get("LIFE_INDEX_NO_NET") == "1":
        return {
            "git_freshness": "unknown",
            "git_upstream": None,
            "git_behind_count": None,
            "git_ahead_count": None,
            "git_error": "disabled by LIFE_INDEX_NO_NET",
        }

    try:
        fetch = _run_git(checkout, ["fetch", "--quiet"])
        if fetch.returncode != 0:
            detail = (fetch.stderr or fetch.stdout or "git fetch failed").strip()
            return {
                "git_freshness": "unknown",
                "git_upstream": None,
                "git_behind_count": None,
                "git_ahead_count": None,
                "git_error": detail,
            }

        upstream_result = _run_git(
            checkout,
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        )
        upstream = upstream_result.stdout.strip() if upstream_result.returncode == 0 else ""
        if not upstream:
            upstream = "origin/main" if _git_ref_exists(checkout, "origin/main") else ""
        if not upstream:
            return {
                "git_freshness": "unknown",
                "git_upstream": None,
                "git_behind_count": None,
                "git_ahead_count": None,
                "git_error": "No upstream branch or origin/main ref found",
            }

        count_result = _run_git(
            checkout,
            ["rev-list", "--left-right", "--count", f"HEAD...{upstream}"],
        )
        if count_result.returncode != 0:
            detail = (count_result.stderr or count_result.stdout or "git rev-list failed").strip()
            return {
                "git_freshness": "unknown",
                "git_upstream": upstream,
                "git_behind_count": None,
                "git_ahead_count": None,
                "git_error": detail,
            }

        parts = count_result.stdout.strip().split()
        ahead = int(parts[0])
        behind = int(parts[1])
        return {
            "git_freshness": "behind" if behind > 0 else "current",
            "git_upstream": upstream,
            "git_behind_count": behind,
            "git_ahead_count": ahead,
            "git_error": None,
        }
    except Exception as exc:
        return {
            "git_freshness": "unknown",
            "git_upstream": None,
            "git_behind_count": None,
            "git_ahead_count": None,
            "git_error": str(exc),
        }


def _detect_release_freshness(
    installed_version: str | None,
    manifest_version: str | None,
    install_type: InstallType = "unknown",
    git_checkout: Path | None = None,
) -> dict[str, Any]:
    if os.environ.get("LIFE_INDEX_NO_NET") == "1":
        git_status = _detect_git_freshness(git_checkout)
        return {
            "freshness": "unknown",
            "latest_release": None,
            "update_available": None,
            "update_reasons": [],
            "freshness_error": "disabled by LIFE_INDEX_NO_NET",
            "suggested_refresh_step": None,
            **git_status,
        }

    latest: str | None = None
    release_error: str | None = None
    try:
        latest = _query_latest_release()
    except Exception as exc:
        release_error = str(exc)

    current = installed_version or manifest_version
    release_update = latest if _is_newer_version(latest, current) else None
    git_status = _detect_git_freshness(git_checkout)
    git_behind = int(git_status.get("git_behind_count") or 0)

    update_reasons: list[str] = []
    if release_update:
        update_reasons.append("release")
    if git_behind > 0:
        update_reasons.append("git_behind")

    errors = [error for error in (release_error, git_status.get("git_error")) if error]
    if update_reasons:
        freshness = "update_available"
    elif errors:
        freshness = "unknown"
    else:
        freshness = "current"

    suggested_refresh_step: str | None = None
    if update_reasons:
        if git_behind > 0 or install_type == "editable":
            suggested_refresh_step = EDITABLE_REFRESH_STEP
        elif install_type == "package":
            suggested_refresh_step = PACKAGE_REFRESH_STEP

    return {
        "freshness": freshness,
        "latest_release": latest,
        "update_available": release_update or ("git-behind" if git_behind > 0 else None),
        "update_reasons": update_reasons,
        "freshness_error": "; ".join(errors) if errors else None,
        "suggested_refresh_step": suggested_refresh_step,
        **git_status,
    }


def _detect_install_type() -> InstallType:
    try:
        dist = _pkg_distribution("life-index")
    except PackageNotFoundError:
        return "unknown"

    direct_url_text = dist.read_text("direct_url.json")
    if direct_url_text:
        try:
            direct_url = json.loads(direct_url_text)
        except json.JSONDecodeError:
            return "unknown"
        dir_info = direct_url.get("dir_info")
        if isinstance(dir_info, dict) and dir_info.get("editable") is True:
            return "editable"
        return "package"

    return "package"


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
    install_type = _detect_install_type()
    install_inventory = inventory_life_index_distributions()
    git_checkout = _detect_git_checkout_path(install_type)
    release_freshness = _detect_release_freshness(
        installed,
        manifest,
        install_type=install_type,
        git_checkout=git_checkout,
    )
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
        "install_type": install_type,
        "install_inventory": install_inventory,
        **release_freshness,
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

    has_user_data = bool(data_state.get("has_user_data"))
    journal_count = int(data_state.get("journal_count", 0) or 0)
    data_dir = str(data_state.get("data_dir", ""))
    install_inventory = data_state.get("install_inventory")
    if isinstance(install_inventory, dict) and install_inventory.get("state") == "conflict":
        route = "upgrade" if has_user_data else "fresh_install"
        route_reason = (
            f"Found {journal_count} journal(s) in {data_dir}"
            if has_user_data
            else "No existing journal data found"
        )
        needs_human.append(
            {
                "code": "INSTALL_DISTRIBUTION_CONFLICT",
                "message": (
                    "Multiple canonical Life Index distributions are installed; ordinary "
                    "refresh steps are unsafe."
                ),
                "suggested_action": (
                    "Use only a trusted checkout with the isolated recovery launcher: "
                    f"{sys.executable} -I TRUSTED_CHECKOUT/tools/upgrade/install_integrity.py "
                    "recover --source-root TRUSTED_CHECKOUT --json"
                ),
            }
        )
        return {
            "route": route,
            "route_reason": route_reason,
            "execution_policy": dict(EXECUTION_POLICY),
            "needs_human": needs_human,
            "safe_next_steps": safe_next_steps,
        }

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

    if has_user_data:
        route = "upgrade"
        route_reason = f"Found {journal_count} journal(s) in {data_dir}"
    else:
        route = "fresh_install"
        route_reason = "No existing journal data found"

    def add_step(step: str) -> None:
        if step not in safe_next_steps:
            safe_next_steps.append(step)

    def refresh_step() -> str | None:
        suggested = data_state.get("suggested_refresh_step")
        if isinstance(suggested, str) and suggested:
            return suggested
        install_type = data_state.get("install_type")
        if install_type == "editable":
            return EDITABLE_REFRESH_STEP
        if install_type == "package":
            return PACKAGE_REFRESH_STEP
        return None

    should_refresh_install = bool(data_state.get("update_available")) or (
        data_state.get("install_in_sync") is False
    )
    if should_refresh_install:
        step = refresh_step()
        if step:
            add_step(step)
        else:
            needs_human.append(
                {
                    "code": "INSTALL_REFRESH_UNKNOWN",
                    "message": "A package refresh may be needed, but install type is unknown.",
                    "suggested_action": (
                        "Inspect how life-index is installed, then run the matching refresh "
                        "command before continuing."
                    ),
                }
            )

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
        "execution_policy": dict(EXECUTION_POLICY),
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
