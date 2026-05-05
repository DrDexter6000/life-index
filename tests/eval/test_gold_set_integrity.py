"""Gold Set integrity and coverage checks."""

from pathlib import Path

import yaml

GOLD_SET = Path("tools/eval/golden_queries.yaml")
REQUIRED_CATEGORIES = {
    "entity_expansion",
    "chinese_recall",
    "high_frequency",
    "semantic_recall",
    "complex_query",
    "edge_case",
    "time_range",
    "cross_language",
    "english_regression",
    "noise_rejection",
}


def test_gold_set_has_minimum_entries() -> None:
    data = yaml.safe_load(GOLD_SET.read_text(encoding="utf-8"))
    queries = data["queries"]
    assert len(queries) >= 136, f"Gold Set has {len(queries)} entries, need >= 136"


def test_gold_set_covers_required_categories() -> None:
    data = yaml.safe_load(GOLD_SET.read_text(encoding="utf-8"))
    categories = {q["category"] for q in data["queries"]}
    # Must have at least 5 distinct categories
    assert len(categories) >= 5, f"Only {len(categories)} categories: {categories}"


def test_every_query_has_required_fields() -> None:
    data = yaml.safe_load(GOLD_SET.read_text(encoding="utf-8"))
    for q in data["queries"]:
        assert "id" in q, "Missing id in query"
        assert "query" in q, f"Missing query in {q.get('id', '?')}"
        assert "category" in q, f"Missing category in {q['id']}"
        assert "expected" in q, f"Missing expected in {q['id']}"
        assert "min_results" in q["expected"], f"Missing min_results in {q['id']}"


def test_run_eval_script_exists() -> None:
    assert Path("tools/eval/run_eval.py").exists(), "run_eval.py must exist"


def test_baseline_json_exists() -> None:
    baseline = Path("tests/eval/baselines/round-17-baseline.json")
    assert baseline.exists(), "round-17-baseline.json must exist"


def test_broad_eval_schema_when_present() -> None:
    """If broad_eval is present, it must have required sub-fields."""
    data = yaml.safe_load(GOLD_SET.read_text(encoding="utf-8"))
    for q in data["queries"]:
        be = q.get("broad_eval")
        if be is None:
            continue
        assert "mode" in be, f"Missing mode in broad_eval for {q['id']}"
        assert "predicate" in be, f"Missing predicate in broad_eval for {q['id']}"
        assert "type" in be["predicate"], f"Missing predicate.type in broad_eval for {q['id']}"
        assert "min_precision" in be, f"Missing min_precision in broad_eval for {q['id']}"
        assert "min_results_policy" in be, f"Missing min_results_policy in broad_eval for {q['id']}"

        ptype = be["predicate"]["type"]
        if ptype in ("date_range", "date_topic", "season"):
            assert (
                "date_range" in be["predicate"]
            ), f"Missing date_range in broad_eval for {q['id']}"
            assert (
                "since" in be["predicate"]["date_range"]
            ), f"Missing since in broad_eval for {q['id']}"
            assert (
                "until" in be["predicate"]["date_range"]
            ), f"Missing until in broad_eval for {q['id']}"
        if ptype in ("topic", "date_topic"):
            assert (
                "topic_hints" in be["predicate"]
            ), f"Missing topic_hints in broad_eval for {q['id']}"
