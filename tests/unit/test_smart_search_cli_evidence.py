"""CLI tests for smart-search --include-evidence flag (R2C3).

Tests argparse wiring and output shape without running full search pipeline.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def _mock_orch_search(query, include_evidence=False):
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
            with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
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
            with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
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


def test_cli_include_evidence_adds_pack():
    """With --include-evidence, output includes evidence_pack."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test", "--include-evidence"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch(),
        ):
            with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
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
