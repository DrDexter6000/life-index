#!/usr/bin/env python3
"""CLI entry point for maintenance cycle (gbrain Phase D).

Usage:
    python -m tools maintenance --dry-run
    python -m tools maintenance --dry-run --output=json
    python -m tools maintenance --dry-run --output=json --data-dir /tmp/test

The maintenance command is a dry-run/report-only cycle that aggregates
six health checks without any production writes. All external CLI calls
are delegated via subprocess.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import run_maintenance, format_text_report, to_json


def _attach_provenance(result: dict) -> dict:
    from ..lib.observability import build_provenance_envelope

    provenance_envelope = build_provenance_envelope(
        source_data=result,
        generator="maintenance",
        params={},
    )
    result["schema_version"] = provenance_envelope["schema_version"]
    result["provenance"] = provenance_envelope["provenance"]
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Life Index - Maintenance cycle (dry-run / report-only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m tools maintenance --dry-run
    python -m tools maintenance --dry-run --output=json
    python -m tools maintenance --dry-run --output=json --data-dir /tmp/sandbox
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run maintenance in dry-run/report-only mode (default).",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="text",
        choices=["text", "json"],
        help='Output format: "text" (default) or "json".',
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override data directory (sets LIFE_INDEX_DATA_DIR).",
    )

    args = parser.parse_args(argv)

    # Set data directory if provided
    data_dir: str | None = None
    if args.data_dir:
        data_dir = str(args.data_dir)
        import os

        os.environ["LIFE_INDEX_DATA_DIR"] = data_dir

    # Run maintenance checks
    result = run_maintenance(data_dir=data_dir)

    # Output
    if args.output == "json":
        result = _attach_provenance(result)
        text = to_json(result)
    else:
        text = format_text_report(result)

    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback for Windows console encoding issues
        if args.output == "json":
            import json

            print(json.dumps(result, ensure_ascii=True, indent=2))
        else:
            print(text.encode("ascii", errors="replace").decode("ascii"))

    # Always exit 0 for the command itself — check health is reported
    # in the output, not the exit code. A failing check does not mean
    # the maintenance command failed.
    sys.exit(0)


if __name__ == "__main__":
    main()
