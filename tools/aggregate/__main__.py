#!/usr/bin/env python3
"""Life Index aggregate CLI entry point.

Usage:
    life-index aggregate --range YYYY-MM-DD..YYYY-MM-DD \\
        --unit <unit> --predicate <predicate> [--json] [--explain]
    python -m tools aggregate --range ... --unit ... \\
        --predicate ... --json
"""

import argparse
import json
import sys

from tools.aggregate.core import run_aggregate

SCHEMA_VERSION = "m16.aggregate.v0"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="life-index aggregate",
        description=("Deterministic aggregate/trend " "computation over journal entries."),
    )
    parser.add_argument(
        "--range",
        required=True,
        dest="range_str",
        help="Date range YYYY-MM-DD..YYYY-MM-DD (inclusive).",
    )
    parser.add_argument(
        "--unit",
        required=True,
        help="Aggregation unit.",
    )
    parser.add_argument(
        "--predicate",
        required=True,
        help=(
            "Whitelisted predicate expression "
            "(e.g. journal_count, "
            "entry_time_after=22:00, "
            "term_presence=TERM, "
            "field_equals=FIELD:VALUE)."
        ),
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        default=False,
        help="Include human-readable interpretation.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        default=False,
        help="Output full JSON contract.",
    )
    parser.add_argument(
        "--query",
        default="",
        help="Original natural-language query (stored in output, not used for computation).",
    )

    args = parser.parse_args()

    result = run_aggregate(
        range_str=args.range_str,
        unit=args.unit,
        predicate=args.predicate,
        query=args.query,
        explain=args.explain,
    )

    result["schema_version"] = SCHEMA_VERSION

    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)

    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
