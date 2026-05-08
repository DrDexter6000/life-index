#!/usr/bin/env python3
"""Run builder utility for eval (R2-B3c2).

Converts EvalRun per_query results into IR-style run format:
    {query_id: {doc_id: float_score}}

Score strategy: 1.0 / rank, rank starting at 1.

This module is independent of run_eval.py. It does not change eval behavior.
Integration with run_eval.py is deferred to a later task.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias

from tools.eval.eval_types import EvalRun, RunResult

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

Run: TypeAlias = dict[str, dict[str, float]]


@dataclass(frozen=True)
class RunCoverageReport:
    """Coverage statistics for a built Run."""

    total_queries: int
    total_result_items: int
    emitted_items: int
    skipped_empty_doc_ids: int
    length_mismatch_query_ids: list[str]
    duplicate_doc_ids_query_ids: list[str]
    queries_with_no_run_items: list[str]
    warnings: list[str]


# ---------------------------------------------------------------------------
# Run builder
# ---------------------------------------------------------------------------


def _build_run_from_results(results: list[RunResult]) -> tuple[Run, RunCoverageReport]:
    total_result_items = 0
    emitted_items = 0
    skipped_empty = 0
    length_mismatch_ids: list[str] = []
    duplicate_ids: list[str] = []
    no_run_ids: list[str] = []
    warnings: list[str] = []
    run: Run = {}

    for result in results:
        qid = result.query_id
        doc_ids = result.top_doc_ids if result.top_doc_ids is not None else []
        titles = result.top_titles if result.top_titles is not None else []

        total_result_items += len(doc_ids)

        # Length mismatch check
        if len(doc_ids) != len(titles):
            length_mismatch_ids.append(qid)
            warnings.append(f"{qid}: top_doc_ids({len(doc_ids)}) != top_titles({len(titles)})")

        # Build scored items
        inner: dict[str, float] = {}
        for rank, doc_id in enumerate(doc_ids, start=1):
            if not doc_id:
                skipped_empty += 1
                continue
            score = 1.0 / rank
            if doc_id in inner:
                # Keep highest score (earliest rank); record duplicate
                duplicate_ids.append(qid)
                warnings.append(f"{qid}: duplicate doc_id {doc_id!r}")
                continue
            inner[doc_id] = score
            emitted_items += 1

        run[qid] = inner

        if not inner:
            no_run_ids.append(qid)

    report = RunCoverageReport(
        total_queries=len(results),
        total_result_items=total_result_items,
        emitted_items=emitted_items,
        skipped_empty_doc_ids=skipped_empty,
        length_mismatch_query_ids=length_mismatch_ids,
        duplicate_doc_ids_query_ids=duplicate_ids,
        queries_with_no_run_items=no_run_ids,
        warnings=warnings,
    )
    return run, report


def build_run_from_eval_run(eval_run: EvalRun) -> Run:
    """Build Run from typed EvalRun. Uses top_doc_ids, score = 1.0/rank."""
    run, _ = _build_run_from_results(eval_run.results.per_query)
    return run


def build_run_from_dict(data: Mapping[str, Any]) -> Run:
    """Build Run from raw eval result dict (EvalRun.to_dict() format)."""
    eval_run = EvalRun.from_dict(dict(data))
    return build_run_from_eval_run(eval_run)


def analyze_run_coverage(eval_run: EvalRun) -> RunCoverageReport:
    """Analyze run coverage without returning the run."""
    _, report = _build_run_from_results(eval_run.results.per_query)
    return report


def build_run_with_report(eval_run: EvalRun) -> tuple[Run, RunCoverageReport]:
    """Build Run and return coverage report."""
    return _build_run_from_results(eval_run.results.per_query)
