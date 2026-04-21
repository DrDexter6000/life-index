#!/usr/bin/env python3
"""
Life Index - Get Command CLI Entry Point

# Added for v2.0 GUI backend (Phase 1.9 SSOT fix)
# Contract: returns JSON to stdout, errors to stderr, non-zero exit on failure
"""

import argparse
import json
import sys

from .core import get_journal
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
        description="Life Index - Retrieve a single journal entry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    life-index get life-index_2026-04-19_001
    life-index get life-index_2026-04-19_001 --format json
        """,
    )

    parser.add_argument(
        "id",
        help="Journal ID (filename without .md extension)",
    )

    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default=None,
        help="Output format (default: human-readable text)",
    )

    args = parser.parse_args()
    ensure_dirs()

    result = get_journal(args.id)

    if result is None:
        print(f"Journal not found: {args.id}", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        _emit_json(result)
    else:
        # Human-readable output
        print(f"Title:   {result['title']}")
        print(f"Date:    {result['date']}")
        if result.get("location"):
            print(f"Location: {result['location']}")
        if result.get("weather"):
            print(f"Weather:  {result['weather']}")
        if result.get("mood"):
            print(f"Mood:     {', '.join(result['mood'])}")
        if result.get("tags"):
            print(f"Tags:     {', '.join(result['tags'])}")
        print()
        print(result["content"])


if __name__ == "__main__":
    main()
