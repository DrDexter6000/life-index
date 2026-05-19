#!/usr/bin/env python3
"""
Life Index - On This Day Command CLI Entry Point
"""

import argparse
import json
import sys

from .core import run_on_this_day


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
        description="Life Index - On This Day",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    life-index on-this-day
    life-index on-this-day --date 2026-05-19 --years-back 5
    life-index on-this-day --date 2024-12-25 --limit 10
        """,
    )

    parser.add_argument(
        "--date",
        default=None,
        help="Target date (YYYY-MM-DD). Defaults to today.",
    )

    parser.add_argument(
        "--years-back",
        type=int,
        default=10,
        help="Number of years to scan back (default: 10).",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of matches to return (default: 20).",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="Output JSON (default and only format).",
    )

    args = parser.parse_args()

    result = run_on_this_day(
        date_str=args.date,
        years_back=args.years_back,
        limit=args.limit,
    )

    _emit_json(result)

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
