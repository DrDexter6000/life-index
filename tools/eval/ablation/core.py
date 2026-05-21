"""Core ablation runner: 8 search pipeline combinations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from unittest import mock

from .metrics import precision_at_k, recall_at_k, mrr_at_k


def run_ablation(queries_path: Path) -> dict[str, Any]:
    """Run graph ablation evaluation across 8 search pipeline combinations.

    Combinations: entity_graph={True,False} × semantic={True,False} × hybrid={True,False}

    For each combination, runs hierarchical_search on every query in the fixture.
    Computes P@5, R@5, MRR@5 aggregated across all queries.

    Args:
        queries_path: Path to the JSON fixture file with ablation queries.

    Returns:
        Dict with schema_version, combinations list, and query_count.
    """
    with open(queries_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    if not isinstance(queries, list):
        raise ValueError("Fixture must be a JSON array of query objects")

    query_count = len(queries)
    combinations: list[dict[str, Any]] = []

    # 8 combinations: 2^3
    for entity_graph in (True, False):
        for semantic in (True, False):
            for hybrid in (True, False):
                metrics = _run_combination(
                    queries=queries,
                    entity_graph=entity_graph,
                    semantic=semantic,
                    hybrid=hybrid,
                )
                combinations.append(
                    {
                        "entity_graph": entity_graph,
                        "semantic": semantic,
                        "hybrid": hybrid,
                        "precision_at_5": metrics["precision_at_5"],
                        "recall_at_5": metrics["recall_at_5"],
                        "mrr_at_5": metrics["mrr_at_5"],
                        "query_count": query_count,
                    }
                )

    return {
        "schema_version": "gbrain-ablation.v1",
        "combinations": combinations,
        "query_count": query_count,
    }


def _run_combination(
    *,
    queries: list[dict[str, Any]],
    entity_graph: bool,
    semantic: bool,
    hybrid: bool,
) -> dict[str, float]:
    """Run a single search pipeline combination and aggregate metrics.

    entity_graph=False: mock expand_query_with_entity_graph to return query unchanged.
    semantic=False: pass semantic=False to hierarchical_search.
    hybrid=True: use semantic_policy="hybrid"; hybrid=False: use semantic_policy="fallback".
    """
    from tools.search_journals.core import (  # noqa: F401 — needed for mock.patch target
        hierarchical_search,
        expand_query_with_entity_graph,
    )

    semantic_policy: Literal["hybrid", "fallback"] = "hybrid" if hybrid else "fallback"

    total_precision = 0.0
    total_recall = 0.0
    total_mrr = 0.0
    n = len(queries)

    # Build the mock for entity_graph=False
    def _identity_expand(query: str) -> str:
        return query

    # Import the module to patch
    # The entity expansion is called from core.py's hierarchical_search function,
    # so we need to mock at the call site: tools.search_journals.core.expand_query_with_entity_graph
    patcher = mock.patch(
        "tools.search_journals.core.expand_query_with_entity_graph",
        side_effect=_identity_expand,
    )
    should_patch = not entity_graph

    if should_patch:
        patcher.start()

    try:
        for query_obj in queries:
            query_text = str(query_obj.get("query", ""))
            expected_ids = set(str(fid) for fid in query_obj.get("expected_relevant_ids", []))

            result = hierarchical_search(
                query=query_text,
                semantic=semantic,
                semantic_policy=semantic_policy,
            )

            merged_results = result.get("merged_results", [])
            if not isinstance(merged_results, list):
                merged_results = []

            p5 = precision_at_k(merged_results, expected_ids, k=5)
            r5 = recall_at_k(merged_results, expected_ids, k=5)
            m5 = mrr_at_k(merged_results, expected_ids, k=5)

            total_precision += p5
            total_recall += r5
            total_mrr += m5
    finally:
        if should_patch:
            patcher.stop()

    if n == 0:
        return {"precision_at_5": 0.0, "recall_at_5": 0.0, "mrr_at_5": 0.0}

    return {
        "precision_at_5": round(total_precision / n, 4),
        "recall_at_5": round(total_recall / n, 4),
        "mrr_at_5": round(total_mrr / n, 4),
    }
