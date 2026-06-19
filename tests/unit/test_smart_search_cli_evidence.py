"""CLI tests for smart-search --include-evidence flag (R2C3).

Tests argparse wiring and output shape without running full search pipeline.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def _mock_orch_search(query, include_evidence=False, **kwargs):
    """Mock orchestrator.search() returning evidence only when flag set."""
    result = {
        "success": True,
        "query": query,
        "rewritten_query": query,
        "filtered_results": [{"title": "mock", "path": "mock.md"}],
        "summary": "",
        "citations": [],
        "agent_decisions": [],
        "agent_unavailable": True,
        "performance": {"total_time_ms": 10.0},
        "smart_search_mode": "deterministic_scaffold",
        "agent_instructions": {
            "schema_version": "smart_search.agent_instructions.v1",
            "role": "calling_agent",
            "mode": "deterministic_scaffold",
            "steps": [
                "Use filtered_results as bounded evidence; do not cite outside returned results."
            ],
        },
        "answer_scaffold": {
            "schema_version": "smart_search.answer_scaffold.v1",
            "query": query,
            "citation_policy": "cite_only_returned_results",
            "result_count": 1,
        },
        "query_plan": {
            "schema_version": "v1.1.1",
            "raw_query": query,
            "expanded_query": query,
            "sub_queries": [query],
            "strategy": "keyword_only",
            "fallback_decision": False,
        },
    }
    if include_evidence:
        result["evidence_pack"] = {
            "query_context": {"query": query},
            "items": [{"document": {"title": "mock"}, "scores": {"source": "fts"}}],
            "semantic_candidates": [],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
        }
        result["performance"]["evidence_build_ms"] = 1.5
    return result


def _make_mock_orch():
    """Create mock orchestrator with search side_effect."""
    orch = MagicMock()
    orch.search.side_effect = _mock_orch_search
    return orch


def test_cli_include_evidence_flag_parsed():
    """--include-evidence is recognized and passed through to search()."""
    with patch("sys.argv", ["smart-search", "--query", "test", "--include-evidence"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch(),
        ) as MockCls:
            with patch("builtins.print"):
                from tools.smart_search.__main__ import main

                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0
            instance = MockCls.return_value
            call_kwargs = instance.search.call_args
    assert call_kwargs.kwargs.get("include_evidence") is True


def test_cli_default_no_evidence():
    """Without --include-evidence, output has no evidence_pack key."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch(),
        ):
            with patch(
                "builtins.print",
                side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
            ):
                from tools.smart_search.__main__ import main

                try:
                    main()
                except SystemExit:
                    pass
    result = json.loads(captured[0])
    assert "evidence_pack" not in result


def test_cli_default_emits_agent_ready_scaffold():
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch(),
        ):
            with patch(
                "builtins.print",
                side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
            ):
                from tools.smart_search.__main__ import main

                try:
                    main()
                except SystemExit:
                    pass

    result = json.loads(captured[0])
    assert result["smart_search_mode"] == "deterministic_scaffold"
    assert result["agent_instructions"]["role"] == "calling_agent"
    assert result["answer_scaffold"]["citation_policy"] == "cite_only_returned_results"


def test_cli_default_does_not_initialize_llm():
    """Default smart-search path must construct the orchestrator without an LLM."""
    with patch("sys.argv", ["smart-search", "--query", "test"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch(),
        ) as MockCls:
            with patch("builtins.print"):
                from tools.smart_search.__main__ import main

                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0

    MockCls.assert_called_once_with(llm_client=None)


def test_cli_use_llm_is_not_accepted():
    """smart-search must not expose an in-tool LLM opt-in flag."""
    with patch("sys.argv", ["smart-search", "--query", "test", "--use-llm"]):
        from tools.smart_search.__main__ import main

        try:
            main()
        except SystemExit as e:
            assert e.code == 2


def test_cli_include_evidence_adds_pack():
    """With --include-evidence, output includes evidence_pack."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test", "--include-evidence"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch(),
        ):
            with patch(
                "builtins.print",
                side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
            ):
                from tools.smart_search.__main__ import main

                try:
                    main()
                except SystemExit:
                    pass
    result = json.loads(captured[0])
    assert "evidence_pack" in result
    assert "items" in result["evidence_pack"]


def test_cli_help_includes_evidence_flag():
    """--include-evidence appears in CLI help text."""
    captured = []
    with patch("sys.argv", ["smart-search", "--help"]):
        with patch("sys.stdout.write", side_effect=lambda text: captured.append(text)):
            from tools.smart_search.__main__ import main

            try:
                main()
            except SystemExit as e:
                assert e.code == 0

    help_text = "".join(captured)
    assert "--include-evidence" in help_text
    assert "evidence pack" in help_text.lower()


# ---------------------------------------------------------------------------
# R2D1: --synthesize CLI tests
# ---------------------------------------------------------------------------


def _mock_orch_search_with_synthesis(query, include_evidence=False, synthesize=False):
    """Mock orchestrator.search() returning answer when synthesize=True."""
    result = {
        "success": True,
        "query": query,
        "rewritten_query": query,
        "filtered_results": [{"title": "mock", "path": "mock.md"}],
        "summary": "",
        "citations": [],
        "agent_decisions": [],
        "agent_unavailable": False,
        "performance": {"total_time_ms": 10.0},
    }
    if synthesize:
        result["answer"] = {
            "answer_text": "Mock answer based on evidence.",
            "citations": ["mock.md"],
            "confidence": "medium",
            "confidence_reason": "Answer supported by retrieved results without evidence pack.",
            "limitations": [],
            "evidence_summary": "",
        }
        result["performance"]["synthesis_ms"] = 50.0
    if include_evidence:
        result["evidence_pack"] = {
            "query_context": {"query": query},
            "items": [{"document": {"title": "mock"}, "scores": {"source": "fts"}}],
            "semantic_candidates": [],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
        }
        result["performance"]["evidence_build_ms"] = 1.5
    return result


def _make_mock_orch_with_synthesis():
    """Create mock orchestrator with search side_effect supporting synthesize."""
    orch = MagicMock()
    orch.search.side_effect = _mock_orch_search_with_synthesis
    return orch


def test_cli_synthesize_flag_parsed():
    """--synthesize is recognized and passed through to search()."""
    with patch("sys.argv", ["smart-search", "--query", "test", "--synthesize"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch_with_synthesis(),
        ) as MockCls:
            with patch("builtins.print"):
                from tools.smart_search.__main__ import main

                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0
            instance = MockCls.return_value
            call_kwargs = instance.search.call_args
    assert call_kwargs.kwargs.get("synthesize") is True


def test_cli_default_no_answer():
    """Without --synthesize, output has no answer key."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch_with_synthesis(),
        ):
            with patch(
                "builtins.print",
                side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
            ):
                from tools.smart_search.__main__ import main

                try:
                    main()
                except SystemExit:
                    pass
    result = json.loads(captured[0])
    assert "answer" not in result


def test_cli_help_includes_synthesize_flag():
    """--synthesize appears in CLI help text."""
    captured = []
    with patch("sys.argv", ["smart-search", "--help"]):
        with patch("sys.stdout.write", side_effect=lambda text: captured.append(text)):
            from tools.smart_search.__main__ import main

            try:
                main()
            except SystemExit as e:
                assert e.code == 0

    help_text = "".join(captured)
    assert "--synthesize" in help_text
    assert "--use-llm" not in help_text
    assert "--no-llm" not in help_text


# ---------------------------------------------------------------------------
# R2D3: Answer transparency CLI tests
# ---------------------------------------------------------------------------


def test_cli_synthesize_output_includes_transparency_fields():
    """--synthesize output includes confidence_reason, limitations, evidence_summary."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test", "--synthesize"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch_with_synthesis(),
        ):
            with patch(
                "builtins.print",
                side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
            ):
                from tools.smart_search.__main__ import main

                try:
                    main()
                except SystemExit:
                    pass
    result = json.loads(captured[0])
    assert "answer" in result
    answer = result["answer"]
    assert "confidence_reason" in answer
    assert "limitations" in answer
    assert "evidence_summary" in answer
    assert isinstance(answer["limitations"], list)


# ---------------------------------------------------------------------------
# R2J: Evidence Pack Diagnostics CLI tests
# ---------------------------------------------------------------------------

_VALID_OUTCOMES = ("ok", "weak_results", "no_confident_match", "zero_results")


def _mock_orch_search_with_diagnostics(query, include_evidence=False, **kwargs):
    """Mock orchestrator.search() with diagnostics in evidence_pack."""
    result = {
        "success": True,
        "query": query,
        "rewritten_query": query,
        "filtered_results": [{"title": "mock", "path": "mock.md"}],
        "summary": "",
        "citations": [],
        "agent_decisions": [],
        "agent_unavailable": True,
        "performance": {"total_time_ms": 10.0},
    }
    if include_evidence:
        result["evidence_pack"] = {
            "query_context": {"query": query},
            "items": [{"document": {"title": "mock"}, "scores": {"source": "fts"}}],
            "semantic_candidates": [],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
            "diagnostics": {
                "retrieval_outcome": "ok",
                "outcome_reason": "confident_results_present",
            },
        }
        result["performance"]["evidence_build_ms"] = 1.5
    return result


def _make_mock_orch_with_diagnostics():
    """Create mock orchestrator with diagnostics-aware search."""
    orch = MagicMock()
    orch.search.side_effect = _mock_orch_search_with_diagnostics
    return orch


def test_cli_evidence_includes_diagnostics():
    """--include-evidence output includes evidence_pack.diagnostics."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test", "--include-evidence"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch_with_diagnostics(),
        ):
            with patch(
                "builtins.print",
                side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
            ):
                from tools.smart_search.__main__ import main

                try:
                    main()
                except SystemExit:
                    pass
    result = json.loads(captured[0])
    assert "evidence_pack" in result
    assert "diagnostics" in result["evidence_pack"]
    diag = result["evidence_pack"]["diagnostics"]
    assert diag["retrieval_outcome"] in _VALID_OUTCOMES
    assert isinstance(diag.get("outcome_reason"), str)
    # notes/suggestions conditionally present (omitted when empty)
    if "notes" in diag:
        assert isinstance(diag["notes"], list)
    if "suggestions" in diag:
        assert isinstance(diag["suggestions"], list)


def test_cli_default_no_diagnostics():
    """Default output has no evidence_pack, hence no diagnostics."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch_with_diagnostics(),
        ):
            with patch(
                "builtins.print",
                side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
            ):
                from tools.smart_search.__main__ import main

                try:
                    main()
                except SystemExit:
                    pass
    result = json.loads(captured[0])
    assert "evidence_pack" not in result


def test_emit_json_falls_back_to_ascii_when_console_rejects_unicode(monkeypatch):
    """Windows GBK consoles must not crash smart-search JSON output."""
    from tools.smart_search.__main__ import _emit_json

    calls = []

    def fake_print(text):
        calls.append(text)
        if len(calls) == 1:
            raise UnicodeEncodeError("gbk", "⭐", 0, 1, "illegal multibyte sequence")

    monkeypatch.setattr("builtins.print", fake_print)

    _emit_json({"text": "⭐"})

    assert len(calls) == 2
    assert "\\u2b50" in calls[1]
