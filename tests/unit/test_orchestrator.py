"""Orchestrator interface and constraint tests.

Phase 5 (Task 4): Smart search orchestrator — TDD RED phase.
These tests define the interface contract. Initially all should FAIL
because the module doesn't exist yet.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def test_orchestrator_module_importable():
    """SmartSearchOrchestrator class must exist."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator  # noqa: F401


def test_orchestrator_has_three_stages():
    """Orchestrator must expose three-stage pipeline methods."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=None)  # None = mock/degradation mode
    assert hasattr(orch, "rewrite_query")
    assert hasattr(orch, "execute_search")
    assert hasattr(orch, "post_filter_and_summarize")


def test_data_minimization_limit():
    """ORCHESTRATOR_MAX_LLM_CANDIDATES must be 15."""
    from tools.lib.search_constants import ORCHESTRATOR_MAX_LLM_CANDIDATES

    assert ORCHESTRATOR_MAX_LLM_CANDIDATES == 15


def test_llm_degradation_on_failure():
    """When LLM is unavailable, must return agent_unavailable: true + valid results."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    mock_result = {
        "success": True,
        "merged_results": [{"title": "test", "path": "test.md", "relevance": 80}],
        "total_available": 1,
        "performance": {},
    }
    orch = SmartSearchOrchestrator(llm_client=None)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn", return_value=lambda **kw: mock_result
    ):
        result = orch.search("乐乐")
    assert result.get("agent_unavailable") is True
    assert "filtered_results" in result
    assert isinstance(result["filtered_results"], list)


def test_output_schema():
    """Output must have all required fields per PRD Task 4."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    mock_result = {
        "success": True,
        "merged_results": [],
        "total_available": 0,
        "performance": {},
    }
    orch = SmartSearchOrchestrator(llm_client=None)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn", return_value=lambda **kw: mock_result
    ):
        result = orch.search("乐乐")
    required_fields = ["filtered_results", "summary", "citations", "agent_decisions"]
    for field in required_fields:
        assert field in result, f"Missing required field: {field}"


def test_data_minimization_in_prompt():
    """No full_content field should appear in LLM prompt construction."""
    orch_file = REPO_ROOT / "tools" / "search_journals" / "orchestrator.py"
    if orch_file.exists():
        text = orch_file.read_text(encoding="utf-8")
        # The orchestrator should never reference full_content in LLM prompt paths
        # Check that no line builds a prompt with full_content
        lines = text.split("\n")
        for i, line in enumerate(lines, 1):
            if "prompt" in line.lower() and "full_content" in line:
                assert False, (
                    f"Line {i}: full_content referenced in prompt construction. "
                    "Data minimization violation."
                )


def test_no_full_content_import():
    """orchestrator.py must NOT import llm_extract from tools.lib."""
    orch_file = REPO_ROOT / "tools" / "search_journals" / "orchestrator.py"
    if orch_file.exists():
        text = orch_file.read_text(encoding="utf-8")
        assert (
            "llm_extract" not in text
        ), "orchestrator must use independent LLM client, not tools.lib.llm_extract"
