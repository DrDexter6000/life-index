#!/usr/bin/env python3
"""Unit tests for deterministic evidence consumer formatter."""

from __future__ import annotations

from tools.evidence.consumer_formatter import format_entity_annotated
from tools.evidence.types import (
    DocumentRef,
    EntityMatch,
    EvidenceDiagnostics,
    EvidenceItem,
    EvidencePack,
    PipelineComposition,
    QueryContext,
    ScoreBreakdown,
    SemanticCandidate,
)


class TestFormatEmptyPack:
    """Formatter handles zero-result packs gracefully."""

    def test_format_empty_pack(self) -> None:
        pack = EvidencePack(
            query_context=QueryContext(query="test"),
            items=[],
            semantic_candidates=[],
            total_available=0,
            has_more=False,
            no_confident_match=False,
        )
        text = format_entity_annotated(pack)
        assert "## Retrieval Quality" in text
        assert "Diagnostics unavailable" in text
        assert "## Evidence Results (0 items)" in text
        assert "No matching documents found" in text


class TestFormatWithEntityMatches:
    """Entity match badges render correctly."""

    def test_format_with_entity_matches(self) -> None:
        pack = EvidencePack(
            query_context=QueryContext(query="乐乐妈"),
            items=[
                EvidenceItem(
                    document=DocumentRef(
                        doc_id="Journals/2026/03/01.md",
                        title="Family Day",
                        date="2026-03-01",
                        path="Journals/2026/03/01.md",
                    ),
                    scores=ScoreBreakdown(source="fts", rank=1, confidence="high"),
                    snippet="Went to park with 乐乐妈.",
                    entity_matches=[
                        EntityMatch(
                            entity_id="wife-001",
                            entity_type="person",
                            matched_terms=["乐乐妈"],
                            match_sources=["snippet", "metadata"],
                            query_matched_term="老婆",
                        )
                    ],
                )
            ],
            semantic_candidates=[],
            total_available=1,
            has_more=False,
            no_confident_match=False,
        )
        text = format_entity_annotated(pack)
        assert "Family Day" in text
        assert "wife-001" in text
        assert "person" in text
        assert "乐乐妈" in text
        assert "snippet, metadata" in text
        assert "query: 老婆" in text

    def test_format_multiple_entity_matches(self) -> None:
        pack = EvidencePack(
            query_context=QueryContext(query="multi"),
            items=[
                EvidenceItem(
                    document=DocumentRef(doc_id="d1", title="Multi Match", date="2026-03-02"),
                    scores=ScoreBreakdown(source="hybrid", rank=1, confidence="medium"),
                    snippet="Snippet",
                    entity_matches=[
                        EntityMatch(
                            entity_id="e1",
                            entity_type="person",
                            matched_terms=["a"],
                            match_sources=["snippet"],
                        ),
                        EntityMatch(
                            entity_id="e2",
                            entity_type="project",
                            matched_terms=["b", "c"],
                            match_sources=["title", "metadata"],
                            query_matched_term="proj",
                        ),
                    ],
                )
            ],
            semantic_candidates=[],
            total_available=1,
            has_more=False,
            no_confident_match=False,
        )
        text = format_entity_annotated(pack)
        assert "e1" in text
        assert "e2" in text
        assert "project" in text
        assert "matched: b, c" in text
        assert "query: proj" in text


class TestFormatWithoutEntityMatches:
    """Items without entity_matches render without entity section."""

    def test_format_without_entity_matches(self) -> None:
        pack = EvidencePack(
            query_context=QueryContext(query="plain"),
            items=[
                EvidenceItem(
                    document=DocumentRef(doc_id="d1", title="Plain Entry", date="2026-03-03"),
                    scores=ScoreBreakdown(source="fts", rank=1, confidence="high"),
                    snippet="Just a plain entry.",
                )
            ],
            semantic_candidates=[],
            total_available=1,
            has_more=False,
            no_confident_match=False,
        )
        text = format_entity_annotated(pack)
        assert "Plain Entry" in text
        assert "Entities:" not in text


class TestFormatDiagnostics:
    """Diagnostics banner renders correctly for each outcome."""

    def test_format_diagnostics_ok(self) -> None:
        diag = EvidenceDiagnostics(
            retrieval_outcome="ok",
            outcome_reason="confident_results_present",
            pipeline_composition=PipelineComposition(primary_pipeline="hybrid"),
        )
        pack = _make_pack_with_diagnostics(diag)
        text = format_entity_annotated(pack)
        assert "Confident results" in text
        assert "confident_results_present" in text
        assert "**Pipeline:** hybrid" in text
        assert "Notes:" not in text
        assert "Suggestions:" not in text

    def test_format_diagnostics_weak_results(self) -> None:
        diag = EvidenceDiagnostics(
            retrieval_outcome="weak_results",
            outcome_reason="low_confidence_only",
            notes=["Few results", "Low scores"],
            suggestions=["Try broader terms", "Check synonyms"],
            pipeline_composition=PipelineComposition(primary_pipeline="fts"),
        )
        pack = _make_pack_with_diagnostics(diag)
        text = format_entity_annotated(pack)
        assert "Weak results" in text
        assert "Few results" in text
        assert "Try broader terms" in text
        assert "**Pipeline:** fts" in text

    def test_format_diagnostics_zero_results(self) -> None:
        diag = EvidenceDiagnostics(
            retrieval_outcome="zero_results",
            outcome_reason="no_matches",
            suggestions=["Rephrase query", "Remove filters"],
        )
        pack = _make_pack_with_diagnostics(diag)
        text = format_entity_annotated(pack)
        assert "No results" in text
        assert "Rephrase query" in text

    def test_format_diagnostics_no_confident_match(self) -> None:
        diag = EvidenceDiagnostics(
            retrieval_outcome="no_confident_match",
            outcome_reason="threshold_not_met",
        )
        pack = _make_pack_with_diagnostics(diag)
        text = format_entity_annotated(pack)
        assert "No confident match" in text

    def test_format_diagnostics_none(self) -> None:
        pack = EvidencePack(
            query_context=QueryContext(query="test"),
            items=[],
            semantic_candidates=[],
            total_available=0,
            has_more=False,
            diagnostics=None,
            no_confident_match=False,
        )
        text = format_entity_annotated(pack)
        assert "Diagnostics unavailable" in text


class TestFormatPipelineComposition:
    """Pipeline composition badge appears correctly."""

    def test_format_pipeline_fts(self) -> None:
        pack = _make_pack_with_diagnostics(
            EvidenceDiagnostics(
                retrieval_outcome="ok",
                pipeline_composition=PipelineComposition(primary_pipeline="fts"),
            )
        )
        text = format_entity_annotated(pack)
        assert "**Pipeline:** fts" in text

    def test_format_pipeline_semantic(self) -> None:
        pack = _make_pack_with_diagnostics(
            EvidenceDiagnostics(
                retrieval_outcome="ok",
                pipeline_composition=PipelineComposition(primary_pipeline="semantic"),
            )
        )
        text = format_entity_annotated(pack)
        assert "**Pipeline:** semantic" in text

    def test_format_pipeline_none(self) -> None:
        pack = _make_pack_with_diagnostics(
            EvidenceDiagnostics(
                retrieval_outcome="zero_results",
                pipeline_composition=PipelineComposition(primary_pipeline="none"),
            )
        )
        text = format_entity_annotated(pack)
        assert "**Pipeline:** none" in text


class TestFormatSemanticCandidates:
    """Semantic candidates render when present."""

    def test_format_with_semantic_candidates(self) -> None:
        pack = EvidencePack(
            query_context=QueryContext(query="semantic"),
            items=[],
            semantic_candidates=[
                SemanticCandidate(
                    document=DocumentRef(doc_id="d1", title="Semantic A", date="2026-03-04"),
                    similarity=0.85,
                    snippet="Semantic snippet A",
                ),
                SemanticCandidate(
                    document=DocumentRef(doc_id="d2", title="Semantic B", date="2026-03-05"),
                    similarity=0.72,
                    snippet="Semantic snippet B",
                ),
            ],
            total_available=0,
            has_more=False,
            no_confident_match=False,
        )
        text = format_entity_annotated(pack)
        assert "## Semantic Candidates (2 items)" in text
        assert "Semantic A" in text
        assert "Semantic B" in text
        assert "0.850" in text or "0.85" in text
        assert "Semantic snippet A" in text

    def test_format_without_semantic_candidates(self) -> None:
        pack = EvidencePack(
            query_context=QueryContext(query="no-candidates"),
            items=[],
            semantic_candidates=[],
            total_available=0,
            has_more=False,
            no_confident_match=False,
        )
        text = format_entity_annotated(pack)
        assert "Semantic Candidates" not in text


class TestFormatDeterminism:
    """Formatter output is deterministic for identical input."""

    def test_same_input_same_output(self) -> None:
        pack = EvidencePack(
            query_context=QueryContext(query="det"),
            items=[
                EvidenceItem(
                    document=DocumentRef(doc_id="d1", title="Det", date="2026-03-06"),
                    scores=ScoreBreakdown(source="fts", rank=1, confidence="high"),
                    snippet="Deterministic.",
                )
            ],
            semantic_candidates=[],
            total_available=1,
            has_more=False,
            no_confident_match=False,
        )
        text1 = format_entity_annotated(pack)
        text2 = format_entity_annotated(pack)
        assert text1 == text2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pack_with_diagnostics(diagnostics: EvidenceDiagnostics) -> EvidencePack:
    return EvidencePack(
        query_context=QueryContext(query="test"),
        items=[
            EvidenceItem(
                document=DocumentRef(doc_id="d1", title="T", date="2026-03-01"),
                scores=ScoreBreakdown(source="fts", rank=1, confidence="high"),
                snippet="s",
            )
        ],
        semantic_candidates=[],
        total_available=1,
        has_more=False,
        no_confident_match=False,
        diagnostics=diagnostics,
    )
