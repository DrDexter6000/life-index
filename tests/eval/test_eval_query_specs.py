#!/usr/bin/env python3
"""Tests for QuerySpec typed loader (R2-B2).

Covers:
  1. All queries from real golden_queries.yaml convert to QuerySpec
  2. Non-overlay query round-trip (semantic equality)
  3. Synthetic overlay query_override case
  4. expected_titles_add / must_contain_title_override post-overlay dict
  5. broad_eval query preserves mode/predicate
  6. Unknown future fields preserved
  7. run_eval.py does not import eval_query_specs / QuerySpec
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tools.eval.eval_query_specs import dicts_to_query_specs, load_query_specs
from tools.eval.eval_serialization import assert_semantic_equal
from tools.eval.eval_types import QuerySpec

GOLDEN_QUERIES_PATH = Path("tools/eval/golden_queries.yaml")


def _load_raw_queries() -> list[dict]:
    payload = yaml.safe_load(GOLDEN_QUERIES_PATH.read_text(encoding="utf-8"))
    return payload.get("queries", []) if isinstance(payload, dict) else []


# ---------------------------------------------------------------------------
# 1. All queries from real golden_queries.yaml convert to QuerySpec
# ---------------------------------------------------------------------------


class TestRealYamlConversion:
    """Every query in the real YAML must convert without error."""

    def test_all_queries_convert(self) -> None:
        specs = load_query_specs()
        raw = _load_raw_queries()
        assert len(specs) == len(raw)

    def test_query_ids_populated(self) -> None:
        specs = load_query_specs()
        for spec in specs:
            assert spec.query_id, f"Empty query_id in {spec}"
            assert spec.query, f"Empty query in {spec}"
            assert spec.category, f"Empty category in {spec}"

    def test_expected_min_results_valid(self) -> None:
        specs = load_query_specs()
        for spec in specs:
            assert spec.expected_min_results >= 0


# ---------------------------------------------------------------------------
# 2. Non-overlay query round-trip
# ---------------------------------------------------------------------------


class TestNonOverlayRoundTrip:
    """QuerySpec.to_dict() must be semantically equal to the original dict."""

    def test_first_query_roundtrip(self) -> None:
        raw = _load_raw_queries()
        # GQ07 — simple non-overlay query
        q = next(q for q in raw if q.get("id") == "GQ07")
        spec = QuerySpec.from_dict(q)
        assert_semantic_equal(q, spec.to_dict())

    def test_broad_eval_query_roundtrip(self) -> None:
        raw = _load_raw_queries()
        # GQ52 — has broad_eval
        q = next(q for q in raw if q.get("id") == "GQ52")
        spec = QuerySpec.from_dict(q)
        assert_semantic_equal(q, spec.to_dict())

    def test_skip_until_phase_roundtrip(self) -> None:
        raw = _load_raw_queries()
        q = next(q for q in raw if q.get("id") == "GQ20")
        spec = QuerySpec.from_dict(q)
        assert_semantic_equal(q, spec.to_dict())
        assert spec.skip_until_phase == 3

    def test_audit_note_string_roundtrip(self) -> None:
        raw = _load_raw_queries()
        q = next(q for q in raw if q.get("id") == "GQ53")
        spec = QuerySpec.from_dict(q)
        assert_semantic_equal(q, spec.to_dict())
        assert isinstance(spec.audit_note, str)

    def test_audit_note_list_roundtrip(self) -> None:
        raw = _load_raw_queries()
        q = next(q for q in raw if q.get("id") == "GQ52")
        spec = QuerySpec.from_dict(q)
        assert isinstance(spec.audit_note, list)

    def test_empty_must_contain_title_roundtrip(self) -> None:
        raw = _load_raw_queries()
        # GQ128 has must_contain_title: []
        q = next(q for q in raw if q.get("id") == "GQ128")
        spec = QuerySpec.from_dict(q)
        rt = spec.to_dict()
        assert rt["expected"]["must_contain_title"] == []
        assert_semantic_equal(q, rt)

    def test_no_must_contain_title_roundtrip(self) -> None:
        raw = _load_raw_queries()
        # GQ09 has no must_contain_title
        q = next(q for q in raw if q.get("id") == "GQ09")
        spec = QuerySpec.from_dict(q)
        rt = spec.to_dict()
        assert "must_contain_title" not in rt["expected"]
        assert_semantic_equal(q, rt)

    def test_all_queries_roundtrip(self) -> None:
        """Every query in the YAML must round-trip."""
        raw = _load_raw_queries()
        for q in raw:
            spec = QuerySpec.from_dict(q)
            assert_semantic_equal(q, spec.to_dict())


# ---------------------------------------------------------------------------
# 3. Synthetic overlay query_override case
# ---------------------------------------------------------------------------


class TestOverlayQueryOverride:
    """Post-overlay dict with query_override."""

    def _make_overlay_dict(self) -> dict:
        return {
            "id": "GQ07",
            "query": "private override query",
            "category": "entity_expansion",
            "description": "Rare alias should still find the parent-child journal",
            "expected": {
                "min_results": 1,
                "must_contain_title": ["想念小英雄"],
            },
            "tags": ["entity", "alias", "expansion"],
            "_public_query": "小豆丁",
        }

    def test_overlay_fields(self) -> None:
        spec = QuerySpec.from_dict(self._make_overlay_dict())
        assert spec.query == "private override query"
        assert spec.public_query == "小豆丁"
        assert spec.overlay_applied is True

    def test_overlay_roundtrip(self) -> None:
        original = self._make_overlay_dict()
        spec = QuerySpec.from_dict(original)
        rt = spec.to_dict()
        assert rt["query"] == "private override query"
        assert rt["_public_query"] == "小豆丁"
        assert_semantic_equal(original, rt)

    def test_overlay_via_applied_query_ids(self) -> None:
        data = {
            "id": "GQ09",
            "query": "人生碎片",
            "category": "edge_case",
            "description": "test",
            "expected": {"min_results": 1},
            "tags": ["test"],
        }
        spec = QuerySpec.from_dict(data, applied_query_ids={"GQ09"})
        assert spec.overlay_applied is True
        # overlay_applied should NOT appear in to_dict
        rt = spec.to_dict()
        assert "overlay_applied" not in rt

    def test_non_overlay_via_applied_query_ids(self) -> None:
        data = {
            "id": "GQ09",
            "query": "人生碎片",
            "category": "edge_case",
            "description": "test",
            "expected": {"min_results": 1},
            "tags": ["test"],
        }
        spec = QuerySpec.from_dict(data, applied_query_ids=set())
        assert spec.overlay_applied is False


# ---------------------------------------------------------------------------
# 4. expected_titles_add / must_contain_title_override post-overlay dict
# ---------------------------------------------------------------------------


class TestOverlayTitleModifications:
    """Post-overlay dicts with modified expected.must_contain_title."""

    def test_must_contain_title_override(self) -> None:
        """Overlay replaced the entire must_contain_title list."""
        data = {
            "id": "GQ25",
            "query": "我的女儿",
            "category": "entity_expansion",
            "description": "test",
            "expected": {
                "min_results": 3,
                "must_contain_title": ["关于乐乐的事", "想念小英雄"],
            },
            "tags": ["test"],
        }
        spec = QuerySpec.from_dict(data)
        assert spec.expected_must_contain_title == ["关于乐乐的事", "想念小英雄"]
        assert_semantic_equal(data, spec.to_dict())

    def test_expected_titles_add(self) -> None:
        """Overlay extended the must_contain_title list."""
        data = {
            "id": "GQ25",
            "query": "我的女儿",
            "category": "entity_expansion",
            "description": "test",
            "expected": {
                "min_results": 3,
                "must_contain_title": [
                    "想念小英雄",
                    "关于乐乐的事",
                    "乐乐最爱的玩具陪我继续睡觉",
                    "new title from overlay",
                ],
            },
            "tags": ["test"],
        }
        spec = QuerySpec.from_dict(data)
        assert len(spec.expected_must_contain_title) == 4
        assert "new title from overlay" in spec.expected_must_contain_title
        assert_semantic_equal(data, spec.to_dict())


# ---------------------------------------------------------------------------
# 5. broad_eval query preserves mode/predicate
# ---------------------------------------------------------------------------


class TestBroadEvalPreservation:
    """broad_eval dict must survive round-trip intact."""

    def test_broad_eval_season(self) -> None:
        raw = _load_raw_queries()
        q = next(q for q in raw if q.get("id") == "GQ52")
        spec = QuerySpec.from_dict(q)
        assert spec.broad_eval is not None
        assert spec.broad_eval["mode"] == "predicate_precision"
        assert spec.broad_eval["predicate"]["type"] == "season"

    def test_broad_eval_date_range(self) -> None:
        raw = _load_raw_queries()
        q = next(q for q in raw if q.get("id") == "GQ086")
        spec = QuerySpec.from_dict(q)
        assert spec.broad_eval is not None
        pred = spec.broad_eval["predicate"]
        assert pred["type"] == "date_range"
        assert pred["date_range"]["since"] == "2026-01-01"

    def test_broad_eval_date_topic(self) -> None:
        raw = _load_raw_queries()
        q = next(q for q in raw if q.get("id") == "GQ099")
        spec = QuerySpec.from_dict(q)
        assert spec.broad_eval is not None
        pred = spec.broad_eval["predicate"]
        assert pred["type"] == "date_topic"
        assert "think" in pred["topic_hints"]


# ---------------------------------------------------------------------------
# 6. Unknown future fields preserved
# ---------------------------------------------------------------------------


class TestUnknownFieldPreservation:
    """Unknown top-level and expected-sub fields must survive round-trip."""

    def test_top_level_unknown_field(self) -> None:
        data = {
            "id": "GQ-TEST",
            "query": "test",
            "category": "test",
            "description": "test",
            "expected": {"min_results": 0},
            "tags": ["test"],
            "future_priority": 5,
            "future_metadata": {"source": "auto"},
        }
        spec = QuerySpec.from_dict(data)
        assert_semantic_equal(data, spec.to_dict())

    def test_expected_unknown_field(self) -> None:
        data = {
            "id": "GQ-TEST",
            "query": "test",
            "category": "test",
            "description": "test",
            "expected": {
                "min_results": 1,
                "future_threshold": 0.8,
            },
            "tags": ["test"],
        }
        spec = QuerySpec.from_dict(data)
        rt = spec.to_dict()
        assert rt["expected"]["future_threshold"] == 0.8
        assert_semantic_equal(data, rt)

    def test_local_notes_preserved(self) -> None:
        data = {
            "id": "GQ07",
            "query": "小豆丁",
            "category": "entity_expansion",
            "description": "test",
            "expected": {"min_results": 1},
            "tags": ["test"],
            "_local_notes": ["private note from overlay"],
        }
        spec = QuerySpec.from_dict(data)
        rt = spec.to_dict()
        assert rt["_local_notes"] == ["private note from overlay"]


# ---------------------------------------------------------------------------
# 7. Runtime integration check
# ---------------------------------------------------------------------------


class TestRuntimeIsolation:
    """run_eval.py must not import eval_query_specs or QuerySpec."""

    def test_run_eval_no_import(self) -> None:
        import importlib

        run_eval = importlib.import_module("tools.eval.run_eval")
        source = Path(run_eval.__file__).read_text(encoding="utf-8")
        assert "eval_query_specs" not in source
        assert "QuerySpec" not in source

    def test_main_no_import(self) -> None:
        main_path = Path("tools/eval/__main__.py")
        if not main_path.exists():
            pytest.skip("__main__.py does not exist")
        source = main_path.read_text(encoding="utf-8")
        assert "eval_query_specs" not in source
        assert "QuerySpec" not in source


# ---------------------------------------------------------------------------
# Unit tests for dicts_to_query_specs helper
# ---------------------------------------------------------------------------


class TestDictsToQuerySpecs:
    """dicts_to_query_specs converts a list of dicts correctly."""

    def test_empty_list(self) -> None:
        assert dicts_to_query_specs([]) == []

    def test_multiple_queries(self) -> None:
        data = [
            {
                "id": "Q1",
                "query": "a",
                "category": "test",
                "description": "test 1",
                "expected": {"min_results": 1},
                "tags": ["test"],
            },
            {
                "id": "Q2",
                "query": "b",
                "category": "test",
                "description": "test 2",
                "expected": {"min_results": 0},
                "tags": ["test"],
            },
        ]
        specs = dicts_to_query_specs(data)
        assert len(specs) == 2
        assert specs[0].query_id == "Q1"
        assert specs[1].query_id == "Q2"
