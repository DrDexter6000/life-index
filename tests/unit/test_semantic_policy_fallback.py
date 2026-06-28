#!/usr/bin/env python3
"""Compatibility tests for deprecated semantic search flags.

The CLI and Python API still accept ``semantic`` and ``semantic_policy`` for
GUI/backward compatibility, but in-tool vector/semantic retrieval is removed.
These tests assert the new public contract: keyword/entity search executes,
semantic diagnostics are explicit no-ops, and no semantic pipeline is exposed.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    l1 = [{"path": f"journals/l1_{i}.md", "score": 1.0} for i in range(count)]
    l2 = []
    l3 = list(l1)
    kw_perf = {"l1_time_ms": 10.0, "l2_time_ms": 5.0, "l3_time_ms": 15.0}
    return (l1, l2, l3, False, count, kw_perf)


def _assert_semantic_noop(result: dict) -> None:
    assert result["semantic_results"] == []
    assert result["semantic_available"] is False
    assert result["semantic_fallback_used"] is False
    assert result["semantic_effective_policy"] == "deprecated_noop"
    assert result["semantic_note"] == (
        "in-tool semantic/vector search is disabled; using keyword + Entity Graph."
    )
    assert any("deprecated_noop" in warning for warning in result["warnings"])


class TestDeprecatedSemanticNoop:
    def test_fallback_policy_on_zero_keyword_results_does_not_run_semantic(self):
        from tools.search_journals import core
        from tools.search_journals.core import hierarchical_search

        assert not hasattr(core, "run_semantic_pipeline")

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(0),
            ) as mock_kw,
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch("tools.search_journals.core.merge_and_rank_results", return_value=[]),
        ):
            result = hierarchical_search(
                query="nonexistent query",
                semantic=True,
                semantic_policy="fallback",
            )

        mock_kw.assert_called_once()
        assert result["semantic_policy"] == "fallback"
        assert result["query_params"]["semantic"] is True
        _assert_semantic_noop(result)

    def test_hybrid_policy_is_accepted_but_runs_keyword_only(self):
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(3),
            ),
            patch(
                "tools.search_journals.core._filter_results_by_candidates",
                side_effect=lambda x, _: x,
            ),
            patch(
                "tools.search_journals.core.merge_and_rank_results",
                side_effect=lambda l1, l2, l3, *a, **kw: l3,
            ) as mock_merge,
        ):
            result = hierarchical_search(
                query="test query",
                semantic=True,
                semantic_policy="hybrid",
            )

        mock_merge.assert_called_once()
        assert result["semantic_policy"] == "hybrid"
        assert len(result["merged_results"]) == 3
        _assert_semantic_noop(result)

    def test_semantic_weight_request_is_also_noop(self):
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
            result = hierarchical_search(query="test", semantic_weight=5.0)

        assert result["query_params"]["semantic"] is False
        _assert_semantic_noop(result)

    def test_default_keyword_search_reports_semantic_off(self):
        from tools.search_journals.core import hierarchical_search

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=_mock_keyword_results(2),
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
            result = hierarchical_search(query="test query")

        assert result["query_params"]["semantic"] is False
        assert result["semantic_available"] is False
        assert result["semantic_fallback_used"] is False
        assert result["semantic_effective_policy"] == "off"
        assert not any("deprecated_noop" in warning for warning in result["warnings"])


class TestCLISemanticPolicyFlags:
    """CLI must keep accepting deprecated semantic flags."""

    def _run_cli(self, argv: list[str]) -> dict:
        from tools.search_journals.__main__ import main

        mock_result = {
            "success": True,
            "merged_results": [],
            "total_found": 0,
            "total_available": 0,
            "semantic_policy": "fallback",
            "semantic_effective_policy": "deprecated_noop",
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
                "tools.search_journals.__main__.hierarchical_search",
                return_value=mock_result,
            ) as mock_search,
            patch("sys.argv", argv),
        ):
            try:
                main()
            except SystemExit:
                pass
            return mock_search.call_args[1]

    def test_cli_default_semantic_false(self):
        kwargs = self._run_cli(["search", "--query", "叶航 小云"])
        assert kwargs["semantic"] is False

    def test_cli_semantic_flag_still_accepted(self):
        kwargs = self._run_cli(["search", "--query", "叶航 小云", "--semantic"])
        assert kwargs["semantic"] is True

    def test_cli_no_semantic_flag_still_accepted(self):
        kwargs = self._run_cli(["search", "--query", "叶航 小云", "--no-semantic"])
        assert kwargs["semantic"] is False

    def test_cli_semantic_policy_still_passed_through(self):
        kwargs = self._run_cli(["search", "--query", "test", "--semantic-policy", "hybrid"])
        assert kwargs["semantic_policy"] == "hybrid"

    def test_cli_gui_compatibility_combination_is_accepted(self):
        kwargs = self._run_cli(
            [
                "search",
                "--query",
                "test",
                "--semantic",
                "--semantic-policy",
                "fallback",
                "--semantic-weight",
                "7",
            ]
        )
        assert kwargs["semantic"] is True
        assert kwargs["semantic_policy"] == "fallback"
        assert kwargs["semantic_weight"] == 7.0


class TestStructuredMetadataStillMerges:
    """Structured metadata supplements are keyword-path behavior, not fallback."""

    def test_structured_metadata_results_in_merged_without_semantic(self):
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

        mock_plan = _MockPlan(date_range=_MockDateRange(), topic_hints=["work"])
        structured_md_path = "journals/2026/01-structured.md"

        def _augment_side_effect(l2_results, candidate_paths, plan, df, dt, result):
            l2_results.append(
                {"path": structured_md_path, "score": 0.8, "source": "structured_metadata"}
            )
            return [structured_md_path]

        with (
            patch(
                "tools.search_journals.core.run_keyword_pipeline",
                return_value=([], [], [], False, 0, {"l1_time_ms": 1.0}),
            ),
            patch(
                "tools.search_journals.core._augment_with_structured_metadata",
                side_effect=_augment_side_effect,
            ),
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
            patch("tools.search_journals.core.build_l0_candidate_set", return_value=None),
            patch(
                "tools.search_journals.ambiguity_detector.detect_ambiguity",
                return_value=type(
                    "Amb",
                    (),
                    {"to_dict": lambda self: {"has_ambiguity": False, "items": []}},
                )(),
            ),
            patch("tools.search_journals.hints_builder.build_hints", return_value=[]),
            patch(
                "tools.search_journals.core.expand_query_with_entity_graph", side_effect=lambda q: q
            ),
            patch("tools.search_journals.core.resolve_query_entities", return_value=[]),
        ):
            result = hierarchical_search(
                query="2026年1月的工作",
                semantic=True,
                semantic_policy="fallback",
            )

        assert result["semantic_fallback_used"] is False
        assert result["semantic_effective_policy"] == "deprecated_noop"
        assert any(structured_md_path == r.get("path") for r in result["merged_results"])
