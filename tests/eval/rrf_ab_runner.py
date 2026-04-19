#!/usr/bin/env python3
"""
RRF_MIN_SCORE A/B Runner — Round 10 Phase 2 Task 2.0.

Runs the eval gate for each candidate RRF_MIN_SCORE value and produces
a comparison table for data-driven threshold selection.

Usage:
    python -m tests.eval.rrf_ab_runner
    python -m pytest tests/eval/rrf_ab_runner.py -v --timeout=300
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

# Candidate values per TDD T2.0 §Task 2.0
CANDIDATES: list[float] = [0.005, 0.008, 0.012]


def _write_fixture_data(data_dir: Path) -> None:
    """Write eval fixture data using the shared fixture from test_eval_runner."""
    from tests.unit.test_eval_runner import _write_eval_fixture_data

    _write_eval_fixture_data(data_dir)


def _run_eval_with_rrf_score(
    candidate_value: float,
    data_dir: Path,
) -> dict[str, Any]:
    """Run eval with a specific RRF_MIN_SCORE value.

    Temporarily patches the constant, rebuilds the index, runs eval,
    then restores the original value.
    """
    import tools.lib.search_constants as constants_mod
    import tools.lib.paths as paths_mod
    import tools.lib.config as cfg_mod
    import tools.lib.search_index as si_mod
    import tools.lib.fts_update as fu_mod
    import tools.lib.fts_search as fs_mod
    import tools.search_journals.ranking as ranking_mod
    import tools.search_journals.semantic as sem_mod
    import tools.search_journals.core as core_mod
    import tools.lib.semantic_search as ss_mod
    import tools.lib.vector_index_simple as vis_mod
    import tools.lib.metadata_cache as mc_mod
    import tools.build_index as bi_mod
    from tools.lib.chinese_tokenizer import reset_tokenizer_state

    original_value = constants_mod.RRF_MIN_SCORE
    original_env = os.environ.get("LIFE_INDEX_DATA_DIR")

    # Patch the constant
    constants_mod.RRF_MIN_SCORE = candidate_value

    try:
        # Reload ranking to pick up patched constant
        importlib.reload(ranking_mod)

        # Set up isolated data directory BEFORE reloading paths
        os.environ["LIFE_INDEX_DATA_DIR"] = str(data_dir)

        # Reload ALL modules in correct dependency order.
        # paths reads LIFE_INDEX_DATA_DIR at module level, so must be first.
        importlib.reload(paths_mod)
        importlib.reload(cfg_mod)
        importlib.reload(mc_mod)
        importlib.reload(si_mod)
        importlib.reload(fu_mod)
        importlib.reload(fs_mod)
        importlib.reload(vis_mod)
        importlib.reload(ss_mod)
        importlib.reload(sem_mod)
        importlib.reload(core_mod)
        importlib.reload(bi_mod)
        reset_tokenizer_state()

        # Build BOTH FTS + vector indexes via build_all().
        # update_index() only builds FTS; RRF fusion requires the vector
        # index (vectors_simple.pkl) to be present for semantic search.
        idx_result = bi_mod.build_all(incremental=False)
        fts_ok = idx_result.get("fts", {}).get("success", False)
        vec_ok = idx_result.get("vector", {}).get("success", False)
        if not fts_ok:
            return {
                "candidate": candidate_value,
                "error": (
                    f"Index build failed: "
                    f"FTS={idx_result.get('fts')} "
                    f"Vector={idx_result.get('vector')}"
                ),
            }
        vec_added = idx_result.get("vector", {}).get("added", 0)
        print(f"  [BUILD] FTS OK, Vector: {vec_added} embeddings")

        # Run eval — MUST use semantic=True so RRF fusion is active.
        # RRF_MIN_SCORE only filters hybrid (keyword + semantic) results;
        # pure keyword mode bypasses RRF entirely, making the threshold
        # irrelevant and all candidates identical.
        from tools.eval.run_eval import run_evaluation, load_golden_queries

        result = run_evaluation(
            data_dir=data_dir,
            use_semantic=True,
            judge="keyword",
        )

        # Compute rejection pass rate
        queries = load_golden_queries()
        rejection_queries = [
            q for q in queries
            if q.get("expected", {}).get("min_results", -1) == 0
        ]
        rejection_total = len(rejection_queries)

        per_query = result.get("per_query", [])
        rejection_passes = sum(
            1 for pq in per_query
            if pq.get("expected_min_results") == 0 and pq.get("pass", False)
        )
        rejection_pass_rate = (
            rejection_passes / rejection_total if rejection_total > 0 else 0.0
        )

        # Compute average result count
        avg_result_count = (
            sum(pq.get("results_found", 0) for pq in per_query) / len(per_query)
            if per_query
            else 0.0
        )

        # Compute positive query metrics (queries with min_results > 0)
        positive_queries = [
            pq for pq in per_query if pq.get("expected_min_results", 0) > 0
        ]
        positive_mrr = (
            sum(pq.get("reciprocal_rank", 0.0) for pq in positive_queries)
            / len(positive_queries)
            if positive_queries
            else 0.0
        )
        positive_p5 = (
            sum(pq.get("precision_at_5", 0.0) for pq in positive_queries)
            / len(positive_queries)
            if positive_queries
            else 0.0
        )

        return {
            "candidate": candidate_value,
            "metrics": result.get("metrics", {}),
            "positive_mrr_at_5": round(positive_mrr, 4),
            "positive_precision_at_5": round(positive_p5, 4),
            "rejection_total": rejection_total,
            "rejection_passes": rejection_passes,
            "rejection_pass_rate": round(rejection_pass_rate, 4),
            "avg_result_count": round(avg_result_count, 2),
            "total_queries": result.get("total_queries", 0),
            "failures": len(result.get("failures", [])),
            "per_query": per_query,
        }

    finally:
        # Restore original value
        constants_mod.RRF_MIN_SCORE = original_value

        # Restore env
        if original_env is None:
            os.environ.pop("LIFE_INDEX_DATA_DIR", None)
        else:
            os.environ["LIFE_INDEX_DATA_DIR"] = original_env

        # Reload ALL modules to restore original state (same order as setup)
        importlib.reload(paths_mod)
        importlib.reload(ranking_mod)
        importlib.reload(cfg_mod)
        importlib.reload(mc_mod)
        importlib.reload(si_mod)
        importlib.reload(fu_mod)
        importlib.reload(fs_mod)
        importlib.reload(vis_mod)
        importlib.reload(ss_mod)
        importlib.reload(sem_mod)
        importlib.reload(core_mod)
        importlib.reload(bi_mod)
        reset_tokenizer_state()


def run_ab_experiment(candidates: list[float] | None = None) -> list[dict[str, Any]]:
    """Run A/B experiment for all candidate RRF_MIN_SCORE values.

    Returns list of result dicts, one per candidate.
    """
    import tempfile

    if candidates is None:
        candidates = CANDIDATES

    results: list[dict[str, Any]] = []

    for candidate in candidates:
        print(f"\n{'='*60}")
        print(f"RRF_MIN_SCORE = {candidate}")
        print(f"{'='*60}")

        with tempfile.TemporaryDirectory(prefix="life_index_ab_") as tmp:
            data_dir = Path(tmp) / "Life-Index"
            data_dir.mkdir(parents=True, exist_ok=True)

            _write_fixture_data(data_dir)
            result = _run_eval_with_rrf_score(candidate, data_dir)
            results.append(result)

            if "error" in result:
                print(f"  ERROR: {result['error']}")
            else:
                print(f"  MRR@5:          {result['positive_mrr_at_5']:.4f}")
                print(f"  P@5:            {result['positive_precision_at_5']:.4f}")
                print(f"  Rejection rate: {result['rejection_pass_rate']:.2%}"
                      f" ({result['rejection_passes']}/{result['rejection_total']})")
                print(f"  Avg results:    {result['avg_result_count']:.1f}")
                print(f"  Failures:       {result['failures']}")

    return results


def select_best_candidate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Select the best candidate based on T2.0 selection rules.

    Priority:
    1. rejection_pass_rate >= 90%
    2. avg_result_count in [3, 15]
    3. highest positive_mrr_at_5
    """
    qualified = []

    for r in results:
        if "error" in r:
            continue
        if r["rejection_pass_rate"] >= 0.90:
            qualified.append(r)

    if not qualified:
        # Fallback: pick the one with highest rejection rate
        valid = [r for r in results if "error" not in r]
        if not valid:
            return {"error": "No valid candidates"}
        qualified = sorted(valid, key=lambda x: x["rejection_pass_rate"], reverse=True)
        return {
            "selected": qualified[0],
            "warning": "No candidate achieved >= 90% rejection pass rate",
            "all_results": results,
        }

    # Filter by result count window
    in_window = [r for r in qualified if 3 <= r["avg_result_count"] <= 15]
    if not in_window:
        in_window = qualified  # Relax if none fit

    # Pick highest MRR@5
    best = sorted(in_window, key=lambda x: x["positive_mrr_at_5"], reverse=True)[0]

    return {
        "selected": best,
        "all_results": results,
    }


def format_comparison_table(results: list[dict[str, Any]]) -> str:
    """Format results as a markdown comparison table."""
    lines = [
        "| candidate | MRR@5 | P@5 | rejection_pass_rate | avg_result_count | failures |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        if "error" in r:
            lines.append(f"| {r['candidate']} | ERROR | - | - | - | - |")
        else:
            lines.append(
                f"| {r['candidate']} | {r['positive_mrr_at_5']:.4f} "
                f"| {r['positive_precision_at_5']:.4f} "
                f"| {r['rejection_pass_rate']:.2%} "
                f"({r['rejection_passes']}/{r['rejection_total']}) "
                f"| {r['avg_result_count']:.1f} "
                f"| {r['failures']} |"
            )
    return "\n".join(lines)


if __name__ == "__main__":
    # UTF-8 encoding protection — prevents UnicodeEncodeError on Windows
    # when printing characters like the warning triangle below
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

    results = run_ab_experiment()

    print(f"\n{'='*60}")
    print("COMPARISON TABLE")
    print(f"{'='*60}")
    print(format_comparison_table(results))

    selection = select_best_candidate(results)
    if "error" not in selection:
        selected = selection["selected"]
        print(f"\n{'='*60}")
        print(f"SELECTED: RRF_MIN_SCORE = {selected['candidate']}")
        print(f"{'='*60}")
        if "warning" in selection:
            print(f"[WARNING] {selection['warning']}")
    else:
        print(f"\nERROR: {selection.get('error', 'No valid candidates')}")
