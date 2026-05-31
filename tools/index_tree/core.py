#!/usr/bin/env python3
"""Read-only public Index Tree Evidence Navigation payload builders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from tools.generate_index.builder import NAVIGABLE_SIGNALS, build_index_tree_model

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
