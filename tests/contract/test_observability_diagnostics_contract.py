"""Contract tests for v1.1.1 explain diagnostics (A3).

Validates that ``search --explain``, ``smart-search --explain``, and
``index --explain`` JSON outputs each contain a top-level ``diagnostics``
field with the required six sub-fields.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from tools.search_journals.core import hierarchical_search
from tools.lib.index_freshness import FreshnessReport

# ── Required diagnostics schema ──

REQUIRED_DIAGNOSTICS_FIELDS = {
    "input_count",
    "filter_drops",
    "cache_hits",
    "cache_misses",
    "latency_ms",
    "fallback_path",
}


def _assert_diagnostics_shape(diagnostics: dict) -> None:
    """Assert a diagnostics dict conforms to the v1.1.1 contract."""
    for field in REQUIRED_DIAGNOSTICS_FIELDS:
        assert field in diagnostics, f"missing diagnostics field: {field}"

    assert isinstance(diagnostics["input_count"], int)
    assert isinstance(diagnostics["filter_drops"], dict)
    assert isinstance(diagnostics["cache_hits"], int)
    assert isinstance(diagnostics["cache_misses"], int)
    assert isinstance(diagnostics["latency_ms"], dict)
    # fallback_path is null or string
    assert diagnostics["fallback_path"] is None or isinstance(diagnostics["fallback_path"], str)


# ── Search --explain contract ──


@pytest.fixture(autouse=True)
def mock_search_dependencies():
    """Mock all search dependencies to isolate contract testing."""
    fresh_report = FreshnessReport(
        fts_fresh=True,
        vector_fresh=True,
        overall_fresh=True,
        issues=[],
    )
    with patch("tools.search_journals.core.search_l1_index", return_value=[]):
        with patch(
            "tools.search_journals.core.search_l2_metadata",
            return_value={"results": [], "truncated": False, "total_available": 0},
        ):
            with patch("tools.search_journals.core.scan_all_indices", return_value=[]):
                with patch(
                    "tools.search_journals.keyword_pipeline.search_l3_content",
                    return_value=[],
                ):
                    with patch(
                        "tools.search_journals.keyword_pipeline.search_l2_metadata",
                        return_value={
                            "results": [],
                            "truncated": False,
                            "total_available": 0,
                        },
                    ):
                        with patch(
                            "tools.search_journals.keyword_pipeline.search_l1_index",
                            return_value=[],
                        ):
                            with patch(
                                "tools.search_journals.semantic_pipeline.search_semantic",
                                return_value=([], {}),
                            ):
                                with patch(
                                    "tools.search_journals.semantic_pipeline."
                                    "get_semantic_runtime_status",
                                    return_value={
                                        "available": True,
                                        "reason": "",
                                        "note": "",
                                    },
                                ):
                                    with patch(
                                        "tools.lib.index_freshness.check_full_freshness",
                                        return_value=fresh_report,
                                    ):
                                        with patch(
                                            "tools.lib.pending_writes.has_pending",
                                            return_value=False,
                                        ):
                                            yield


class TestSearchExplainDiagnostics:
    """``search --explain`` output contains deterministic diagnostics."""

    def test_level3_explain_has_diagnostics(self):
        result = hierarchical_search(query="test", level=3, explain=True)
        assert "diagnostics" in result, "explain output missing diagnostics"
        _assert_diagnostics_shape(result["diagnostics"])

    def test_level2_explain_has_diagnostics(self):
        result = hierarchical_search(location="Beijing", level=2, explain=True)
        assert "diagnostics" in result, "explain output missing diagnostics"
        _assert_diagnostics_shape(result["diagnostics"])

    def test_level1_explain_has_diagnostics(self):
        result = hierarchical_search(topic="work", level=1, explain=True)
        assert "diagnostics" in result, "explain output missing diagnostics"
        _assert_diagnostics_shape(result["diagnostics"])

    def test_explain_latency_ms_is_mapping(self):
        result = hierarchical_search(query="test", level=3, explain=True)
        lat = result["diagnostics"]["latency_ms"]
        assert isinstance(lat, dict)
        # At minimum total_time_ms is present
        assert "total" in lat or "total_time_ms" in lat

    def test_explain_filter_drops_is_mapping(self):
        result = hierarchical_search(query="test", level=3, explain=True)
        drops = result["diagnostics"]["filter_drops"]
        assert isinstance(drops, dict)

    def test_explain_fallback_path_is_null_or_string(self):
        result = hierarchical_search(query="test", level=3, explain=True)
        fb = result["diagnostics"]["fallback_path"]
        assert fb is None or isinstance(fb, str)

    def test_non_explain_does_not_add_diagnostics(self):
        """Without explain=True, diagnostics must NOT appear."""
        result = hierarchical_search(query="test", level=3, explain=False)
        assert "diagnostics" not in result

    def test_diagnostics_does_not_contain_user_content(self):
        """Diagnostics must never include raw journal snippets or user text."""
        result = hierarchical_search(query="test", level=3, explain=True)
        diag = json.dumps(result["diagnostics"])
        assert "snippet" not in diag.lower()
        assert "content" not in diag.lower()


# ── Smart Search --explain contract ──


def _mock_hierarchical_search(query="", **kwargs):
    return {
        "success": True,
        "merged_results": [
            {
                "title": "Test Journal Entry",
                "path": "Journals/2026/03/life-index_2026-03-06_001.md",
                "rel_path": "Journals/2026/03/life-index_2026-03-06_001.md",
                "date": "2026-03-06",
                "rrf_score": 0.85,
                "abstract": "A test abstract about memories.",
                "snippet": "Test snippet content.",
            }
        ],
        "total_found": 1,
        "total_available": 1,
        "performance": {"total_time_ms": 10.0},
    }


class TestSmartSearchExplainDiagnostics:
    """``smart-search --explain`` output contains deterministic diagnostics."""

    def test_smart_search_cli_explain_has_diagnostics(self):
        """CLI layer --explain produces diagnostics in emitted JSON."""
        from io import StringIO

        # Mock orchestrator result WITHOUT diagnostics — CLI layer must add it
        mock_result = {
            "success": True,
            "query": "test",
            "rewritten_query": "test",
            "filtered_results": [],
            "summary": "",
            "citations": [],
            "agent_decisions": [],
            "agent_unavailable": True,
            "performance": {"total_time_ms": 10, "total_available": 1},
        }

        captured = StringIO()
        with patch("sys.argv", ["smart-search", "--query", "test", "--explain"]):
            with patch("tools.search_journals.orchestrator.SmartSearchOrchestrator") as MockCls:
                mock_orch = MagicMock()
                mock_orch.search.return_value = mock_result.copy()
                MockCls.return_value = mock_orch
                with patch(
                    "builtins.print",
                    side_effect=lambda *a, **kw: captured.write(str(a[0])) if a else None,
                ):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit:
                        pass

        result = json.loads(captured.getvalue())
        assert "diagnostics" in result, "CLI explain output missing diagnostics"
        _assert_diagnostics_shape(result["diagnostics"])
        assert result["diagnostics"]["input_count"] == 1
        assert result["diagnostics"]["latency_ms"]["total"] == 10
        assert result["diagnostics"]["fallback_path"] is None
        assert result["query_plan"]["strategy"] == "keyword_only"
        assert result["query_plan"]["fallback_decision"] is False

    def test_smart_search_cli_explain_reports_semantic_fallback_truthfully(self):
        """CLI query_plan must not invert semantic fallback status."""
        from io import StringIO

        mock_result = {
            "success": True,
            "query": "test",
            "rewritten_query": "test",
            "filtered_results": [],
            "summary": "",
            "citations": [],
            "agent_decisions": [],
            "agent_unavailable": True,
            "semantic_fallback_used": True,
            "performance": {"total_time_ms": 10, "total_available": 1},
        }

        captured = StringIO()
        with patch("sys.argv", ["smart-search", "--query", "test", "--explain"]):
            with patch("tools.search_journals.orchestrator.SmartSearchOrchestrator") as MockCls:
                mock_orch = MagicMock()
                mock_orch.search.return_value = mock_result.copy()
                MockCls.return_value = mock_orch
                with patch(
                    "builtins.print",
                    side_effect=lambda *a, **kw: captured.write(str(a[0])) if a else None,
                ):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit:
                        pass

        result = json.loads(captured.getvalue())
        assert result["diagnostics"]["fallback_path"] == "semantic"
        assert result["query_plan"]["strategy"] == "keyword_with_semantic_fallback"
        assert result["query_plan"]["fallback_decision"] is True

    def test_smart_search_explain_preserves_orchestrator_query_plan(self):
        """CLI explain must not overwrite orchestrator multi-query plans."""
        from io import StringIO

        mock_result = {
            "success": True,
            "query": "test",
            "rewritten_query": "test",
            "filtered_results": [],
            "summary": "",
            "citations": [],
            "agent_decisions": [],
            "agent_unavailable": False,
            "performance": {"total_time_ms": 1, "total_available": 0},
            "semantic_fallback_used": False,
            "query_plan": {
                "schema_version": "v1.1.1",
                "raw_query": "test",
                "expanded_query": "test",
                "sub_queries": ["a", "b"],
                "strategy": "keyword_multi_pass",
                "fallback_decision": False,
            },
        }

        captured = StringIO()
        with patch("sys.argv", ["smart-search", "--query", "test", "--explain"]):
            with patch("tools.search_journals.orchestrator.SmartSearchOrchestrator") as MockCls:
                mock_orch = MagicMock()
                mock_orch.search.return_value = mock_result.copy()
                MockCls.return_value = mock_orch
                with patch(
                    "builtins.print",
                    side_effect=lambda *a, **kw: captured.write(str(a[0])) if a else None,
                ):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit:
                        pass

        result = json.loads(captured.getvalue())
        assert result["query_plan"]["sub_queries"] == ["a", "b"]
        assert result["query_plan"]["strategy"] == "keyword_multi_pass"

    def test_smart_search_cli_no_explain_no_diagnostics(self):
        """Without --explain, CLI output must NOT contain diagnostics."""
        from io import StringIO

        mock_result = {
            "success": True,
            "query": "test",
            "rewritten_query": "test",
            "filtered_results": [],
            "summary": "",
            "citations": [],
            "agent_decisions": [],
            "agent_unavailable": True,
            "performance": {"total_time_ms": 10},
        }

        captured = StringIO()
        with patch("sys.argv", ["smart-search", "--query", "test"]):
            with patch("tools.search_journals.orchestrator.SmartSearchOrchestrator") as MockCls:
                mock_orch = MagicMock()
                mock_orch.search.return_value = mock_result.copy()
                MockCls.return_value = mock_orch
                with patch(
                    "builtins.print",
                    side_effect=lambda *a, **kw: captured.write(str(a[0])) if a else None,
                ):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit:
                        pass

        result = json.loads(captured.getvalue())
        assert "diagnostics" not in result


# ── Index --explain contract ──


class TestIndexExplainDiagnostics:
    """``index --explain`` output contains deterministic diagnostics."""

    def test_index_explain_has_diagnostics(self, tmp_path):
        """CLI --explain emits diagnostics computed from build_all result."""
        from io import StringIO

        captured = StringIO()
        mock_build_result = {
            "success": True,
            "fts": {"success": True, "added": 5, "updated": 3},
            "vector": None,
            "duration_seconds": 0.25,
            "rebuild_hint": "",
            "auto_rebuild_triggered": False,
        }

        with patch("sys.argv", ["build-index", "--explain"]):
            with patch(
                "tools.build_index.__main__.build_all",
                return_value=mock_build_result,
            ):
                with patch(
                    "tools.build_index.__main__.get_cache_stats",
                    return_value={"total_entries": 42, "rebuild_hint": ""},
                ):
                    with patch(
                        "builtins.print",
                        side_effect=lambda *a, **kw: captured.write(str(a[0])) if a else None,
                    ):
                        from tools.build_index.__main__ import main

                        try:
                            main()
                        except SystemExit:
                            pass

        result = json.loads(captured.getvalue())
        assert "diagnostics" in result, "explain output missing diagnostics"
        _assert_diagnostics_shape(result["diagnostics"])
        assert result["diagnostics"]["input_count"] == 8
        assert result["diagnostics"]["latency_ms"]["total"] == 250
        assert result["diagnostics"]["cache_hits"] == 42

    def test_index_no_explain_no_diagnostics(self, tmp_path):
        """Without --explain, CLI JSON output must NOT contain diagnostics."""
        from io import StringIO

        captured = StringIO()
        mock_build_result = {
            "success": True,
            "fts": {"success": True, "added": 0},
            "vector": None,
            "duration_seconds": 0.1,
            "rebuild_hint": "",
            "auto_rebuild_triggered": False,
        }

        with patch("sys.argv", ["build-index", "--json"]):
            with patch(
                "tools.build_index.__main__.build_all",
                return_value=mock_build_result,
            ):
                with patch(
                    "builtins.print",
                    side_effect=lambda *a, **kw: captured.write(str(a[0])) if a else None,
                ):
                    from tools.build_index.__main__ import main

                    try:
                        main()
                    except SystemExit:
                        pass

        result = json.loads(captured.getvalue())
        assert "diagnostics" not in result

    def test_index_cli_explain_emits_json_with_diagnostics(self, tmp_path):
        """--explain on CLI emits JSON containing diagnostics."""
        from io import StringIO

        captured = StringIO()
        mock_build_result = {
            "success": True,
            "fts": {"success": True, "added": 0},
            "vector": None,
            "duration_seconds": 0.1,
            "rebuild_hint": "",
            "auto_rebuild_triggered": False,
            "diagnostics": {
                "input_count": 0,
                "filter_drops": {},
                "cache_hits": 0,
                "cache_misses": 0,
                "latency_ms": {"total": 100},
                "fallback_path": None,
            },
        }

        with patch("sys.argv", ["build-index", "--explain"]):
            with patch(
                "tools.build_index.__main__.build_all",
                return_value=mock_build_result,
            ):
                with patch(
                    "tools.build_index.__main__.get_cache_stats",
                    return_value={"total_entries": 0, "rebuild_hint": ""},
                ):
                    with patch(
                        "builtins.print",
                        side_effect=lambda *a, **kw: captured.write(str(a[0])) if a else None,
                    ):
                        from tools.build_index.__main__ import main

                        try:
                            main()
                        except SystemExit:
                            pass

        result = json.loads(captured.getvalue())
        assert "diagnostics" in result
        _assert_diagnostics_shape(result["diagnostics"])
