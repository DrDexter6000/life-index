#!/usr/bin/env python3
"""Tests for Qrels builder utility (R2-B3b).

Covers:
  1. resolve_title_to_doc_ids: exact, substring, empty, no match, dedupe
  2. build_qrels_from_query_specs: single/multi/ambiguous/unresolved/negative
  3. classify_qrel_coverage: full classification + ID-only output
  4. Overlay privacy: no title/query text in output
  5. Edge cases: empty specs, empty catalog, integration smoke
"""

from __future__ import annotations

from tools.eval.eval_doc_catalog import DocRecord
from tools.eval.eval_qrels import (
    build_qrels_from_query_specs,
    classify_qrel_coverage,
    resolve_title_to_doc_ids,
)
from tools.eval.eval_types import QuerySpec

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _doc(
    doc_id: str,
    title: str = "Test",
    date: str = "2026-01-01",
    **extra,
) -> DocRecord:
    return DocRecord(
        doc_id=doc_id,
        title=title,
        date=date,
        journal_route_path=doc_id,
        **extra,
    )


def _spec(
    query_id: str = "Q1",
    query: str = "test query",
    must_contain_title: list[str] | None = None,
    min_results: int = 1,
    broad_eval: dict | None = None,
    **extra,
) -> QuerySpec:
    expected = {"min_results": min_results}
    if must_contain_title is not None:
        expected["must_contain_title"] = must_contain_title
    return QuerySpec.from_dict(
        {
            "id": query_id,
            "query": query,
            "category": "test",
            "description": "test spec",
            "expected": expected,
            "tags": ["test"],
            **({"broad_eval": broad_eval} if broad_eval else {}),
            **extra,
        }
    )


CATALOG_THREE = [
    _doc("2026/01/a.md", title="Morning Reflection"),
    _doc("2026/01/b.md", title="Evening Review"),
    _doc("2026/01/c.md", title="Morning Reflection"),  # duplicate title
]

TITLE_MAP_THREE = {
    "Morning Reflection": ["2026/01/a.md", "2026/01/c.md"],
    "Evening Review": ["2026/01/b.md"],
}


# ---------------------------------------------------------------------------
# 1. resolve_title_to_doc_ids
# ---------------------------------------------------------------------------


class TestResolveTitleToDocIds:
    def test_exact_match(self) -> None:
        result = resolve_title_to_doc_ids("Evening Review", TITLE_MAP_THREE)
        assert result == ["2026/01/b.md"]

    def test_exact_match_returns_sorted(self) -> None:
        result = resolve_title_to_doc_ids("Morning Reflection", TITLE_MAP_THREE)
        assert result == ["2026/01/a.md", "2026/01/c.md"]

    def test_substring_fallback(self) -> None:
        result = resolve_title_to_doc_ids("Morning", TITLE_MAP_THREE)
        assert "2026/01/a.md" in result
        assert "2026/01/c.md" in result

    def test_substring_no_match(self) -> None:
        result = resolve_title_to_doc_ids("Nonexistent", TITLE_MAP_THREE)
        assert result == []

    def test_empty_fragment_returns_empty(self) -> None:
        assert resolve_title_to_doc_ids("", TITLE_MAP_THREE) == []

    def test_whitespace_fragment_returns_empty(self) -> None:
        assert resolve_title_to_doc_ids("   ", TITLE_MAP_THREE) == []

    def test_empty_map_returns_empty(self) -> None:
        assert resolve_title_to_doc_ids("anything", {}) == []

    def test_dedupe_deterministic(self) -> None:
        # If two different titles both contain the fragment and both
        # resolve to the same doc_id, result is deduplicated
        title_map = {
            "Alpha": ["2026/01/x.md"],
            "Alpha Beta": ["2026/01/x.md"],
        }
        result = resolve_title_to_doc_ids("Alpha", title_map)
        assert result == ["2026/01/x.md"]

    def test_exact_match_dedupes_duplicate_doc_ids(self) -> None:
        # Exact match where title_map has duplicate doc_id entries
        title_map = {"Alpha": ["2026/01/a.md", "2026/01/a.md"]}
        result = resolve_title_to_doc_ids("Alpha", title_map)
        assert result == ["2026/01/a.md"]


# ---------------------------------------------------------------------------
# 2. build_qrels_from_query_specs
# ---------------------------------------------------------------------------


class TestBuildQrels:
    def test_single_resolved_title(self) -> None:
        spec = _spec(query_id="Q1", must_contain_title=["Evening Review"])
        qrels = build_qrels_from_query_specs([spec], CATALOG_THREE)
        assert qrels == {"Q1": {"2026/01/b.md": 1}}

    def test_multiple_titles_build_multiple_qrels(self) -> None:
        catalog = [
            _doc("2026/01/a.md", title="Alpha"),
            _doc("2026/01/b.md", title="Beta"),
            _doc("2026/01/c.md", title="Gamma"),
        ]
        spec = _spec(query_id="Q1", must_contain_title=["Alpha", "Gamma"])
        qrels = build_qrels_from_query_specs([spec], catalog)
        assert qrels == {
            "Q1": {"2026/01/a.md": 1, "2026/01/c.md": 1},
        }

    def test_ambiguous_title_emits_multiple_relevant(self) -> None:
        spec = _spec(query_id="Q1", must_contain_title=["Morning Reflection"])
        qrels = build_qrels_from_query_specs([spec], CATALOG_THREE)
        assert qrels == {
            "Q1": {"2026/01/a.md": 1, "2026/01/c.md": 1},
        }

    def test_unresolved_title_emits_empty_qrels(self) -> None:
        spec = _spec(query_id="Q1", must_contain_title=["Does Not Exist"])
        qrels = build_qrels_from_query_specs([spec], CATALOG_THREE)
        assert qrels == {"Q1": {}}

    def test_negative_query_emits_empty_qrels(self) -> None:
        spec = _spec(query_id="Q1", min_results=0)
        qrels = build_qrels_from_query_specs([spec], CATALOG_THREE)
        assert qrels == {"Q1": {}}

    def test_min_results_only_emits_empty_qrels(self) -> None:
        spec = _spec(query_id="Q1", min_results=2, must_contain_title=None)
        qrels = build_qrels_from_query_specs([spec], CATALOG_THREE)
        assert qrels == {"Q1": {}}

    def test_broad_eval_with_title_builds_qrels_from_title(self) -> None:
        spec = _spec(
            query_id="Q1",
            must_contain_title=["Evening Review"],
            broad_eval={"predicate": {"type": "date_range", "date_range": {}}},
        )
        qrels = build_qrels_from_query_specs([spec], CATALOG_THREE)
        assert qrels == {"Q1": {"2026/01/b.md": 1}}

    def test_broad_eval_without_title_emits_empty(self) -> None:
        spec = _spec(
            query_id="Q1",
            must_contain_title=None,
            min_results=1,
            broad_eval={"predicate": {"type": "season", "date_range": {}}},
        )
        qrels = build_qrels_from_query_specs([spec], CATALOG_THREE)
        assert qrels == {"Q1": {}}

    def test_overlay_spec_no_leak(self) -> None:
        spec = _spec(
            query_id="Q1",
            must_contain_title=["Private Title"],
            query="private query text here",
        )
        catalog = [_doc("2026/01/a.md", title="Private Title")]
        qrels = build_qrels_from_query_specs([spec], catalog)
        # Only query_id, doc_id, grade - no title or query text
        assert qrels == {"Q1": {"2026/01/a.md": 1}}
        for inner in qrels.values():
            for key in inner:
                assert isinstance(key, str)
                assert isinstance(inner[key], int)

    def test_empty_specs_returns_empty(self) -> None:
        qrels = build_qrels_from_query_specs([], CATALOG_THREE)
        assert qrels == {}

    def test_empty_catalog_produces_unresolved(self) -> None:
        spec = _spec(query_id="Q1", must_contain_title=["Anything"])
        qrels = build_qrels_from_query_specs([spec], [])
        assert qrels == {"Q1": {}}

    def test_relevance_grade_is_always_1(self) -> None:
        spec = _spec(query_id="Q1", must_contain_title=["Morning Reflection"])
        qrels = build_qrels_from_query_specs([spec], CATALOG_THREE)
        for inner in qrels.values():
            for grade in inner.values():
                assert grade == 1

    def test_multiple_specs(self) -> None:
        specs = [
            _spec(query_id="Q1", must_contain_title=["Evening Review"]),
            _spec(query_id="Q2", must_contain_title=["Morning Reflection"]),
        ]
        qrels = build_qrels_from_query_specs(specs, CATALOG_THREE)
        assert len(qrels) == 2
        assert qrels["Q1"] == {"2026/01/b.md": 1}
        assert qrels["Q2"] == {"2026/01/a.md": 1, "2026/01/c.md": 1}


# ---------------------------------------------------------------------------
# 3. classify_qrel_coverage
# ---------------------------------------------------------------------------


class TestClassifyQrelCoverage:
    def test_resolved_query(self) -> None:
        spec = _spec(query_id="Q1", must_contain_title=["Evening Review"])
        report = classify_qrel_coverage([spec], CATALOG_THREE)
        assert report.resolved == 1
        assert report.ambiguous == 0
        assert report.unresolved == 0
        assert report.total_queries == 1

    def test_ambiguous_query(self) -> None:
        spec = _spec(query_id="Q1", must_contain_title=["Morning Reflection"])
        report = classify_qrel_coverage([spec], CATALOG_THREE)
        assert report.resolved == 0
        assert report.ambiguous == 1
        assert "Q1" in report.ambiguous_ids

    def test_unresolved_query(self) -> None:
        spec = _spec(query_id="Q1", must_contain_title=["Does Not Exist"])
        report = classify_qrel_coverage([spec], CATALOG_THREE)
        assert report.unresolved == 1
        assert "Q1" in report.unresolved_ids
        assert "Q1" in report.procedural_only_ids

    def test_negative_query(self) -> None:
        spec = _spec(query_id="Q1", min_results=0)
        report = classify_qrel_coverage([spec], CATALOG_THREE)
        assert report.negative == 1
        assert "Q1" in report.procedural_only_ids

    def test_min_results_only(self) -> None:
        spec = _spec(query_id="Q1", min_results=2, must_contain_title=None)
        report = classify_qrel_coverage([spec], CATALOG_THREE)
        assert report.min_results_only == 1
        assert "Q1" in report.procedural_only_ids

    def test_broad_eval_counters(self) -> None:
        spec = _spec(
            query_id="Q1",
            must_contain_title=["Evening Review"],
            broad_eval={"predicate": {"type": "topic", "topic_hints": ["work"]}},
        )
        report = classify_qrel_coverage([spec], CATALOG_THREE)
        assert report.broad_eval == 1
        assert report.broad_eval_with_titles == 1

    def test_broad_eval_without_titles(self) -> None:
        spec = _spec(
            query_id="Q1",
            must_contain_title=None,
            min_results=1,
            broad_eval={
                "predicate": {"type": "season", "date_range": {}},
            },
        )
        report = classify_qrel_coverage([spec], CATALOG_THREE)
        assert report.broad_eval == 1
        assert report.broad_eval_with_titles == 0
        assert "Q1" in report.procedural_only_ids

    def test_report_has_no_title_strings(self) -> None:
        spec = _spec(query_id="Q1", must_contain_title=["Evening Review"])
        report = classify_qrel_coverage([spec], CATALOG_THREE)
        report_str = str(report)
        assert "Evening Review" not in report_str

    def test_empty_specs(self) -> None:
        report = classify_qrel_coverage([], [])
        assert report.total_queries == 0
        assert report.resolved == 0
        assert report.warnings == []

    def test_mixed_coverage(self) -> None:
        catalog = [
            _doc("2026/01/a.md", title="Alpha"),
            _doc("2026/01/b.md", title="Beta"),
        ]
        specs = [
            _spec(query_id="Q1", must_contain_title=["Alpha"]),  # resolved
            _spec(query_id="Q2", must_contain_title=["Missing"]),  # unresolved
            _spec(query_id="Q3", min_results=0),  # negative
            _spec(query_id="Q4", min_results=2, must_contain_title=None),  # min_only
        ]
        report = classify_qrel_coverage(specs, catalog)
        assert report.resolved == 1
        assert report.unresolved == 1
        assert report.negative == 1
        assert report.min_results_only == 1
        assert report.total_queries == 4
        assert "Q1" not in report.procedural_only_ids
        assert "Q2" in report.procedural_only_ids
        assert "Q3" in report.procedural_only_ids
        assert "Q4" in report.procedural_only_ids

    def test_two_distinct_titles_each_one_doc_is_resolved(self) -> None:
        catalog = [
            _doc("2026/01/a.md", title="Alpha"),
            _doc("2026/01/b.md", title="Beta"),
        ]
        spec = _spec(query_id="Q1", must_contain_title=["Alpha", "Beta"])
        report = classify_qrel_coverage([spec], catalog)
        assert report.resolved == 1
        assert report.ambiguous == 0
        assert report.unresolved == 0
        # Qrels still has 2 doc_ids - that's fine, not ambiguous
        qrels = build_qrels_from_query_specs([spec], catalog)
        assert len(qrels["Q1"]) == 2

    def test_single_fragment_multi_doc_is_ambiguous(self) -> None:
        catalog = [
            _doc("2026/01/a.md", title="Shared Title"),
            _doc("2026/01/b.md", title="Shared Title"),
        ]
        spec = _spec(query_id="Q1", must_contain_title=["Shared Title"])
        report = classify_qrel_coverage([spec], catalog)
        assert report.ambiguous == 1
        assert report.resolved == 0
        assert "Q1" in report.ambiguous_ids

    def test_mixed_resolved_and_unresolved_title_fragments(self) -> None:
        catalog = [
            _doc("2026/01/a.md", title="Alpha"),
        ]
        spec = _spec(query_id="Q1", must_contain_title=["Alpha", "Missing"])
        report = classify_qrel_coverage([spec], catalog)
        # Conservative: incomplete coverage -> unresolved + procedural_only
        assert report.unresolved == 1
        assert report.resolved == 0
        assert "Q1" in report.unresolved_ids
        assert "Q1" in report.procedural_only_ids
        # Warning about partial resolution
        assert any("Q1" in w for w in report.warnings)

    def test_warnings_contain_no_title_text(self) -> None:
        catalog = [_doc("2026/01/a.md", title="Alpha")]
        spec = _spec(query_id="Q1", must_contain_title=["Alpha", "Secret Title"])
        report = classify_qrel_coverage([spec], catalog)
        for w in report.warnings:
            assert "Secret Title" not in w


# ---------------------------------------------------------------------------
# 4. Overlay privacy
# ---------------------------------------------------------------------------


class TestOverlayPrivacy:
    def test_overlay_query_text_not_in_qrels(self) -> None:
        spec = _spec(
            query_id="Q1",
            query="sensitive private query about real names",
            must_contain_title=["Alpha"],
        )
        catalog = [_doc("2026/01/a.md", title="Alpha")]
        qrels = build_qrels_from_query_specs([spec], catalog)
        qrels_str = str(qrels)
        assert "sensitive" not in qrels_str
        assert "real names" not in qrels_str

    def test_overlay_title_not_in_coverage_report(self) -> None:
        spec = _spec(query_id="Q1", must_contain_title=["Secret Private Title"])
        catalog = [_doc("2026/01/a.md", title="Secret Private Title")]
        report = classify_qrel_coverage([spec], catalog)
        report_str = str(report)
        assert "Secret Private Title" not in report_str
        # Q1 is resolved (single doc_id), so it appears in resolved count but
        # not in any ID list (ID lists only hold unresolved/ambiguous/procedural)
        assert report.resolved == 1
        assert "Q1" not in report.unresolved_ids
        assert "Q1" not in report.ambiguous_ids


# ---------------------------------------------------------------------------
# 5. Integration smoke with DocRecord + QuerySpec fixtures
# ---------------------------------------------------------------------------


class TestIntegrationSmoke:
    def test_catalog_and_specs_round_trip(self) -> None:
        catalog = [
            _doc("2026/03/a.md", title="Morning Standup", date="2026-03-14"),
            _doc("2026/03/b.md", title="Deep Work Session", date="2026-03-14"),
            _doc("2026/03/c.md", title="Weekly Retrospective", date="2026-03-15"),
        ]
        specs = [
            _spec(query_id="GQ01", must_contain_title=["Morning Standup"]),
            _spec(
                query_id="GQ02", must_contain_title=["Deep Work Session", "Weekly Retrospective"]
            ),
            _spec(query_id="GQ03", min_results=0),
        ]
        qrels = build_qrels_from_query_specs(specs, catalog)

        assert qrels["GQ01"] == {"2026/03/a.md": 1}
        assert qrels["GQ02"] == {
            "2026/03/b.md": 1,
            "2026/03/c.md": 1,
        }
        assert qrels["GQ03"] == {}

        report = classify_qrel_coverage(specs, catalog)
        # GQ01: 1 title -> 1 doc -> resolved
        # GQ02: 2 titles, each -> 1 doc -> resolved (not ambiguous)
        # GQ03: negative
        assert report.resolved == 2
        assert report.ambiguous == 0
        assert report.negative == 1
        assert report.total_queries == 3

    def test_type_round_trip_preserves_structure(self) -> None:
        catalog = [_doc("2026/01/a.md", title="Test Title")]
        spec = _spec(query_id="Q1", must_contain_title=["Test Title"])
        qrels = build_qrels_from_query_specs([spec], catalog)

        # Verify Qrels type structure
        assert isinstance(qrels, dict)
        assert isinstance(qrels["Q1"], dict)
        assert all(isinstance(k, str) for k in qrels["Q1"])
        assert all(isinstance(v, int) for v in qrels["Q1"].values())
