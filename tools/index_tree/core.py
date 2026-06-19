#!/usr/bin/env python3
"""Read-only public Index Tree Evidence Navigation payload builders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from tools.generate_index.builder import NAVIGABLE_SIGNALS, build_index_tree_model
from tools.index_tree.materialize import (
    FACETS,
    INDEX_B_DIR,
    build_ensure_payload,
    _collect_entries,
    _facet_values,
    _parse_month,
)

SCHEMA_VERSION = "m31.index_tree.v1"


def _generated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _error_payload(
    command: str, code: str, message: str, details: dict[str, Any]
) -> dict[str, Any]:
    return {
        "success": False,
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "generated_at": _generated_at(),
        "data": None,
        "errors": [{"code": code, "message": message, "details": details}],
    }


def _success_payload(command: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "generated_at": _generated_at(),
        "data": data,
        "errors": [],
    }


def build_nodes_payload(level: str = "all") -> dict[str, Any]:
    try:
        model = build_index_tree_model(level=level)
    except ValueError as exc:
        return _error_payload(
            "index-tree.nodes",
            "INDEX_TREE_INVALID_LEVEL",
            str(exc),
            {"level": level},
        )
    return _success_payload(
        "index-tree.nodes",
        {
            "truth_source": "journals",
            "level": level,
            "nodes": model["nodes"],
        },
    )


def _empty_lens_item(value: str) -> dict[str, Any]:
    return {
        "value": value,
        "count": 0,
        "node_refs": [],
        "evidence_paths": [],
        "freshness": [],
    }


def _combine_coverage(nodes: list[dict[str, Any]], signal: str) -> dict[str, int]:
    coverage = {"entries_in_scope": 0, "present": 0, "parseable": 0}
    for node in nodes:
        node_coverage = node.get("signal_coverage", {}).get(signal, {})
        for key in coverage:
            coverage[key] += int(node_coverage.get(key, 0) or 0)
    return coverage


def build_lens_payload(signal: str) -> dict[str, Any]:
    if signal not in NAVIGABLE_SIGNALS:
        return _error_payload(
            "index-tree.lens",
            "INDEX_TREE_INVALID_SIGNAL",
            f"signal must be one of {list(NAVIGABLE_SIGNALS)}, got '{signal}'",
            {"signal": signal, "allowed": list(NAVIGABLE_SIGNALS)},
        )

    model = build_index_tree_model(level="month")
    nodes = model["nodes"]
    by_value: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_ref = None
        for entry in node.get("entry_refs", []):
            for value in entry.get("signals", {}).get(signal, []):
                item = by_value.setdefault(value, _empty_lens_item(value))
                item["count"] += 1
                item["evidence_paths"].append(entry["relative_path"])
                node_ref = entry.get("node_ref")
                if node_ref and node_ref not in item["node_refs"]:
                    item["node_refs"].append(node_ref)
                freshness = node.get("freshness")
                if freshness and freshness not in item["freshness"]:
                    item["freshness"].append(freshness)

    items = sorted(by_value.values(), key=lambda item: (-item["count"], item["value"]))
    return _success_payload(
        "index-tree.lens",
        {
            "truth_source": "journals",
            "privacy_level": "same_as_journals",
            "signal": signal,
            "coverage": _combine_coverage(nodes, signal),
            "items": items,
        },
    )


def _all_entry_paths(nodes: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for node in nodes:
        for entry in node.get("entry_refs", []):
            path = entry.get("relative_path")
            if isinstance(path, str) and path and path not in paths:
                paths.append(path)
    return paths


def build_shadow_payload(
    query: str,
    *,
    candidate_filter: Callable[[list[str]], list[str]] | None = None,
) -> dict[str, Any]:
    model = build_index_tree_model(level="month")
    nodes = model["nodes"]
    freshness_issues = [
        {
            "node_id": node["node_id"],
            "freshness": node["freshness"],
            "relative_path": node["relative_path"],
        }
        for node in nodes
        if node.get("freshness") in ("stale", "missing_index")
    ]
    if freshness_issues:
        return _success_payload(
            "index-tree.shadow",
            {
                "query": query,
                "enabled": False,
                "disabled_reason": "index_tree_not_fresh",
                "freshness_issues": freshness_issues,
                "baseline_paths": [],
                "shadow_candidate_paths": [],
                "recall_preserved": None,
                "dropped_paths": [],
                "diagnostic_only": True,
                "default_search_mutated": False,
                "default_smart_search_mutated": False,
            },
        )

    baseline_paths = _baseline_paths_by_scan(query, nodes)
    candidate_paths = _all_entry_paths(nodes)
    if candidate_filter is not None:
        candidate_paths = candidate_filter(candidate_paths)
    dropped_paths = [path for path in baseline_paths if path not in set(candidate_paths)]
    return _success_payload(
        "index-tree.shadow",
        {
            "query": query,
            "enabled": True,
            "disabled_reason": None,
            "freshness_issues": [],
            "baseline_paths": baseline_paths,
            "shadow_candidate_paths": candidate_paths,
            "recall_preserved": not dropped_paths,
            "dropped_paths": dropped_paths,
            "diagnostic_only": True,
            "default_search_mutated": False,
            "default_smart_search_mutated": False,
        },
    )


def _baseline_paths_by_scan(query: str, nodes: list[dict[str, Any]]) -> list[str]:
    needle = query.casefold()
    if not needle:
        return []
    matches: list[str] = []
    for node in nodes:
        for entry in node.get("entry_refs", []):
            haystack_parts = [
                str(entry.get("relative_path", "")),
                str(entry.get("title", "")),
                str(entry.get("date", "")),
            ]
            for values in entry.get("signals", {}).values():
                haystack_parts.extend(str(value) for value in values)
            haystack = " ".join(haystack_parts).casefold()
            if needle in haystack:
                path = entry.get("relative_path")
                if isinstance(path, str) and path not in matches:
                    matches.append(path)
    return matches


def _facet_specs_by_name() -> dict[str, Any]:
    return {spec.name: spec for spec in FACETS}


def _normalize_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            normalized.append(text)
    return normalized


def _validate_navigation_operations(operations: list[Any]) -> str | None:
    facet_specs = _facet_specs_by_name()
    for operation in operations:
        if not isinstance(operation, dict):
            return "operation must be an object"
        op_type = operation.get("type")
        if op_type != "facet_value_filter":
            return f"unsupported operation type: {op_type!r}"
        facet = operation.get("facet")
        if facet not in facet_specs:
            return f"facet must be one of {sorted(facet_specs)}, got {facet!r}"
        match = operation.get("match", "any")
        if match not in ("any", "all"):
            return f"match must be 'any' or 'all', got {match!r}"
        values = _normalize_values(operation.get("values"))
        if not values:
            return "facet_value_filter requires at least one non-empty value"
    return None


def _entry_matches_operation(entry: Any, operation: dict[str, Any]) -> bool:
    facet_specs = _facet_specs_by_name()
    facet = str(operation["facet"])
    spec = facet_specs[facet]
    wanted = {value.casefold() for value in _normalize_values(operation["values"])}
    actual = {value.casefold() for value in _facet_values(entry, spec)}
    if operation.get("match", "any") == "all":
        return wanted.issubset(actual)
    return bool(actual & wanted)


def _matched_facets(entry: Any, operations: list[dict[str, Any]]) -> dict[str, list[str]]:
    facet_specs = _facet_specs_by_name()
    facets: dict[str, list[str]] = {}
    for operation in operations:
        facet = str(operation["facet"])
        spec = facet_specs[facet]
        wanted = {value.casefold() for value in _normalize_values(operation["values"])}
        matched = [value for value in _facet_values(entry, spec) if value.casefold() in wanted]
        if matched:
            facets[facet] = matched
    return facets


def _entry_payload(entry: Any, operations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "date": entry.date,
        "title": entry.title,
        "path": entry.rel_path,
        "matched_facets": _matched_facets(entry, operations),
    }


def _navigation_docs_for_entries(entries: list[Any]) -> list[str]:
    docs: list[str] = [f"{INDEX_B_DIR}/INDEX.md"]
    seen: set[str] = set(docs)
    for entry in entries:
        for rel in (
            f"{INDEX_B_DIR}/Journals/{entry.year}/index.md",
            f"{INDEX_B_DIR}/Journals/{entry.year}/{entry.month}/index.md",
        ):
            if rel not in seen:
                seen.add(rel)
                docs.append(rel)
    return docs


def build_navigate_payload(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    operations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run deterministic structured navigation over the materialized Index B scope.

    ``operations`` is intentionally typed as a list of explicit operations rather
    than natural-language text.  P2a implements ``facet_value_filter`` only; P2b
    can add sibling operations such as entity-neighbor traversal without
    replacing this shape.
    """
    operations = operations or []
    invalid = _validate_navigation_operations(operations)
    if invalid:
        return _error_payload(
            "index-tree.navigate",
            "INDEX_TREE_NAVIGATE_INVALID_OPERATION",
            invalid,
            {"operations": operations},
        )

    try:
        start = _parse_month(date_from)
        end = _parse_month(date_to, fallback=start)
        if start is not None and end is not None and end < start:
            raise ValueError("--to must be greater than or equal to --from")
        ensured = build_ensure_payload(date_from=start, date_to=end)
    except ValueError as exc:
        return _error_payload(
            "index-tree.navigate",
            "INDEX_TREE_NAVIGATE_INVALID_RANGE",
            str(exc),
            {"date_from": date_from, "date_to": date_to},
        )

    scoped_entries = _collect_entries(start, end)
    matched_entries = [
        entry
        for entry in scoped_entries
        if all(_entry_matches_operation(entry, operation) for operation in operations)
    ]

    source = ensured.get("source") if isinstance(ensured, dict) else None
    if source not in ("index-b", "journals"):
        source = "index-b"

    data = {
        "truth_source": "journals",
        "privacy_level": "same_as_journals",
        "source": source,
        "artifact": ensured.get("artifact") if isinstance(ensured, dict) else "index-b",
        "date_from": start,
        "date_to": end,
        "operation_model": "deterministic_navigation.v1",
        "operations": operations,
        "exhaustive": True,
        "count": len(matched_entries),
        "entry_pointers": [entry.rel_path for entry in matched_entries],
        "entries": [_entry_payload(entry, operations) for entry in matched_entries],
        "navigation_docs": (
            _navigation_docs_for_entries(scoped_entries) if source == "index-b" else []
        ),
        "coverage": {
            "candidate_count_before_filters": len(scoped_entries),
            "candidate_count_after_filters": len(matched_entries),
            "filter_count": len(operations),
        },
        "freshness": (
            ensured.get("freshness") or ensured.get("freshness_before")
            if isinstance(ensured, dict)
            else None
        ),
        "fallback": ensured.get("fallback") if isinstance(ensured, dict) else None,
        "extension_points": ["entity_neighbors"],
    }
    return _success_payload("index-tree.navigate", data)
