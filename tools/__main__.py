#!/usr/bin/env python3
"""
Life Index - Unified CLI Entry Point
统一命令行入口

Usage:
    life-index <command> [options]
    python -m tools <command> [options]

Commands:
    write     Write a journal entry
    confirm   Apply write confirmation updates
    search    Search journals (pure dual-pipeline)
    smart-search  Deterministic evidence scaffold for host agents
    edit      Edit a journal entry
    journal   Read journals through stable get/list contracts
    attachment  Read/export/stream archived attachments
    entity    Manage entity graph
    weather   Query weather information
    index     Build/rebuild search index
    generate-index  Generate index tree and entity profile docs
    abstract  Alias for generate-index
    backup    Backup journal data
    verify    Verify data integrity
    timeline  Output chronological summary stream
    on-this-day  Find prior-year entries on same month/day
    recall    Deprecated compatibility wrapper over search
    trajectory  Typed observations (weight/sleep/mood/location/project)
    migrate   Schema migration tool
    eval      Run search evaluation gate
    entity-graph-eval  Run graph ablation evaluation (gbrain #1)
    aggregate Deterministic counts, buckets, and claim envelopes
    analyze   Alias for aggregate
    maintenance  Run maintenance cycle (dry-run health checks)
    bootstrap    Detect install/data state and route onboarding (read-only)
    sync-skill    Synchronize SKILL.md and references into host skill directory
    health    Check installation health
              --data-audit  Summarize Data Doctor audit and next steps
              --cache-audit  Read-only cache version audit (JSON)
    import    Import provider (plan, run, status, rollback)
    index-tree  Index Tree Evidence Navigation
    version   Show package and bootstrap manifest version info
"""

import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Tuple

from tools.eval.compat import LANGUAGE_JUDGE_ERROR, language_judge_requested

if (
    len(sys.argv) > 1
    and sys.argv[1] == "eval"
    and language_judge_requested(sys.argv, command_offset=2)
):
    print(json.dumps({"success": False, "error": LANGUAGE_JUDGE_ERROR}, ensure_ascii=False))
    raise SystemExit(2)

from importlib.metadata import PackageNotFoundError, version as package_version


def _should_guard_import_stdout(argv: list[str]) -> bool:
    return len(argv) > 1 and argv[1] in {"abstract", "generate-index"} and "--json" in argv[2:]


_IMPORT_STDOUT_ORIGINAL = sys.stdout if _should_guard_import_stdout(sys.argv) else None
if _IMPORT_STDOUT_ORIGINAL is not None:
    sys.stdout = sys.stderr

from tools.lib.journal_files import count_journal_files  # noqa: E402
from tools.lib.config import get_model_cache_dir  # noqa: E402,F401 — used via monkeypatch in tests
from tools.lib.paths import (  # noqa: E402
    ValidationModeDataDirError,
    enforce_validation_mode_data_dir,
    get_journals_dir,
    get_user_data_dir,
)
from tools.lib.bootstrap_manifest import (  # noqa: E402
    read_bootstrap_manifest as _read_bootstrap_manifest,
)

HEALTH_SCHEMA_VERSION = "m16.health.v0"
INDEX_TREE_REBUILD_COMMAND = "life-index generate-index --all-months"
CHRONIC_HEALTH_CHECKS = {"virtual_env", "data_directory", "entity_graph", "index_tree"}
CHANGELOG_POINTER = "CHANGELOG.md"
DIRTY_WORKTREE_WARNING = (
    "Repository clone has uncommitted changes; dirty clones can cause "
    "Life Index upgrades to fail."
)
DIRTY_WORKTREE_SUGGESTED_COMMAND = "git --no-optional-locks status --short"
DERIVED_INDEX_NOTE = "Writes derived index artifacts only; source journals are not modified."
DERIVED_ENTITY_PROFILES_NOTE = (
    "Writes derived Entities/ profile docs only; entity_graph.yaml is not modified."
)
REPO_RECOVERY_NOTE = (
    "Read-only inspection of uncommitted checkout changes; leave them untouched and ask the owner."
)
UPGRADE_REFRESH_NOTE = "Read-only upgrade planning; follow the returned onboarding pointer."
READ_ONLY_ENTITY_REVIEW_NOTE = (
    "Read-only review queue/audit command unless an explicit action is supplied."
)

BOOTSTRAP_MANIFEST_PATH = Path(__file__).resolve().parent.parent / "bootstrap-manifest.json"


def _restore_import_stdout() -> None:
    global _IMPORT_STDOUT_ORIGINAL
    if _IMPORT_STDOUT_ORIGINAL is None:
        return
    sys.stdout = _IMPORT_STDOUT_ORIGINAL
    _IMPORT_STDOUT_ORIGINAL = None


def _canonical_journal_date(filename: str) -> str | None:
    if not filename.startswith("life-index_") or not filename.endswith(".md"):
        return None
    date_part = filename[len("life-index_") : len("life-index_") + 10]
    suffix = filename[len("life-index_") + 10 : -3]
    if (
        len(date_part) == 10
        and date_part[4] == "-"
        and date_part[7] == "-"
        and date_part[:4].isdigit()
        and date_part[5:7].isdigit()
        and date_part[8:10].isdigit()
        and suffix.startswith("_")
        and suffix[1:].isdigit()
    ):
        return date_part
    return None


def _latest_journal_date(journals_dir: Path) -> str | None:
    latest: str | None = None
    if not journals_dir.exists():
        return None
    for path in journals_dir.rglob("*.md"):
        if not path.is_file():
            continue
        journal_date = _canonical_journal_date(path.name)
        if journal_date and (latest is None or journal_date > latest):
            latest = journal_date
    return latest


def read_bootstrap_manifest() -> Dict[str, Any]:
    return _read_bootstrap_manifest(BOOTSTRAP_MANIFEST_PATH)


def get_package_version() -> str:
    try:
        manifest_version = read_bootstrap_manifest().get("repo_version")
        if isinstance(manifest_version, str) and manifest_version:
            return manifest_version
    except (OSError, ValueError, json.JSONDecodeError):
        pass

    try:
        return package_version("life-index")
    except PackageNotFoundError:
        return "dev"


def get_version_info() -> Dict[str, Any]:
    return {
        "package_version": get_package_version(),
        "bootstrap_manifest": read_bootstrap_manifest(),
    }


def _raw_installed_package_version() -> str | None:
    try:
        return package_version("life-index")
    except PackageNotFoundError:
        return None


def _run_git_local(checkout: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


def _detect_local_git_worktree(checkout: Path) -> Dict[str, Any]:
    try:
        result = _run_git_local(checkout, ["--no-optional-locks", "status", "--porcelain"])
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "git status failed").strip()
            return {
                "git_worktree_dirty": None,
                "git_worktree_dirty_count": None,
                "git_worktree_dirty_error": detail,
            }
        dirty_lines = [line for line in result.stdout.splitlines() if line.strip()]
        return {
            "git_worktree_dirty": bool(dirty_lines),
            "git_worktree_dirty_count": len(dirty_lines),
            "git_worktree_dirty_error": None,
        }
    except Exception as exc:
        return {
            "git_worktree_dirty": None,
            "git_worktree_dirty_count": None,
            "git_worktree_dirty_error": str(exc),
        }


def _detect_local_git_freshness(checkout: Path | None) -> Dict[str, Any]:
    if checkout is None or not (checkout / ".git").exists():
        return {
            "git_freshness": "not_applicable",
            "git_upstream": None,
            "git_behind_count": None,
            "git_ahead_count": None,
            "git_error": None,
            "git_worktree_dirty": False,
            "git_worktree_dirty_count": 0,
            "git_worktree_dirty_error": None,
        }

    worktree_status = _detect_local_git_worktree(checkout)

    try:
        upstream_result = _run_git_local(
            checkout,
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        )
        upstream = upstream_result.stdout.strip() if upstream_result.returncode == 0 else ""
        if not upstream:
            ref_result = _run_git_local(checkout, ["rev-parse", "--verify", "origin/main"])
            upstream = "origin/main" if ref_result.returncode == 0 else ""
        if not upstream:
            return {
                "git_freshness": "unknown",
                "git_upstream": None,
                "git_behind_count": None,
                "git_ahead_count": None,
                "git_error": "No upstream branch or origin/main ref found",
                **worktree_status,
            }

        if "/" not in upstream:
            return {
                "git_freshness": "unknown",
                "git_upstream": upstream,
                "git_behind_count": None,
                "git_ahead_count": None,
                "git_error": (
                    "Upstream is not a remote-tracking branch; run "
                    "life-index upgrade --plan --json."
                ),
                **worktree_status,
            }

        remote, branch = upstream.split("/", 1)
        local_upstream_result = _run_git_local(checkout, ["rev-parse", upstream])
        if local_upstream_result.returncode != 0:
            detail = (
                local_upstream_result.stderr
                or local_upstream_result.stdout
                or "local upstream ref was not found"
            ).strip()
            return {
                "git_freshness": "unknown",
                "git_upstream": upstream,
                "git_behind_count": None,
                "git_ahead_count": None,
                "git_error": f"{detail}; run life-index upgrade --plan --json.",
                **worktree_status,
            }

        remote_result = _run_git_local(checkout, ["ls-remote", "--heads", remote, branch])
        if remote_result.returncode != 0:
            detail = (remote_result.stderr or remote_result.stdout or "remote probe failed").strip()
            return {
                "git_freshness": "unknown",
                "git_upstream": upstream,
                "git_behind_count": None,
                "git_ahead_count": None,
                "git_error": f"{detail}; run life-index upgrade --plan --json.",
                **worktree_status,
            }

        remote_head = next(
            (
                line.split()[0]
                for line in remote_result.stdout.splitlines()
                if len(line.split()) >= 2
            ),
            None,
        )
        local_upstream_head = local_upstream_result.stdout.strip()
        if not remote_head:
            return {
                "git_freshness": "unknown",
                "git_upstream": upstream,
                "git_behind_count": None,
                "git_ahead_count": None,
                "git_error": ("Remote branch was not found; run life-index upgrade --plan --json."),
                **worktree_status,
            }
        if remote_head != local_upstream_head:
            return {
                "git_freshness": "unknown",
                "git_upstream": upstream,
                "git_behind_count": None,
                "git_ahead_count": None,
                "git_error": (
                    "Remote tip differs from the local tracking ref; exact ancestry is "
                    "unknown without updating refs. Run life-index upgrade --plan --json."
                ),
                **worktree_status,
            }

        count_result = _run_git_local(
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
                **worktree_status,
            }

        ahead_text, behind_text = count_result.stdout.strip().split()[:2]
        ahead = int(ahead_text)
        behind = int(behind_text)
        return {
            "git_freshness": "behind" if behind > 0 else "current",
            "git_upstream": upstream,
            "git_behind_count": behind,
            "git_ahead_count": ahead,
            "git_error": None,
            **worktree_status,
        }
    except Exception as exc:
        return {
            "git_freshness": "unknown",
            "git_upstream": None,
            "git_behind_count": None,
            "git_ahead_count": None,
            "git_error": str(exc),
            **worktree_status,
        }


def _detect_upgrade_freshness_state() -> Dict[str, Any]:
    """Local-only session freshness signal for health output."""
    manifest = read_bootstrap_manifest()
    manifest_version = manifest.get("repo_version")
    if not isinstance(manifest_version, str):
        manifest_version = None

    installed_version = _raw_installed_package_version()
    checkout = BOOTSTRAP_MANIFEST_PATH.parent
    install_type = "editable" if (checkout / ".git").exists() else "package"
    git_status = _detect_local_git_freshness(checkout if install_type == "editable" else None)

    update_reasons: list[str] = []
    if installed_version and manifest_version and installed_version != manifest_version:
        update_reasons.append("install_mismatch")
    if int(git_status.get("git_behind_count") or 0) > 0:
        update_reasons.append("git_behind")

    freshness_error = git_status.get("git_error")
    suggested_refresh_step: str | None = None
    if update_reasons or freshness_error:
        suggested_refresh_step = "life-index upgrade --plan --json"

    return {
        "installed_version": installed_version,
        "manifest_version": manifest_version,
        "install_type": install_type,
        "freshness": (
            "update_available" if update_reasons else "unknown" if freshness_error else "current"
        ),
        "update_available": (
            ("git-behind" if "git_behind" in update_reasons else "install-mismatch")
            if update_reasons
            else None
        ),
        "update_reasons": update_reasons,
        "suggested_refresh_step": suggested_refresh_step,
        "freshness_error": freshness_error,
        **git_status,
    }


def _check_upgrade_freshness() -> Tuple[Dict[str, Any], str]:
    try:
        state = _detect_upgrade_freshness_state()
    except Exception as exc:
        check: Dict[str, Any] = {
            "name": "upgrade_freshness",
            "status": "info",
            "freshness": "unknown",
            "installed_version": None,
            "manifest_version": None,
            "install_type": "unknown",
            "update_available": None,
            "update_reasons": [],
            "suggested_refresh_step": None,
            "freshness_error": str(exc),
            "changelog": CHANGELOG_POINTER,
            "git": {
                "freshness": "unknown",
                "upstream": None,
                "behind_count": None,
                "ahead_count": None,
                "error": str(exc),
                "dirty": None,
                "dirty_count": None,
                "dirty_error": str(exc),
            },
            "suggested_command": None,
        }
        return check, ""

    update_reasons = list(state.get("update_reasons") or [])
    dirty_worktree = state.get("git_worktree_dirty") is True
    status = (
        "warning"
        if update_reasons or dirty_worktree
        else "info" if state.get("freshness_error") else "ok"
    )
    suggested_refresh_step = state.get("suggested_refresh_step")
    if suggested_refresh_step:
        suggested_refresh_step = "life-index upgrade --plan --json"

    check = {
        "name": "upgrade_freshness",
        "status": status,
        "freshness": state.get("freshness", "unknown"),
        "installed_version": state.get("installed_version"),
        "manifest_version": state.get("manifest_version"),
        "install_type": state.get("install_type", "unknown"),
        "update_available": state.get("update_available"),
        "update_reasons": update_reasons,
        "suggested_refresh_step": suggested_refresh_step,
        "freshness_error": state.get("freshness_error"),
        "changelog": CHANGELOG_POINTER,
        "git": {
            "freshness": state.get("git_freshness"),
            "upstream": state.get("git_upstream"),
            "behind_count": state.get("git_behind_count"),
            "ahead_count": state.get("git_ahead_count"),
            "error": state.get("git_error"),
            "dirty": state.get("git_worktree_dirty"),
            "dirty_count": state.get("git_worktree_dirty_count"),
            "dirty_error": state.get("git_worktree_dirty_error"),
        },
        "suggested_command": (DIRTY_WORKTREE_SUGGESTED_COMMAND if dirty_worktree else None),
    }

    if check["suggested_refresh_step"]:
        check["suggested_refresh_step_side_effect"] = "read"
        check["suggested_refresh_step_side_effect_note"] = UPGRADE_REFRESH_NOTE

    if dirty_worktree:
        check["warning"] = DIRTY_WORKTREE_WARNING
        check["side_effect"] = "read"
        check["side_effect_note"] = REPO_RECOVERY_NOTE

    if not update_reasons:
        return check, ""

    reason = str(state.get("update_available") or ",".join(update_reasons))
    step = check["suggested_refresh_step"] or "life-index bootstrap --json"
    issue = (
        f"Life Index upgrade freshness reports {reason}; run: {step}; "
        f"then follow the returned onboarding pointer. See {CHANGELOG_POINTER}."
    )
    check["issue"] = issue
    return check, issue


def _check_python_version() -> Tuple[Dict[str, Any], str, bool]:
    """检查 Python 版本"""
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    check = {
        "name": "python_version",
        "status": "ok" if py_ok else "error",
        "value": py_version,
        "required": ">=3.11",
    }
    issue = f"Python {py_version} is too old. Requires >=3.11." if not py_ok else ""
    return check, issue, not py_ok


def _check_venv() -> Tuple[Dict[str, Any], str]:
    """检查虚拟环境"""
    in_venv = sys.prefix != sys.base_prefix
    venv_path = sys.prefix if in_venv else None
    check = {
        "name": "virtual_env",
        "status": "ok" if in_venv else "warning",
        "active": in_venv,
        "path": venv_path,
    }
    if not in_venv:
        issue = (
            "Not running inside a virtual environment. "
            "Recommended: create venv with 'python -m venv .venv' in skill directory."
        )
    else:
        issue = ""
    return check, issue


def _check_pyyaml() -> Tuple[Dict[str, Any], str, bool]:
    """检查 pyyaml 依赖"""
    try:
        import yaml

        yaml_version = getattr(yaml, "__version__", "unknown")
        return (
            {
                "name": "pyyaml",
                "status": "ok",
                "version": yaml_version,
            },
            "",
            False,
        )
    except ImportError:
        return (
            {
                "name": "pyyaml",
                "status": "error",
                "version": None,
            },
            "pyyaml is not installed. Run: pip install pyyaml",
            True,
        )


def _check_data_dir() -> Tuple[Dict[str, Any], str]:
    """检查数据目录"""
    data_dir = get_user_data_dir()
    journals_dir = get_journals_dir()
    data_exists = data_dir.exists()
    journal_count = count_journal_files(journals_dir)
    check = {
        "name": "data_directory",
        "status": "ok" if data_exists else "info",
        "path": str(data_dir),
        "exists": data_exists,
        "journal_count": journal_count,
        "last_journal_date": _latest_journal_date(journals_dir),
    }
    if not data_exists:
        issue = (
            f"Data directory not found: {data_dir}. "
            "It will be created automatically on first journal write."
        )
    else:
        issue = ""
    return check, issue


def _check_index() -> Tuple[Dict[str, Any], str]:
    """检查索引状态"""
    data_dir = get_user_data_dir()
    index_dir = data_dir / ".index"
    fts_db = index_dir / "journals_fts.db"
    data_exists = get_user_data_dir().exists()
    semantic = {
        "status": "disabled",
        "reason": "in-tool semantic/vector search has been removed",
    }
    check = {
        "name": "search_index",
        "status": "ok" if fts_db.exists() else "info",
        "fts_index_exists": fts_db.exists(),
        "vector_index_exists": False,
        "semantic_status": "disabled",
        "semantic": semantic,
        "path": str(index_dir),
    }
    if not fts_db.exists() and data_exists:
        check["suggested_command"] = "life-index index"
        check["side_effect"] = "write"
        check["side_effect_note"] = DERIVED_INDEX_NOTE
        return check, "Search index not built. Run: life-index index"
    return check, ""


def _check_entity_graph(graph_path: Path) -> Dict[str, Any]:
    """Check if entity graph exists and is populated (Round 10, T1.3)."""
    check: Dict[str, Any] = {
        "name": "entity_graph",
        "status": "ok",
        "entity_count": 0,
        "suggested_command": None,
    }

    if not graph_path.exists():
        check["status"] = "warning"
        check["issue"] = "Entity graph not found — run review when candidates appear"
        check["suggested_command"] = "life-index entity --review"
        check["side_effect"] = "read"
        check["side_effect_note"] = READ_ONLY_ENTITY_REVIEW_NOTE
        check["maintenance"] = _build_entity_maintenance(graph_path, exists=False)
        return check

    try:
        from tools.lib.entity_graph import load_entity_graph

        entities = load_entity_graph(graph_path)
        check["entity_count"] = len(entities)
        maintenance = _build_entity_maintenance(graph_path, entities=entities)
        check["maintenance"] = maintenance

        if len(entities) == 0:
            check["status"] = "warning"
            check["issue"] = "Entity graph is empty — run review when candidates appear"
            check["suggested_command"] = "life-index entity --review"
            check["side_effect"] = "read"
            check["side_effect_note"] = READ_ONLY_ENTITY_REVIEW_NOTE
        elif maintenance["traffic_light"] == "red":
            check["status"] = "warning"
            check["issue"] = "Entity graph needs review — run life-index entity --review"
            check["suggested_command"] = "life-index entity --review"
            check["side_effect"] = "read"
            check["side_effect_note"] = READ_ONLY_ENTITY_REVIEW_NOTE
        elif maintenance["traffic_light"] == "yellow":
            check["status"] = "warning"
            check["issue"] = "Entity graph has pending maintenance — run life-index entity --review"
            check["suggested_command"] = "life-index entity --review"
            check["side_effect"] = "read"
            check["side_effect_note"] = READ_ONLY_ENTITY_REVIEW_NOTE
    except Exception as e:
        check["status"] = "warning"
        check["issue"] = f"Entity graph error: {e}"
        check["suggested_command"] = "life-index entity --review"
        check["side_effect"] = "read"
        check["side_effect_note"] = READ_ONLY_ENTITY_REVIEW_NOTE
        check["maintenance"] = _build_entity_maintenance(
            graph_path,
            exists=True,
            structure_error=str(e),
        )

    return check


def _build_entity_maintenance(
    graph_path: Path,
    *,
    entities: List[Dict[str, Any]] | None = None,
    exists: bool = True,
    structure_error: str | None = None,
) -> Dict[str, Any]:
    """Build the session-visible entity maintenance traffic light."""
    from datetime import datetime, timezone

    review_command = "life-index entity --review"
    audit_age_days: int | None = None
    if graph_path.exists():
        modified = datetime.fromtimestamp(graph_path.stat().st_mtime, tz=timezone.utc)
        audit_age_days = (datetime.now(timezone.utc) - modified).days

    pending_count = 0
    duplicate_count = 0
    if entities is None:
        entities = []

    if structure_error is None and entities:
        pending_count = sum(
            1 for entity in entities if entity.get("status", "confirmed") == "candidate"
        )
        pending_count += sum(
            1
            for entity in entities
            for relationship in entity.get("relationships", []) or []
            if relationship.get("status", "confirmed") == "candidate"
        )
        duplicate_count = _count_confirmed_duplicate_names(entities)

    if structure_error or duplicate_count:
        traffic_light = "red"
        reason = structure_error or "duplicate confirmed entities require review"
    elif pending_count or (audit_age_days is not None and audit_age_days > 30) or not exists:
        traffic_light = "yellow"
        reason = "pending review items or stale audit"
    else:
        traffic_light = "green"
        reason = "no pending entity review items"

    suggested_next_step: Dict[str, Any] = {
        "command": review_command,
        "reason": reason,
        "side_effect": "read",
        "side_effect_note": READ_ONLY_ENTITY_REVIEW_NOTE,
    }
    if traffic_light == "green" and pending_count == 0:
        suggested_next_step = {
            "command": None,
            "reason": "no pending entity review items",
        }

    return {
        "traffic_light": traffic_light,
        "pending_count": pending_count,
        "audit_age_days": audit_age_days,
        "duplicate_count": duplicate_count,
        "review_command": review_command,
        "suggested_next_step": suggested_next_step,
    }


def _count_confirmed_duplicate_names(entities: List[Dict[str, Any]]) -> int:
    names: Dict[str, int] = {}
    for entity in entities:
        if entity.get("status", "confirmed") != "confirmed":
            continue
        values = [entity.get("primary_name", ""), *entity.get("aliases", [])]
        seen_entity_names: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value.strip():
                continue
            seen_entity_names.add(" ".join(value.casefold().split()))
        for name in seen_entity_names:
            names[name] = names.get(name, 0) + 1
    return sum(1 for count in names.values() if count > 1)


def _check_index_tree() -> Dict[str, Any]:
    """Check Index Tree freshness using existing check_index_tree_freshness()."""
    check: Dict[str, Any] = {
        "name": "index_tree",
        "status": "ok",
        "freshness_status": None,
        "total_nodes": 0,
        "issues": [],
        "suggested_command": None,
    }

    try:
        from tools.generate_index.navigation import check_index_tree_freshness

        result = check_index_tree_freshness(level="month")
        check["freshness_status"] = result.get("status")
        check["total_nodes"] = result.get("total_nodes", 0)
        issues = result.get("issues", [])

        if result.get("status") == "empty_tree":
            check["status"] = "info"
            check["issue"] = f"Index Tree is empty — run '{INDEX_TREE_REBUILD_COMMAND}' to build"
            check["suggested_command"] = INDEX_TREE_REBUILD_COMMAND
            check["side_effect"] = "write"
            check["side_effect_note"] = DERIVED_INDEX_NOTE
        elif issues:
            check["status"] = "warning"
            check["issues"] = issues
            stale_count = sum(1 for i in issues if i.get("freshness") == "stale")
            missing_count = sum(1 for i in issues if i.get("freshness") == "missing_index")
            parts = []
            if stale_count:
                parts.append(f"{stale_count} stale")
            if missing_count:
                parts.append(f"{missing_count} missing")
            check["issue"] = (
                f"Index Tree has {' and '.join(parts)} nodes — run "
                f"'{INDEX_TREE_REBUILD_COMMAND}'"
            )
            check["suggested_command"] = INDEX_TREE_REBUILD_COMMAND
            check["side_effect"] = "write"
            check["side_effect_note"] = DERIVED_INDEX_NOTE
        else:
            check["status"] = "ok"
    except Exception as e:
        check["status"] = "info"
        check["issue"] = f"Could not check Index Tree: {e}"

    return check


def _record_health_issue(check: Dict[str, Any], issue: str, issues: List[str]) -> None:
    check["issue"] = issue
    issues.append(issue)


def _classify_health_issues(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    actionable: List[str] = []
    chronic: List[str] = []

    for check in checks:
        issue = check.get("issue")
        if not isinstance(issue, str) or not issue:
            continue

        if check.get("name") in CHRONIC_HEALTH_CHECKS:
            check["issue_class"] = "chronic_debt"
            chronic.append(issue)
        else:
            check["issue_class"] = "actionable"
            actionable.append(issue)

    return {
        "actionable_issues": actionable,
        "chronic_debt": chronic,
        "issue_summary": {
            "actionable_count": len(actionable),
            "chronic_debt_count": len(chronic),
            "non_blocking_count": len(chronic),
        },
    }


def build_health_payload() -> Dict[str, Any]:
    """Build the canonical health domain envelope without printing it.

    检查项:
    1. Python 版本 (>=3.11)
    2. 虚拟环境状态
    3. 核心依赖 (pyyaml)
    4. 数据目录
    5. 索引状态
    """
    checks: List[Dict[str, Any]] = []
    issues: List[str] = []
    has_critical = False

    # 1. Python version
    check, issue, critical = _check_python_version()
    checks.append(check)
    if issue:
        _record_health_issue(check, issue, issues)
    has_critical = has_critical or critical

    # 2. Virtual environment
    check, issue = _check_venv()
    checks.append(check)
    if issue:
        _record_health_issue(check, issue, issues)

    # 3. Core dependency: pyyaml
    check, issue, critical = _check_pyyaml()
    checks.append(check)
    if issue:
        _record_health_issue(check, issue, issues)
    has_critical = has_critical or critical

    # 4. Data directory
    check, issue = _check_data_dir()
    checks.append(check)
    if issue:
        _record_health_issue(check, issue, issues)

    # 5. Index status
    check, issue = _check_index()
    checks.append(check)
    if issue:
        _record_health_issue(check, issue, issues)

    # 6. Entity graph (Round 10, T1.3)
    from tools.lib.paths import resolve_user_data_dir

    graph_path = resolve_user_data_dir() / "entity_graph.yaml"
    check = _check_entity_graph(graph_path)
    entity_maintenance = check.get("maintenance", {})
    checks.append(check)
    if check.get("issue"):
        issues.append(check["issue"])

    # 9. Index Tree freshness
    check = _check_index_tree()
    checks.append(check)
    if check.get("issue"):
        issues.append(check["issue"])

    # Session-visible upgrade freshness; non-blocking unless an update signal is present.
    upgrade_check, issue = _check_upgrade_freshness()
    checks.append(upgrade_check)
    if issue:
        _record_health_issue(upgrade_check, issue, issues)

    issue_groups = _classify_health_issues(checks)

    # Build result
    overall = "healthy" if not has_critical else "unhealthy"
    if not has_critical and issues:
        overall = "degraded"

    result: Dict[str, Any] = {
        "success": True,
        "schema_version": HEALTH_SCHEMA_VERSION,
        "data": {
            "status": overall,
            "checks": checks,
            "upgrade_freshness": upgrade_check,
            "entity_maintenance": entity_maintenance,
            "issues": issues,
            "issue_count": len(issues),
            **issue_groups,
        },
    }

    # Attach piggyback events
    from tools.lib.events import detect_events
    from tools.lib.event_detectors import register_all_detectors

    register_all_detectors()
    context = {"journals_dir": get_journals_dir(), "data_dir": get_user_data_dir()}
    events = detect_events(context=context)
    result["events"] = [e.to_dict() for e in events]

    return result


def health_check() -> None:
    """Print the canonical health domain envelope for the direct CLI."""
    print(json.dumps(build_health_payload(), ensure_ascii=False, indent=2))


def _run_data_audit() -> None:
    """Run Data Doctor audit summary and print health-compatible JSON result."""
    from tools.maintenance.audit import run_audit

    audit = run_audit(data_dir=get_user_data_dir())
    summary = audit.get("summary", {})
    total_issues = int(summary.get("total_issues", 0) or 0)
    preview_limit = 10
    result = {
        "success": True,
        "schema_version": HEALTH_SCHEMA_VERSION,
        "data": {
            "status": "ok" if total_issues == 0 else "issues_found",
            "source": "maintenance audit",
            "issue_count": total_issues,
            "summary": summary,
            "detectors": audit.get("detectors", []),
            "issues_preview": (audit.get("issues", []) or [])[:preview_limit],
            "preview_limit": preview_limit,
            "truncated": total_issues > preview_limit,
            "next_command": "life-index maintenance audit --json",
            "plan_command_template": "life-index maintenance plan --issue-id <issue-id> --json",
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def print_health_usage() -> None:
    """Print health command usage without running health checks."""
    print("Usage: life-index health [options]")
    print("       python -m tools health [options]")
    print()
    print("Options:")
    print("  --json         Emit health JSON output (default).")
    print("  --data-audit   Summarize Data Doctor audit and next steps (JSON).")
    print("  --cache-audit  Run read-only cache version audit (JSON).")
    print("  --help, -h     Show this help text.")


def main() -> None:
    """Unified CLI entry point"""
    _restore_import_stdout()
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    subcmd = sys.argv[1]
    if subcmd == "health" and any(arg in ("--help", "-h", "help") for arg in sys.argv[2:]):
        print_health_usage()
        return

    if subcmd not in ("--help", "-h", "help"):
        try:
            enforce_validation_mode_data_dir()
        except ValidationModeDataDirError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(2)

    # Handle health check directly (no submodule import needed)
    if subcmd == "health":
        if "--cache-audit" in sys.argv[2:]:
            from tools.lib.metadata_cache import run_cache_audit

            report = run_cache_audit()
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif "--data-audit" in sys.argv[2:]:
            _run_data_audit()
        else:
            health_check()
        return

    if subcmd == "--version":
        print(json.dumps(get_version_info(), ensure_ascii=False, indent=2))
        return

    # Map subcommands to __main__ module paths
    # Each submodule has its own __main__.py with a main() function
    cmd_map = {
        "write": "tools.write_journal.__main__",
        "confirm": "tools.write_journal.__main__",
        "search": "tools.search_journals.__main__",
        "edit": "tools.edit_journal.__main__",
        "journal": "tools.journal.__main__",
        "attachment": "tools.attachment.__main__",
        "entity": "tools.entity.__main__",
        "weather": "tools.query_weather.__main__",
        "index": "tools.build_index.__main__",
        "generate-index": "tools.generate_index.__main__",
        "abstract": "tools.generate_index.__main__",
        "backup": "tools.backup.__main__",
        "verify": "tools.verify.__main__",  # Task 1.3.2
        "timeline": "tools.timeline.__main__",  # Task 3.2
        "migrate": "tools.migrate.__main__",  # Round 6 Phase 1
        "eval": "tools.eval.__main__",
        "entity-graph-eval": "tools.eval.ablation.__main__",
        "smart-search": "tools.smart_search.__main__",
        "aggregate": "tools.aggregate.__main__",
        "analyze": "tools.aggregate.__main__",
        "on-this-day": "tools.on_this_day.__main__",
        "recall": "tools.recall.__main__",
        "maintenance": "tools.maintenance.__main__",
        "bootstrap": "tools.bootstrap.__main__",
        "sync-skill": "tools.sync_skill.__main__",
        "upgrade": "tools.upgrade.__main__",
        "trajectory": "tools.trajectory.__main__",
        "import": "tools.ingest.__main__",
        "index-tree": "tools.index_tree.__main__",
    }

    if subcmd in cmd_map:
        # Rewrite argv so the submodule's argparse works correctly
        # Keep the original argv[0] for proper error messages
        sys.argv = [f"life-index {subcmd}"] + sys.argv[2:]

        # Import and run the submodule's main()
        module = __import__(cmd_map[subcmd], fromlist=["main"])
        ret = module.main()
        if isinstance(ret, int):
            sys.exit(ret)
    elif subcmd in ("-V", "version"):
        print(json.dumps(get_version_info(), ensure_ascii=False, indent=2))
    elif subcmd in ("--help", "-h", "help"):
        print_usage()
    else:
        print(f"Unknown command: {subcmd}")
        print_usage()
        sys.exit(1)


def print_usage() -> None:
    """Print usage information"""
    print("Usage: life-index <command> [options]")
    print("       python -m tools <command> [options]")
    print()
    print("Commands:")
    print("  write     Write a journal entry")
    print("  confirm   Apply write confirmation updates")
    print("  search    Search journals")
    print("  edit      Edit a journal entry")
    print("  journal   Read journals through stable get/list contracts")
    print("  attachment  Read/export/stream archived attachments")
    print("  entity    Manage entity graph")
    print("  weather   Query weather information")
    print("  index     Build/rebuild search index")
    print("  generate-index  Generate index tree and entity profile docs")
    print("  abstract        Alias for generate-index")
    print("  backup    Backup journal data")
    print("  verify    Verify data integrity")
    print("  timeline  Output chronological summary stream")
    print("  on-this-day  Find prior-year entries on same month/day")
    print("  recall    Deprecated compatibility wrapper over search")
    print("  trajectory  Typed observations (weight/sleep/mood/location/project)")
    print("  migrate   Schema migration tool")
    print("  eval      Run search evaluation gate")
    print("  entity-graph-eval  Run graph ablation evaluation")
    print("  maintenance  Run maintenance cycle (dry-run health checks)")
    print("  bootstrap  Detect install/data state and route onboarding (read-only)")
    print("  sync-skill  Synchronize SKILL.md and references into host skill directory")
    print("  upgrade   Plan/apply deterministic host-agent CLI upgrade steps")
    print("  smart-search  Deterministic evidence scaffold for host agents")
    print("  aggregate  Deterministic counts, buckets, and claim envelopes")
    print("  analyze   Alias for deterministic aggregate counts")
    print("  health    Check installation health")
    print("            --data-audit  Summarize Data Doctor audit and next steps")
    print("            --cache-audit  Read-only cache version audit (JSON)")
    print("  import    Import provider (plan, run, status, rollback)")
    print("  index-tree  Index Tree Evidence Navigation")
    print("  version   Show package and bootstrap manifest version info")
    print()
    print("Run 'life-index <command> --help' for command-specific options.")
    print()
    print("Developer mode:")
    print("  python -m tools.write_journal --data '{...}'")
    print("  python -m tools.search_journals --query '关键词'")


if __name__ == "__main__":
    main()
