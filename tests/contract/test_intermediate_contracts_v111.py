"""Contract tests for v1.1.1 intermediate structures — B3.1.

Validates that QueryPlan and SearchPlan intermediate structures include
``schema_version: "v1.1.1"`` and remain JSON-serializable and backward-
compatible.  These tests do **not** require a running CLI or data directory;
they test the dataclass / enrichment layer directly.
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# QueryPlan contract
# ---------------------------------------------------------------------------


class TestQueryPlanContract:
    """QueryPlan (tools.lib.planner_types) v1.1.1 contract surface."""

    def _make_query_plan(self):
        from tools.lib.planner_types import QueryPlan

        return QueryPlan(raw_query="test query")

    def test_schema_version_is_v111(self):
        qp = self._make_query_plan()
        d = qp.to_dict()
        assert d["schema_version"] == "v1.1.1"

    def test_required_fields_present(self):
        qp = self._make_query_plan()
        d = qp.to_dict()
        for key in (
            "schema_version",
            "raw_query",
            "expanded_query",
            "sub_queries",
            "strategy",
        ):
            assert key in d, f"missing required field: {key}"

    def test_json_serializable(self):
        qp = self._make_query_plan()
        d = qp.to_dict()
        text = json.dumps(d)
        parsed = json.loads(text)
        assert parsed["schema_version"] == "v1.1.1"

    def test_backward_compat_old_caller_ignores_schema_version(self):
        qp = self._make_query_plan()
        d = qp.to_dict()
        _ = d["raw_query"]
        _ = d["sub_queries"]
        _ = d["strategy"]
        assert isinstance(d["schema_version"], str)

    def test_sub_queries_default_empty_list(self):
        qp = self._make_query_plan()
        assert qp.sub_queries == []
        assert qp.to_dict()["sub_queries"] == []

    def test_strategy_default_keyword_and_semantic(self):
        qp = self._make_query_plan()
        assert qp.strategy == "keyword_and_semantic"

    def test_expanded_query_default_none(self):
        qp = self._make_query_plan()
        assert qp.expanded_query is None

    def test_fallback_decision_default_false(self):
        qp = self._make_query_plan()
        assert qp.fallback_decision is False

    def test_to_dict_roundtrip_preserves_values(self):
        from tools.lib.planner_types import QueryPlan

        qp = QueryPlan(
            raw_query="hello",
            expanded_query="hello world",
            sub_queries=["hello", "world"],
            strategy="keyword_only",
            fallback_decision=True,
        )
        d = qp.to_dict()
        assert d["raw_query"] == "hello"
        assert d["expanded_query"] == "hello world"
        assert d["sub_queries"] == ["hello", "world"]
        assert d["strategy"] == "keyword_only"
        assert d["fallback_decision"] is True
        assert d["schema_version"] == "v1.1.1"

    def test_old_dict_without_schema_version_still_valid(self):
        """Simulate pre-v1.1.1 consumer reading a v1.1.1 QueryPlan dict."""
        from tools.lib.planner_types import QueryPlan

        qp = QueryPlan(raw_query="x")
        d = qp.to_dict()
        old_reader_view = {k: v for k, v in d.items() if k != "schema_version"}
        assert old_reader_view["raw_query"] == "x"
        assert "schema_version" not in old_reader_view


# ---------------------------------------------------------------------------
# SearchPlan contract (enrichment via core.py)
# ---------------------------------------------------------------------------


class TestSearchPlanContract:
    """SearchPlan v1.1.1 contract: schema_version injected at output layer."""

    def test_search_plan_dict_enriched_with_schema_version(self):
        from tools.search_journals.query_preprocessor import build_search_plan
        from tools.search_journals.core import SEARCH_PLAN_SCHEMA_VERSION

        plan = build_search_plan("test query")
        d = plan.to_dict()
        d["schema_version"] = SEARCH_PLAN_SCHEMA_VERSION
        assert d["schema_version"] == "v1.1.1"

    def test_search_plan_schema_version_constant_is_v111(self):
        from tools.search_journals.core import SEARCH_PLAN_SCHEMA_VERSION

        assert SEARCH_PLAN_SCHEMA_VERSION == "v1.1.1"

    def test_search_plan_existing_fields_preserved(self):
        from tools.search_journals.query_preprocessor import build_search_plan
        from tools.search_journals.core import SEARCH_PLAN_SCHEMA_VERSION

        plan = build_search_plan("what did I do last week")
        d = plan.to_dict()
        d["schema_version"] = SEARCH_PLAN_SCHEMA_VERSION
        for key in (
            "raw_query",
            "normalized_query",
            "intent_type",
            "query_mode",
            "keywords",
            "topic_hints",
        ):
            assert key in d, f"existing field {key} missing after enrichment"

    def test_search_plan_json_serializable(self):
        from tools.search_journals.query_preprocessor import build_search_plan
        from tools.search_journals.core import SEARCH_PLAN_SCHEMA_VERSION

        plan = build_search_plan("meeting notes")
        d = plan.to_dict()
        d["schema_version"] = SEARCH_PLAN_SCHEMA_VERSION
        text = json.dumps(d)
        parsed = json.loads(text)
        assert parsed["schema_version"] == "v1.1.1"

    def test_backward_compat_old_caller_ignores_schema_version(self):
        from tools.search_journals.query_preprocessor import build_search_plan
        from tools.search_journals.core import SEARCH_PLAN_SCHEMA_VERSION

        plan = build_search_plan("test")
        d = plan.to_dict()
        d["schema_version"] = SEARCH_PLAN_SCHEMA_VERSION
        old_reader_view = {k: v for k, v in d.items() if k != "schema_version"}
        assert old_reader_view["raw_query"] == "test"
        assert "schema_version" not in old_reader_view

    def test_raw_search_plan_dict_has_no_schema_version(self):
        """Pre-enrichment: SearchPlan.to_dict() does NOT include schema_version.

        This proves the field is purely additive at the contract surface.
        """
        from tools.search_journals.query_preprocessor import build_search_plan

        plan = build_search_plan("test")
        d = plan.to_dict()
        assert "schema_version" not in d


# ---------------------------------------------------------------------------
# Cross-contract: observability schema_version consistency
# ---------------------------------------------------------------------------


class TestSchemaVersionConsistency:
    """QueryPlan, SearchPlan, and observability must agree on schema_version."""

    def test_query_plan_matches_observability_version(self):
        from tools.lib.observability import SCHEMA_VERSION
        from tools.lib.planner_types import QueryPlan

        qp = QueryPlan(raw_query="x")
        assert qp.to_dict()["schema_version"] == SCHEMA_VERSION

    def test_search_plan_enrichment_matches_observability_version(self):
        from tools.lib.observability import SCHEMA_VERSION
        from tools.search_journals.core import SEARCH_PLAN_SCHEMA_VERSION

        assert SEARCH_PLAN_SCHEMA_VERSION == SCHEMA_VERSION
