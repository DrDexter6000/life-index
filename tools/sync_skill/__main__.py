"""CLI entry point for syncing Life Index skill artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.sync_skill import find_host_skill_dir, sync_skill_artifacts


def _default_source_root() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2],
        Path.cwd(),
    ]
    for candidate in candidates:
        if (candidate / "SKILL.md").is_file():
            return candidate
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="life-index sync-skill",
        description=(
            "Synchronize SKILL.md and references into an existing host agent skill "
            "directory. Missing host directories are reported as a non-fatal skip."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--host-skill-dir",
        default=None,
        help="Existing host skill directory to update.",
    )
    parser.add_argument(
        "--source-root",
        default=None,
        help="Life Index checkout root containing SKILL.md and references/.",
    )
    args = parser.parse_args()

    target_dir, diagnostics = find_host_skill_dir(args.host_skill_dir)
    source_root = Path(args.source_root) if args.source_root else _default_source_root()
    payload = sync_skill_artifacts(source_root=source_root, target_dir=target_dir)
    if diagnostics and payload["data"]["status"] != "synced":
        payload["data"]["diagnostics"] = diagnostics

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        status = payload["data"]["status"]
        print(f"sync-skill: {status}")
        for item in payload["data"]["copied"]:
            print(f"  {item}")
        for diagnostic in payload["data"]["diagnostics"]:
            print(f"  [{diagnostic['code']}] {diagnostic['message']}", file=sys.stderr)

    return 0 if payload["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
