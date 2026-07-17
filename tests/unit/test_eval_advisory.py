#!/usr/bin/env python3
import importlib
from pathlib import Path

import pytest

from tools.eval.private_data import get_golden_queries_path

pytestmark = pytest.mark.skipif(
    not get_golden_queries_path().exists(),
    reason="local/private eval query set not present in public checkout",
)


def _write_eval_fixture_data(data_dir: Path) -> None:
    """Write the standard eval fixture dataset."""
    from tests.unit.test_eval_runner import _write_eval_fixture_data as _write

    _write(data_dir)


def test_eval_advisory_completes_successfully(isolated_data_dir: Path) -> None:
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


def test_eval_advisory_reports_configured_categories(isolated_data_dir: Path) -> None:
    _write_eval_fixture_data(isolated_data_dir)

    run_eval = importlib.import_module("tools.eval.run_eval")
    result = run_eval.run_evaluation(data_dir=isolated_data_dir)

    by_category = result["by_category"]
    observed = {query["category"] for query in result["per_query"]}
    assert observed
    assert observed <= set(by_category)
    assert all(by_category[category]["query_count"] > 0 for category in observed)


def test_eval_advisory_reports_aggregate_observations(isolated_data_dir: Path) -> None:
    _write_eval_fixture_data(isolated_data_dir)

    run_eval = importlib.import_module("tools.eval.run_eval")
    result = run_eval.run_evaluation(data_dir=isolated_data_dir)

    aggregate_eval = result.get("aggregate_eval")
    assert aggregate_eval is not None
    assert isinstance(aggregate_eval["total_queries"], int)
    assert isinstance(aggregate_eval["failed_queries"], int)
    assert isinstance(aggregate_eval["failures"], list)


def test_eval_advisory_baseline_comparison_works(isolated_data_dir: Path, tmp_path: Path) -> None:
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
