#!/usr/bin/env python3
"""Contract tests: smart-search response shape.

Verifies that SmartSearchOrchestrator output conforms to the contract
documented in docs/API.md:
1. Default output contains public stable fields
2. --include-evidence adds evidence_pack
3. --synthesize adds answer
4. Combined flags produce both additive sections
5. --explain swaps agent_decisions_summary for agent_decisions
6. answer fields follow trust-gate semantics
7. Performance sub-fields are conditionally present
8. evidence_pack.diagnostics present and well-formed when --include-evidence
"""

import json
from unittest.mock import MagicMock, patch

from tools.search_journals.orchestrator import SmartSearchOrchestrator


def _make_mock_llm():
    """Create mock LLM client that returns valid JSON responses."""

    class MockLLM:
        def chat(self, messages, *, max_tokens=2000):
            text = messages[0]["content"]
            if "search query analyzer" in text:
                return json.dumps(
                    {
                        "core_terms": "test",
                        "expanded_terms": [],
                        "time_range": None,
                        "intent_type": "simple",
                        "rewritten_query": "test",
                    }
                )
            elif "search result curator" in text:
                return json.dumps(
                    {
                        "filtered_indices": [1],
                        "summary": "Test summary.",
                        "citations": ["Test Title"],
                    }
                )
            elif "personal journal assistant" in text:
                return json.dumps(
                    {
                        "answer_text": "Test answer.",
                        "citations": [1],
                        "confidence": "medium",
                    }
                )
            return "{}"

    return MockLLM()


def _mock_hierarchical_search(query="", **kwargs):
    """Mock deterministic search returning minimal valid output."""
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


# Default output shape


class TestDefaultOutputShape:
    """Verify default (no flags) output contains exactly the public stable fields."""

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_default_has_required_fields(self, _mock):
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query")

        # Public stable fields
        assert "success" in result
        assert "query" in result
        assert "rewritten_query" in result
        assert "filtered_results" in result
        assert "summary" in result
        assert "citations" in result
        assert "agent_unavailable" in result
        assert "performance" in result

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_default_no_evidence_pack(self, _mock):
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query")
        assert "evidence_pack" not in result

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_default_no_answer(self, _mock):
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query")
        assert "answer" not in result

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_default_has_agent_decisions_list(self, _mock):
        """Default orchestrator output includes agent_decisions list."""
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query")
        assert "agent_decisions" in result
        assert isinstance(result["agent_decisions"], list)

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_default_no_agent_decisions_summary(self, _mock):
        """Orchestrator does NOT produce agent_decisions_summary; CLI layer does."""
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query")
        assert "agent_decisions_summary" not in result

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_degradation_mode_agent_unavailable(self, _mock):
        orch = SmartSearchOrchestrator(llm_client=None)
        result = orch.search("test query")
        assert result["agent_unavailable"] is True

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_llm_mode_agent_available(self, _mock):
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query")
        assert result["agent_unavailable"] is False

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_no_stale_fields(self, _mock):
        """Fields documented as not existing must not appear."""
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query")
        assert "results" not in result
        assert "total_found" not in result
        assert "mode" not in result


# Performance sub-fields


class TestPerformanceFields:
    """Verify performance sub-fields are conditionally present."""

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_always_present_fields(self, _mock):
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query")
        perf = result["performance"]
        assert "total_time_ms" in perf
        assert "search_time_ms" in perf
        assert "total_available" in perf

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_synthesize_adds_synthesis_ms(self, _mock):
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query", synthesize=True)
        perf = result["performance"]
        assert "synthesis_ms" in perf


# --include-evidence output shape


class TestIncludeEvidenceShape:
    """Verify --include-evidence adds evidence_pack."""

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    @patch("tools.evidence.adapter.extract_evidence_from_orchestrator")
    def test_evidence_pack_present(self, mock_ev, _mock):
        from tools.evidence.types import (
            DocumentRef,
            EvidenceItem,
            EvidencePack,
            QueryContext,
            ScoreBreakdown,
        )

        pack = EvidencePack(
            query_context=QueryContext(query="test"),
            items=[
                EvidenceItem(
                    document=DocumentRef(
                        doc_id="1",
                        title="Test",
                        path="Journals/2026/03/test.md",
                        date="2026-03-06",
                    ),
                    scores=ScoreBreakdown(source="fts", rank=1),
                    snippet="test snippet",
                )
            ],
            semantic_candidates=[],
            total_available=1,
            has_more=False,
            no_confident_match=False,
        )
        mock_ev.return_value = pack

        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query", include_evidence=True)

        assert "evidence_pack" in result
        assert "items" in result["evidence_pack"]
        assert "performance" in result
        assert "evidence_build_ms" in result["performance"]

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    @patch(
        "tools.evidence.adapter.extract_evidence_from_orchestrator",
        side_effect=Exception("build failed"),
    )
    def test_evidence_failure_still_succeeds(self, mock_ev, _mock):
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query", include_evidence=True)

        assert result["success"] is True
        assert "evidence_pack" not in result
        assert "evidence_build_ms" in result["performance"]
        assert "evidence_error" in result["performance"]


# --synthesize output shape


class TestSynthesizeShape:
    """Verify --synthesize adds answer with trust-gate fields."""

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_answer_present(self, _mock):
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query", synthesize=True)

        assert "answer" in result
        answer = result["answer"]
        assert "answer_text" in answer
        assert "citations" in answer
        assert "confidence" in answer
        assert "confidence_reason" in answer
        assert "limitations" in answer
        assert "evidence_summary" in answer

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_answer_no_llm(self, _mock):
        orch = SmartSearchOrchestrator(llm_client=None)
        result = orch.search("test query", synthesize=True)
        assert "answer" not in result

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_confidence_values(self, _mock):
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query", synthesize=True)
        assert result["answer"]["confidence"] in ("high", "medium", "low")


# Combined flags


class TestCombinedFlags:
    """Verify --include-evidence --synthesize produces both sections."""

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    @patch("tools.evidence.adapter.extract_evidence_from_orchestrator")
    def test_combined_has_both(self, mock_ev, _mock):
        from tools.evidence.types import (
            DocumentRef,
            EvidenceItem,
            EvidencePack,
            QueryContext,
            ScoreBreakdown,
        )

        pack = EvidencePack(
            query_context=QueryContext(query="test"),
            items=[
                EvidenceItem(
                    document=DocumentRef(
                        doc_id="1",
                        title="Test",
                        path="Journals/2026/03/test.md",
                        date="2026-03-06",
                    ),
                    scores=ScoreBreakdown(source="fts", rank=1, confidence="medium"),
                    snippet="test snippet",
                )
            ],
            semantic_candidates=[],
            total_available=1,
            has_more=False,
            no_confident_match=False,
        )
        mock_ev.return_value = pack

        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query", include_evidence=True, synthesize=True)

        assert "evidence_pack" in result
        assert "answer" in result
        assert "synthesis_ms" in result["performance"]
        assert "evidence_build_ms" in result["performance"]


# CLI --explain shape


class TestExplainFlag:
    """Verify --explain output shape at CLI level."""

    def test_explain_keeps_agent_decisions(self):
        """With --explain, agent_decisions list is kept (not replaced by summary)."""
        from io import StringIO

        mock_result = {
            "success": True,
            "query": "test",
            "rewritten_query": "test",
            "filtered_results": [],
            "summary": "",
            "citations": [],
            "agent_decisions": [
                {"stage": "rewrite", "input_summary": "q", "output_summary": "r", "latency_ms": 10}
            ],
            "agent_unavailable": True,
            "performance": {"total_time_ms": 10},
        }

        captured = StringIO()
        with patch("sys.argv", ["smart-search", "--query", "test", "--explain"]):
            with patch("tools.search_journals.orchestrator.SmartSearchOrchestrator") as MockCls:
                mock_orch = MagicMock()
                mock_orch.search.return_value = mock_result.copy()
                MockCls.return_value = mock_orch
                with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
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
        assert "agent_decisions" in result
        assert isinstance(result["agent_decisions"], list)
        assert "agent_decisions_summary" not in result

    def test_no_explain_replaces_with_summary(self):
        """Without --explain, agent_decisions is replaced by agent_decisions_summary."""
        from io import StringIO

        mock_result = {
            "success": True,
            "query": "test",
            "rewritten_query": "test",
            "filtered_results": [],
            "summary": "",
            "citations": [],
            "agent_decisions": [
                {"stage": "rewrite", "input_summary": "q", "output_summary": "r", "latency_ms": 10}
            ],
            "agent_unavailable": True,
            "performance": {"total_time_ms": 10},
        }

        captured = StringIO()
        with patch("sys.argv", ["smart-search", "--query", "test"]):
            with patch("tools.search_journals.orchestrator.SmartSearchOrchestrator") as MockCls:
                mock_orch = MagicMock()
                mock_orch.search.return_value = mock_result.copy()
                MockCls.return_value = mock_orch
                with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
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
        assert "agent_decisions" not in result
        assert "agent_decisions_summary" in result
        assert isinstance(result["agent_decisions_summary"], str)


# Evidence Pack Diagnostics


class TestEvidencePackDiagnostics:
    """Verify evidence_pack.diagnostics contract when --include-evidence."""

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    @patch("tools.evidence.adapter.extract_evidence_from_orchestrator")
    def test_diagnostics_ok_outcome_omits_empty_notes(self, mock_ev, _mock):
        """``ok`` outcome produces empty notes/suggestions — serializer omits them."""
        from tools.evidence.types import (
            DocumentRef,
            EvidenceDiagnostics,
            EvidenceItem,
            EvidencePack,
            QueryContext,
            ScoreBreakdown,
        )

        pack = EvidencePack(
            query_context=QueryContext(query="test"),
            items=[
                EvidenceItem(
                    document=DocumentRef(
                        doc_id="1",
                        title="Test",
                        path="Journals/2026/03/test.md",
                        date="2026-03-06",
                    ),
                    scores=ScoreBreakdown(source="fts", rank=1, confidence="medium"),
                    snippet="test snippet",
                )
            ],
            semantic_candidates=[],
            total_available=1,
            has_more=False,
            no_confident_match=False,
            diagnostics=EvidenceDiagnostics(
                retrieval_outcome="ok",
                outcome_reason="confident_results_present",
            ),
        )
        mock_ev.return_value = pack

        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query", include_evidence=True)

        assert "evidence_pack" in result
        diag = result["evidence_pack"]["diagnostics"]
        assert "retrieval_outcome" in diag
        assert diag["retrieval_outcome"] == "ok"
        assert "outcome_reason" in diag
        assert "notes" not in diag
        assert "suggestions" not in diag

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    @patch("tools.evidence.adapter.extract_evidence_from_orchestrator")
    def test_diagnostics_has_required_fields(self, mock_ev, _mock):
        """When notes/suggestions are non-empty, serializer includes them."""
        from tools.evidence.types import (
            DocumentRef,
            EvidenceDiagnostics,
            EvidenceItem,
            EvidencePack,
            QueryContext,
            ScoreBreakdown,
        )

        pack = EvidencePack(
            query_context=QueryContext(query="test"),
            items=[
                EvidenceItem(
                    document=DocumentRef(
                        doc_id="1",
                        title="Test",
                        path="Journals/2026/03/test.md",
                        date="2026-03-06",
                    ),
                    scores=ScoreBreakdown(source="fts", rank=1, confidence="high"),
                    snippet="test snippet",
                )
            ],
            semantic_candidates=[],
            total_available=1,
            has_more=False,
            no_confident_match=False,
            diagnostics=EvidenceDiagnostics(
                retrieval_outcome="ok",
                outcome_reason="confident_results_present",
                notes=["High-confidence result found."],
                suggestions=["Results look good."],
            ),
        )
        mock_ev.return_value = pack

        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query", include_evidence=True)

        diag = result["evidence_pack"]["diagnostics"]
        assert "retrieval_outcome" in diag
        assert diag["retrieval_outcome"] in (
            "ok",
            "weak_results",
            "no_confident_match",
            "zero_results",
        )
        assert "outcome_reason" in diag
        assert "notes" in diag
        assert isinstance(diag["notes"], list)
        assert "suggestions" in diag
        assert isinstance(diag["suggestions"], list)

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    def test_no_diagnostics_without_evidence(self, _mock):
        """Without --include-evidence, no evidence_pack and no diagnostics."""
        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query")
        assert "evidence_pack" not in result

    @patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=_mock_hierarchical_search,
    )
    @patch("tools.evidence.adapter.extract_evidence_from_orchestrator")
    def test_diagnostics_includes_pipeline_composition(self, mock_ev, _mock):
        """Evidence pack diagnostics includes additive pipeline_composition field.

        Asserts the additive contract: pipeline_composition is present alongside
        all other standard diagnostic fields without replacing or omitting them.
        """
        from tools.evidence.types import (
            DocumentRef,
            EvidenceDiagnostics,
            EvidenceItem,
            EvidencePack,
            PipelineComposition,
            QueryContext,
            ScoreBreakdown,
        )

        pack = EvidencePack(
            query_context=QueryContext(query="test"),
            items=[
                EvidenceItem(
                    document=DocumentRef(
                        doc_id="1",
                        title="Test",
                        path="Journals/2026/03/test.md",
                        date="2026-03-06",
                    ),
                    scores=ScoreBreakdown(source="fts", rank=1, confidence="high"),
                    snippet="test snippet",
                )
            ],
            semantic_candidates=[],
            total_available=1,
            has_more=False,
            no_confident_match=False,
            diagnostics=EvidenceDiagnostics(
                retrieval_outcome="ok",
                outcome_reason="confident_results_present",
                pipeline_composition=PipelineComposition(primary_pipeline="fts"),
            ),
        )
        mock_ev.return_value = pack

        orch = SmartSearchOrchestrator(llm_client=_make_mock_llm())
        result = orch.search("test query", include_evidence=True)

        assert "evidence_pack" in result
        diag = result["evidence_pack"]["diagnostics"]

        # Additive contract: pipeline_composition is present
        assert "pipeline_composition" in diag
        assert diag["pipeline_composition"]["primary_pipeline"] in (
            "none",
            "fts",
            "semantic",
            "hybrid",
        )

        # Additive contract: all other standard fields remain intact
        assert "retrieval_outcome" in diag
        assert diag["retrieval_outcome"] == "ok"
        assert "outcome_reason" in diag
        assert diag["outcome_reason"] == "confident_results_present"
        # notes/suggestions are empty for ok outcome → serializer omits them
        assert "notes" not in diag
        assert "suggestions" not in diag
