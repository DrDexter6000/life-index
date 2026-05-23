"""Cycle2 multi-signal eval harness tests.

A5 TDD RED tests: validate cycle2 fixture loading, per-category R@5/MRR@5
metrics, and baseline delta output shape.
"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def cycle2_fixture_dir(tmp_path: Path) -> Path:
    fixture_dir = tmp_path / "gold" / "cycle2-multi-signal"
    fixture_dir.mkdir(parents=True)

    c1_queries = [
        {
            "id": "C2-C1-001",
            "query": "Python code",
            "category": "C1_keyword_exact",
            "expected": {"min_results": 1, "must_contain_title": ["Life Index"]},
        },
        {
            "id": "C2-C1-002",
            "query": "integration testing",
            "category": "C1_keyword_exact",
            "expected": {"min_results": 1},
        },
    ]
    c2_queries = [
        {
            "id": "C2-C2-001",
            "query": "feeling exhausted",
            "category": "C2_paraphrase",
            "expected": {"min_results": 1},
        },
    ]
    c3_queries = [
        {
            "id": "C2-C3-001",
            "query": "last Saturday",
            "category": "C3_temporal",
            "expected": {"min_results": 1},
        },
    ]
    c4_queries = [
        {
            "id": "C2-C4-001",
            "query": "Dexter Life Index discussion",
            "category": "C4_entity_heavy",
            "expected": {"min_results": 1},
        },
        {
            "id": "C2-C4-002",
            "query": "OpenClaw project",
            "category": "C4_entity_heavy",
            "expected": {"min_results": 1},
        },
    ]

    (fixture_dir / "C1_keyword_exact.json").write_text(
        json.dumps(c1_queries, ensure_ascii=False), encoding="utf-8"
    )
    (fixture_dir / "C2_paraphrase.json").write_text(
        json.dumps(c2_queries, ensure_ascii=False), encoding="utf-8"
    )
    (fixture_dir / "C3_temporal.json").write_text(
        json.dumps(c3_queries, ensure_ascii=False), encoding="utf-8"
    )
    (fixture_dir / "C4_entity_heavy.json").write_text(
        json.dumps(c4_queries, ensure_ascii=False), encoding="utf-8"
    )
    return fixture_dir


class TestCycle2FixtureLoader:
    def test_load_cycle2_queries_returns_all_categories(self, cycle2_fixture_dir: Path) -> None:
        from tools.eval.cycle2_loader import load_cycle2_queries

        queries = load_cycle2_queries(cycle2_fixture_dir)

        categories = {q["category"] for q in queries}
        assert categories >= {
            "C1_keyword_exact",
            "C2_paraphrase",
            "C3_temporal",
            "C4_entity_heavy",
        }

    def test_load_cycle2_queries_preserves_fixture_shape(self, cycle2_fixture_dir: Path) -> None:
        from tools.eval.cycle2_loader import load_cycle2_queries

        queries = load_cycle2_queries(cycle2_fixture_dir)

        for q in queries:
            assert "id" in q
            assert "query" in q
            assert "category" in q
            assert "expected" in q
            assert isinstance(q["expected"], dict)
            assert "min_results" in q["expected"]

    def test_load_cycle2_queries_count_matches_fixture(self, cycle2_fixture_dir: Path) -> None:
        from tools.eval.cycle2_loader import load_cycle2_queries

        queries = load_cycle2_queries(cycle2_fixture_dir)

        assert len(queries) == 6

    def test_load_cycle2_queries_empty_dir_raises(self, tmp_path: Path) -> None:
        from tools.eval.cycle2_loader import load_cycle2_queries

        empty_dir = tmp_path / "empty_gold"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            load_cycle2_queries(empty_dir)


class TestCycle2PerCategoryMetrics:
    def test_per_category_recall_at_5(self, cycle2_fixture_dir: Path) -> None:
        from tools.eval.cycle2_loader import load_cycle2_queries

        queries = load_cycle2_queries(cycle2_fixture_dir)

        by_category: dict[str, list] = {}
        for q in queries:
            by_category.setdefault(q["category"], []).append(q)

        for category, items in by_category.items():
            assert len(items) >= 1, f"Category {category} has no queries"
            for item in items:
                assert "expected" in item
                assert "min_results" in item["expected"]

    def test_per_category_mrr_at_5(self, tmp_path: Path, monkeypatch) -> None:
        from tools.eval.run_eval import run_evaluation

        queries = [
            {
                "id": "C2-C1-001",
                "query": "test query a",
                "category": "C1_keyword_exact",
                "expected": {"min_results": 1, "must_contain_title": ["Title A"]},
            },
            {
                "id": "C2-C1-002",
                "query": "test query b",
                "category": "C1_keyword_exact",
                "expected": {"min_results": 0},
            },
            {
                "id": "C2-C4-001",
                "query": "test query c",
                "category": "C4_entity_heavy",
                "expected": {"min_results": 1, "must_contain_title": ["Title B"]},
            },
        ]

        from tools.search_journals import core as search_core

        monkeypatch.setattr("tools.eval.run_eval.load_golden_queries", lambda _: queries)
        monkeypatch.setattr("tools.eval.run_eval.load_aggregate_queries", lambda _: [])
        monkeypatch.setattr("tools.eval.run_eval.load_smart_aggregate_queries", lambda _: [])
        monkeypatch.setattr("tools.eval.run_eval.load_timeline_queries", lambda _: [])
        monkeypatch.setattr(
            search_core,
            "hierarchical_search",
            lambda query, level, semantic: {
                "merged_results": [
                    {"title": "Title A", "date": "2026-03-01"},
                    {"title": "Title B", "date": "2026-03-02"},
                ]
            },
        )

        result = run_evaluation(data_dir=tmp_path / "data")

        by_cat = result["by_category"]
        assert "C1_keyword_exact" in by_cat
        assert "C4_entity_heavy" in by_cat

        for cat_name, cat_metrics in by_cat.items():
            assert "mrr_at_5" in cat_metrics, f"Missing mrr_at_5 in {cat_name}"
            assert "recall_at_5" in cat_metrics, f"Missing recall_at_5 in {cat_name}"
            assert "query_count" in cat_metrics, f"Missing query_count in {cat_name}"

    def test_baseline_delta_includes_per_category_deltas(self, tmp_path: Path, monkeypatch) -> None:
        from tools.eval.run_eval import compare_against_baseline

        baseline_path = tmp_path / "baseline.json"
        baseline = {
            "frozen_at": "2026-03-31",
            "anchor_date": "2026-03-31",
            "metrics": {
                "mrr_at_5": 0.5,
                "recall_at_5": 0.6,
                "precision_at_5": 0.7,
            },
            "by_category": {
                "C1_keyword_exact": {
                    "mrr_at_5": 0.4,
                    "recall_at_5": 0.5,
                    "precision_at_5": 0.6,
                    "query_count": 2,
                },
                "C4_entity_heavy": {
                    "mrr_at_5": 0.6,
                    "recall_at_5": 0.7,
                    "precision_at_5": 0.8,
                    "query_count": 1,
                },
            },
            "per_query": [
                {"id": "C2-C1-001", "query": "test", "pass": True, "first_relevant_rank": 1},
            ],
            "recall_gaps": [],
        }
        baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(
            "tools.eval.run_eval.run_evaluation",
            lambda **kwargs: {
                "metrics": {
                    "mrr_at_5": 0.6,
                    "recall_at_5": 0.7,
                    "precision_at_5": 0.8,
                },
                "by_category": {
                    "C1_keyword_exact": {
                        "mrr_at_5": 0.5,
                        "recall_at_5": 0.6,
                        "precision_at_5": 0.7,
                        "query_count": 2,
                    },
                    "C4_entity_heavy": {
                        "mrr_at_5": 0.7,
                        "recall_at_5": 0.8,
                        "precision_at_5": 0.9,
                        "query_count": 1,
                    },
                },
                "per_query": [
                    {"id": "C2-C1-001", "query": "test", "pass": True, "first_relevant_rank": 1},
                ],
                "recall_gaps": [],
            },
        )

        comparison = compare_against_baseline(baseline_path=baseline_path)

        per_cat_deltas = comparison["diff"]["per_category_deltas"]
        assert isinstance(per_cat_deltas, dict)

        assert "C1_keyword_exact" in per_cat_deltas
        c1_delta = per_cat_deltas["C1_keyword_exact"]
        assert "mrr_at_5" in c1_delta
        assert "recall_at_5" in c1_delta
        assert c1_delta["mrr_at_5"]["delta"] == 0.1
        assert c1_delta["recall_at_5"]["delta"] == 0.1

        assert "C4_entity_heavy" in per_cat_deltas
        c4_delta = per_cat_deltas["C4_entity_heavy"]
        assert c4_delta["mrr_at_5"]["delta"] == 0.1
        assert c4_delta["recall_at_5"]["delta"] == 0.1

    def test_baseline_delta_per_category_shape(self, tmp_path: Path, monkeypatch) -> None:
        from tools.eval.run_eval import compare_against_baseline

        baseline_path = tmp_path / "baseline.json"
        baseline = {
            "frozen_at": "2026-03-31",
            "anchor_date": "2026-03-31",
            "metrics": {"mrr_at_5": 0.5, "recall_at_5": 0.5, "precision_at_5": 0.5},
            "by_category": {
                "C1_keyword_exact": {
                    "mrr_at_5": 0.4,
                    "recall_at_5": 0.5,
                    "precision_at_5": 0.6,
                    "query_count": 2,
                },
            },
            "per_query": [
                {"id": "Q1", "query": "q", "pass": True, "first_relevant_rank": 1},
            ],
            "recall_gaps": [],
        }
        baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(
            "tools.eval.run_eval.run_evaluation",
            lambda **kwargs: {
                "metrics": {"mrr_at_5": 0.6, "recall_at_5": 0.7, "precision_at_5": 0.8},
                "by_category": {
                    "C1_keyword_exact": {
                        "mrr_at_5": 0.5,
                        "recall_at_5": 0.6,
                        "precision_at_5": 0.7,
                        "query_count": 2,
                    },
                },
                "per_query": [
                    {"id": "Q1", "query": "q", "pass": True, "first_relevant_rank": 1},
                ],
                "recall_gaps": [],
            },
        )

        comparison = compare_against_baseline(baseline_path=baseline_path)

        delta_entry = comparison["diff"]["per_category_deltas"]["C1_keyword_exact"]
        for metric_name in ("mrr_at_5", "recall_at_5"):
            assert "baseline" in delta_entry[metric_name]
            assert "current" in delta_entry[metric_name]
            assert "delta" in delta_entry[metric_name]
            assert isinstance(delta_entry[metric_name]["baseline"], float)
            assert isinstance(delta_entry[metric_name]["current"], float)
            assert isinstance(delta_entry[metric_name]["delta"], float)
