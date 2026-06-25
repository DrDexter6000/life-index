"""Low-risk maintenance repair execution."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .plan import build_plan

REPAIR_SCHEMA_VERSION = "m33.maintenance_repair.v0"
_TIMESTAMPED_JOURNAL_COPY_RE = re.compile(
    r"^(life-index_\d{4}-\d{2}-\d{2}_\d+)_\d{8}_\d{6}_\d{6}(?:_\d+)?\.md$"
)
_TIMESTAMPED_COPY_ARCHIVE_ROOT = ".trash/maintenance/timestamped-journal-copies"
_ENTITY_GRAPH_BACKUP_ARCHIVE_ROOT = ".trash/maintenance/entity-graph-backups"


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
    if path.startswith(".life-index/index-b/"):
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


def _is_relative_inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _canonical_rel_for_timestamped_copy(rel_path: str) -> str | None:
    path = Path(rel_path)
    match = _TIMESTAMPED_JOURNAL_COPY_RE.match(path.name)
    if not match:
        return None
    return path.with_name(f"{match.group(1)}.md").as_posix()


def _archive_destination(root: Path, rel_path: str, source_bytes: bytes) -> Path:
    base = root / _TIMESTAMPED_COPY_ARCHIVE_ROOT / rel_path
    if not base.exists():
        return base
    stem = base.stem
    suffix = base.suffix
    digest = hashlib.sha256(source_bytes).hexdigest()[:12]
    return base.with_name(f"{stem}.{digest}{suffix}")


def _archive_destination_under(
    root: Path, archive_root: str, rel_path: str, source_bytes: bytes
) -> Path:
    base = root / archive_root / rel_path
    if not base.exists():
        return base
    stem = base.stem
    suffix = base.suffix
    digest = hashlib.sha256(source_bytes).hexdigest()[:12]
    return base.with_name(f"{stem}.{digest}{suffix}")


def _archive_loose_timestamped_copy(root: Path, planned_paths: list[str]) -> tuple[int, str]:
    duplicate_rel = next(
        (path for path in planned_paths if _canonical_rel_for_timestamped_copy(path) is not None),
        None,
    )
    if duplicate_rel is None:
        return 2, "No timestamped journal copy path was present in the repair plan."

    canonical_rel = _canonical_rel_for_timestamped_copy(duplicate_rel)
    if canonical_rel is None:
        return 2, "Timestamped journal copy path did not match the expected filename contract."

    source = root / duplicate_rel
    canonical = root / canonical_rel
    if not _is_relative_inside(root, source) or not _is_relative_inside(root, canonical):
        return 2, "Repair path escapes LIFE_INDEX_DATA_DIR."
    if not source.is_file():
        return 2, "Timestamped journal copy is no longer present."
    if not canonical.is_file():
        return 2, "Canonical journal original is missing."
    if ".revisions" in source.parts:
        return 2, "Timestamped copy is already inside .revisions; refusing automatic archive."

    source_bytes = source.read_bytes()
    canonical.read_bytes()
    destination = _archive_destination(root, duplicate_rel, source_bytes)
    if not _is_relative_inside(root, destination):
        return 2, "Archive destination escapes LIFE_INDEX_DATA_DIR."
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    if destination.read_bytes() != source_bytes:
        return 2, "Archived timestamped copy failed byte-for-byte verification."
    return 0, ""


def _archive_entity_graph_backup(root: Path, planned_paths: list[str]) -> tuple[int, str]:
    backup_rel = next(
        (path for path in planned_paths if Path(path).name.startswith("entity_graph.yaml.backup")),
        None,
    )
    if backup_rel is None:
        return 2, "No entity_graph.yaml backup path was present in the repair plan."

    source = root / backup_rel
    canonical = root / "entity_graph.yaml"
    if not _is_relative_inside(root, source) or not _is_relative_inside(root, canonical):
        return 2, "Repair path escapes LIFE_INDEX_DATA_DIR."
    if not source.is_file():
        return 2, "Entity graph backup copy is no longer present."
    if not canonical.is_file():
        return 2, "Canonical entity_graph.yaml is missing."
    if source.name == "entity_graph.yaml":
        return 2, "Refusing to archive the canonical entity_graph.yaml."

    source_bytes = source.read_bytes()
    canonical.read_bytes()
    destination = _archive_destination_under(
        root, _ENTITY_GRAPH_BACKUP_ARCHIVE_ROOT, backup_rel, source_bytes
    )
    if not _is_relative_inside(root, destination):
        return 2, "Archive destination escapes LIFE_INDEX_DATA_DIR."
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    if destination.read_bytes() != source_bytes:
        return 2, "Archived entity graph backup failed byte-for-byte verification."
    return 0, ""


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
    elif issue_domain == "revisions" and issue_type == "loose_timestamped_journal_copy":
        duplicate_rel = next(
            (
                path
                for path in planned_paths
                if _canonical_rel_for_timestamped_copy(path) is not None
            ),
            "",
        )
        code, output = _archive_loose_timestamped_copy(root, planned_paths)

        def allowed(path: str) -> bool:
            return path == duplicate_rel or path.startswith(f"{_TIMESTAMPED_COPY_ARCHIVE_ROOT}/")

    elif issue_domain == "revisions" and issue_type == "entity_graph_backup_copy":
        backup_rel = next(
            (
                path
                for path in planned_paths
                if Path(path).name.startswith("entity_graph.yaml.backup")
            ),
            "",
        )
        code, output = _archive_entity_graph_backup(root, planned_paths)

        def allowed(path: str) -> bool:
            return path == backup_rel or path.startswith(f"{_ENTITY_GRAPH_BACKUP_ARCHIVE_ROOT}/")

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
