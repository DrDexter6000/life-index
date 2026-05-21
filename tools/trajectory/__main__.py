"""Life Index - Trajectory CLI Entry Point"""

import argparse
import json
import sys

from .core import run_trajectory


def _emit_json(payload: dict) -> None:
    """Print JSON safely across Windows console encodings."""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        fallback_text = json.dumps(payload, ensure_ascii=True, indent=2)
        print(fallback_text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Life Index - Trajectory (typed observations)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    life-index trajectory --field=weight --range=2025-01..2025-12
    life-index trajectory --field=sleep --range=2025-06..2025-08
    life-index trajectory --field=mood --range=2025-01..2025-12
        """,
    )

    parser.add_argument(
        "--field",
        required=True,
        help="Typed observation field to extract (weight|sleep|mood|location|project).",
    )

    parser.add_argument(
        "--range",
        required=True,
        help="Month range YYYY-MM..YYYY-MM (inclusive).",
    )

    args = parser.parse_args()

    result = run_trajectory(
        field=args.field,
        range_str=args.range,
    )

    _emit_json(result)

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
