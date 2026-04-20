"""Tests for search_plan / ambiguity / hints type definitions (Round 11 Phase 0 T0.1)."""

from __future__ import annotations

import json
from enum import Enum

import pytest

from tools.search_journals.query_types import (
    AmbiguityItem,
    AmbiguityReport,
    AmbiguityType,
    DateRange,
    HintItem,
    IntentType,
    QueryMode,
    SearchPlan,
)


# ── Enum completeness ──────────────────────────────────────────────────


class TestIntentType:
    def test_has_required_members(self) -> None:
        expected = {"recall", "count", "compare", "summarize", "unknown"}
        actual = {m.value for m in IntentType}
        assert actual == expected

    def test_is_enum(self) -> None:
        assert issubclass(IntentType, Enum)


class TestQueryMode:
    def test_has_required_members(self) -> None:
        expected = {"keyword", "natural_language", "mixed"}
        actual = {m.value for m in QueryMode}
        assert actual == expected

    def test_is_enum(self) -> None:
        assert issubclass(QueryMode, Enum)


class TestAmbiguityType:
    def test_has_required_members(self) -> None:
        expected = {
            "aggregation_requires_agent_judgement",
            "time_range_interpretation",
            "entity_resolution_multiple_candidates",
            "query_too_broad",
        }
        actual = {m.value for m in AmbiguityType}
        assert actual == expected


# ── DateRange ──────────────────────────────────────────────────────────


class TestDateRange:
    def test_full_construction(self) -> None:
        dr = DateRange(since="2026-02-16", until="2026-04-18", source="relative_time_parse")
        assert dr.since == "2026-02-16"
        assert dr.until == "2026-04-18"
        assert dr.source == "relative_time_parse"

    def test_optional_fields_default_none(self) -> None:
        dr = DateRange()
        assert dr.since is None
        assert dr.until is None
        assert dr.source is None

    def test_to_dict(self) -> None:
        dr = DateRange(since="2026-02-16", until="2026-04-18", source="test")
        d = dr.to_dict()
        assert d["since"] == "2026-02-16"
        assert d["until"] == "2026-04-18"
        assert d["source"] == "test"

    def test_to_dict_none_fields(self) -> None:
        dr = DateRange()
        d = dr.to_dict()
        assert d["since"] is None


# ── SearchPlan ─────────────────────────────────────────────────────────


class TestSearchPlan:
    def _make_plan(
        self,
        *,
        raw_query: str = "测试查询",
        normalized_query: str = "测试查询",
        intent_type: IntentType = IntentType.RECALL,
        query_mode: QueryMode = QueryMode.KEYWORD,
        keywords: list[str] | None = None,
        date_range: DateRange | None = None,
        topic_hints: list[str] | None = None,
        entity_hints_used: list[dict] | None = None,
        expanded_query: str = "测试",
        pipelines: dict[str, bool] | None = None,
    ) -> SearchPlan:
        return SearchPlan(
            raw_query=raw_query,
            normalized_query=normalized_query,
            intent_type=intent_type,
            query_mode=query_mode,
            keywords=keywords or ["测试"],
            date_range=date_range,
            topic_hints=topic_hints or [],
            entity_hints_used=entity_hints_used or [],
            expanded_query=expanded_query,
            pipelines=pipelines or {"keyword": True, "semantic": True},
        )

    def test_full_construction(self) -> None:
        plan = self._make_plan()
        assert plan.raw_query == "测试查询"
        assert plan.intent_type == IntentType.RECALL

    def test_date_range_can_be_none(self) -> None:
        plan = self._make_plan(date_range=None)
        assert plan.date_range is None

    def test_date_range_can_be_daterange(self) -> None:
        plan = self._make_plan(date_range=DateRange(since="2026-01-01", until="2026-12-31"))
        assert plan.date_range is not None
        assert plan.date_range.since == "2026-01-01"

    def test_to_dict_json_serializable(self) -> None:
        plan = self._make_plan()
        d = plan.to_dict()
        # Must not raise
        json_str = json.dumps(d, ensure_ascii=False)
        assert "测试查询" in json_str

    def test_to_dict_keys_match_prd(self) -> None:
        plan = self._make_plan()
        d = plan.to_dict()
        expected_keys = {
            "raw_query", "normalized_query", "intent_type", "query_mode",
            "keywords", "date_range", "topic_hints", "entity_hints_used",
            "expanded_query", "pipelines",
        }
        assert expected_keys.issubset(set(d.keys()))

    def test_entity_hints_used_default_empty(self) -> None:
        plan = self._make_plan()
        assert plan.entity_hints_used == []

    def test_pipelines_dict(self) -> None:
        plan = self._make_plan()
        assert plan.pipelines == {"keyword": True, "semantic": True}


# ── AmbiguityItem + AmbiguityReport ────────────────────────────────────


class TestAmbiguityItem:
    def test_construction(self) -> None:
        item = AmbiguityItem(
            type=AmbiguityType.AGGREGATION_REQUIRES_AGENT_JUDGEMENT,
            severity="high",
            reason="search cannot derive exact count deterministically",
            candidates=[],
        )
        assert item.type == AmbiguityType.AGGREGATION_REQUIRES_AGENT_JUDGEMENT
        assert item.severity == "high"

    def test_severity_literal(self) -> None:
        for sev in ("low", "medium", "high"):
            item = AmbiguityItem(
                type=AmbiguityType.QUERY_TOO_BROAD,
                severity=sev,
                reason="test",
                candidates=[],
            )
            assert item.severity == sev

    def test_to_dict(self) -> None:
        item = AmbiguityItem(
            type=AmbiguityType.TIME_RANGE_INTERPRETATION,
            severity="medium",
            reason="test",
            candidates=["a", "b"],
        )
        d = item.to_dict()
        assert d["type"] == "time_range_interpretation"
        assert d["candidates"] == ["a", "b"]


class TestAmbiguityReport:
    def test_no_ambiguity(self) -> None:
        report = AmbiguityReport(has_ambiguity=False, items=[])
        assert not report.has_ambiguity
        assert report.items == []

    def test_with_items(self) -> None:
        items = [
            AmbiguityItem(
                type=AmbiguityType.AGGREGATION_REQUIRES_AGENT_JUDGEMENT,
                severity="high",
                reason="test",
                candidates=[],
            )
        ]
        report = AmbiguityReport(has_ambiguity=True, items=items)
        assert report.has_ambiguity
        assert len(report.items) == 1

    def test_to_dict_json_serializable(self) -> None:
        items = [
            AmbiguityItem(
                type=AmbiguityType.QUERY_TOO_BROAD,
                severity="low",
                reason="test",
                candidates=[],
            )
        ]
        report = AmbiguityReport(has_ambiguity=True, items=items)
        d = report.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["has_ambiguity"] is True


# ── HintItem ───────────────────────────────────────────────────────────


class TestHintItem:
    def test_construction(self) -> None:
        hint = HintItem(
            type="retrieval_boundary",
            severity="high",
            message="Search returns evidence, not final answer.",
        )
        assert hint.type == "retrieval_boundary"
        assert hint.severity == "high"
        assert "evidence" in hint.message

    def test_to_dict(self) -> None:
        hint = HintItem(type="test", severity="low", message="msg")
        d = hint.to_dict()
        assert set(d.keys()) == {"type", "severity", "message"}
        assert d["type"] == "test"
