"""Tests for ambiguity detector and hints builder (Round 11 Phase 2)."""

from __future__ import annotations

import pytest

from tools.search_journals.ambiguity_detector import detect_ambiguity
from tools.search_journals.hints_builder import build_hints
from tools.search_journals.query_types import (
    AmbiguityReport,
    AmbiguityType,
    DateRange,
    HintItem,
    IntentType,
    QueryMode,
    SearchPlan,
)


def _plan(**overrides) -> SearchPlan:
    defaults = dict(
        raw_query="test",
        normalized_query="test",
        intent_type=IntentType.RECALL,
        query_mode=QueryMode.KEYWORD,
        keywords=["test"],
        date_range=None,
        topic_hints=[],
        entity_hints_used=[],
        expanded_query="test",
        pipelines={"keyword": True, "semantic": True},
    )
    defaults.update(overrides)
    return SearchPlan(**defaults)


# ── Ambiguity Detector ────────────────────────────────────────────────


class TestAmbiguityAggregation:
    def test_count_intent_triggers_aggregation(self):
        plan = _plan(intent_type=IntentType.COUNT)
        report = detect_ambiguity(plan, "多少次")
        assert report.has_ambiguity
        types = [item.type for item in report.items]
        assert AmbiguityType.AGGREGATION_REQUIRES_AGENT_JUDGEMENT in types

    def test_compare_intent_triggers_aggregation(self):
        plan = _plan(intent_type=IntentType.COMPARE)
        report = detect_ambiguity(plan, "哪个多")
        assert report.has_ambiguity
        types = [item.type for item in report.items]
        assert AmbiguityType.AGGREGATION_REQUIRES_AGENT_JUDGEMENT in types

    def test_summarize_intent_triggers_aggregation(self):
        plan = _plan(intent_type=IntentType.SUMMARIZE)
        report = detect_ambiguity(plan, "什么进展")
        assert report.has_ambiguity

    def test_aggregation_severity_is_high(self):
        plan = _plan(intent_type=IntentType.COUNT)
        report = detect_ambiguity(plan, "多少次")
        agg = [i for i in report.items if i.type == AmbiguityType.AGGREGATION_REQUIRES_AGENT_JUDGEMENT]
        assert agg[0].severity == "high"


class TestAmbiguityTimeRange:
    def test_relative_time_triggers_time_interpretation(self):
        plan = _plan(date_range=DateRange(since="2026-02-16", until="2026-04-18", source="relative_time_parse"))
        report = detect_ambiguity(plan, "过去60天我有多少次晚于10点睡觉？")
        types = [item.type for item in report.items]
        assert AmbiguityType.TIME_RANGE_INTERPRETATION in types

    def test_no_date_range_no_time_ambiguity(self):
        plan = _plan(date_range=None)
        report = detect_ambiguity(plan, "乐乐")
        types = [item.type for item in report.items]
        assert AmbiguityType.TIME_RANGE_INTERPRETATION not in types

    def test_time_ambiguity_has_candidates(self):
        plan = _plan(date_range=DateRange(since="2026-03-01", until="2026-03-31", source="relative_time_parse"))
        report = detect_ambiguity(plan, "上个月...")
        time_items = [i for i in report.items if i.type == AmbiguityType.TIME_RANGE_INTERPRETATION]
        assert len(time_items) == 1
        assert len(time_items[0].candidates) > 0


class TestAmbiguityEntityMultipleCandidates:
    def test_multiple_entity_candidates(self):
        plan = _plan()
        entity_hints = [
            {"matched_term": "女儿", "entity_id": "e1"},
            {"matched_term": "女儿", "entity_id": "e2"},
        ]
        report = detect_ambiguity(plan, "女儿", entity_hints=entity_hints)
        types = [item.type for item in report.items]
        assert AmbiguityType.ENTITY_RESOLUTION_MULTIPLE_CANDIDATES in types

    def test_single_entity_no_ambiguity(self):
        plan = _plan()
        entity_hints = [{"matched_term": "乐乐", "entity_id": "e1"}]
        report = detect_ambiguity(plan, "乐乐", entity_hints=entity_hints)
        types = [item.type for item in report.items]
        assert AmbiguityType.ENTITY_RESOLUTION_MULTIPLE_CANDIDATES not in types


class TestAmbiguityQueryTooBroad:
    def test_no_keywords_triggers_broad(self):
        plan = _plan(keywords=[])
        report = detect_ambiguity(plan, "我的")
        types = [item.type for item in report.items]
        assert AmbiguityType.QUERY_TOO_BROAD in types

    def test_single_char_keywords_triggers_broad(self):
        plan = _plan(keywords=["我", "的"])
        report = detect_ambiguity(plan, "我的")
        types = [item.type for item in report.items]
        assert AmbiguityType.QUERY_TOO_BROAD in types


class TestAmbiguityNoAmbiguity:
    def test_simple_recall_no_ambiguity(self):
        plan = _plan(intent_type=IntentType.RECALL, keywords=["乐乐"])
        report = detect_ambiguity(plan, "乐乐")
        assert not report.has_ambiguity
        assert report.items == []


class TestAmbiguityMultipleSignals:
    def test_count_plus_time(self):
        plan = _plan(
            intent_type=IntentType.COUNT,
            date_range=DateRange(since="2026-02-16", until="2026-04-18", source="relative_time_parse"),
            keywords=["睡觉"],
        )
        report = detect_ambiguity(plan, "过去60天我有多少次晚于10点睡觉？")
        assert report.has_ambiguity
        assert len(report.items) >= 2


# ── Hints Builder ──────────────────────────────────────────────────────


class TestHintsAggregation:
    def test_count_intent_produces_hints(self):
        plan = _plan(intent_type=IntentType.COUNT)
        ambiguity = AmbiguityReport(has_ambiguity=True, items=[])
        hints = build_hints(plan, ambiguity)
        assert len(hints) >= 1
        types = [h.type for h in hints]
        assert "retrieval_boundary" in types

    def test_retrieval_boundary_first_is_high_severity(self):
        plan = _plan(intent_type=IntentType.COUNT)
        ambiguity = AmbiguityReport(has_ambiguity=True, items=[])
        hints = build_hints(plan, ambiguity)
        retrieval = [h for h in hints if h.type == "retrieval_boundary"]
        assert retrieval[0].severity == "high"


class TestHintsNoAmbiguity:
    def test_recall_no_ambiguity_minimal_hints(self):
        plan = _plan(intent_type=IntentType.RECALL, keywords=["乐乐"])
        ambiguity = AmbiguityReport(has_ambiguity=False, items=[])
        hints = build_hints(plan, ambiguity)
        assert len(hints) <= 1


class TestHintsTimeRange:
    def test_parsed_time_range_hint(self):
        plan = _plan(
            date_range=DateRange(since="2026-02-16", until="2026-04-18", source="relative_time_parse"),
        )
        ambiguity = AmbiguityReport(has_ambiguity=False, items=[])
        hints = build_hints(plan, ambiguity)
        types = [h.type for h in hints]
        assert "time_range_parsed" in types


class TestHintsConstraints:
    def test_max_five_hints(self):
        # Construct a plan that triggers many hints
        plan = _plan(
            intent_type=IntentType.COUNT,
            date_range=DateRange(since="2026-01-01", until="2026-12-31", source="relative_time_parse"),
            topic_hints=["work", "health"],
            entity_hints_used=[{"id": "e1"}],
        )
        ambiguity = AmbiguityReport(has_ambiguity=True, items=[])
        hints = build_hints(plan, ambiguity)
        assert len(hints) <= 5

    def test_message_length_under_120(self):
        plan = _plan(
            intent_type=IntentType.COUNT,
            date_range=DateRange(since="2026-01-01", until="2026-12-31", source="relative_time_parse"),
        )
        ambiguity = AmbiguityReport(has_ambiguity=True, items=[])
        hints = build_hints(plan, ambiguity)
        for h in hints:
            assert len(h.message) <= 120


class TestHintsToDict:
    def test_to_dict_keys(self):
        hint = HintItem(type="test", severity="low", message="msg")
        d = hint.to_dict()
        assert set(d.keys()) == {"type", "severity", "message"}
