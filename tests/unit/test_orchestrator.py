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


# ---------------------------------------------------------------------------
# R2C3: Evidence Pack opt-in wiring tests
# ---------------------------------------------------------------------------


def _mock_search_result(count=2):
    """Build a mock hierarchical_search() result for evidence tests."""
    items = []
    for i in range(1, count + 1):
        items.append(
            {
                "path": f"Journals/2026/03/life-index_2026-03-0{i}_001.md",
                "title": f"Test Entry {i}",
                "date": f"2026-03-0{i}",
                "snippet": f"snippet {i}",
                "source": "fts",
                "relevance": 90 - i * 10,
                "fts_score": float(90 - i * 10),
                "semantic_score": 0.0,
                "rrf_score": 0.0,
                "final_score": float(90 - i * 10),
                "search_rank": i,
                "confidence": "high" if i == 1 else "medium",
                "metadata": {
                    "topic": "test",
                    "location": "Beijing",
                    "abstract": f"Abstract for entry {i}.",
                },
            }
        )
    return {
        "success": True,
        "query_params": {"query": "test", "expanded_query": "test expanded"},
        "merged_results": items,
        "semantic_results": [],
        "total_available": count,
        "has_more": False,
        "no_confident_match": False,
        "performance": {"total_time_ms": 42.0},
    }


def test_default_search_no_evidence_pack():
    """Default orch.search() must NOT include evidence_pack in output."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=None)
    mock_result = _mock_search_result()
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test")
    assert "evidence_pack" not in result


def test_include_evidence_produces_pack():
    """orch.search(include_evidence=True) must include evidence_pack dict."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=None)
    mock_result = _mock_search_result(count=3)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", include_evidence=True)
    assert "evidence_pack" in result
    pack = result["evidence_pack"]
    assert isinstance(pack, dict)
    assert "items" in pack
    assert "query_context" in pack
    assert "total_available" in pack
    assert len(pack["items"]) == 3


def test_evidence_pack_uses_raw_results_not_filtered():
    """Evidence pack items come from raw merged_results, not post-LLM-filter."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=None)
    mock_result = _mock_search_result(count=5)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", include_evidence=True)
    pack = result["evidence_pack"]
    # Pack items count should match raw merged_results (5), not filtered_results
    assert len(pack["items"]) == 5


def test_include_evidence_degradation_mode():
    """include_evidence=True works in degradation mode (no LLM)."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=None)
    mock_result = _mock_search_result(count=1)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", include_evidence=True)
    assert result["agent_unavailable"] is True
    assert "evidence_pack" in result
    assert len(result["evidence_pack"]["items"]) == 1


def test_evidence_rewrite_overlay_separate_from_expansion():
    """LLM rewritten_query goes into evidence extra, not expanded_query."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    class FakeLLM:
        def chat(self, messages, *, max_tokens=2000):
            import json

            return json.dumps(
                {
                    "core_terms": "family",
                    "expanded_terms": [],
                    "time_range": None,
                    "intent_type": "simple",
                    "rewritten_query": "family activities with kids",
                }
            )

    orch = SmartSearchOrchestrator(llm_client=FakeLLM())
    mock_result = _mock_search_result()
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("family", include_evidence=True)
    pack = result["evidence_pack"]
    # rewritten_query is flattened into top-level by EvidencePack.to_dict()
    assert pack.get("rewritten_query") == "family activities with kids"
    # expanded_query must be from entity expansion, not LLM rewrite
    assert pack["query_context"].get("expanded_query") == "test expanded"


def test_evidence_build_ms_in_performance():
    """performance.evidence_build_ms is present when include_evidence=True."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=None)
    mock_result = _mock_search_result()
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", include_evidence=True)
    assert "evidence_build_ms" in result["performance"]
    assert result["performance"]["evidence_build_ms"] >= 0


def test_no_raw_results_leak():
    """Returned dict must not contain raw_results internal key."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=None)
    mock_result = _mock_search_result()
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", include_evidence=True)
    assert "raw_results" not in result
