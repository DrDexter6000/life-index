#!/usr/bin/env python3
"""Boundary simulation tests for broad_eval soft gate (Phase 2)."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest
import yaml


def _write_minimal_fixture(data_dir: Path) -> None:
    """Write standard eval fixture data."""
    from tests.unit.test_eval_runner import _write_eval_fixture_data

    _write_eval_fixture_data(data_dir)


def _make_temp_gold_set(tmp_path: Path, queries: list[dict]) -> Path:
    p = tmp_path / "gold.yaml"
    p.write_text(
        yaml.dump({"queries": queries}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return p


@pytest.fixture(autouse=True)
def _anchor():
    os.environ["LIFE_INDEX_TIME_ANCHOR"] = "2026-05-04"
    yield


@pytest.fixture
def mock_precision(monkeypatch):
    """Mock _compute_predicate_precision to return a fixed tuple."""

    def _set(precision: float, matched: int, returned: int):
        monkeypatch.setattr(
            "tools.eval.run_eval._compute_predicate_precision",
            lambda _top_results, _predicate: (precision, matched, returned),
        )

    return _set


@pytest.fixture
def mock_global_matched(monkeypatch):
    """Mock _compute_global_matched_count to return a fixed value."""

    def _set(value: int):
        monkeypatch.setattr(
            "tools.eval.run_eval._compute_global_matched_count",
            lambda _all_docs, _predicate: value,
        )

    return _set


def test_broad_eval_precision_10_pass(mock_precision, mock_global_matched, tmp_path):
    """precision=1.0, min_results_ok=true -> pass, no failure."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_minimal_fixture(data_dir)
    mock_precision(1.0, 5, 5)
    mock_global_matched(5)

    gold = _make_temp_gold_set(
        tmp_path,
        [
            {
                "id": "TEST01",
                "query": "work logs",
                "category": "complex_query",
                "expected": {"min_results": 1},
                "broad_eval": {
                    "mode": "predicate_precision",
                    "predicate": {"type": "topic", "topic_hints": ["work"]},
                    "min_precision": 1.0,
                    "min_results_policy": "min(5, global_matched_count)",
                },
            }
        ],
    )

    run_eval = importlib.import_module("tools.eval.run_eval")
    result = run_eval.run_evaluation(data_dir=data_dir, queries_path=gold)
    pq = result["per_query"][0]
    assert pq["eval_mode"] == "predicate_precision"
    assert pq["predicate_precision"] == 1.0
    assert pq["strict_pass"] is True
    assert pq["soft_pass"] is True
    assert pq["pass"] is True
    assert not any(f["id"] == "TEST01" for f in result["failures"])


def test_broad_eval_precision_08_pass(mock_precision, mock_global_matched, tmp_path):
    """precision=0.8, min_results_ok=true -> soft_pass, pass, no failure."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_minimal_fixture(data_dir)
    mock_precision(0.8, 4, 5)
    mock_global_matched(5)

    gold = _make_temp_gold_set(
        tmp_path,
        [
            {
                "id": "TEST02",
                "query": "work logs",
                "category": "complex_query",
                "expected": {"min_results": 1},
                "broad_eval": {
                    "mode": "predicate_precision",
                    "predicate": {"type": "topic", "topic_hints": ["work"]},
                    "min_precision": 1.0,
                    "min_results_policy": "min(5, global_matched_count)",
                },
            }
        ],
    )

    run_eval = importlib.import_module("tools.eval.run_eval")
    result = run_eval.run_evaluation(data_dir=data_dir, queries_path=gold)
    pq = result["per_query"][0]
    assert pq["predicate_precision"] == 0.8
    assert pq["strict_pass"] is False
    assert pq["soft_pass"] is True
    assert pq["pass"] is True
    assert not any(f["id"] == "TEST02" for f in result["failures"])


def test_broad_eval_precision_06_fail(mock_precision, mock_global_matched, tmp_path):
    """precision=0.6, min_results_ok=true -> soft_pass false, fail, enters failures."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_minimal_fixture(data_dir)
    mock_precision(0.6, 3, 5)
    mock_global_matched(5)

    gold = _make_temp_gold_set(
        tmp_path,
        [
            {
                "id": "TEST03",
                "query": "work logs",
                "category": "complex_query",
                "expected": {"min_results": 1},
                "broad_eval": {
                    "mode": "predicate_precision",
                    "predicate": {"type": "topic", "topic_hints": ["work"]},
                    "min_precision": 1.0,
                    "min_results_policy": "min(5, global_matched_count)",
                },
            }
        ],
    )

    run_eval = importlib.import_module("tools.eval.run_eval")
    result = run_eval.run_evaluation(data_dir=data_dir, queries_path=gold)
    pq = result["per_query"][0]
    assert pq["predicate_precision"] == 0.6
    assert pq["strict_pass"] is False
    assert pq["soft_pass"] is False
    assert pq["pass"] is False
    fail = next(f for f in result["failures"] if f["id"] == "TEST03")
    assert "soft gate fail" in fail["reason"]


def test_broad_eval_min_results_fail(mock_precision, mock_global_matched, tmp_path):
    """returned_count < required_count -> min_results_ok false, fail."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_minimal_fixture(data_dir)
    mock_precision(1.0, 2, 2)
    mock_global_matched(5)

    gold = _make_temp_gold_set(
        tmp_path,
        [
            {
                "id": "TEST04",
                "query": "work logs",
                "category": "complex_query",
                "expected": {"min_results": 1},
                "broad_eval": {
                    "mode": "predicate_precision",
                    "predicate": {"type": "topic", "topic_hints": ["work"]},
                    "min_precision": 1.0,
                    "min_results_policy": "min(5, global_matched_count)",
                },
            }
        ],
    )

    run_eval = importlib.import_module("tools.eval.run_eval")
    result = run_eval.run_evaluation(data_dir=data_dir, queries_path=gold)
    pq = result["per_query"][0]
    assert pq["predicate_precision"] == 1.0
    assert pq["min_results_ok"] is False
    assert pq["soft_pass"] is False
    assert pq["pass"] is False
    fail = next(f for f in result["failures"] if f["id"] == "TEST04")
    assert "min_results fail" in fail["reason"]


def test_broad_eval_error_fail(monkeypatch, tmp_path):
    """broad_eval predicate build error -> fail, enters failures, retains eval_mode."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_minimal_fixture(data_dir)

    # Force _build_predicate to raise
    monkeypatch.setattr(
        "tools.eval.run_eval._build_predicate",
        lambda _be_predicate: (_ for _ in ()).throw(ValueError("bad predicate")),
    )

    gold = _make_temp_gold_set(
        tmp_path,
        [
            {
                "id": "TEST05",
                "query": "work logs",
                "category": "complex_query",
                "expected": {"min_results": 1},
                "broad_eval": {
                    "mode": "predicate_precision",
                    "predicate": {"type": "topic", "topic_hints": ["work"]},
                    "min_precision": 1.0,
                    "min_results_policy": "min(5, global_matched_count)",
                },
            }
        ],
    )

    run_eval = importlib.import_module("tools.eval.run_eval")
    result = run_eval.run_evaluation(data_dir=data_dir, queries_path=gold)
    pq = result["per_query"][0]
    assert pq["eval_mode"] == "predicate_precision"
    assert "broad_eval_error" in pq
    assert pq["strict_pass"] is False
    assert pq["soft_pass"] is False
    assert pq["pass"] is False
    fail = next(f for f in result["failures"] if f["id"] == "TEST05")
    assert "broad_eval error" in fail["reason"]


def test_exact_mrr_unchanged(monkeypatch, mock_precision, mock_global_matched, tmp_path):
    """exact_mrr queries without broad_eval are untouched by soft gate."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_minimal_fixture(data_dir)
    # Even if mocks are active, they should not affect exact_mrr queries
    mock_precision(0.6, 0, 0)
    mock_global_matched(0)

    run_eval = importlib.import_module("tools.eval.run_eval")

    # Call _evaluate_queries directly (avoids _reload_runtime_modules inside run_evaluation)
    queries = [
        {
            "id": "TEST06",
            "query": "想念小英雄",
            "category": "entity_expansion",
            "expected": {"min_results": 1, "must_contain_title": ["想念小英雄"]},
        }
    ]

    # Mock search so the exact_mrr query gets results and passes on its own terms
    monkeypatch.setattr(
        "tools.search_journals.core.hierarchical_search",
        lambda query, level, semantic: {
            "merged_results": [
                {
                    "title": "想念小英雄",
                    "date": "2026-03-04",
                    "abstract": "回忆",
                    "snippet": "小英雄",
                }
            ]
        },
    )

    per_query, failures = run_eval._evaluate_queries(
        queries,
        use_semantic=False,
        judge="keyword",
        live=False,
        llm_client=None,
        all_docs=[],
    )
    pq = per_query[0]
    assert pq["eval_mode"] == "exact_mrr"
    assert "strict_pass" not in pq
    assert "soft_pass" not in pq
    assert pq["pass"] is True
    assert not any(f["id"] == "TEST06" for f in failures)
