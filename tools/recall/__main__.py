#!/usr/bin/env python3
"""
Life Index - Recall Command CLI Entry Point

Usage:
    life-index recall --mode {default|recall|deep} --query "..."
"""

import argparse
import json
import sys

from .core import run_recall


def _emit_json(payload: dict) -> None:
    """Print JSON safely across Windows console encodings."""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        fallback_text = json.dumps(payload, ensure_ascii=True, indent=2)
        print(fallback_text)


def main() -> None:
    """CLI entry point for recall command."""
    parser = argparse.ArgumentParser(
        description="Life Index - Recall search (L3 module consuming L2 search)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  default  Pure FTS keyword search (fastest, most deterministic)
  recall   Hybrid search (FTS + semantic fallback)
  deep     Compatibility alias for deterministic recall

Examples:
    life-index recall --mode default --query "python"
    life-index recall --mode recall --query "family memories"
    life-index recall --mode deep --query "lessons from failures"
        """,
    )

    parser.add_argument(
        "--mode",
        required=True,
        choices=["default", "recall", "deep"],
        help="Search mode: default (FTS), recall (hybrid), deep (deterministic recall)",
    )

    parser.add_argument(
        "--query",
        required=True,
        help="Search query string",
    )

    args = parser.parse_args()

    result = run_recall(
        mode=args.mode,
        query=args.query,
    )

    _emit_json(result)

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
