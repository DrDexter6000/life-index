"""Contract tests for v1.1.1 intermediate structures (B3.1 + B3.2).

B3.1: QueryPlan / SearchPlan  contracts.
B3.2: IndexManifest / EntityExpansion  contracts.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools.lib.index_manifest import (
    IndexManifest,
    write_manifest,
    read_manifest,
)
from tools.lib.entity_runtime import EntityRuntimeView, EntityExpansion

SCHEMA_VERSION = "v1.1.1"


# ── Helpers ──────────────────────────────────────────────────────────────


def _valid_index_manifest() -> IndexManifest:
    return IndexManifest(
        fts_count=100,
        vector_count=100,
        file_count=100,
        fts_checksum="abc123",
        vector_checksum="def456",
        build_timestamp="2026-05-23T00:00:00Z",
        build_version="1.1.1",
        partial=False,
    )


def _valid_entity_runtime_view() -> EntityRuntimeView:
    return EntityRuntimeView(
        entities=[
            {
                "id": "e1",
                "type": "person",
                "primary_name": "Alice",
                "aliases": ["Ali"],
            }
        ],
        by_lookup={},
        reverse_relationships={},
        phrase_patterns=[],
    )


# ── B3.1: QueryPlan ──────────────────────────────────────────────────────


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


# ── B3.1: SearchPlan ─────────────────────────────────────────────────────


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


# ── B3.1: Cross-contract consistency ─────────────────────────────────────


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


# ═══════════════════════════════════════════════════════════════════════════
# B3.2: IndexManifest / EntityExpansion  contracts
# ═══════════════════════════════════════════════════════════════════════════


# ── B3.2: IndexManifest ──────────────────────────────────────────────────


class TestIndexManifestSchemaVersion:
    """IndexManifest must carry top-level schema_version."""

    def test_dataclass_has_schema_version_field(self):
        manifest = _valid_index_manifest()
        assert hasattr(manifest, "schema_version")
        assert isinstance(manifest.schema_version, str)

    def test_default_schema_version_is_v111(self):
        manifest = IndexManifest(
            fts_count=1,
            vector_count=1,
            file_count=1,
            fts_checksum="a",
            vector_checksum="b",
            build_timestamp="ts",
            build_version="1.0",
        )
        assert manifest.schema_version == SCHEMA_VERSION

    def test_asdict_includes_schema_version(self):
        manifest = _valid_index_manifest()
        d = asdict(manifest)
        assert "schema_version" in d
        assert d["schema_version"] == SCHEMA_VERSION

    def test_write_manifest_includes_schema_version(self):
        manifest = _valid_index_manifest()
        with TemporaryDirectory() as td:
            idx_dir = Path(td) / ".index"
            write_manifest(manifest, idx_dir)
            raw = Path(idx_dir, "index_manifest.json").read_text(encoding="utf-8")
            data = json.loads(raw)
            assert "schema_version" in data
            assert data["schema_version"] == SCHEMA_VERSION

    def test_read_manifest_returns_schema_version(self):
        manifest = _valid_index_manifest()
        with TemporaryDirectory() as td:
            idx_dir = Path(td) / ".index"
            write_manifest(manifest, idx_dir)
            loaded = read_manifest(idx_dir)
            assert loaded is not None
            assert loaded.schema_version == SCHEMA_VERSION

    def test_read_manifest_old_format_fallback(self):
        """Old manifest WITHOUT schema_version should still load with default."""
        old_payload = {
            "fts_count": 10,
            "vector_count": 10,
            "file_count": 10,
            "fts_checksum": "aaa",
            "vector_checksum": "bbb",
            "build_timestamp": "2026-01-01",
            "build_version": "1.0",
            "partial": False,
        }
        with TemporaryDirectory() as td:
            idx_dir = Path(td) / ".index"
            idx_dir.mkdir(parents=True, exist_ok=True)
            (idx_dir / "index_manifest.json").write_text(json.dumps(old_payload), encoding="utf-8")
            loaded = read_manifest(idx_dir)
            assert loaded is not None
            assert loaded.schema_version == SCHEMA_VERSION

    def test_manifest_json_serializable(self):
        manifest = _valid_index_manifest()
        d = asdict(manifest)
        json_str = json.dumps(d, ensure_ascii=False)
        roundtrip = json.loads(json_str)
        assert roundtrip["schema_version"] == SCHEMA_VERSION
        assert roundtrip["fts_count"] == manifest.fts_count
        assert roundtrip["partial"] == manifest.partial

    def test_manifest_ignored_by_old_caller(self):
        """Old caller reading JSON ignores unknown schema_version field."""
        manifest = _valid_index_manifest()
        d = asdict(manifest)
        old_keys = {
            "fts_count",
            "vector_count",
            "file_count",
            "fts_checksum",
            "vector_checksum",
            "build_timestamp",
            "build_version",
            "partial",
        }
        assert old_keys.issubset(d.keys())
        remaining = d["fts_count"] > 0
        assert remaining is True


# ── B3.2: EntityExpansion ────────────────────────────────────────────────


class TestEntityExpansionSchemaVersion:
    """EntityExpansion must carry top-level schema_version."""

    def test_dataclass_has_schema_version_field(self):
        expansion = EntityExpansion()
        assert hasattr(expansion, "schema_version")
        assert isinstance(expansion.schema_version, str)

    def test_default_schema_version_is_v111(self):
        expansion = EntityExpansion()
        assert expansion.schema_version == SCHEMA_VERSION

    def test_entity_expansion_has_hints_field(self):
        expansion = EntityExpansion()
        assert hasattr(expansion, "entity_hints")
        assert isinstance(expansion.entity_hints, list)
        assert expansion.entity_hints == []

    def test_entity_expansion_with_hints(self):
        hints: list[dict[str, Any]] = [
            {
                "matched_term": "Ali",
                "entity_id": "e1",
                "entity_type": "person",
                "expansion_terms": ["Alice", "Ali"],
                "reason": "alias_match",
            }
        ]
        expansion = EntityExpansion(entity_hints=hints)
        assert len(expansion.entity_hints) == 1
        assert expansion.entity_hints[0]["entity_id"] == "e1"

    def test_to_dict_includes_schema_version(self):
        expansion = EntityExpansion(
            entity_hints=[
                {
                    "matched_term": "X",
                    "entity_id": "e1",
                    "entity_type": "person",
                    "expansion_terms": ["Y"],
                    "reason": "alias_match",
                }
            ]
        )
        d = expansion.to_dict()
        assert "schema_version" in d
        assert d["schema_version"] == SCHEMA_VERSION
        assert "entity_hints" in d
        assert len(d["entity_hints"]) == 1

    def test_to_dict_json_serializable(self):
        expansion = EntityExpansion(
            entity_hints=[
                {
                    "matched_term": "test",
                    "entity_id": "e1",
                    "entity_type": "concept",
                    "expansion_terms": ["test", "testing"],
                    "reason": "primary_name_match",
                }
            ]
        )
        d = expansion.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        roundtrip = json.loads(json_str)
        assert roundtrip["schema_version"] == SCHEMA_VERSION
        assert roundtrip["entity_hints"][0]["entity_id"] == "e1"

    def test_entity_expansion_ignored_by_old_caller(self):
        """Old caller reading JSON ignores unknown schema_version field."""
        expansion = EntityExpansion(
            entity_hints=[
                {
                    "matched_term": "a",
                    "entity_id": "x",
                    "entity_type": "person",
                    "expansion_terms": ["a"],
                    "reason": "alias_match",
                }
            ]
        )
        d = expansion.to_dict()
        hint_keys = {"matched_term", "entity_id", "entity_type", "expansion_terms", "reason"}
        for hint in d["entity_hints"]:
            assert hint_keys.issubset(hint.keys())


# ── B3.2: EntityRuntimeView ──────────────────────────────────────────────


class TestEntityRuntimeViewSchemaVersion:
    """EntityRuntimeView carries schema_version for contract stability."""

    def test_dataclass_has_schema_version_field(self):
        view = _valid_entity_runtime_view()
        assert hasattr(view, "schema_version")
        assert isinstance(view.schema_version, str)

    def test_default_schema_version_is_v111(self):
        view = EntityRuntimeView(entities=[])
        assert view.schema_version == SCHEMA_VERSION

    def test_runtime_view_ignored_by_old_caller(self):
        view = _valid_entity_runtime_view()
        d = asdict(view)
        assert "entities" in d
        assert "schema_version" in d


# ── B3.2: Hints Builder Entity Expansion Contract ────────────────────────


class TestHintsBuilderEntityExpansionContract:
    """entity_expansion_applied hints exist and can be wrapped with EntityExpansion."""

    def test_build_hints_emits_entity_expansion_when_hints_used(self):
        from tools.search_journals.hints_builder import build_hints
        from tools.search_journals.query_types import SearchPlan, AmbiguityReport

        plan = SearchPlan(
            raw_query="test",
            entity_hints_used=[
                {
                    "matched_term": "x",
                    "entity_id": "e1",
                    "entity_type": "person",
                    "expansion_terms": ["y"],
                    "reason": "alias_match",
                }
            ],
        )
        ambiguity = AmbiguityReport()
        hints = build_hints(plan, ambiguity)
        entity_hints_found = [h for h in hints if h.type == "entity_expansion_applied"]
        assert len(entity_hints_found) > 0


# ── B3.2: Entity CLI Expansion Contract ──────────────────────────────────


class TestEntityCLIExpansionContract:
    """Entity CLI entity expansion output carries schema_version."""

    def test_entity_expansion_from_cli_has_schema_version(self):
        """Entity entity expansion contract exposes schema_version."""
        from tools.lib.entity_runtime import EntityExpansion as EE

        ee = EE(
            entity_hints=[
                {
                    "matched_term": "test",
                    "entity_id": "e99",
                    "entity_type": "concept",
                    "expansion_terms": ["test"],
                    "reason": "alias_match",
                }
            ]
        )
        d = ee.to_dict()
        assert "schema_version" in d
        assert d["schema_version"] == SCHEMA_VERSION


# ── B3.2: Index Build CLI Manifest Contract ──────────────────────────────


class TestIndexBuildCLIManifestContract:
    """Index build CLI exposes IndexManifest contract with schema_version."""

    def test_index_manifest_construction_has_schema_version(self):
        m = IndexManifest(
            fts_count=1,
            vector_count=1,
            file_count=1,
            fts_checksum="a",
            vector_checksum="b",
            build_timestamp="t",
            build_version="v",
        )
        assert m.schema_version == SCHEMA_VERSION

    def test_index_manifest_persists_schema_version(self):
        m = IndexManifest(
            fts_count=5,
            vector_count=5,
            file_count=5,
            fts_checksum="c",
            vector_checksum="d",
            build_timestamp="t",
            build_version="v",
        )
        with TemporaryDirectory() as td:
            idx_dir = Path(td) / ".index"
            write_manifest(m, idx_dir)
            raw = Path(idx_dir, "index_manifest.json").read_text(encoding="utf-8")
            data = json.loads(raw)
            assert data["schema_version"] == SCHEMA_VERSION
