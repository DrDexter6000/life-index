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


# ---------------------------------------------------------------------------
# R2D2: Answer Trust Gate tests
# ---------------------------------------------------------------------------


class TrustGateLLM:
    """LLM returning configurable synthesis responses for trust gate testing."""

    def __init__(
        self,
        answer_text: str = "Test answer",
        citations: list | None = None,
        confidence: str = "high",
    ):
        self._answer_text = answer_text
        self._citations = citations or []
        self._confidence = confidence

    def chat(self, messages, *, max_tokens=2000):
        import json

        return json.dumps(
            {
                "answer_text": self._answer_text,
                "citations": self._citations,
                "confidence": self._confidence,
            }
        )


def _trust_gate_filtered_results(count: int = 3) -> list[dict]:
    """Build filtered_results with known rel_paths for trust gate tests."""
    results = []
    for i in range(1, count + 1):
        results.append(
            {
                "title": f"Entry {i}",
                "date": f"2026-03-{i:02d}",
                "abstract": f"Abstract {i}",
                "rel_path": f"Journals/2026/03/life-index_2026-03-{i:02d}_001.md",
                "snippet": f"Snippet {i}",
            }
        )
    return results


def _trust_gate_evidence_context(
    count: int = 3,
    confidences: list[str] | None = None,
) -> list[dict]:
    """Build evidence_context with known rel_paths and confidences."""
    if confidences is None:
        confidences = ["medium"] * count
    results = []
    for i in range(1, count + 1):
        results.append(
            {
                "title": f"Entry {i}",
                "date": f"2026-03-{i:02d}",
                "snippet": f"Snippet {i}",
                "rel_path": f"Journals/2026/03/life-index_2026-03-{i:02d}_001.md",
                "provenance": "keyword",
                "source": "fts",
                "score": 0.7,
                "confidence": confidences[i - 1],
            }
        )
    return results


def test_trust_gate_numeric_citations_map_to_relative_paths():
    """LLM numeric citations map to expected relative paths from filtered_results."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(citations=[1, 2])
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
    )

    assert result is not None
    assert result["citations"] == [
        "Journals/2026/03/life-index_2026-03-01_001.md",
        "Journals/2026/03/life-index_2026-03-02_001.md",
    ]


def test_trust_gate_string_citation_not_in_set_dropped():
    """LLM string citation not in current evidence/filter set is dropped."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(
        citations=[
            "Journals/2026/03/life-index_2026-03-01_001.md",  # valid
            "Journals/2026/03/FAKE_NONEXISTENT_PATH.md",  # hallucinated
        ]
    )
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
    )

    assert result is not None
    assert result["citations"] == [
        "Journals/2026/03/life-index_2026-03-01_001.md",
    ]


def test_trust_gate_absolute_citation_dropped():
    """Absolute path citations are always dropped."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(
        citations=[
            "C:/Users/test/Documents/Life-Index/Journals/2026/03/life-index_2026-03-01_001.md",
        ]
    )
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
    )

    assert result is not None
    assert result["citations"] == []
    assert result["confidence"] == "low"


def test_trust_gate_high_confidence_no_valid_citations_capped_low():
    """LLM confidence='high' is capped to 'low' when no valid citations."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(
        citations=["Journals/2026/03/FAKE.md"],
        confidence="high",
    )
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
    )

    assert result is not None
    assert result["citations"] == []
    assert result["confidence"] == "low"


def test_trust_gate_high_confidence_cited_evidence_medium_capped_medium():
    """LLM confidence='high' is capped to 'medium' when cited evidence max is medium."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(citations=[1], confidence="high")
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)
    evidence = _trust_gate_evidence_context(3, confidences=["medium", "medium", "low"])

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
        evidence_context=evidence,
    )

    assert result is not None
    assert result["confidence"] == "medium"


def test_trust_gate_low_confidence_stays_low_with_high_evidence():
    """LLM confidence='low' remains low even when evidence is high."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(citations=[1], confidence="low")
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)
    evidence = _trust_gate_evidence_context(3, confidences=["high", "medium", "low"])

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
        evidence_context=evidence,
    )

    assert result is not None
    assert result["confidence"] == "low"


def test_trust_gate_no_evidence_context_valid_citations_cap_medium():
    """Without evidence context, valid filtered-results citations cap at medium."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(citations=[1], confidence="high")
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
    )

    assert result is not None
    assert len(result["citations"]) == 1
    assert result["confidence"] == "medium"


def test_trust_gate_high_confidence_with_high_evidence_allowed():
    """LLM confidence='high' with high-evidence citations is allowed."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(citations=[1], confidence="high")
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)
    evidence = _trust_gate_evidence_context(3, confidences=["high", "medium", "low"])

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
        evidence_context=evidence,
    )

    assert result is not None
    assert result["confidence"] == "high"


# ---------------------------------------------------------------------------
# R2D3: Answer Transparency Contract tests
# ---------------------------------------------------------------------------


def test_transparency_high_evidence_has_reason_and_summary():
    """High-evidence cited answer has confidence_reason and non-empty evidence_summary."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(citations=[1], confidence="high")
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)
    evidence = _trust_gate_evidence_context(3, confidences=["high", "medium", "low"])

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
        evidence_context=evidence,
    )

    assert result is not None
    assert "confidence_reason" in result, "Missing transparency field: confidence_reason"
    assert "high" in result["confidence_reason"].lower()
    assert "evidence_summary" in result, "Missing transparency field: evidence_summary"
    assert result["evidence_summary"] != ""
    assert "limitations" in result, "Missing transparency field: limitations"
    assert isinstance(result["limitations"], list)


def test_transparency_no_valid_citations_has_limitations():
    """No valid citation answer has low confidence and explicit limitations."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(
        citations=["Journals/2026/03/FAKE.md"],
        confidence="high",
    )
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
    )

    assert result is not None
    assert result["confidence"] == "low"
    assert "limitations" in result
    assert any(
        "no validated citations" in lim.lower() for lim in result["limitations"]
    ), f"Expected 'no validated citations' in limitations, got: {result['limitations']}"
    assert result["evidence_summary"] == ""


def test_transparency_medium_evidence_medium_reason():
    """Medium evidence produces confidence_reason mentioning moderate evidence."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(citations=[1], confidence="high")
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)
    evidence = _trust_gate_evidence_context(3, confidences=["medium", "medium", "low"])

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
        evidence_context=evidence,
    )

    assert result is not None
    assert "confidence_reason" in result
    assert "moderate" in result["confidence_reason"].lower()


def test_transparency_llm_injected_fields_not_trusted():
    """LLM-provided transparency fields are not blindly trusted when citations are dropped."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    class TransparencyInjectingLLM:
        def chat(self, messages, *, max_tokens=2000):
            import json

            return json.dumps(
                {
                    "answer_text": "Some answer about events.",
                    "citations": [
                        "Journals/2026/03/FAKE_NONEXISTENT.md",
                        "Journals/2026/03/life-index_2026-03-01_001.md",
                    ],
                    "confidence": "high",
                    "confidence_reason": "LLM INJECTED: Very confident!",
                    "limitations": ["LLM INJECTED: None at all"],
                    "evidence_summary": "LLM INJECTED: Strong evidence",
                }
            )

    llm = TransparencyInjectingLLM()
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)
    evidence = _trust_gate_evidence_context(3, confidences=["medium", "medium", "low"])

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
        evidence_context=evidence,
    )

    assert result is not None
    assert result["confidence_reason"] != "LLM INJECTED: Very confident!"
    assert result["limitations"] != ["LLM INJECTED: None at all"]
    assert result["evidence_summary"] != "LLM INJECTED: Strong evidence"
    assert any(
        "dropped" in lim.lower() for lim in result["limitations"]
    ), f"Expected 'dropped' in limitations, got: {result['limitations']}"


# ---------------------------------------------------------------------------
# R2-D Closure: Orchestrator failure-mode gap tests
# ---------------------------------------------------------------------------


def test_synthesis_empty_answer_text_returns_none():
    """LLM returning answer_text="" yields None from synthesize_answer."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    class EmptyAnswerLLM:
        def chat(self, messages, *, max_tokens=2000):
            import json

            return json.dumps({"answer_text": "", "citations": [1], "confidence": "high"})

    orch = SmartSearchOrchestrator(llm_client=EmptyAnswerLLM())
    filtered = _trust_gate_filtered_results(3)
    result = orch.synthesize_answer(query="test", filtered_results=filtered, summary="")
    assert result is None


def test_synthesis_out_of_range_citations_dropped():
    """Numeric citations beyond filtered_results range are dropped."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(citations=[1, 99])
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)

    result = orch.synthesize_answer(query="test", filtered_results=filtered, summary="")
    assert result is not None
    assert len(result["citations"]) == 1
    assert result["citations"][0] == "Journals/2026/03/life-index_2026-03-01_001.md"


def test_trust_gate_empty_evidence_context_list():
    """evidence_context=[] (empty list, not None) caps confidence at low."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(citations=[1], confidence="high")
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
        evidence_context=[],
    )
    assert result is not None
    assert result["confidence"] == "low"


def test_transparency_dropped_citations_reported():
    """Transparency limitations include 'dropped' when citations are dropped."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    class HalfHallucinatingLLM:
        def chat(self, messages, *, max_tokens=2000):
            import json

            return json.dumps(
                {
                    "answer_text": "Some answer.",
                    "citations": [
                        "Journals/2026/03/life-index_2026-03-01_001.md",
                        "Journals/2026/03/FAKE_PATH.md",
                    ],
                    "confidence": "high",
                }
            )

    llm = HalfHallucinatingLLM()
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)
    evidence = _trust_gate_evidence_context(3, confidences=["high", "medium", "low"])

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
        evidence_context=evidence,
    )
    assert result is not None
    assert any("dropped" in lim.lower() for lim in result["limitations"])


def test_transparency_low_confidence_evidence_noted():
    """When cited evidence has low confidence, limitations note it."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm = TrustGateLLM(citations=[3], confidence="low")
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)
    evidence = _trust_gate_evidence_context(3, confidences=["high", "medium", "low"])

    result = orch.synthesize_answer(
        query="test",
        filtered_results=filtered,
        summary="",
        evidence_context=evidence,
    )
    assert result is not None
    assert result["confidence"] == "low"
    assert any("low" in lim.lower() for lim in result["limitations"])


def test_synthesis_json_code_block_wrapping():
    """LLM response wrapped in ```json...``` is parsed correctly."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    class CodeBlockLLM:
        def chat(self, messages, *, max_tokens=2000):
            return (
                "```json\n"
                '{"answer_text": "Found one entry.", "citations": [1], "confidence": "medium"}\n'
                "```"
            )

    llm = CodeBlockLLM()
    orch = SmartSearchOrchestrator(llm_client=llm)
    filtered = _trust_gate_filtered_results(3)

    result = orch.synthesize_answer(query="test", filtered_results=filtered, summary="")
    assert result is not None
    assert result["answer_text"] == "Found one entry."
    assert result["confidence"] == "medium"


def test_search_synthesize_empty_answer_text_no_answer_field():
    """Full search() with LLM returning empty answer_text omits answer."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    class EmptyTextLLM:
        def chat(self, messages, *, max_tokens=2000):
            import json

            # Rewrite stage
            if "query analyzer" in messages[0]["content"].lower():
                return json.dumps(
                    {
                        "core_terms": "test",
                        "expanded_terms": [],
                        "time_range": None,
                        "intent_type": "simple",
                        "rewritten_query": "test",
                    }
                )
            return json.dumps({"answer_text": "", "citations": [], "confidence": "low"})

    orch = SmartSearchOrchestrator(llm_client=EmptyTextLLM())
    mock_result = _mock_search_result(count=2)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kw: mock_result,
    ):
        result = orch.search("test", synthesize=True)
    assert "answer" not in result
    assert result["success"] is True


# ---------------------------------------------------------------------------
# R2-D Closure: Answer eval harness integration
# ---------------------------------------------------------------------------


def test_answer_eval_classifies_supported_from_orchestrator():
    """answer_eval classifies a valid orchestrator synthesis as SUPPORTED."""
    from tools.eval.answer_eval import AnswerVerdict, evaluate_answer_from_orchestrator_output

    output = {
        "success": True,
        "filtered_results": [
            {"rel_path": "Journals/2026/03/life-index_2026-03-01_001.md"},
        ],
        "answer": {
            "answer_text": "You had a family gathering.",
            "citations": ["Journals/2026/03/life-index_2026-03-01_001.md"],
            "confidence": "high",
            "confidence_reason": "Supported by high-confidence evidence.",
            "limitations": [],
            "evidence_summary": "Entry 1; source: fts; confidence: high",
        },
    }
    eval_result = evaluate_answer_from_orchestrator_output(output)
    assert eval_result is not None
    assert eval_result.verdict == AnswerVerdict.SUPPORTED
    assert eval_result.valid_citation_count == 1
    assert eval_result.transparency.verdict.value == "complete"


def test_answer_eval_classifies_invalid_citation_from_orchestrator():
    """answer_eval classifies hallucinated citation as INVALID_CITATION."""
    from tools.eval.answer_eval import AnswerVerdict, evaluate_answer_from_orchestrator_output

    output = {
        "success": True,
        "filtered_results": [
            {"rel_path": "Journals/2026/03/life-index_2026-03-01_001.md"},
        ],
        "answer": {
            "answer_text": "Some claim.",
            "citations": ["Journals/2026/03/FAKE_NONEXISTENT.md"],
            "confidence": "high",
        },
    }
    eval_result = evaluate_answer_from_orchestrator_output(output)
    assert eval_result is not None
    assert eval_result.verdict == AnswerVerdict.INVALID_CITATION
    assert eval_result.invalid_citation_count == 1


def test_answer_eval_classifies_no_citations_from_orchestrator():
    """answer_eval classifies answer without citations as NO_CITATIONS."""
    from tools.eval.answer_eval import AnswerVerdict, evaluate_answer_from_orchestrator_output

    output = {
        "success": True,
        "filtered_results": [],
        "answer": {
            "answer_text": "No relevant entries found.",
            "citations": [],
            "confidence": "low",
            "confidence_reason": "No evidence found.",
            "limitations": ["No validated citations support this answer."],
            "evidence_summary": "",
        },
    }
    eval_result = evaluate_answer_from_orchestrator_output(output)
    assert eval_result is not None
    assert eval_result.verdict == AnswerVerdict.NO_CITATIONS


def test_answer_eval_classifies_overclaiming_from_orchestrator():
    """answer_eval flags overclaiming answer from orchestrator output."""
    from tools.eval.answer_eval import AnswerVerdict, evaluate_answer_from_orchestrator_output

    output = {
        "success": True,
        "filtered_results": [
            {"rel_path": "Journals/2026/03/life-index_2026-03-01_001.md"},
        ],
        "answer": {
            "answer_text": "These are all entries from that month.",
            "citations": ["Journals/2026/03/life-index_2026-03-01_001.md"],
            "confidence": "high",
        },
    }
    eval_result = evaluate_answer_from_orchestrator_output(output)
    assert eval_result is not None
    assert eval_result.verdict == AnswerVerdict.OVERCLAIMING


def test_answer_eval_detects_missing_transparency():
    """answer_eval flags MISSING transparency when fields absent."""
    from tools.eval.answer_eval import (
        AnswerVerdict,
        TransparencyVerdict,
        evaluate_answer_from_orchestrator_output,
    )

    output = {
        "success": True,
        "filtered_results": [
            {"rel_path": "Journals/2026/03/life-index_2026-03-01_001.md"},
        ],
        "answer": {
            "answer_text": "Minimal answer.",
            "citations": ["Journals/2026/03/life-index_2026-03-01_001.md"],
            "confidence": "medium",
        },
    }
    eval_result = evaluate_answer_from_orchestrator_output(output)
    assert eval_result is not None
    assert eval_result.verdict == AnswerVerdict.SUPPORTED
    assert eval_result.transparency.verdict == TransparencyVerdict.MISSING


def test_answer_eval_skips_absolute_paths_in_known_paths():
    """Absolute paths from orchestrator are excluded from known_paths."""
    from tools.eval.answer_eval import evaluate_answer_from_orchestrator_output

    output = {
        "success": True,
        "filtered_results": [
            {"rel_path": "C:/Users/secret/test.md"},
        ],
        "answer": {
            "answer_text": "Leaked.",
            "citations": ["C:/Users/secret/test.md"],
            "confidence": "low",
        },
    }
    eval_result = evaluate_answer_from_orchestrator_output(output)
    assert eval_result is not None
    assert eval_result.invalid_citation_count == 1
    assert eval_result.citation_checks[0].reason == "absolute_path"


def test_answer_eval_no_answer_returns_none():
    """evaluate_answer_from_orchestrator_output returns None when no answer."""
    from tools.eval.answer_eval import evaluate_answer_from_orchestrator_output

    output = {"success": True, "filtered_results": []}
    assert evaluate_answer_from_orchestrator_output(output) is None


# ---------------------------------------------------------------------------
# S1D-B: Entity-hint context in rewrite prompt
# ---------------------------------------------------------------------------


class RewriteCapturingLLM:
    """LLM that captures the rewrite prompt for inspection."""

    def __init__(self):
        self.rewrite_prompt: str | None = None

    def chat(self, messages, *, max_tokens=2000):
        import json

        content = messages[0]["content"] if messages else ""
        if "query analyzer" in content.lower():
            self.rewrite_prompt = content
            return json.dumps(
                {
                    "core_terms": "test",
                    "expanded_terms": [],
                    "time_range": None,
                    "intent_type": "simple",
                    "rewritten_query": "test",
                }
            )
        return json.dumps(
            {
                "filtered_indices": [1],
                "summary": "test",
                "citations": [],
            }
        )


def test_rewrite_prompt_includes_entity_context_with_hints():
    """When entity hints match, _build_rewrite_prompt includes entity graph context."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=RewriteCapturingLLM())
    hints = [
        {
            "entity_id": "lele",
            "entity_type": "person",
            "matched_term": "乐乐",
            "expansion_terms": ["乐乐", "小乐乐"],
        }
    ]
    prompt = orch._build_rewrite_prompt("乐乐的生日", entity_hints=hints)
    assert "Local entity graph matches" in prompt
    assert "lele" in prompt
    assert "person" in prompt
    assert "乐乐" in prompt
    assert "小乐乐" in prompt


def test_rewrite_prompt_no_entity_context_without_hints():
    """When no entity hints, _build_rewrite_prompt has no entity graph context."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=RewriteCapturingLLM())
    prompt = orch._build_rewrite_prompt("some random query", entity_hints=None)
    assert "Local entity graph matches" not in prompt
    assert "entity graph" not in prompt.lower()


def test_rewrite_prompt_empty_hints_list_no_entity_context():
    """When entity_hints=[], prompt has no entity graph context."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=RewriteCapturingLLM())
    prompt = orch._build_rewrite_prompt("some random query", entity_hints=[])
    assert "Local entity graph matches" not in prompt


def test_rewrite_query_resolves_entity_hints_via_core():
    """rewrite_query calls resolve_query_entities and passes hints to prompt."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = RewriteCapturingLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    mock_hints = [
        {
            "entity_id": "lele",
            "entity_type": "person",
            "matched_term": "乐乐",
            "expansion_terms": ["乐乐"],
        }
    ]
    with patch(
        "tools.search_journals.core.resolve_query_entities",
        return_value=mock_hints,
    ):
        orch.rewrite_query("乐乐")

    assert fake_llm.rewrite_prompt is not None
    assert "lele" in fake_llm.rewrite_prompt
    assert "Local entity graph matches" in fake_llm.rewrite_prompt


def test_rewrite_query_degradation_no_entity_call():
    """Degradation mode (no LLM) returns raw query without entity resolution."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=None)
    result = orch.rewrite_query("乐乐")
    assert result["rewritten_query"] == "乐乐"
    assert result["intent_type"] == "simple"


def test_resolve_entity_hints_returns_bounded_fields():
    """_resolve_entity_hints returns only safe, bounded fields."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator()
    mock_hints = [
        {
            "entity_id": "beijing",
            "entity_type": "place",
            "matched_term": "北京",
            "expansion_terms": ["北京", "Beijing", "京城"],
            "reason": "primary_name_match",
        }
    ]
    with patch(
        "tools.search_journals.core.resolve_query_entities",
        return_value=mock_hints,
    ):
        result = orch._resolve_entity_hints("北京")
    assert len(result) == 1
    h = result[0]
    assert "entity_id" in h
    assert "entity_type" in h
    assert "matched_term" in h
    assert "expansion_terms" in h
    assert "reason" not in h


def test_resolve_entity_hints_exception_returns_empty():
    """_resolve_entity_hints returns [] on exception (e.g. no entity graph)."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator()
    with patch(
        "tools.search_journals.core.resolve_query_entities",
        side_effect=Exception("no graph"),
    ):
        result = orch._resolve_entity_hints("anything")
    assert result == []


def test_multiple_entity_hints_in_prompt():
    """Multiple entity hints produce multi-line context block."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=RewriteCapturingLLM())
    hints = [
        {
            "entity_id": "lele",
            "entity_type": "person",
            "matched_term": "乐乐",
            "expansion_terms": ["乐乐"],
        },
        {
            "entity_id": "beijing",
            "entity_type": "place",
            "matched_term": "北京",
            "expansion_terms": ["北京", "Beijing"],
        },
    ]
    prompt = orch._build_rewrite_prompt("乐乐在北京", entity_hints=hints)
    assert prompt.count("matched") == 2
    assert "lele" in prompt
    assert "beijing" in prompt


def test_entity_hint_count_capped_at_five():
    """More than 5 entity hints are truncated to 5 in _resolve_entity_hints."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    many_hints = [
        {
            "entity_id": f"e{i}",
            "entity_type": "person",
            "matched_term": f"term{i}",
            "expansion_terms": [f"term{i}"],
        }
        for i in range(10)
    ]
    orch = SmartSearchOrchestrator()
    with patch(
        "tools.search_journals.core.resolve_query_entities",
        return_value=many_hints,
    ):
        result = orch._resolve_entity_hints("big query")
    assert len(result) == 5
    assert result[0]["entity_id"] == "e0"
    assert result[4]["entity_id"] == "e4"


def test_expansion_terms_capped_at_three_per_hint():
    """More than 3 expansion terms per hint are truncated in _resolve_entity_hints."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    hints = [
        {
            "entity_id": "lele",
            "entity_type": "person",
            "matched_term": "乐乐",
            "expansion_terms": ["乐乐", "小乐乐", "乐宝", "乐儿", "小乐"],
        }
    ]
    orch = SmartSearchOrchestrator()
    with patch(
        "tools.search_journals.core.resolve_query_entities",
        return_value=hints,
    ):
        result = orch._resolve_entity_hints("乐乐")
    assert len(result) == 1
    assert len(result[0]["expansion_terms"]) == 3
    assert result[0]["expansion_terms"] == ["乐乐", "小乐乐", "乐宝"]


def test_expansion_term_length_capped():
    """Expansion terms longer than 20 chars are truncated in _resolve_entity_hints."""
    from unittest.mock import patch
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    long_term = "A" * 30
    hints = [
        {
            "entity_id": "test",
            "entity_type": "person",
            "matched_term": "test",
            "expansion_terms": [long_term, "short"],
        }
    ]
    orch = SmartSearchOrchestrator()
    with patch(
        "tools.search_journals.core.resolve_query_entities",
        return_value=hints,
    ):
        result = orch._resolve_entity_hints("test")
    assert len(result[0]["expansion_terms"][0]) == 20
    assert result[0]["expansion_terms"][1] == "short"


def test_rewrite_prompt_capped_entity_hints():
    """_build_rewrite_prompt only includes up to 5 entity hints in the prompt."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    orch = SmartSearchOrchestrator(llm_client=RewriteCapturingLLM())
    hints = [
        {
            "entity_id": f"e{i}",
            "entity_type": "person",
            "matched_term": f"term{i}",
            "expansion_terms": [f"exp{i}"],
        }
        for i in range(8)
    ]
    prompt = orch._build_rewrite_prompt("big query", entity_hints=hints)
    assert prompt.count("matched") == 5
    assert "e0" in prompt
    assert "e4" in prompt
    assert "e5" not in prompt


# ---------------------------------------------------------------------------
# S1I: Entity-aware synthesis context tests
# ---------------------------------------------------------------------------


def _mock_evidence_pack_with_entity_matches(
    entity_matches_per_item: list[list[dict]] | None = None,
):
    """Build a mock EvidencePack with entity_matches for synthesis tests."""
    from tools.evidence.types import (
        DocumentRef,
        EntityMatch,
        EvidenceDiagnostics,
        EvidenceItem,
        EvidencePack,
        QueryContext,
        ScoreBreakdown,
    )

    items = []
    n = len(entity_matches_per_item) if entity_matches_per_item else 2
    for i in range(1, n + 1):
        em_list = []
        if entity_matches_per_item and i <= len(entity_matches_per_item):
            for em_data in entity_matches_per_item[i - 1]:
                em_list.append(
                    EntityMatch(
                        entity_id=em_data.get("entity_id", f"entity-{i}"),
                        entity_type=em_data.get("entity_type", "person"),
                        matched_terms=em_data.get("matched_terms", [f"term-{i}"]),
                        match_sources=em_data.get("match_sources", ["fts"]),
                        query_matched_term=em_data.get("query_matched_term"),
                    )
                )
        items.append(
            EvidenceItem(
                document=DocumentRef(
                    doc_id=f"doc-{i}",
                    title=f"Entry {i}",
                    date=f"2026-03-{i:02d}",
                    path=f"Journals/2026/03/life-index_2026-03-{i:02d}_001.md",
                ),
                scores=ScoreBreakdown(
                    source="fts",
                    rank=i,
                    final_score=0.9 - i * 0.1,
                    confidence="high" if i == 1 else "medium",
                ),
                snippet=f"Snippet {i}",
                abstract=f"Abstract {i}",
                provenance="keyword",
                entity_matches=em_list,
            )
        )

    return EvidencePack(
        query_context=QueryContext(query="test"),
        items=items,
        semantic_candidates=[],
        total_available=n,
        has_more=False,
        no_confident_match=False,
        diagnostics=EvidenceDiagnostics(retrieval_outcome="ok"),
    )


def test_synthesis_prompt_includes_entity_matches_when_present():
    """Synthesis prompt includes bounded entity match context when evidence
    items have entity_matches."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    pack = _mock_evidence_pack_with_entity_matches(
        entity_matches_per_item=[
            [
                {
                    "entity_id": "lele",
                    "entity_type": "person",
                    "matched_terms": ["乐乐", "小乐乐"],
                    "match_sources": ["fts"],
                }
            ],
            [
                {
                    "entity_id": "beijing",
                    "entity_type": "place",
                    "matched_terms": ["北京", "Beijing"],
                    "match_sources": ["fts"],
                },
                {
                    "entity_id": "lele",
                    "entity_type": "person",
                    "matched_terms": ["乐乐"],
                    "match_sources": ["fts"],
                },
            ],
        ]
    )
    evidence_context = SmartSearchOrchestrator._evidence_to_synthesis_context(pack)
    prompt = orch._build_synthesis_prompt(
        "test query",
        [
            {"title": "Entry 1", "date": "2026-03-01", "abstract": "Abstract 1"},
            {"title": "Entry 2", "date": "2026-03-02", "abstract": "Abstract 2"},
        ],
        "",
        evidence_context,
    )
    assert "entities:" in prompt, "Entity match context missing from synthesis prompt"
    assert "lele(person)" in prompt
    assert "beijing(place)" in prompt
    assert "乐乐" in prompt
    assert "北京" in prompt


def test_synthesis_prompt_no_entity_matches_no_leak():
    """Synthesis prompt does not leak full_content, raw metadata, absolute
    paths, or entity fields outside the bounded whitelist."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    fake_llm = FakeSynthesisLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    pack = _mock_evidence_pack_with_entity_matches(
        entity_matches_per_item=[
            [
                {
                    "entity_id": "lele",
                    "entity_type": "person",
                    "matched_terms": ["乐乐", "小乐乐"],
                    "match_sources": ["fts", "metadata"],
                    "query_matched_term": "乐乐",
                },
            ],
        ]
    )
    evidence_context = SmartSearchOrchestrator._evidence_to_synthesis_context(pack)
    prompt = orch._build_synthesis_prompt(
        "test query",
        [
            {
                "title": "Entry 1",
                "date": "2026-03-01",
                "abstract": "Abstract 1",
                "full_content": "This is the full private content that must not leak.",
                "metadata": {"people": ["Alice"], "secret_field": "secret_value"},
            },
        ],
        "",
        evidence_context,
    )
    assert "full_content" not in prompt
    assert "C:/" not in prompt
    assert "secret_value" not in prompt
    assert "Alice" not in prompt
    assert "match_sources" not in prompt
    assert "query_matched_term" not in prompt
    assert "lele(person)" in prompt


def test_evidence_to_synthesis_context_bounded_entity_matches():
    """_evidence_to_synthesis_context includes bounded entity_matches with
    only whitelisted fields (entity_id, entity_type, matched_terms)."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    pack = _mock_evidence_pack_with_entity_matches(
        entity_matches_per_item=[
            [
                {
                    "entity_id": "lele",
                    "entity_type": "person",
                    "matched_terms": ["乐乐", "小乐乐"],
                    "match_sources": ["fts"],
                    "query_matched_term": "乐乐",
                },
            ],
        ]
    )
    ctx = SmartSearchOrchestrator._evidence_to_synthesis_context(pack)
    assert len(ctx) == 1
    item = ctx[0]
    assert "entity_matches" in item
    em = item["entity_matches"][0]
    assert em["entity_id"] == "lele"
    assert em["entity_type"] == "person"
    assert em["matched_terms"] == ["乐乐", "小乐乐"]
    assert "match_sources" not in em
    assert "query_matched_term" not in em


def test_evidence_to_synthesis_context_no_entity_matches():
    """_evidence_to_synthesis_context omits entity_matches key when none present."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    pack = _mock_evidence_pack_with_entity_matches(entity_matches_per_item=[[], []])
    ctx = SmartSearchOrchestrator._evidence_to_synthesis_context(pack)
    assert len(ctx) == 2
    for item in ctx:
        assert "entity_matches" not in item


def test_entity_matches_capped_at_three_per_item():
    """More than 3 entity_matches per item are truncated."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    many_em = [
        {"entity_id": f"e{i}", "entity_type": "person", "matched_terms": [f"t{i}"]}
        for i in range(6)
    ]
    pack = _mock_evidence_pack_with_entity_matches(entity_matches_per_item=[many_em])
    ctx = SmartSearchOrchestrator._evidence_to_synthesis_context(pack)
    assert len(ctx[0]["entity_matches"]) == 3


def test_matched_terms_capped_at_three_per_entity():
    """More than 3 matched_terms per entity match are truncated."""
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    pack = _mock_evidence_pack_with_entity_matches(
        entity_matches_per_item=[
            [
                {
                    "entity_id": "lele",
                    "entity_type": "person",
                    "matched_terms": ["a", "b", "c", "d", "e"],
                }
            ]
        ]
    )
    ctx = SmartSearchOrchestrator._evidence_to_synthesis_context(pack)
    assert len(ctx[0]["entity_matches"][0]["matched_terms"]) == 3


def test_string_length_caps_on_entity_synthesis_fields():
    """Overly long entity_id, entity_type, and matched_term strings are
    truncated by the respective length caps."""
    from tools.search_journals.orchestrator import (
        _MAX_ENTITY_ID_LENGTH,
        _MAX_ENTITY_TYPE_LENGTH,
        _MAX_MATCHED_TERM_LENGTH,
        SmartSearchOrchestrator,
    )

    long_id = "x" * (_MAX_ENTITY_ID_LENGTH + 40)
    long_type = "y" * (_MAX_ENTITY_TYPE_LENGTH + 40)
    long_term = "z" * (_MAX_MATCHED_TERM_LENGTH + 40)

    pack = _mock_evidence_pack_with_entity_matches(
        entity_matches_per_item=[
            [
                {
                    "entity_id": long_id,
                    "entity_type": long_type,
                    "matched_terms": [long_term],
                }
            ]
        ]
    )
    ctx = SmartSearchOrchestrator._evidence_to_synthesis_context(pack)
    em = ctx[0]["entity_matches"][0]
    assert len(em["entity_id"]) == _MAX_ENTITY_ID_LENGTH
    assert em["entity_id"] == long_id[:_MAX_ENTITY_ID_LENGTH]
    assert len(em["entity_type"]) == _MAX_ENTITY_TYPE_LENGTH
    assert em["entity_type"] == long_type[:_MAX_ENTITY_TYPE_LENGTH]
    assert len(em["matched_terms"][0]) == _MAX_MATCHED_TERM_LENGTH
    assert em["matched_terms"][0] == long_term[:_MAX_MATCHED_TERM_LENGTH]


def test_string_length_caps_propagate_to_synthesis_prompt():
    """Truncated strings appear in the synthesis prompt, not the full originals."""
    from tools.search_journals.orchestrator import (
        _MAX_ENTITY_ID_LENGTH,
        _MAX_ENTITY_TYPE_LENGTH,
        _MAX_MATCHED_TERM_LENGTH,
        SmartSearchOrchestrator,
    )

    long_id = "a" * (_MAX_ENTITY_ID_LENGTH + 20)
    long_type = "b" * (_MAX_ENTITY_TYPE_LENGTH + 20)
    long_term = "c" * (_MAX_MATCHED_TERM_LENGTH + 20)

    fake_llm = FakeSynthesisLLM()
    orch = SmartSearchOrchestrator(llm_client=fake_llm)
    pack = _mock_evidence_pack_with_entity_matches(
        entity_matches_per_item=[
            [
                {
                    "entity_id": long_id,
                    "entity_type": long_type,
                    "matched_terms": [long_term],
                }
            ]
        ]
    )
    evidence_context = SmartSearchOrchestrator._evidence_to_synthesis_context(pack)
    prompt = orch._build_synthesis_prompt(
        "test query",
        [{"title": "Entry 1", "date": "2026-03-01", "abstract": "Abstract 1"}],
        "",
        evidence_context,
    )
    capped_id = long_id[:_MAX_ENTITY_ID_LENGTH]
    capped_type = long_type[:_MAX_ENTITY_TYPE_LENGTH]
    capped_term = long_term[:_MAX_MATCHED_TERM_LENGTH]
    assert capped_id in prompt
    assert capped_type in prompt
    assert capped_term in prompt
    assert long_id not in prompt
    assert long_type not in prompt
    assert long_term not in prompt
