"""Contract tests for search_plan / ambiguity / hints output shape (Round 11 Phase 0 T0.2).

These tests verify the top-level field structure of hierarchical_search()
output when the new Round 11 fields are present.

Basic tests (field existence + type) should be GREEN after adding placeholder
fields. Advanced tests (intent_type values, date_range content) are marked
xfail until Phase 1/2 implementation.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from tools.search_journals.core import hierarchical_search
from tools.lib.index_freshness import FreshnessReport


@pytest.fixture(autouse=True)
def _mock_fresh_index_state():
    fresh_report = FreshnessReport(
        fts_fresh=True,
        vector_fresh=True,
        overall_fresh=True,
        issues=[],
    )
    with patch("tools.lib.index_freshness.check_full_freshness", return_value=fresh_report):
        with patch("tools.lib.pending_writes.has_pending", return_value=False):
            yield


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def result_with_nl_query(tmp_path, monkeypatch):
    """Run hierarchical_search with a NL query using isolated data dir."""
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))

    return hierarchical_search(query="过去60天我有多少次晚于10点睡觉？")


@pytest.fixture
def result_with_keyword_query(tmp_path, monkeypatch):
    """Run hierarchical_search with a keyword query."""
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))

    return hierarchical_search(query="团团")


# ── Basic field existence (should be GREEN after placeholder) ──────────


class TestSearchPlanFieldBasic:
    def test_search_plan_exists(self, result_with_nl_query):
        r = result_with_nl_query
        assert "search_plan" in r, "search_plan field must be present in output"

    def test_search_plan_is_dict_or_none(self, result_with_nl_query):
        r = result_with_nl_query
        sp = r["search_plan"]
        assert sp is None or isinstance(sp, dict), \
            "search_plan must be None or dict"

    def test_search_plan_not_none_when_query_given(self, result_with_nl_query):
        r = result_with_nl_query
        assert r["search_plan"] is not None, \
            "search_plan should not be None when query is provided"


class TestAmbiguityFieldBasic:
    def test_ambiguity_exists(self, result_with_nl_query):
        r = result_with_nl_query
        assert "ambiguity" in r, "ambiguity field must be present in output"

    def test_ambiguity_has_structure(self, result_with_nl_query):
        r = result_with_nl_query
        amb = r["ambiguity"]
        assert isinstance(amb, dict)
        assert "has_ambiguity" in amb
        assert "items" in amb
        assert isinstance(amb["has_ambiguity"], bool)
        assert isinstance(amb["items"], list)


class TestHintsFieldBasic:
    def test_hints_exists(self, result_with_nl_query):
        r = result_with_nl_query
        assert "hints" in r, "hints field must be present in output"

    def test_hints_is_list(self, result_with_nl_query):
        r = result_with_nl_query
        assert isinstance(r["hints"], list)


# ── Default values when no preprocessor yet (Phase 0 state) ────────────


class TestDefaultValues:
    def test_default_ambiguity_no_ambiguity(self, result_with_nl_query):
        """Without preprocessor, ambiguity should report no ambiguity."""
        r = result_with_nl_query
        # Default is no ambiguity until Phase 2 implements detection
        assert isinstance(r["ambiguity"]["has_ambiguity"], bool)

    def test_default_hints_empty(self, result_with_nl_query):
        """Without hints builder, hints should be empty list."""
        r = result_with_nl_query
        assert isinstance(r["hints"], list)

    def test_output_json_serializable(self, result_with_nl_query):
        """Full output must be JSON serializable."""
        r = result_with_nl_query
        json_str = json.dumps(r, default=str, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["success"] is True


# ── No query = no search_plan ──────────────────────────────────────────


class TestNoQuery:
    def test_search_plan_none_when_no_query(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))

        r = hierarchical_search(query=None, topic="work")
        assert r.get("search_plan") is None


# ── Advanced tests (Phase 1/2 verified) ──────────────


class TestSearchPlanAdvanced:
    def test_intent_type_is_count(self, result_with_nl_query):
        r = result_with_nl_query
        assert r["search_plan"]["intent_type"] == "count"

    def test_date_range_not_null(self, result_with_nl_query):
        r = result_with_nl_query
        assert r["search_plan"]["date_range"] is not None

    def test_keywords_not_empty(self, result_with_nl_query):
        r = result_with_nl_query
        assert len(r["search_plan"]["keywords"]) > 0

    def test_keyword_query_mode(self, result_with_keyword_query):
        r = result_with_keyword_query
        assert r["search_plan"]["query_mode"] == "keyword"


class TestAmbiguityAdvanced:
    def test_aggregation_ambiguity(self, result_with_nl_query):
        r = result_with_nl_query
        types = [item["type"] for item in r["ambiguity"]["items"]]
        assert "aggregation_requires_agent_judgement" in types

    def test_hints_not_empty_for_count(self, result_with_nl_query):
        r = result_with_nl_query
        assert len(r["hints"]) > 0
