#!/usr/bin/env python3
"""
Life Index - Stats Command CLI Entry Point

# Added for v2.0 GUI backend (Phase 1.9 SSOT fix)
# Contract: returns JSON to stdout, errors to stderr, non-zero exit on failure
"""

import argparse
import json
import sys

from .core import compute_stats
from ..lib.config import ensure_dirs


def _emit_json(payload: dict) -> None:
    """Print JSON safely across Windows console encodings."""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        fallback_text = json.dumps(payload, ensure_ascii=True, indent=2)
        print(fallback_text)


def main() -> None:
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Life Index - Dashboard statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    life-index stats
    life-index stats --format json
        """,
    )

    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default=None,
        help="Output format (default: human-readable table)",
    )

    args = parser.parse_args()
    ensure_dirs()

    try:
        stats = compute_stats()
    except Exception as e:
        print(f"Error computing stats: {e}", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        _emit_json(stats)
    else:
        # Human-readable table
        print("Life Index - Dashboard Statistics")
        print("=" * 36)
        print(f"  Total Journals : {stats['totalJournals']}")
        print(f"  Total Words    : {stats['totalWords']}")
        print(f"  Active Days    : {stats['activeDays']}")
        print(f"  Current Streak : {stats['streakDays']} day(s)")
        print(f"  Avg Words/Day  : {stats['avgWordsPerDay']}")
        if stats["topics"]:
            print()
            print("  Topics:")
            for t in stats["topics"]:
                print(f"    {t['name']}: {t['count']}")
        if stats["moods"]:
            print()
            print("  Moods:")
            for m in stats["moods"]:
                print(f"    {m['name']}: {m['count']}")
        print("=" * 36)


if __name__ == "__main__":
    main()
