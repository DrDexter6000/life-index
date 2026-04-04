#!/usr/bin/env python3
"""
Life Index - Verify Command CLI Entry Point
"""

import argparse
import json
import sys

from .core import run_verify
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
        description="Life Index - Verify Data Integrity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    life-index verify
    life-index verify --json
        """,
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format (default)",
    )

    args = parser.parse_args()
    ensure_dirs()

    result = run_verify()
    _emit_json(result)

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
