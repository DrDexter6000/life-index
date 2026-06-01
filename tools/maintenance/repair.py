"""Low-risk maintenance repair execution."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .plan import build_plan

REPAIR_SCHEMA_VERSION = "m33.maintenance_repair.v0"


def _data_dir(data_dir: str | Path | None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    override = os.environ.get("LIFE_INDEX_DATA_DIR")
    if override:
        return Path(override)
    return Path.home() / "Documents" / "Life-Index"


def _file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if not root.exists():
        return hashes
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed = set(before) ^ set(after)
    changed.update(path for path in before.keys() & after.keys() if before[path] != after[path])
    return sorted(changed)


def _allowed_generated_index_path(path: str) -> bool:
    if path == "INDEX.md":
        return True
    parts = path.split("/")
    if len(parts) == 3 and parts[0] == "Journals" and parts[2] == f"index_{parts[1]}.md":
        return True
    return (
        len(parts) == 4 and parts[0] == "Journals" and parts[3] == f"index_{parts[1]}-{parts[2]}.md"
    )


def _allowed_index_cache_path(path: str) -> bool:
    return (
        path.startswith(".index/")
        or path.startswith(".cache/")
        or path.startswith(".life-index/cache/")
    )


def _run_subprocess(args: list[str], root: Path) -> tuple[int, str]:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(root)
    proc = subprocess.run(
        [sys.executable, "-m", "tools", *args],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _base_payload(issue_id: str, dry_run: bool, planned_paths: list[str]) -> dict[str, Any]:
    return {
        "success": True,
        "schema_version": REPAIR_SCHEMA_VERSION,
        "command": "maintenance repair",
        "issue_id": issue_id,
        "dry_run": dry_run,
        "applied": False,
        "planned_paths": planned_paths,
        "changed_paths": [],
        "error": None,
    }


def run_repair(
    data_dir: str | Path | None,
    issue_id: str,
    *,
    apply: bool,
) -> tuple[dict[str, Any], int]:
    plan, plan_exit = build_plan(data_dir=data_dir, issue_id=issue_id)
    if plan_exit != 0:
        return (
            {
                "success": False,
                "schema_version": REPAIR_SCHEMA_VERSION,
                "command": "maintenance repair",
                "issue_id": issue_id,
                "dry_run": not apply,
                "applied": False,
                "planned_paths": [],
                "changed_paths": [],
                "error": plan.get("error"),
            },
            plan_exit,
        )

    planned_paths = list(plan.get("touched_paths", []) or [])
    payload = _base_payload(issue_id, dry_run=not apply, planned_paths=planned_paths)
    if not plan.get("repairable"):
        payload["success"] = False
        payload["error"] = {
            "code": "MAINTENANCE_REPAIR_NOT_ALLOWED",
            "message": "Issue is not eligible for automatic maintenance repair.",
        }
        return payload, 2

    if not apply:
        return payload, 0

    root = _data_dir(data_dir)
    before = _file_hashes(root)
    issue_domain = plan.get("domain")
    issue_type = plan.get("type")

    if issue_domain == "layout" and issue_type == "missing_generated_index":
        code, output = _run_subprocess(["generate-index", "--rebuild", "--json"], root)
        allowed = _allowed_generated_index_path
    elif issue_domain == "search_index" and issue_type == "missing_rebuildable_index":
        code, output = _run_subprocess(["index", "--rebuild", "--fts-only", "--json"], root)
        allowed = _allowed_index_cache_path
    else:
        payload["success"] = False
        payload["error"] = {
            "code": "MAINTENANCE_REPAIR_NOT_IMPLEMENTED",
            "message": "No automatic repair implementation exists for this issue type.",
        }
        return payload, 2

    after = _file_hashes(root)
    changed = _changed_paths(before, after)
    payload["changed_paths"] = changed
    payload["applied"] = code == 0

    unsafe = [path for path in changed if not allowed(path)]
    if code != 0:
        payload["success"] = False
        payload["applied"] = False
        payload["error"] = {
            "code": "MAINTENANCE_REPAIR_COMMAND_FAILED",
            "message": "Underlying rebuild command failed.",
            "detail": output[-500:],
        }
        return payload, 1
    if unsafe:
        payload["success"] = False
        payload["error"] = {
            "code": "MAINTENANCE_REPAIR_UNSAFE_CHANGED_PATH",
            "message": "Repair changed paths outside the derived-artifact allowlist.",
            "paths": unsafe,
        }
        return payload, 1
    return payload, 0


__all__ = ["REPAIR_SCHEMA_VERSION", "run_repair"]
