#!/usr/bin/env python3
"""
Life Index - Timeline Command CLI Entry Point
"""

import argparse
import json
import sys

from .core import run_timeline
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
        description="Life Index - Timeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    life-index timeline --range 2026-01 2026-03
    life-index timeline --range 2026-01 2026-03 --topic work
        """,
    )

    parser.add_argument(
        "--range",
        nargs=2,
        required=True,
        metavar=("START", "END"),
        help="Date range (YYYY-MM YYYY-MM)",
    )

    parser.add_argument(
        "--topic",
        help="Filter by topic",
    )

    args = parser.parse_args()
    ensure_dirs()

    result = run_timeline(
        range_start=args.range[0],
        range_end=args.range[1],
        topic=args.topic,
    )
    _emit_json(result)

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
