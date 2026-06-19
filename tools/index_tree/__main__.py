#!/usr/bin/env python3
"""CLI entry point for Index Tree Evidence Navigation."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .core import (
    _error_payload,
    _success_payload,
    build_lens_payload,
    build_navigate_payload,
    build_nodes_payload,
    build_shadow_payload,
)
from .materialize import build_materialize_payload
from .materialize import build_ensure_payload, build_freshness_payload


def _emit(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="life-index index-tree",
        description="Index Tree Evidence Navigation",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    nodes = subparsers.add_parser("nodes", help="Emit Index Tree node summaries")
    nodes.add_argument("--level", default="all", choices=["all", "root", "year", "month"])
    nodes.add_argument("--json", action="store_true", help="Emit JSON output")

    lens = subparsers.add_parser("lens", help="Emit cross-time derived lens")
    lens.add_argument("--signal", required=True, help="Signal: topic, people, or project")
    lens.add_argument("--json", action="store_true", help="Emit JSON output")

    shadow = subparsers.add_parser("shadow", help="Emit search-shadow diagnostics")
    shadow.add_argument("--query", required=True, help="Query to diagnose")
    shadow.add_argument("--json", action="store_true", help="Emit JSON output")

    materialize = subparsers.add_parser(
        "materialize",
        help="Write deterministic Index B facet navigation docs",
    )
    materialize.add_argument("--from", dest="date_from", help="Start month, YYYY-MM")
    materialize.add_argument("--to", dest="date_to", help="End month, YYYY-MM")
    materialize.add_argument(
        "--incremental",
        action="store_true",
        help="Only rewrite stale Index B scope docs",
    )
    materialize.add_argument("--dry-run", action="store_true", help="Plan docs without writing")
    materialize.add_argument("--json", action="store_true", help="Emit JSON output")

    freshness = subparsers.add_parser(
        "freshness",
        help="Check whether materialized Index B docs match journal hashes",
    )
    freshness.add_argument("--from", dest="date_from", help="Start month, YYYY-MM")
    freshness.add_argument("--to", dest="date_to", help="End month, YYYY-MM")
    freshness.add_argument("--json", action="store_true", help="Emit JSON output")

    ensure = subparsers.add_parser(
        "ensure",
        help="Ensure Index B is fresh or return journal fallback pointers",
    )
    ensure.add_argument("--from", dest="date_from", help="Start month, YYYY-MM")
    ensure.add_argument("--to", dest="date_to", help="End month, YYYY-MM")
    ensure.add_argument("--json", action="store_true", help="Emit JSON output")

    navigate = subparsers.add_parser(
        "navigate",
        help="Run deterministic structured navigation over Index B",
    )
    navigate.add_argument("--from", dest="date_from", help="Start month, YYYY-MM")
    navigate.add_argument("--to", dest="date_to", help="End month, YYYY-MM")
    navigate.add_argument(
        "--filter",
        action="append",
        default=[],
        metavar="FACET=VALUE",
        help=(
            "Explicit facet filter. Repeat for intersections. Use VALUE1||VALUE2 "
            "for multiple allowed values in one facet."
        ),
    )
    navigate.add_argument("--json", action="store_true", help="Emit JSON output")

    return parser.parse_args(argv)


def _parse_filter_operations(filters: list[str]) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    for item in filters:
        if "=" not in item:
            operations.append({"type": "invalid_filter", "raw": item})
            continue
        facet, raw_values = item.split("=", 1)
        values = [value.strip() for value in raw_values.split("||") if value.strip()]
        operations.append(
            {
                "type": "facet_value_filter",
                "facet": facet.strip(),
                "values": values,
                "match": "any",
            }
        )
    return operations


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.subcommand == "nodes":
        payload = build_nodes_payload(level=args.level)
    elif args.subcommand == "lens":
        payload = build_lens_payload(signal=args.signal)
    elif args.subcommand == "shadow":
        payload = build_shadow_payload(query=args.query)
    elif args.subcommand == "materialize":
        try:
            data = build_materialize_payload(
                date_from=args.date_from,
                date_to=args.date_to,
                dry_run=args.dry_run,
                incremental=args.incremental,
            )
            payload = _success_payload("index-tree.materialize", data)
        except ValueError as exc:
            payload = _error_payload(
                "index-tree.materialize",
                "INDEX_TREE_MATERIALIZE_INVALID_RANGE",
                str(exc),
                {"date_from": args.date_from, "date_to": args.date_to},
            )
    elif args.subcommand == "freshness":
        try:
            data = build_freshness_payload(date_from=args.date_from, date_to=args.date_to)
            payload = _success_payload("index-tree.freshness", data)
        except ValueError as exc:
            payload = _error_payload(
                "index-tree.freshness",
                "INDEX_TREE_FRESHNESS_INVALID_RANGE",
                str(exc),
                {"date_from": args.date_from, "date_to": args.date_to},
            )
    elif args.subcommand == "ensure":
        try:
            data = build_ensure_payload(date_from=args.date_from, date_to=args.date_to)
            payload = _success_payload("index-tree.ensure", data)
        except ValueError as exc:
            payload = _error_payload(
                "index-tree.ensure",
                "INDEX_TREE_ENSURE_INVALID_RANGE",
                str(exc),
                {"date_from": args.date_from, "date_to": args.date_to},
            )
    elif args.subcommand == "navigate":
        payload = build_navigate_payload(
            date_from=args.date_from,
            date_to=args.date_to,
            operations=_parse_filter_operations(args.filter),
        )
    else:
        raise AssertionError(f"unreachable subcommand: {args.subcommand}")

    _emit(payload)
    sys.exit(0 if payload.get("success") else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
