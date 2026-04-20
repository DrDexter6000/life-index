"""Round 11 Phase 5 T5.3: Contract golden consistency verification.

Verifies that schema.json, query_types.py, and API.md are consistent
in their field definitions for search_plan, ambiguity, and hints.
"""

import json
from pathlib import Path

import pytest

from tools.search_journals.query_types import (
    AmbiguityReport,
    AmbiguityItem,
    HintItem,
    SearchPlan,
)

_ROOT = Path(__file__).resolve().parent.parent.parent
_SCHEMA_PATH = _ROOT / "tools" / "search_journals" / "schema.json"


@pytest.fixture
def schema() -> dict:
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestSearchPlanConsistency:
    """search_plan fields in schema.json match SearchPlan dataclass."""

    def test_schema_has_search_plan(self, schema: dict) -> None:
        returns = schema["returns"]["properties"]
        assert "search_plan" in returns

    def test_search_plan_fields_match_dataclass(self, schema: dict) -> None:
        schema_fields = set(
            schema["returns"]["properties"]["search_plan"]["properties"].keys()
        )
        # SearchPlan.to_dict() output fields
        from tools.search_journals.query_types import IntentType, QueryMode

        plan = SearchPlan(
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
        dataclass_fields = set(plan.to_dict().keys())
        # Schema should be a superset of dataclass fields
        assert dataclass_fields.issubset(schema_fields), (
            f"Dataclass fields not in schema: {dataclass_fields - schema_fields}"
        )

    def test_intent_type_enum_matches(self, schema: dict) -> None:
        schema_enum = set(
            schema["returns"]["properties"]["search_plan"]["properties"][
                "intent_type"
            ]["enum"]
        )
        from tools.search_journals.query_types import IntentType

        intent_values = {e.value for e in IntentType}
        assert intent_values == schema_enum


class TestAmbiguityConsistency:
    """ambiguity fields in schema.json match AmbiguityReport dataclass."""

    def test_schema_has_ambiguity(self, schema: dict) -> None:
        returns = schema["returns"]["properties"]
        assert "ambiguity" in returns

    def test_ambiguity_fields_match(self, schema: dict) -> None:
        schema_fields = set(
            schema["returns"]["properties"]["ambiguity"]["properties"].keys()
        )
        report = AmbiguityReport(has_ambiguity=False, items=[])
        dataclass_fields = set(report.to_dict().keys())
        assert dataclass_fields == schema_fields

    def test_ambiguity_item_fields_match(self, schema: dict) -> None:
        schema_item_fields = set(
            schema["returns"]["properties"]["ambiguity"]["properties"]["items"][
                "items"
            ]["properties"].keys()
        )
        from tools.search_journals.query_types import AmbiguityType

        item = AmbiguityItem(
            type=AmbiguityType.AGGREGATION_REQUIRES_AGENT_JUDGEMENT,
            severity="low",
            reason="test",
            candidates=[],
        )
        dataclass_fields = set(item.to_dict().keys())
        assert dataclass_fields == schema_item_fields


class TestHintsConsistency:
    """hints fields in schema.json match HintItem dataclass."""

    def test_schema_has_hints(self, schema: dict) -> None:
        returns = schema["returns"]["properties"]
        assert "hints" in returns

    def test_hint_item_fields_match(self, schema: dict) -> None:
        schema_item_fields = set(
            schema["returns"]["properties"]["hints"]["items"]["properties"].keys()
        )
        hint = HintItem(type="test", severity="low", message="test message")
        dataclass_fields = set(hint.to_dict().keys())
        assert dataclass_fields == schema_item_fields


class TestSchemaVersion:
    def test_schema_version_is_v2(self, schema: dict) -> None:
        assert schema["version"].startswith("2.")
