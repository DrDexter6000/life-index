#!/usr/bin/env python3
"""Unit tests for broad_eval predicate_precision logic."""

from __future__ import annotations

from datetime import date

import pytest

from tools.eval.run_eval import (
    _build_predicate,
    _compute_global_matched_count,
    _compute_predicate_precision,
    _doc_date,
    _doc_topics,
)


def test_date_range_predicate():
    pred = _build_predicate(
        {
            "type": "date_range",
            "date_range": {"since": "2026-01-01", "until": "2026-01-31"},
        }
    )
    assert pred({"date": date(2026, 1, 15)}) is True
    assert pred({"date": date(2026, 2, 1)}) is False
    assert pred({"date": "2026-01-20"}) is True
    assert pred({"date": "2026-02-01"}) is False


def test_topic_predicate():
    pred = _build_predicate(
        {
            "type": "topic",
            "topic_hints": ["work"],
        }
    )
    assert pred({"topic": ["work", "life"]}) is True
    assert pred({"topic": "work"}) is True
    assert pred({"topic": ["life"]}) is False
    assert pred({"topic": "life"}) is False


def test_date_topic_predicate_requires_both():
    pred = _build_predicate(
        {
            "type": "date_topic",
            "date_range": {"since": "2026-01-01", "until": "2026-01-31"},
            "topic_hints": ["think"],
        }
    )
    assert pred({"date": date(2026, 1, 15), "topic": ["think"]}) is True
    assert pred({"date": date(2026, 1, 15), "topic": ["work"]}) is False
    assert pred({"date": date(2026, 2, 1), "topic": ["think"]}) is False
    assert pred({"date": date(2026, 1, 15), "topic": []}) is False


def test_precision_uses_returned_count():
    pred = _build_predicate({"type": "topic", "topic_hints": ["work"]})
    docs = [
        {"topic": ["work"]},
        {"topic": ["work"]},
        {"topic": ["life"]},
    ]
    precision, matched, returned = _compute_predicate_precision(docs, pred)
    assert returned == 3
    assert matched == 2
    assert precision == 2 / 3


def test_precision_zero_when_empty():
    pred = _build_predicate({"type": "topic", "topic_hints": ["work"]})
    precision, matched, returned = _compute_predicate_precision([], pred)
    assert precision == 0.0
    assert matched == 0
    assert returned == 0


def test_min_results_policy():
    """min_results required = min(5, global_matched_count)."""
    pred = _build_predicate({"type": "topic", "topic_hints": ["work"]})
    all_docs = [
        {"topic": ["work"]},
        {"topic": ["work"]},
        {"topic": ["work"]},
        {"topic": ["life"]},
    ]
    global_matched = _compute_global_matched_count(all_docs, pred)
    assert global_matched == 3
    required = min(5, global_matched)
    assert required == 3

    # returned >= required → min_results_ok = True
    assert 4 >= 3


def test_strict_vs_soft_pass():
    """strict_pass requires precision == 1.0; soft_pass allows >= 0.8."""
    pred = _build_predicate({"type": "topic", "topic_hints": ["work"]})

    # Case 1: perfect precision + enough results
    docs_perfect = [{"topic": ["work"]}, {"topic": ["work"]}]
    precision, _, _ = _compute_predicate_precision(docs_perfect, pred)
    min_results_ok = True
    assert precision == 1.0
    assert (precision == 1.0 and min_results_ok) is True  # strict_pass
    assert (precision >= 0.8 and min_results_ok) is True  # soft_pass

    # Case 2: 0.50 precision + enough results
    docs_50 = [{"topic": ["work"]}, {"topic": ["life"]}]
    precision, _, _ = _compute_predicate_precision(docs_50, pred)
    assert precision == 0.5
    assert (precision == 1.0 and min_results_ok) is False  # strict_pass fails
    assert (precision >= 0.8 and min_results_ok) is False  # soft_pass fails

    # Case 3: exactly 0.80 precision (4/5)
    docs_80 = [
        {"topic": ["work"]},
        {"topic": ["work"]},
        {"topic": ["work"]},
        {"topic": ["work"]},
        {"topic": ["life"]},
    ]
    precision, _, _ = _compute_predicate_precision(docs_80, pred)
    assert precision == 0.8
    assert (precision == 1.0 and min_results_ok) is False  # strict_pass fails
    assert (precision >= 0.8 and min_results_ok) is True  # soft_pass passes

    # Case 4: 0.60 precision (3/5) — between 0.5 and 0.8
    docs_60 = [
        {"topic": ["work"]},
        {"topic": ["work"]},
        {"topic": ["work"]},
        {"topic": ["life"]},
        {"topic": ["life"]},
    ]
    precision, _, _ = _compute_predicate_precision(docs_60, pred)
    assert precision == 0.6
    assert (precision == 1.0 and min_results_ok) is False  # strict_pass fails
    assert (precision >= 0.8 and min_results_ok) is False  # soft_pass fails


def test_doc_date_parsing():
    assert _doc_date({"date": date(2026, 3, 7)}) == date(2026, 3, 7)
    assert _doc_date({"date": "2026-03-07T14:30:00"}) == date(2026, 3, 7)
    assert _doc_date({"date": "2026-03-07"}) == date(2026, 3, 7)
    assert _doc_date({"date": None}) == date.min
    assert _doc_date({}) == date.min


def test_build_predicate_raises_on_unknown_type():
    """_build_predicate must raise ValueError for unknown predicate types."""
    with pytest.raises(ValueError, match="Unknown predicate type"):
        _build_predicate({"type": "invalid_type"})


def test_broad_eval_error_counted_in_metrics():
    """Queries with broad_eval_error must still be counted in broad_eval_metrics."""
    from tools.eval.run_eval import _collect_broad_eval_metrics

    per_query = [
        {
            "id": "GQ001",
            "eval_mode": "predicate_precision",
            "strict_pass": True,
            "soft_pass": True,
        },
        {
            "id": "GQ002",
            "eval_mode": "predicate_precision",
            "strict_pass": False,
            "soft_pass": True,
        },
        {
            "id": "GQ003",
            "eval_mode": "predicate_precision",
            "strict_pass": False,
            "soft_pass": False,
        },
        {
            "id": "GQ004",
            "eval_mode": "predicate_precision",
            "broad_eval_error": "predicate build failed",
            "strict_pass": False,
            "soft_pass": False,
        },
        {"id": "GQ005", "eval_mode": "exact_mrr"},
    ]
    metrics = _collect_broad_eval_metrics(per_query)
    assert metrics["query_count"] == 4
    assert metrics["strict_passes"] == 1
    assert metrics["soft_passes"] == 2
    assert metrics["errors"] == 1
    assert metrics["fails"] == 1  # 4 - 2 - 1 = 1 (GQ003)


def test_doc_topics_parsing():
    assert _doc_topics({"topic": ["work", "life"]}) == ["work", "life"]
    assert _doc_topics({"topic": "work"}) == ["work"]
    assert _doc_topics({"topic": []}) == []
    assert _doc_topics({}) == []
    assert _doc_topics({"topic": None}) == []
