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
    """LLM rewritten_query goes into query_context, not expanded_query."""
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
    assert "rewritten_query" not in pack
    assert pack["query_context"].get("rewritten_query") == "family activities with kids"
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


def test_evidence_pack_empty_results():
    """include_evidence=True with empty merged_results produces valid empty pack."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    empty_result = {
        "success": True,
        "query_params": {"query": "nonexistent"},
        "merged_results": [],
        "semantic_results": [],
        "total_available": 0,
        "has_more": False,
        "no_confident_match": True,
        "performance": {"total_time_ms": 5.0},
    }
    orch = SmartSearchOrchestrator(llm_client=None)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: empty_result,
    ):
        result = orch.search("nonexistent", include_evidence=True)
    assert "evidence_pack" in result
    pack = result["evidence_pack"]
    assert pack["items"] == []
    assert pack["total_available"] == 0
    assert pack["no_confident_match"] is True


# ---------------------------------------------------------------------------
# R2D1: Opt-in Answer Synthesis tests
# ---------------------------------------------------------------------------


class FakeSynthesisLLM:
    """LLM that returns a canned synthesis response."""

    def __init__(self, response_override: str | None = None):
        self._response = response_override
        self.last_messages: list[dict[str, str]] | None = None

    def chat(self, messages, *, max_tokens=2000):
        self.last_messages = messages
        if self._response is not None:
            return self._response
        import json

        return json.dumps(
            {
                "answer_text": "Based on your journals, you had two family events.",
                "citations": [
                    "Journals/2026/03/life-index_2026-03-01_001.md",
                    "Journals/2026/03/life-index_2026-03-02_001.md",
                ],
                "confidence": "high",
            }
        )


def test_synthesize_default_no_answer():
    """Default orch.search() must NOT include answer in output."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=None)
    mock_result = _mock_search_result(count=2)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test")
    assert "answer" not in result


def test_synthesize_fake_llm_produces_answer():
    """Fake LLM + synthesize=True produces answer field."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    mock_result = _mock_search_result(count=2)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", synthesize=True)
    assert "answer" in result
    assert result["answer"]["answer_text"] != ""
    assert isinstance(result["answer"]["citations"], list)
    assert result["answer"]["confidence"] in ("high", "medium", "low")


def test_synthesize_no_llm_omits_answer():
    """No LLM + synthesize=True omits answer and preserves search output."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=None)
    mock_result = _mock_search_result(count=2)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", synthesize=True)
    assert "answer" not in result
    assert result["success"] is True
    assert len(result["filtered_results"]) == 2


def test_synthesize_empty_results_omits_answer():
    """Empty results + synthesize=True omits answer."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    empty_result = {
        "success": True,
        "query_params": {"query": "none"},
        "merged_results": [],
        "semantic_results": [],
        "total_available": 0,
        "has_more": False,
        "no_confident_match": True,
        "performance": {"total_time_ms": 5.0},
    }
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: empty_result,
    ):
        result = orch.search("none", synthesize=True)
    assert "answer" not in result
    assert result["success"] is True


def test_synthesize_llm_exception_best_effort():
    """LLM exception during synthesis does not fail search."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    class ExplodingLLM:
        def chat(self, messages, *, max_tokens=2000):
            raise RuntimeError("LLM timeout")

    orch = SmartSearchOrchestrator(llm_client=ExplodingLLM())
    mock_result = _mock_search_result(count=2)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", synthesize=True)
    assert result["success"] is True
    assert "answer" not in result
    assert len(result["filtered_results"]) == 2


def test_synthesize_malformed_response_graceful():
    """Malformed LLM synthesis response omits answer without failing search."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM(response_override="this is not JSON at all")
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    mock_result = _mock_search_result(count=2)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", synthesize=True)
    assert result["success"] is True
    # Malformed response should either omit answer or produce a fallback
    if "answer" in result:
        assert result["answer"]["answer_text"] != ""


def test_synthesis_prompt_data_minimization():
    """Synthesis prompt must not contain full_content, raw metadata, or absolute paths."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    # Include a candidate with full_content and absolute path to verify stripping
    mock_result = {
        "success": True,
        "query_params": {"query": "test"},
        "merged_results": [
            {
                "path": (
                    "C:/Users/secret/Documents/Life-Index/Journals/2026/03/"
                    "life-index_2026-03-01_001.md"
                ),
                "title": "Secret Entry",
                "date": "2026-03-01",
                "snippet": "some snippet",
                "source": "fts",
                "relevance": 90,
                "rrf_score": 0.9,
                "full_content": (
                    "This is the full private journal content that must not be " "sent to LLM."
                ),
                "metadata": {
                    "topic": "secret",
                    "people": ["Alice", "Bob"],
                    "mood": ["happy"],
                    "tags": ["private"],
                },
            },
        ],
        "semantic_results": [],
        "total_available": 1,
        "has_more": False,
        "performance": {},
    }
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        orch.search("test", synthesize=True)
    # Verify the prompt sent to LLM
    prompt_text = fake_llm.last_messages[0]["content"] if fake_llm.last_messages else ""
    assert "full_content" not in prompt_text, "full_content leaked into synthesis prompt"
    assert "C:/Users/secret" not in prompt_text, "Absolute path leaked into synthesis prompt"
    assert "Alice" not in prompt_text, "Raw metadata.people leaked into synthesis prompt"
    assert "private" not in prompt_text or "private" in "Secret Entry", "Raw tags leaked"


def test_synthesize_filtered_results_unchanged():
    """filtered_results are identical with and without synthesis."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM()
    mock_result = _mock_search_result(count=3)

    orch_no_synth = SmartSearchOrchestrator(llm_client=fake_llm)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        r_no = orch_no_synth.search("test", synthesize=False)

    orch_synth = SmartSearchOrchestrator(llm_client=fake_llm)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        r_yes = orch_synth.search("test", synthesize=True)

    assert r_no["filtered_results"] == r_yes["filtered_results"]


def test_synthesize_adds_performance_synthesis_ms():
    """performance.synthesis_ms is present when synthesis is attempted."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    mock_result = _mock_search_result(count=2)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", synthesize=True)
    assert "synthesis_ms" in result["performance"]
    assert result["performance"]["synthesis_ms"] >= 0


def test_evidence_build_failure_does_not_fail_search():
    """Evidence build failure is best-effort and does not leak raw results."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=None)
    mock_result = _mock_search_result()
    with (
        patch(
            "tools.search_journals.orchestrator._get_search_fn",
            return_value=lambda **kw: mock_result,
        ),
        patch(
            "tools.evidence.adapter.extract_evidence_from_orchestrator",
            side_effect=ValueError("missing query_params"),
        ),
    ):
        result = orch.search("test", include_evidence=True)

    assert result["success"] is True
    assert "evidence_pack" not in result
    assert "raw_results" not in result
    assert result["performance"]["evidence_build_ms"] >= 0
    assert "missing query_params" in result["performance"]["evidence_error"]


# ---------------------------------------------------------------------------
# R2D1 Rework: Evidence-aware synthesis tests
# ---------------------------------------------------------------------------


def test_synthesize_builds_evidence_internally_no_evidence_in_output():
    """synthesize=True, include_evidence=False: evidence is built internally
    but evidence_pack is NOT in the output."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    mock_result = _mock_search_result(count=2)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", synthesize=True, include_evidence=False)
    assert "answer" in result
    assert "evidence_pack" not in result


def test_synthesize_prompt_includes_evidence_provenance():
    """Synthesis prompt includes evidence-derived provenance/source/score
    when evidence is available."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    mock_result = _mock_search_result(count=2)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", synthesize=True)
    assert result["success"] is True
    prompt_text = fake_llm.last_messages[0]["content"] if fake_llm.last_messages else ""
    # Evidence pack items have provenance="keyword" and source="fts" by default
    assert "provenance:" in prompt_text, "Evidence provenance missing from synthesis prompt"
    assert "source:" in prompt_text, "Evidence source missing from synthesis prompt"
    assert "score:" in prompt_text, "Evidence score missing from synthesis prompt"


def test_synthesize_evidence_build_failure_still_succeeds():
    """Evidence build failure with synthesize=True still allows search
    to succeed and omits or falls back on answer safely."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    mock_result = _mock_search_result(count=2)
    with (
        patch(
            "tools.search_journals.orchestrator._get_search_fn",
            return_value=lambda **kw: mock_result,
        ),
        patch(
            "tools.evidence.adapter.extract_evidence_from_orchestrator",
            side_effect=ValueError("broken evidence"),
        ),
    ):
        result = orch.search("test", synthesize=True)
    assert result["success"] is True
    assert "evidence_pack" not in result
    # Answer may still be present (fallback to filtered_results) or absent
    if "answer" in result:
        assert result["answer"]["answer_text"] != ""


def test_include_evidence_and_synthesize_combined():
    """include_evidence=True, synthesize=True: both evidence_pack and answer
    are present in output."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    mock_result = _mock_search_result(count=2)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", synthesize=True, include_evidence=True)
    assert "answer" in result
    assert "evidence_pack" in result
    assert result["evidence_pack"]["total_available"] == 2
