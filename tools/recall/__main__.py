#!/usr/bin/env python3
"""
Life Index - Deprecated Recall Compatibility CLI Entry Point

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
        description=(
            "Life Index - Deprecated recall compatibility wrapper over `life-index search`"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Deprecated compatibility command:
  New host-agent flows should call search directly:
    FTS-only retrieval: life-index search --query "..." --no-semantic
    Normal retrieval:   life-index search --query "..."

Modes:
  default  Compatibility alias for search --no-semantic
  recall   Compatibility alias for search
  deep     Compatibility alias for search with effective_mode=recall

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
        help=(
            "Compatibility mode: default (search --no-semantic), "
            "recall (search), deep (search with effective_mode=recall)"
        ),
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
