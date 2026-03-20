#!/usr/bin/env python3
"""Life Index - Backup Tool - CLI Entry Point"""

import argparse
import json
import sys
from pathlib import Path

from . import create_backup, restore_backup, list_backups
from ..lib.config import ensure_dirs


def main() -> None:
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Life Index - Backup Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # 增量备份到指定目录
    python -m tools.backup --dest /path/to/backup

    # 全量备份
    python -m tools.backup --dest /path/to/backup --full

    # 模拟运行（不实际复制文件）
    python -m tools.backup --dest /path/to/backup --dry-run

    # 列出所有备份
    python -m tools.backup --dest /path/to/backup --list

    # 从备份恢复
    python -m tools.backup --restore /path/to/backup/life-index-backup-20260101_120000
        """,
    )

    parser.add_argument("--dest", help="备份目标目录")
    parser.add_argument("--full", action="store_true", help="执行全量备份")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行")
    parser.add_argument("--list", action="store_true", help="列出备份记录")
    parser.add_argument("--restore", help="从指定备份恢复")

    args = parser.parse_args()
    ensure_dirs()

    if args.list:
        if not args.dest:
            print(
                json.dumps(
                    {"success": False, "error": "需要指定 --dest"},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            sys.exit(1)

        backups = list_backups(Path(args.dest))
        print(json.dumps({"success": True, "backups": backups}, ensure_ascii=False, indent=2))
        sys.exit(0)

    elif args.restore:
        result = restore_backup(args.restore, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["success"] else 1)

    elif args.dest:
        result = create_backup(
            dest_path=args.dest,
            full=args.full,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["success"] else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
