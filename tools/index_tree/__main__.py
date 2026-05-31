#!/usr/bin/env python3
"""CLI entry point for Index Tree Evidence Navigation."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .core import build_lens_payload, build_nodes_payload, build_shadow_payload


def _emit(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="life-index index-tree",
        description="Read-only Index Tree Evidence Navigation",
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

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.subcommand == "nodes":
        payload = build_nodes_payload(level=args.level)
    elif args.subcommand == "lens":
        payload = build_lens_payload(signal=args.signal)
    elif args.subcommand == "shadow":
        payload = build_shadow_payload(query=args.query)
    else:
        raise AssertionError(f"unreachable subcommand: {args.subcommand}")

    _emit(payload)
    sys.exit(0 if payload.get("success") else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
