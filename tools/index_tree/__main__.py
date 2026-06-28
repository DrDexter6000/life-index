#!/usr/bin/env python3
"""CLI entry point for Index Tree Evidence Navigation."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from tools.lib.tool_call_log import emit_tool_call_log

from .core import (
    build_discover_payload,
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

    nodes = subparsers.add_parser(
        "nodes",
        help="Debug-only legacy: emit Index Tree node summaries",
    )
    nodes.add_argument("--level", default="all", choices=["all", "root", "year", "month"])
    nodes.add_argument("--json", action="store_true", help="Emit JSON output")

    lens = subparsers.add_parser(
        "lens",
        help="Debug-only legacy: emit cross-time derived lens",
    )
    lens.add_argument("--signal", required=True, help="Signal: topic, people, or project")
    lens.add_argument("--json", action="store_true", help="Emit JSON output")

    shadow = subparsers.add_parser(
        "shadow",
        help="Debug-only legacy: emit search-shadow diagnostics",
    )
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

    discover = subparsers.add_parser(
        "discover",
        help="Return scoped deterministic facet value menus for host-agent selection",
    )
    discover.add_argument("--from", dest="date_from", help="Start month, YYYY-MM")
    discover.add_argument("--to", dest="date_to", help="End month, YYYY-MM")
    discover.add_argument(
        "--facet",
        action="append",
        default=[],
        help=(
            "Facet to include in the menu. Repeat to include multiple facets. "
            "Use content_term explicitly for observed journal-body terms."
        ),
    )
    discover.add_argument("--json", action="store_true", help="Emit JSON output")

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
            "for multiple allowed values in one facet. Use content_term=VALUE only "
            "with observed journal-body terms."
        ),
    )
    navigate.add_argument(
        "--entity-neighbors",
        action="append",
        default=[],
        metavar="ENTITY",
        help=(
            "Explicit entity-neighbor traversal. Repeat for multiple start entities. "
            "The host agent chooses entities; the tool only traverses graph edges."
        ),
    )
    navigate.add_argument(
        "--entity-relation",
        action="append",
        default=[],
        metavar="RELATION",
        help="Optional relationship type filter for --entity-neighbors. Repeatable.",
    )
    navigate.add_argument(
        "--entity-max-hops",
        type=int,
        default=1,
        help="Maximum relationship traversal depth for --entity-neighbors.",
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


def _parse_entity_neighbor_operations(
    entities: list[str],
    *,
    max_hops: int,
    relations: list[str],
) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    normalized_relations = [relation.strip() for relation in relations if relation.strip()]
    for entity in entities:
        text = entity.strip()
        if not text:
            operations.append({"type": "entity_neighbors", "entity": "", "max_hops": max_hops})
            continue
        operations.append(
            {
                "type": "entity_neighbors",
                "entity": text,
                "max_hops": max_hops,
                "relations": normalized_relations,
            }
        )
    return operations


def _log_index_tree_call(
    args: argparse.Namespace, payload: dict[str, Any], elapsed_ms: float
) -> None:
    if args.subcommand not in {"ensure", "discover", "navigate"}:
        return

    raw_data = payload.get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    raw_fallback = data.get("fallback")
    fallback: dict[str, Any] = raw_fallback if isinstance(raw_fallback, dict) else {}
    result: dict[str, Any] = {
        "source": data.get("source"),
        "fallback_used": fallback.get("used"),
    }
    if args.subcommand == "ensure":
        result["entry_count"] = data.get("entry_count")
    elif args.subcommand == "discover":
        raw_coverage = data.get("coverage")
        discover_coverage: dict[str, Any] = raw_coverage if isinstance(raw_coverage, dict) else {}
        raw_facets = data.get("facets")
        facets: dict[str, Any] = raw_facets if isinstance(raw_facets, dict) else {}
        result["candidate_count"] = discover_coverage.get("candidate_count")
        result["facet_value_counts"] = {
            name: facet.get("value_count")
            for name, facet in facets.items()
            if isinstance(facet, dict)
        }
    else:
        result["count"] = data.get("count")
        result["entry_pointers"] = data.get("entry_pointers", [])
        raw_entity_neighbors = data.get("entity_neighbors", [])
        entity_neighbors: list[Any] = (
            raw_entity_neighbors if isinstance(raw_entity_neighbors, list) else []
        )
        result["entity_neighbor_counts"] = [
            item.get("neighbor_count") for item in entity_neighbors if isinstance(item, dict)
        ]
        raw_coverage = data.get("coverage")
        navigate_coverage: dict[str, Any] = raw_coverage if isinstance(raw_coverage, dict) else {}
        result["candidate_count_before_filters"] = navigate_coverage.get(
            "candidate_count_before_filters"
        )
        result["candidate_count_after_filters"] = navigate_coverage.get(
            "candidate_count_after_filters"
        )

    raw_error = payload.get("error")
    error: dict[str, Any] | None = raw_error if isinstance(raw_error, dict) else None
    raw_errors = payload.get("errors")
    if error is None and isinstance(raw_errors, list) and raw_errors:
        first_error = raw_errors[0]
        error = first_error if isinstance(first_error, dict) else None

    params: dict[str, Any] = {
        "date_from": getattr(args, "date_from", None),
        "date_to": getattr(args, "date_to", None),
    }
    if args.subcommand == "navigate":
        params["filters"] = list(getattr(args, "filter", []) or [])
        entity_neighbors = list(getattr(args, "entity_neighbors", []) or [])
        entity_relations = list(getattr(args, "entity_relation", []) or [])
        if entity_neighbors:
            params["entity_neighbors"] = entity_neighbors
            params["entity_relations"] = entity_relations
            params["entity_max_hops"] = getattr(args, "entity_max_hops", None)
    if args.subcommand == "discover":
        params["facets"] = list(getattr(args, "facet", []) or [])

    emit_tool_call_log(
        f"index-tree.{args.subcommand}",
        params=params,
        result=result,
        elapsed_ms=elapsed_ms,
        success=bool(payload.get("success")),
        error_code=str(error.get("code")) if error else None,
    )


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    started = time.perf_counter()
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
    elif args.subcommand == "discover":
        payload = build_discover_payload(
            date_from=args.date_from,
            date_to=args.date_to,
            facets=args.facet,
        )
    elif args.subcommand == "navigate":
        operations = _parse_filter_operations(args.filter)
        operations.extend(
            _parse_entity_neighbor_operations(
                args.entity_neighbors,
                max_hops=args.entity_max_hops,
                relations=args.entity_relation,
            )
        )
        payload = build_navigate_payload(
            date_from=args.date_from,
            date_to=args.date_to,
            operations=operations,
        )
    else:
        raise AssertionError(f"unreachable subcommand: {args.subcommand}")

    _log_index_tree_call(args, payload, (time.perf_counter() - started) * 1000.0)
    _emit(payload)
    sys.exit(0 if payload.get("success") else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
