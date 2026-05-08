#!/usr/bin/env python3
"""Tests for eval_run Run builder (R2-B3c2).

Covers:
  A. Basic run build: scores, query_id, no title/query text
  B. Empty/missing doc IDs
  C. Length mismatch detection
  D. Duplicate doc_id handling
  E. Dict adapter (old JSON without top_doc_ids)
  F. Live-ish fixtures with minimal EvalRun/RunResult
"""

from __future__ import annotations

from tools.eval.eval_run import (
    RunCoverageReport,
    analyze_run_coverage,
    build_run_from_dict,
    build_run_from_eval_run,
    build_run_with_report,
)
from tools.eval.eval_types import EvalRun, EvalRunConfig, EvalRunMetadata, EvalRunResults, RunResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    qid: str = "GQ01",
    doc_ids: list[str] | None = None,
    titles: list[str] | None = None,
    results_found: int = 0,
) -> RunResult:
    if doc_ids is None:
        doc_ids = []
    if titles is None:
        titles = ["T"] * len(doc_ids)
    return RunResult(
        query_id=qid,
        query="test query",
        category="test",
        results_found=results_found or len(doc_ids),
        top_titles=titles,
        top_doc_ids=doc_ids,
        first_relevant_rank=None,
        first_relevant_rank_at_10=None,
        reciprocal_rank=0.0,
        precision_at_5=0.0,
        ndcg_at_5=None,
        expected_min_results=1,
        passed=False,
        eval_mode="exact_mrr",
    )


def _make_eval_run(results: list[RunResult]) -> EvalRun:
    return EvalRun(
        config=EvalRunConfig(
            judge_mode="keyword",
            semantic_enabled=False,
            live_mode=True,
            overlay_enabled=False,
        ),
        metadata=EvalRunMetadata(
            timestamp="2026-05-08T00:00:00+00:00",
            frozen_at="2026-05-08",
            anchor_date="2026-05-08",
            commit="abc123",
            python_version="3.12.10",
            tokenizer_version=2,
        ),
        results=EvalRunResults(
            total_queries=len(results),
            skipped_queries=0,
            metrics={"mrr_at_5": 0.5},
            by_category={},
            per_query=results,
            failures=[],
        ),
    )


# ---------------------------------------------------------------------------
# A. Basic run build
# ---------------------------------------------------------------------------


class TestBasicRunBuild:
    def test_three_doc_ids_scores(self) -> None:
        run = build_run_from_eval_run(
            _make_eval_run([_make_result(doc_ids=["a.md", "b.md", "c.md"])])
        )
        assert "GQ01" in run
        inner = run["GQ01"]
        assert inner["a.md"] == 1.0
        assert inner["b.md"] == 0.5
        assert abs(inner["c.md"] - 1.0 / 3) < 1e-9

    def test_query_id_correct(self) -> None:
        run = build_run_from_eval_run(_make_eval_run([_make_result(qid="GQ42", doc_ids=["x.md"])]))
        assert "GQ42" in run
        assert "GQ01" not in run

    def test_no_title_or_query_text_in_output(self) -> None:
        run = build_run_from_eval_run(
            _make_eval_run([_make_result(doc_ids=["a.md"], titles=["Secret Title"])])
        )
        inner = run["GQ01"]
        assert "Secret Title" not in inner
        assert "test query" not in inner
        assert set(inner.keys()) == {"a.md"}

    def test_multiple_queries(self) -> None:
        run = build_run_from_eval_run(
            _make_eval_run(
                [
                    _make_result(qid="GQ01", doc_ids=["a.md"]),
                    _make_result(qid="GQ02", doc_ids=["b.md", "c.md"]),
                ]
            )
        )
        assert len(run) == 2
        assert run["GQ01"]["a.md"] == 1.0
        assert run["GQ02"]["b.md"] == 1.0


# ---------------------------------------------------------------------------
# B. Empty / missing doc IDs
# ---------------------------------------------------------------------------


class TestEmptyMissingDocIds:
    def test_empty_doc_ids_produces_empty_inner(self) -> None:
        run, report = build_run_with_report(_make_eval_run([_make_result(doc_ids=[])]))
        assert run["GQ01"] == {}
        assert "GQ01" in report.queries_with_no_run_items

    def test_none_doc_ids_produces_empty_inner(self) -> None:
        r = _make_result(doc_ids=None)
        r.top_doc_ids = None
        run = build_run_from_eval_run(_make_eval_run([r]))
        assert run["GQ01"] == {}

    def test_empty_string_skipped(self) -> None:
        run, report = build_run_with_report(
            _make_eval_run([_make_result(doc_ids=["a.md", "", "b.md"])])
        )
        inner = run["GQ01"]
        assert "" not in inner
        assert len(inner) == 2
        assert report.skipped_empty_doc_ids == 1

    def test_all_empty_strings(self) -> None:
        run, report = build_run_with_report(_make_eval_run([_make_result(doc_ids=["", ""])]))
        assert run["GQ01"] == {}
        assert report.skipped_empty_doc_ids == 2
        assert "GQ01" in report.queries_with_no_run_items


# ---------------------------------------------------------------------------
# C. Length mismatch
# ---------------------------------------------------------------------------


class TestLengthMismatch:
    def test_mismatch_recorded(self) -> None:
        run, report = build_run_with_report(
            _make_eval_run([_make_result(doc_ids=["a.md"], titles=["T1", "T2"])])
        )
        assert "GQ01" in report.length_mismatch_query_ids
        assert run["GQ01"]["a.md"] == 1.0

    def test_no_mismatch_when_matching(self) -> None:
        _, report = build_run_with_report(
            _make_eval_run([_make_result(doc_ids=["a.md", "b.md"], titles=["T1", "T2"])])
        )
        assert report.length_mismatch_query_ids == []

    def test_mismatch_warning_text(self) -> None:
        _, report = build_run_with_report(
            _make_eval_run([_make_result(qid="GQ99", doc_ids=["a.md"], titles=["T1", "T2"])])
        )
        assert any("GQ99" in w and "top_doc_ids" in w for w in report.warnings)


# ---------------------------------------------------------------------------
# D. Duplicate doc_id
# ---------------------------------------------------------------------------


class TestDuplicateDocId:
    def test_duplicate_keeps_highest_score(self) -> None:
        run, report = build_run_with_report(
            _make_eval_run([_make_result(doc_ids=["dup.md", "dup.md", "other.md"])])
        )
        inner = run["GQ01"]
        assert inner["dup.md"] == 1.0  # rank 1 score
        assert inner["other.md"] == 1.0 / 3
        assert len(inner) == 2

    def test_duplicate_recorded_in_report(self) -> None:
        _, report = build_run_with_report(
            _make_eval_run([_make_result(qid="GQ50", doc_ids=["dup.md", "dup.md"])])
        )
        assert "GQ50" in report.duplicate_doc_ids_query_ids

    def test_no_false_positive_duplicates(self) -> None:
        _, report = build_run_with_report(_make_eval_run([_make_result(doc_ids=["a.md", "b.md"])]))
        assert report.duplicate_doc_ids_query_ids == []


# ---------------------------------------------------------------------------
# E. Dict adapter
# ---------------------------------------------------------------------------


def _minimal_eval_dict() -> dict:
    return {
        "baseline_id": "test-baseline",
        "meta": {"source_commit": "abc123"},
        "timestamp": "2026-05-08T00:00:00+00:00",
        "frozen_at": "2026-05-08",
        "anchor_date": "2026-05-08",
        "commit": "abc123",
        "python_version": "3.12.10",
        "tokenizer_version": 2,
        "judge_mode": "keyword",
        "semantic_enabled": False,
        "live_mode": True,
        "total_queries": 1,
        "skipped_queries": 0,
        "metrics": {"mrr_at_5": 0.5},
        "by_category": {},
        "per_query": [],
        "failures": [],
        "recall_gaps": [],
        "summary_lines": [],
    }


class TestDictAdapter:
    def test_build_run_from_dict_with_top_doc_ids(self) -> None:
        data = _minimal_eval_dict()
        data["per_query"] = [
            {
                "id": "GQ01",
                "query": "test",
                "category": "test",
                "results_found": 2,
                "top_titles": ["A", "B"],
                "top_doc_ids": ["2026/03/a.md", "2026/03/b.md"],
                "first_relevant_rank": 1,
                "first_relevant_rank_at_10": 1,
                "reciprocal_rank": 1.0,
                "precision_at_5": 0.5,
                "expected_min_results": 1,
                "pass": True,
            }
        ]
        run = build_run_from_dict(data)
        assert run["GQ01"]["2026/03/a.md"] == 1.0
        assert run["GQ01"]["2026/03/b.md"] == 0.5

    def test_old_json_without_top_doc_ids(self) -> None:
        data = _minimal_eval_dict()
        data["per_query"] = [
            {
                "id": "GQ-OLD",
                "query": "old",
                "category": "test",
                "results_found": 1,
                "top_titles": ["Title"],
                "first_relevant_rank": 1,
                "first_relevant_rank_at_10": 1,
                "reciprocal_rank": 1.0,
                "precision_at_5": 1.0,
                "expected_min_results": 1,
                "pass": True,
            }
        ]
        run = build_run_from_dict(data)
        assert run["GQ-OLD"] == {}

    def test_old_json_coverage_reports_no_run_items(self) -> None:
        data = _minimal_eval_dict()
        data["per_query"] = [
            {
                "id": "GQ-OLD",
                "query": "old",
                "category": "test",
                "results_found": 0,
                "top_titles": [],
                "first_relevant_rank": None,
                "first_relevant_rank_at_10": None,
                "reciprocal_rank": 0.0,
                "precision_at_5": 0.0,
                "expected_min_results": 1,
                "pass": False,
            }
        ]
        eval_run = EvalRun.from_dict(data)
        report = analyze_run_coverage(eval_run)
        assert "GQ-OLD" in report.queries_with_no_run_items


# ---------------------------------------------------------------------------
# F. Coverage report fields
# ---------------------------------------------------------------------------


class TestCoverageReport:
    def test_report_counts(self) -> None:
        results = [
            _make_result(qid="GQ01", doc_ids=["a.md", "b.md"]),
            _make_result(qid="GQ02", doc_ids=[""]),
            _make_result(qid="GQ03", doc_ids=[]),
        ]
        _, report = build_run_with_report(_make_eval_run(results))
        assert report.total_queries == 3
        assert report.total_result_items == 3  # 2 + 1 + 0
        assert report.emitted_items == 2
        assert report.skipped_empty_doc_ids == 1
        assert "GQ02" in report.queries_with_no_run_items
        assert "GQ03" in report.queries_with_no_run_items

    def test_report_frozen(self) -> None:
        report = RunCoverageReport(
            total_queries=0,
            total_result_items=0,
            emitted_items=0,
            skipped_empty_doc_ids=0,
            length_mismatch_query_ids=[],
            duplicate_doc_ids_query_ids=[],
            queries_with_no_run_items=[],
            warnings=[],
        )
        assert report.total_queries == 0
