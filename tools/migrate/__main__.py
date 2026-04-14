"""CLI entry point: life-index migrate [--dry-run] [--apply] [--version N]"""

from __future__ import annotations

import argparse
import json

from tools.lib.config import JOURNALS_DIR


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="life-index migrate",
        description="Schema migration tool for Life Index journals",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Scan and report without modifying files (default)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute deterministic migrations",
    )
    parser.add_argument(
        "--version",
        type=int,
        default=None,
        help="Target schema version (default: latest)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="Output as JSON (default)",
    )
    args = parser.parse_args()

    from tools.migrate import scan_journals

    if args.apply:
        from tools.migrate import apply_migrations

        report = apply_migrations(JOURNALS_DIR, target_version=args.version)
    else:
        report = scan_journals(JOURNALS_DIR)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
