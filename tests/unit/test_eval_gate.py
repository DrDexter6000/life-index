#!/usr/bin/env python3
"""Search eval quality gate — CI regression gate for search quality.

This module runs the search evaluation against isolated fixture data and
validates that:
1. The eval infrastructure is intact (completes without error)
2. All golden query categories are represented
3. Search returns results for queries that should have hits
4. Noise queries return zero results (rejection works)
5. Baseline comparison infrastructure works

The fixture-based eval uses keyword-mode judging (no LLM). It validates
structural correctness of the search pipeline, not absolute ranking quality.
For live ranking quality, use `life-index eval --live --judge llm`.
"""

import importlib
from pathlib import Path


# ---------------------------------------------------------------------------
# Eval profile constants — SSOT: tools/eval/golden_queries.yaml
#
# run_eval.run_evaluation() defaults to phase=2.  Queries with
# skip_until_phase > 2 are skipped.  The following constants reflect the
# *actual* categories present at phase 2.  If the gold set changes, update
# these constants to match — do NOT soften assertions to make CI green.
# ---------------------------------------------------------------------------
EVAL_PHASE2_REQUIRED_CATEGORIES = frozenset({
    "complex_query",
    "edge_case",
    "english_regression",
    "entity_expansion",
    "high_frequency",
    "noise_rejection",
    "time_range",
    "typo_precision",
})
# english_regression has only 1 query in phase 2; all others have >= 3.
# Using a uniform minimum of 1 keeps the assertion honest without hiding
# accidental category deletion.
EVAL_PHASE2_MIN_QUERY_COUNT = 1

# Categories whose queries are expected to return at least one result.
# This is a product-level contract, not a CI convenience.
EVAL_PHASE2_POSITIVE_CATEGORIES = frozenset({
    "english_regression",
})


def _write_eval_fixture_data(data_dir: Path) -> None:
    """Write the standard eval fixture dataset."""
    from tests.unit.test_eval_runner import _write_eval_fixture_data as _write

    _write(data_dir)


def test_eval_gate_completes_successfully(isolated_data_dir: Path) -> None:
    """CI gate: eval runs against isolated data without errors.

    This validates that the eval infrastructure, golden queries, and search
    pipeline are all wired together correctly.
    """
    _write_eval_fixture_data(isolated_data_dir)

    run_eval = importlib.import_module("tools.eval.run_eval")
    result = run_eval.run_evaluation(data_dir=isolated_data_dir)

    # Structural completeness checks
    assert result["total_queries"] >= 20, f"Expected >= 20 queries, got {result['total_queries']}"
    assert set(result["metrics"].keys()) >= {
        "mrr_at_5",
        "recall_at_5",
        "precision_at_5",
    }
    assert isinstance(result["per_query"], list)
    assert len(result["per_query"]) >= 20
    assert isinstance(result["failures"], list)


def test_eval_gate_categories_covered(isolated_data_dir: Path) -> None:
    """CI gate: all required golden query categories have coverage."""
    _write_eval_fixture_data(isolated_data_dir)

    run_eval = importlib.import_module("tools.eval.run_eval")
    result = run_eval.run_evaluation(data_dir=isolated_data_dir)

    by_category = result.get("by_category", {})
    for category in EVAL_PHASE2_REQUIRED_CATEGORIES:
        assert (
            category in by_category
        ), f"Missing eval category: {category}. Available: {list(by_category.keys())}"
        assert (
            by_category[category]["query_count"] >= EVAL_PHASE2_MIN_QUERY_COUNT
        ), f"Category {category} has only {by_category[category]['query_count']} queries"


def test_eval_gate_noise_rejection(isolated_data_dir: Path) -> None:
    """CI gate: most noise/boundary queries return zero results.

    Note: jieba tokenization may produce partial matches for single
    Chinese characters, so we allow up to 1 noise query with results.
    The pure punctuation and pure English noise queries must still be 0.
    """
    _write_eval_fixture_data(isolated_data_dir)

    run_eval = importlib.import_module("tools.eval.run_eval")
    result = run_eval.run_evaluation(data_dir=isolated_data_dir)

    noise_queries = [pq for pq in result["per_query"] if pq.get("category") == "noise_rejection"]
    assert len(noise_queries) >= 3, f"Expected >= 3 noise queries, got {len(noise_queries)}"

    # Pure punctuation and pure English noise must return 0
    strict_noise = [
        nq for nq in noise_queries if all(ord(c) < 128 or c in "！？" for c in nq["query"])
    ]
    for nq in strict_noise:
        assert (
            nq["results_found"] == 0
        ), f"Strict noise query '{nq['query']}' returned {nq['results_found']} results"

    # At least 3 out of 4 noise queries must return 0 (allow 1 jieba partial match)
    zero_count = sum(1 for nq in noise_queries if nq["results_found"] == 0)
    assert (
        zero_count >= 3
    ), f"Only {zero_count}/{len(noise_queries)} noise queries returned 0 results"


def test_eval_gate_positive_recall(isolated_data_dir: Path) -> None:
    """CI gate: queries that should find results do find results."""
    _write_eval_fixture_data(isolated_data_dir)

    run_eval = importlib.import_module("tools.eval.run_eval")
    result = run_eval.run_evaluation(data_dir=isolated_data_dir)

    for pq in result["per_query"]:
        if pq.get("category") in EVAL_PHASE2_POSITIVE_CATEGORIES:
            assert (
                pq["results_found"] > 0
            ), f"Positive query '{pq['query']}' ({pq['id']}) found 0 results"


def test_eval_gate_baseline_comparison_works(isolated_data_dir: Path, tmp_path: Path) -> None:
    """CI gate: baseline save/compare infrastructure is functional."""
    _write_eval_fixture_data(isolated_data_dir)

    run_eval = importlib.import_module("tools.eval.run_eval")
    baseline_path = tmp_path / "baseline.json"

    # Save baseline
    run_eval.run_evaluation(
        data_dir=isolated_data_dir,
        save_baseline=baseline_path,
    )
    assert baseline_path.exists(), "Baseline file was not created"

    # Compare against self (should show no regressions)
    comparison = run_eval.compare_against_baseline(
        baseline_path=baseline_path,
        data_dir=isolated_data_dir,
    )
    assert "diff" in comparison
    assert "metric_deltas" in comparison["diff"]
    assert isinstance(comparison["diff_lines"], list)
