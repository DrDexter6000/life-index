#!/usr/bin/env python3
"""
Life Index - Build Index Tool - CLI Entry Point
索引构建工具（FTS + 向量索引）
"""

import argparse
import json
import sys

from . import build_all, show_stats
from ..lib.config import ensure_dirs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Life Index - Build Search Index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Daily incremental update (default)
    python -m tools.build_index

    # Full rebuild (monthly maintenance)
    python -m tools.build_index --rebuild

    # Only FTS index
    python -m tools.build_index --fts-only

    # View statistics
    python -m tools.build_index --stats
        """,
    )

    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Full rebuild (delete and recreate all indexes)",
    )

    parser.add_argument("--fts-only", action="store_true", help="Only update FTS index")

    parser.add_argument(
        "--vec-only", action="store_true", help="Only update vector index"
    )

    parser.add_argument("--stats", action="store_true", help="Show index statistics")

    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()
    ensure_dirs()

    if args.stats:
        show_stats()
        return

    # 执行索引构建
    result = build_all(
        incremental=not args.rebuild, fts_only=args.fts_only, vec_only=args.vec_only
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
