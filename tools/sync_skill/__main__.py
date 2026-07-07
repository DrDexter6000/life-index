"""CLI entry point for syncing Life Index skill artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from importlib import import_module
from pathlib import Path

from tools.sync_skill import (
    SYNC_SKILL_SCHEMA_VERSION,
    find_host_skill_dir,
    install_target_from_host_home,
    list_host_skill_dirs,
    sync_skill_artifacts,
    uninstall_skill_artifacts,
)


def _default_source_root() -> Path:
    tools_package = import_module("tools")
    package_artifact_roots = [
        Path(raw_path) / "_skill_artifacts"
        for raw_path in getattr(tools_package, "__path__", ())
        if Path(raw_path).is_dir()
    ]
    candidates = [
        Path(__file__).resolve().parents[2],
        *package_artifact_roots,
    ]
    for candidate in candidates:
        if (candidate / "SKILL.md").is_file():
            return candidate
    return candidates[0]


def _emit_payload(payload: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    status = payload["data"]["status"]
    action = payload["data"].get("action", "sync")
    if action == "list":
        print(f"sync-skill: {status} (found={len(payload['data']['discovered'])})")
        for item in payload["data"]["discovered"]:
            print(f"  {item}")
    elif action == "refused":
        print(f"sync-skill: {status}")
    elif action == "uninstall":
        print(f"sync-skill: {status} (removed={len(payload['data']['removed'])})")
        for item in payload["data"]["removed"]:
            print(f"  removed {item}")
        for item in payload["data"]["skipped"]:
            print(f"  skipped {item['path']} ({item['reason']})")
    else:
        delivered = "true" if payload["data"].get("delivered") else "false"
        print(f"sync-skill: {status} (delivered={delivered})")
        for item in payload["data"]["copied"]:
            print(f"  {item}")
        playbook_status = payload["data"].get("playbook_status")
        changelog = payload["data"].get("changelog")
        if playbook_status and changelog:
            if playbook_status == "unchanged":
                print(f"  playbook unchanged; changelog: {changelog}")
            else:
                print(f"  playbook {playbook_status}; changelog: {changelog}")
        dedupe = payload["data"].get("dedupe") or {}
        if dedupe.get("status") in {"would_remove", "removed"}:
            print(f"  nested duplicate {dedupe['status']}: {dedupe['nested_dir']}")

    for diagnostic in payload["data"]["diagnostics"]:
        print(f"  [{diagnostic['code']}] {diagnostic['message']}", file=sys.stderr)


def _refused_payload(code: str, message: str) -> dict:
    return {
        "success": False,
        "schema_version": SYNC_SKILL_SCHEMA_VERSION,
        "command": "sync-skill",
        "data": {
            "status": "refused",
            "action": "refused",
            "removed": [],
            "skipped": [],
            "diagnostics": [{"code": code, "message": message}],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="life-index sync-skill",
        description=(
            "Synchronize SKILL.md and references into an existing host agent skill "
            "directory. Missing host directories are reported as a non-fatal skip "
            "unless --install is set."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--host-skill-dir",
        default=None,
        help="Host skill directory to update; with --install it may be created.",
    )
    parser.add_argument(
        "--host-home",
        default=None,
        help=(
            "Host home directory such as ~/.hermes or ~/.codex. Only used with "
            "--install; target is <host-home>/skills/life-index."
        ),
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Create the target skill directory before copying artifacts.",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove managed Life Index skill artifacts under explicit --host-home.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List discovered managed Life Index skill directories without mutation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="For --uninstall, report what would be removed without deleting.",
    )
    parser.add_argument(
        "--source-root",
        default=None,
        help="Life Index checkout root containing SKILL.md and references/.",
    )
    args = parser.parse_args()

    action_count = sum(1 for enabled in (args.install, args.uninstall, args.list) if enabled)
    if action_count > 1:
        payload = _refused_payload(
            "SYNC_SKILL_ACTION_CONFLICT",
            "Choose only one sync-skill action: --install, --uninstall, or --list.",
        )
        _emit_payload(payload, as_json=args.json)
        return 1
    if args.dry_run and not (args.uninstall or args.install):
        payload = _refused_payload(
            "DRY_RUN_REQUIRES_INSTALL_OR_UNINSTALL",
            "--dry-run is only valid with --install or --uninstall.",
        )
        _emit_payload(payload, as_json=args.json)
        return 1

    if args.list:
        host_homes = [Path(args.host_home)] if args.host_home else None
        payload = list_host_skill_dirs(host_homes=host_homes)
        _emit_payload(payload, as_json=args.json)
        return 0

    if args.uninstall:
        payload = uninstall_skill_artifacts(host_home=args.host_home, dry_run=args.dry_run)
        _emit_payload(payload, as_json=args.json)
        return 0 if payload["success"] else 1

    target_dir: Path | None
    diagnostics: list[dict[str, str]]
    if args.install:
        if args.host_skill_dir:
            target_dir = Path(args.host_skill_dir)
            diagnostics = []
        elif args.host_home:
            target_dir = install_target_from_host_home(args.host_home)
            diagnostics = []
        else:
            target_dir, diagnostics = find_host_skill_dir()
    else:
        target_dir, diagnostics = find_host_skill_dir(args.host_skill_dir)

    source_root = Path(args.source_root) if args.source_root else _default_source_root()
    payload = sync_skill_artifacts(
        source_root=source_root,
        target_dir=target_dir,
        install=args.install,
        dry_run=args.dry_run,
    )
    if diagnostics:
        existing_diagnostics = payload["data"].get("diagnostics", [])
        if (
            payload["data"]["status"] == "skipped"
            and existing_diagnostics
            and existing_diagnostics[0]["code"] == "HOST_SKILL_DIR_NOT_FOUND"
        ):
            payload["data"]["diagnostics"] = diagnostics
        else:
            payload["data"]["diagnostics"] = [*diagnostics, *existing_diagnostics]

    _emit_payload(payload, as_json=args.json)

    return 0 if payload["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
