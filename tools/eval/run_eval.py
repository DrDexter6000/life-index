#!/usr/bin/env python3
"""Minimal evaluation runner for search quality."""

from __future__ import annotations

import importlib
import json
import os
import platform
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml


GOLDEN_QUERIES_PATH = Path(__file__).with_name("golden_queries.yaml")
TOP_K = 5
MODULES_TO_RELOAD = (
    "tools.lib.paths",
    "tools.lib.config",
    "tools.lib.metadata_cache",
    "tools.lib.vector_index_simple",
    "tools.lib.entity_runtime",
    "tools.lib.search_index",
    "tools.lib.fts_update",
    "tools.lib.fts_search",
    "tools.search_journals.semantic",
    "tools.search_journals.semantic_pipeline",
    "tools.search_journals.keyword_pipeline",
    "tools.search_journals.core",
)


def load_golden_queries(file_path: Path | None = None) -> list[dict[str, Any]]:
    """Load the golden query set from YAML."""
    payload = yaml.safe_load(
        (file_path or GOLDEN_QUERIES_PATH).read_text(encoding="utf-8")
    )
    queries = payload.get("queries", []) if isinstance(payload, dict) else []
    if not isinstance(queries, list):
        raise ValueError("golden_queries.yaml must contain a 'queries' list")
    return queries


def _get_git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _round_metric(value: float) -> float:
    return round(value, 4)


def _safe_float_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _query_expected(query_case: dict[str, Any]) -> dict[str, Any]:
    expected = query_case.get("expected", {})
    return expected if isinstance(expected, dict) else {}


def _must_contain_titles(query_case: dict[str, Any]) -> list[str]:
    expected = _query_expected(query_case)
    raw_value = expected.get("must_contain_title", [])
    if not raw_value:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("must_contain_title must be a list when present")
    return [str(item) for item in raw_value]


def _min_results(query_case: dict[str, Any]) -> int:
    return int(_query_expected(query_case).get("min_results", 0))


def _result_is_relevant(result: dict[str, Any], query_case: dict[str, Any]) -> bool:
    title = str(result.get("title", ""))
    must_contain_titles = _must_contain_titles(query_case)
    if must_contain_titles:
        return any(fragment in title for fragment in must_contain_titles)
    return _min_results(query_case) > 0


def _first_relevant_rank(
    top_results: list[dict[str, Any]], query_case: dict[str, Any]
) -> int | None:
    for index, result in enumerate(top_results, start=1):
        if _result_is_relevant(result, query_case):
            return index
    return None


def _query_precision_at_5(
    top_results: list[dict[str, Any]], query_case: dict[str, Any]
) -> float:
    if not top_results:
        return 0.0

    must_contain_titles = _must_contain_titles(query_case)
    if not must_contain_titles:
        return 1.0 if _min_results(query_case) > 0 else 0.0

    relevant_count = sum(
        1 for result in top_results if _result_is_relevant(result, query_case)
    )
    return relevant_count / min(len(top_results), TOP_K)


def _query_passes(
    *, top_results: list[dict[str, Any]], query_case: dict[str, Any], results_found: int
) -> tuple[bool, str | None]:
    expected_min_results = _min_results(query_case)
    if expected_min_results == 0:
        if results_found == 0:
            return True, None
        return False, f"Expected 0 results, got {results_found}"

    if results_found < expected_min_results:
        return False, f"Expected >= {expected_min_results} results, got {results_found}"

    if (
        _must_contain_titles(query_case)
        and _first_relevant_rank(top_results, query_case) is None
    ):
        return (
            False,
            "Expected one of must_contain_title within top 5, but none matched",
        )

    return True, None


def _collect_metrics(per_query: list[dict[str, Any]]) -> dict[str, float]:
    mrr_total = sum(float(item["reciprocal_rank"]) for item in per_query)
    recall_candidates = [
        item for item in per_query if int(item["expected_min_results"]) > 0
    ]
    recall_hits = [
        item for item in recall_candidates if item["first_relevant_rank"] is not None
    ]
    precision_candidates = [
        item for item in per_query if int(item["results_found"]) > 0
    ]
    precision_total = sum(
        float(item["precision_at_5"]) for item in precision_candidates
    )

    return {
        "mrr_at_5": _round_metric(_safe_float_divide(mrr_total, len(per_query))),
        "recall_at_5": _round_metric(
            _safe_float_divide(len(recall_hits), len(recall_candidates))
        ),
        "precision_at_5": _round_metric(
            _safe_float_divide(precision_total, len(precision_candidates))
        ),
    }


def _build_summary_lines(result: dict[str, Any]) -> list[str]:
    metrics = result["metrics"]
    lines = [
        f"Queries: {result['total_queries']}",
        f"MRR@5: {metrics['mrr_at_5']:.4f}",
        f"Recall@5: {metrics['recall_at_5']:.4f}",
        f"Precision@5: {metrics['precision_at_5']:.4f}",
    ]
    if result["failures"]:
        lines.append(f"Failures: {len(result['failures'])}")
        for failure in result["failures"][:5]:
            lines.append(
                f'FAIL {failure["id"]} "{failure["query"]}" — {failure["reason"]}'
            )
    else:
        lines.append("Failures: 0")
    return lines


def _reload_runtime_modules() -> None:
    for module_name in MODULES_TO_RELOAD:
        module = importlib.import_module(module_name)
        importlib.reload(module)

    from tools.lib.chinese_tokenizer import reset_tokenizer_state

    reset_tokenizer_state()


@contextmanager
def _temporary_data_dir(data_dir: Path | None) -> Iterator[None]:
    if data_dir is None:
        yield
        return

    original_env = os.environ.get("LIFE_INDEX_DATA_DIR")
    os.environ["LIFE_INDEX_DATA_DIR"] = str(Path(data_dir))
    _reload_runtime_modules()
    try:
        yield
    finally:
        if original_env is None:
            os.environ.pop("LIFE_INDEX_DATA_DIR", None)
        else:
            os.environ["LIFE_INDEX_DATA_DIR"] = original_env
        _reload_runtime_modules()


def _evaluate_queries(
    queries: list[dict[str, Any]], *, use_semantic: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from tools.search_journals.core import hierarchical_search

    per_query: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for query_case in queries:
        raw_result = hierarchical_search(
            query=str(query_case["query"]),
            level=3,
            semantic=use_semantic,
        )
        merged_results = list(raw_result.get("merged_results", []))
        top_results = merged_results[:TOP_K]
        results_found = len(merged_results)
        first_relevant_rank = _first_relevant_rank(top_results, query_case)
        reciprocal_rank = (
            0.0 if first_relevant_rank is None else 1.0 / first_relevant_rank
        )
        precision_at_5 = _query_precision_at_5(top_results, query_case)
        passed, failure_reason = _query_passes(
            top_results=top_results,
            query_case=query_case,
            results_found=results_found,
        )

        entry = {
            "id": query_case["id"],
            "query": query_case["query"],
            "category": query_case["category"],
            "results_found": results_found,
            "top_titles": [str(item.get("title", "")) for item in top_results],
            "first_relevant_rank": first_relevant_rank,
            "reciprocal_rank": _round_metric(reciprocal_rank),
            "precision_at_5": _round_metric(precision_at_5),
            "expected_min_results": _min_results(query_case),
            "pass": passed,
        }
        per_query.append(entry)

        if failure_reason:
            failures.append(
                {
                    "id": query_case["id"],
                    "query": query_case["query"],
                    "reason": failure_reason,
                }
            )

    return per_query, failures


def run_evaluation(
    *,
    data_dir: Path | None = None,
    save_baseline: Path | None = None,
    use_semantic: bool = False,
    queries_path: Path | None = None,
) -> dict[str, Any]:
    """Run the search evaluation suite and optionally persist a baseline."""
    queries = load_golden_queries(queries_path)

    with _temporary_data_dir(data_dir):
        per_query, failures = _evaluate_queries(queries, use_semantic=use_semantic)

    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in per_query:
        by_category.setdefault(str(item["category"]), []).append(item)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit": _get_git_commit(),
        "python_version": platform.python_version(),
        "tokenizer_version": importlib.import_module(
            "tools.lib.search_constants"
        ).TOKENIZER_VERSION,
        "semantic_enabled": use_semantic,
        "total_queries": len(per_query),
        "metrics": _collect_metrics(per_query),
        "by_category": {},
        "per_query": per_query,
        "failures": failures,
    }

    for category, items in by_category.items():
        result["by_category"][category] = {
            **_collect_metrics(items),
            "query_count": len(items),
        }

    result["summary_lines"] = _build_summary_lines(result)

    if save_baseline is not None:
        save_baseline.parent.mkdir(parents=True, exist_ok=True)
        save_baseline.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return result


def compare_against_baseline(
    *,
    baseline_path: Path,
    data_dir: Path | None = None,
    use_semantic: bool = False,
    queries_path: Path | None = None,
) -> dict[str, Any]:
    """Run evaluation and compare current results against a saved baseline."""
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    current = run_evaluation(
        data_dir=data_dir,
        use_semantic=use_semantic,
        queries_path=queries_path,
    )

    metric_deltas: dict[str, dict[str, float]] = {}
    diff_lines: list[str] = []
    for metric_name in ("mrr_at_5", "recall_at_5", "precision_at_5"):
        before = float(baseline.get("metrics", {}).get(metric_name, 0.0))
        after = float(current.get("metrics", {}).get(metric_name, 0.0))
        delta = after - before
        metric_deltas[metric_name] = {
            "baseline": _round_metric(before),
            "current": _round_metric(after),
            "delta": _round_metric(delta),
        }
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "→"
        diff_lines.append(
            f"{metric_name.upper().replace('_AT_', '@').replace('_', '')}: "
            f" {before:.4f} → {after:.4f}  ({arrow} {delta:+.4f})"
        )

    baseline_per_query = {
        str(item["id"]): item for item in baseline.get("per_query", []) if "id" in item
    }
    current_per_query = {
        str(item["id"]): item for item in current.get("per_query", []) if "id" in item
    }
    regressions: list[dict[str, Any]] = []

    for query_id, baseline_query in baseline_per_query.items():
        current_query = current_per_query.get(query_id)
        if current_query is None:
            regressions.append(
                {
                    "id": query_id,
                    "query": baseline_query.get("query", ""),
                    "reason": "Current evaluation missing query result",
                }
            )
            continue

        baseline_rank = baseline_query.get("first_relevant_rank")
        current_rank = current_query.get("first_relevant_rank")
        if baseline_query.get("pass") and not current_query.get("pass"):
            if baseline_rank and current_rank is None:
                reason = f"was rank {baseline_rank}, now not found"
            else:
                reason = f"was pass with rank {baseline_rank}, now rank {current_rank}"
            regressions.append(
                {
                    "id": query_id,
                    "query": current_query.get(
                        "query", baseline_query.get("query", "")
                    ),
                    "reason": reason,
                }
            )
        elif (
            isinstance(baseline_rank, int)
            and isinstance(current_rank, int)
            and current_rank > baseline_rank
        ):
            regressions.append(
                {
                    "id": query_id,
                    "query": current_query.get(
                        "query", baseline_query.get("query", "")
                    ),
                    "reason": f"was rank {baseline_rank}, now rank {current_rank}",
                }
            )

    for regression in regressions:
        diff_lines.append(
            f'REGRESSION: {regression["id"]} "{regression["query"]}" — {regression["reason"]}'
        )

    return {
        "baseline": baseline,
        "current": current,
        "diff": {
            "metric_deltas": metric_deltas,
            "regressions": regressions,
        },
        "diff_lines": diff_lines,
    }


if __name__ == "__main__":
    payload = run_evaluation()
    print(json.dumps({"success": True, "data": payload}, ensure_ascii=False, indent=2))
