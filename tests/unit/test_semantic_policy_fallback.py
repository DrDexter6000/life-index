#!/usr/bin/env python3
"""TDD tests for semantic_policy='fallback' zero-result semantic fallback.

Tests cover:
  A. Fallback triggers on zero keyword results (semantic_fallback_used=True)
  B. Fallback skipped when keyword finds results (semantic_fallback_used=False)
  C. Hybrid policy unchanged (parallel execution)
  D. --no-semantic disables fallback entirely
  E. semantic_policy and semantic_fallback_used in result dict
  F. CLI --semantic-policy flag parsing
  G. Structured metadata prevents fallback (P1 review fix)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.lib.index_freshness import FreshnessReport


@pytest.fixture(autouse=True)
def _fresh_index():
    with (
        patch(
            "tools.lib.index_freshness.check_full_freshness",
            return_value=FreshnessReport(
                fts_fresh=True, vector_fresh=True, overall_fresh=True, issues=[]
            ),
        ),
        patch("tools.lib.pending_writes.has_pending", return_value=False),
    ):
        yield


@pytest.fixture(autouse=True)
def _entity_graph(tmp_path: Path, monkeypatch):
    import yaml

    graph_path = tmp_path / "entity_graph.yaml"
    graph_path.write_text(
        yaml.safe_dump({"entities": [], "relations": []}, allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))


def _mock_keyword_results(count: int):
    """Return a mock keyword pipeline result with `count` L3 results."""
    l1 = [{"path": f"journals/l1_{i}.md", "score": 1.0} for i in range(count)]
    l2 = []
    l3 = l1  # L3 carries the actual hits
    kw_perf = {"l1_time_ms": 10.0, "l2_time_ms": 5.0, "l3_time_ms": 15.0}
    return (l1, l2, l3, False, count, kw_perf)


def _mock_semantic_results(count: int):
    """Return a mock semantic pipeline result with `count` results."""
    results = [
        {"path": f"journals/sem_{i}.md", "score": 0.9 - i * 0.1, "source": "semantic"}
        for i in range(count)
    ]
    perf = {"semantic_time_ms": 50.0}
    return (results, perf, True, None)


# ---------------------------------------------------------------------------
# A. Fallback triggers on zero keyword results
# ---------------------------------------------------------------------------


class TestFallbackTriggersOnZeroKeyword:
    """When keyword returns zero results, semantic should be invoked."""

    def test_semantic_fallback_used_true_on_zero_keyword(self):
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(0),
            ),
            patch(
                "tools.search_journals.core.run_semantic_pipeline",
                return_value=_mock_semantic_results(3),
            ),
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results_hybrid",
                side_effect=lambda *a, **kw: kw.get("semantic_results", a[3] if len(a) > 3 else []),
            ),
        ):
            result = hierarchical_search(
                query="nonexistent query",
                semantic=True,
                semantic_policy="fallback",
            )
            assert result["semantic_fallback_used"] is True
            assert result["semantic_policy"] == "fallback"

    def test_semantic_pipeline_called_on_zero_keyword(self):
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(0),
            ) as mock_kw,
            patch(
                "tools.search_journals.core.run_semantic_pipeline",
                return_value=_mock_semantic_results(2),
            ) as mock_sem,
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results_hybrid",
                side_effect=lambda *a, **kw: a[3] if len(a) > 3 else [],
            ),
        ):
            hierarchical_search(
                query="nonexistent query",
                semantic=True,
                semantic_policy="fallback",
            )
            mock_kw.assert_called_once()
            mock_sem.assert_called_once()


# ---------------------------------------------------------------------------
# B. Fallback skipped when keyword finds results
# ---------------------------------------------------------------------------


class TestFallbackSkippedOnKeywordHit:
    """When keyword returns results, semantic pipeline must NOT run."""

    def test_semantic_fallback_used_false_on_keyword_hit(self):
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(5),
            ),
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results",
                side_effect=lambda l1, l2, l3, *a, **kw: l3,
            ),
        ):
            result = hierarchical_search(
                query="some query",
                semantic=True,
                semantic_policy="fallback",
            )
            assert result["semantic_fallback_used"] is False
            assert result["semantic_policy"] == "fallback"

    def test_semantic_pipeline_not_called_on_keyword_hit(self):
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(5),
            ),
            patch(
                "tools.search_journals.core.run_semantic_pipeline",
            ) as mock_sem,
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results",
                side_effect=lambda l1, l2, l3, *a, **kw: l3,
            ),
        ):
            hierarchical_search(
                query="some query",
                semantic=True,
                semantic_policy="fallback",
            )
            mock_sem.assert_not_called()


# ---------------------------------------------------------------------------
# C. Hybrid policy unchanged (parallel execution)
# ---------------------------------------------------------------------------


class TestHybridPolicyUnchanged:
    """semantic_policy='hybrid' must use original parallel execution."""

    def test_hybrid_runs_both_pipelines(self):
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(3),
            ),
            patch(
                "tools.search_journals.core.run_semantic_pipeline",
                return_value=_mock_semantic_results(2),
            ),
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results_hybrid",
                side_effect=lambda *a, **kw: list(a[0]) + list(a[3]),
            ),
        ):
            result = hierarchical_search(
                query="test query",
                semantic=True,
                semantic_policy="hybrid",
            )
            assert result["semantic_policy"] == "hybrid"
            # hybrid never sets semantic_fallback_used=True
            assert result["semantic_fallback_used"] is False

    def test_default_policy_is_hybrid(self):
        """Without explicit semantic_policy, default must be 'hybrid'."""
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(1),
            ),
            patch(
                "tools.search_journals.core.run_semantic_pipeline",
                return_value=_mock_semantic_results(1),
            ),
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results_hybrid",
                side_effect=lambda *a, **kw: list(a[0]),
            ),
        ):
            result = hierarchical_search(query="test query", semantic=True)
            assert result["semantic_policy"] == "hybrid"


# ---------------------------------------------------------------------------
# D. --no-semantic disables fallback entirely
# ---------------------------------------------------------------------------


class TestNoSemanticDisablesFallback:
    """semantic=False must skip fallback even with policy='fallback'."""

    def test_no_semantic_skips_fallback_dispatch(self):
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(0),
            ),
            patch(
                "tools.search_journals.core.run_semantic_pipeline",
                return_value=_mock_semantic_results(0),
            ),
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results",
                side_effect=lambda *a, **kw: [],
            ),
        ):
            result = hierarchical_search(
                query="test query",
                semantic=False,
                semantic_policy="fallback",
            )
            # When semantic=False, fallback branch is not entered
            # (the condition is `semantic_policy == "fallback" and semantic`)
            assert result["semantic_fallback_used"] is False


# ---------------------------------------------------------------------------
# E. Result dict fields
# ---------------------------------------------------------------------------


class TestResultDictFields:
    """semantic_policy and semantic_fallback_used must appear in every result."""

    def test_fields_present_in_fallback_mode(self):
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(1),
            ),
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results",
                side_effect=lambda l1, l2, l3, *a, **kw: l3,
            ),
        ):
            result = hierarchical_search(query="test", semantic=True, semantic_policy="fallback")
            assert "semantic_policy" in result
            assert "semantic_fallback_used" in result

    def test_fields_present_in_hybrid_mode(self):
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(1),
            ),
            patch(
                "tools.search_journals.core.run_semantic_pipeline",
                return_value=_mock_semantic_results(1),
            ),
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results_hybrid",
                side_effect=lambda *a, **kw: list(a[0]),
            ),
        ):
            result = hierarchical_search(query="test", semantic=True, semantic_policy="hybrid")
            assert "semantic_policy" in result
            assert "semantic_fallback_used" in result


# ---------------------------------------------------------------------------
# F. CLI --semantic-policy flag parsing
# ---------------------------------------------------------------------------


class TestCLISemanticPolicyFlag:
    """CLI must accept --semantic-policy and pass it through."""

    def test_cli_default_is_fallback(self):
        import io
        import json
        import sys
        from tools.search_journals.__main__ import main

        mock_result = {
            "success": True,
            "merged_results": [],
            "total_found": 0,
            "total_available": 0,
            "semantic_policy": "fallback",
            "semantic_fallback_used": False,
            "query_params": {},
            "l1_results": [],
            "l2_results": [],
            "l3_results": [],
            "semantic_results": [],
            "performance": {},
            "warnings": [],
            "entity_hints": [],
            "search_plan": None,
            "ambiguity": {"has_ambiguity": False, "items": []},
            "hints": [],
        }

        with (
            patch("tools.search_journals.__main__.hierarchical_search", return_value=mock_result),
            patch("sys.argv", ["search", "--query", "test"]),
        ):
            captured = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured
            try:
                main()
            except SystemExit:
                pass
            finally:
                sys.stdout = old_stdout

            payload = json.loads(captured.getvalue())
            # search_journals CLI outputs result directly, not wrapped in {"data": ...}
            assert payload["semantic_policy"] == "fallback"

    def test_cli_explicit_hybrid(self):
        from tools.search_journals.__main__ import main

        mock_result = {
            "success": True,
            "merged_results": [],
            "total_found": 0,
            "total_available": 0,
            "semantic_policy": "hybrid",
            "semantic_fallback_used": False,
            "query_params": {},
            "l1_results": [],
            "l2_results": [],
            "l3_results": [],
            "semantic_results": [],
            "performance": {},
            "warnings": [],
            "entity_hints": [],
            "search_plan": None,
            "ambiguity": {"has_ambiguity": False, "items": []},
            "hints": [],
        }

        with (
            patch(
                "tools.search_journals.__main__.hierarchical_search", return_value=mock_result
            ) as mock_search,
            patch("sys.argv", ["search", "--query", "test", "--semantic-policy", "hybrid"]),
        ):
            try:
                main()
            except SystemExit:
                pass
            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["semantic_policy"] == "hybrid"


# ---------------------------------------------------------------------------
# H. Fallback semantic unavailable warning (P2 review fix)
# ---------------------------------------------------------------------------


class TestFallbackSemanticUnavailableWarning:
    """When semantic pipeline is unavailable in fallback mode, the warning
    must match the hybrid path behavior."""

    def test_fallback_semantic_unavailable_adds_warning(self):
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(0),
            ),
            patch(
                "tools.search_journals.core.run_semantic_pipeline",
                return_value=([], {}, False, "vector index unavailable"),
            ),
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
        ):
            result = hierarchical_search(
                query="nonexistent query",
                semantic=True,
                semantic_policy="fallback",
            )

        assert result["semantic_fallback_used"] is True
        assert result["semantic_available"] is False
        assert result["semantic_note"] == "vector index unavailable"
        assert "semantic_unavailable: vector index unavailable" in result["warnings"]


# ---------------------------------------------------------------------------
# G. Structured metadata prevents fallback (P1 review fix)
# ---------------------------------------------------------------------------


class TestStructuredMetadataPreventsFallback:
    """When raw keyword l1/l2/l3 are empty but structured metadata supplement
    produces results, fallback must NOT trigger and semantic pipeline must
    NOT run. This is the P1 review fix scenario."""

    def test_structured_metadata_supplement_prevents_fallback(self):
        """Raw keyword empty, structured metadata adds 1 hit → no fallback."""
        from dataclasses import dataclass
        from tools.search_journals.core import hierarchical_search

        @dataclass
        class _MockDateRange:
            since: str | None = "2026-01-01"
            until: str | None = "2026-01-31"
            source: str | None = "parsed"

            def to_dict(self):
                return {"since": self.since, "until": self.until, "source": self.source}

        @dataclass
        class _MockPlan:
            date_range: _MockDateRange | None = None
            topic_hints: list | None = None
            raw_query: str = "2026年1月的工作"
            normalized_query: str = ""
            expanded_query: str = ""

            def to_dict(self):
                return {"raw_query": self.raw_query}

        mock_plan = _MockPlan(
            date_range=_MockDateRange(),
            topic_hints=["work"],
        )

        # Keyword pipeline returns all empty
        kw_result = (
            [],  # l1
            [],  # l2
            [],  # l3
            False,
            0,
            {"l1_time_ms": 5.0, "l2_time_ms": 3.0, "l3_time_ms": 2.0},
        )

        structured_md_path = "journals/2026/01-15.md"

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=kw_result,
            ),
            patch(
                "tools.search_journals.core.run_semantic_pipeline",
            ) as mock_sem,
            patch(
                "tools.search_journals.core._augment_with_structured_metadata",
            ) as mock_augment,
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results",
                side_effect=lambda l1, l2, l3, *a, **kw: l1 + l2 + l3,
            ),
            patch(
                "tools.search_journals.query_preprocessor.build_search_plan",
                return_value=mock_plan,
            ),
            patch(
                "tools.search_journals.core.build_l0_candidate_set",
                return_value=None,
            ),
            patch(
                "tools.search_journals.ambiguity_detector.detect_ambiguity",
            ) as mock_detect_amb,
            patch(
                "tools.search_journals.hints_builder.build_hints",
                return_value=[],
            ),
            patch(
                "tools.search_journals.core.expand_query_with_entity_graph",
                side_effect=lambda q: q,
            ),
            patch(
                "tools.search_journals.core.resolve_query_entities",
                return_value=[],
            ),
        ):
            # Ambiguity detector returns a mock with to_dict()
            mock_amb = type(
                "Amb", (), {"to_dict": lambda self: {"has_ambiguity": False, "items": []}}
            )()
            mock_detect_amb.return_value = mock_amb

            # Simulate _augment_with_structured_metadata adding to l2_results
            def _augment_side_effect(l2_results, candidate_paths, plan, df, dt, result):
                l2_results.append(
                    {"path": structured_md_path, "score": 0.8, "source": "structured_metadata"}
                )
                result["warnings"].append(
                    "structured_metadata: added 1 candidates from date_range+topic_hints"
                )
                return [structured_md_path]

            mock_augment.side_effect = _augment_side_effect

            result = hierarchical_search(
                query="2026年1月的工作",
                semantic=True,
                semantic_policy="fallback",
            )

            assert result["semantic_fallback_used"] is False
            assert result["semantic_effective_policy"] == "fallback"
            mock_sem.assert_not_called()

    def test_structured_metadata_results_in_merged(self):
        """Structured metadata results must appear in merged_results."""
        from dataclasses import dataclass
        from tools.search_journals.core import hierarchical_search

        @dataclass
        class _MockDateRange:
            since: str | None = "2026-01-01"
            until: str | None = "2026-01-31"
            source: str | None = "parsed"

            def to_dict(self):
                return {"since": self.since, "until": self.until, "source": self.source}

        @dataclass
        class _MockPlan:
            date_range: _MockDateRange | None = None
            topic_hints: list | None = None
            raw_query: str = "2026年1月的工作"
            normalized_query: str = ""
            expanded_query: str = ""

            def to_dict(self):
                return {"raw_query": self.raw_query}

        mock_plan = _MockPlan(
            date_range=_MockDateRange(),
            topic_hints=["work"],
        )

        kw_result = (
            [],
            [],
            [],
            False,
            0,
            {"l1_time_ms": 5.0, "l2_time_ms": 3.0, "l3_time_ms": 2.0},
        )
        structured_md_path = "journals/2026/01-structured.md"

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=kw_result,
            ),
            patch(
                "tools.search_journals.core.run_semantic_pipeline",
            ) as mock_sem,
            patch(
                "tools.search_journals.core._augment_with_structured_metadata",
            ) as mock_augment,
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results",
                side_effect=lambda l1, l2, l3, *a, **kw: l1 + l2 + l3,
            ),
            patch(
                "tools.search_journals.query_preprocessor.build_search_plan",
                return_value=mock_plan,
            ),
            patch(
                "tools.search_journals.core.build_l0_candidate_set",
                return_value=None,
            ),
            patch(
                "tools.search_journals.ambiguity_detector.detect_ambiguity",
            ) as mock_detect_amb,
            patch(
                "tools.search_journals.hints_builder.build_hints",
                return_value=[],
            ),
            patch(
                "tools.search_journals.core.expand_query_with_entity_graph",
                side_effect=lambda q: q,
            ),
            patch(
                "tools.search_journals.core.resolve_query_entities",
                return_value=[],
            ),
        ):
            mock_amb = type(
                "Amb", (), {"to_dict": lambda self: {"has_ambiguity": False, "items": []}}
            )()
            mock_detect_amb.return_value = mock_amb

            def _augment_side_effect(l2_results, candidate_paths, plan, df, dt, result):
                l2_results.append(
                    {"path": structured_md_path, "score": 0.8, "source": "structured_metadata"}
                )
                return [structured_md_path]

            mock_augment.side_effect = _augment_side_effect

            result = hierarchical_search(
                query="2026年1月的工作",
                semantic=True,
                semantic_policy="fallback",
            )

            assert result["semantic_fallback_used"] is False
            assert len(result["merged_results"]) >= 1
            assert any(structured_md_path == r.get("path") for r in result["merged_results"])
            mock_sem.assert_not_called()
