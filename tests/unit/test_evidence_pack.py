#!/usr/bin/env python3
"""TDD tests for Evidence Pack schema and builder (R2-C MVP).

Covers:
- ScoreBreakdown round-trip
- DocumentRef normalization and round-trip
- EvidenceItem nested round-trip
- EvidencePack full round-trip with items + semantic candidates
- build_evidence_pack() from synthetic search result
- build_evidence_pack() separates semantic-only candidates
- build_evidence_pack() handles missing semantic_results and empty results
- Unknown extra fields survive round-trip
"""

from __future__ import annotations

import pytest

from tools.evidence.builder import build_evidence_pack
from tools.evidence.types import (
    DocumentRef,
    EvidenceDiagnostics,
    EvidenceItem,
    EvidencePack,
    PipelineComposition,
    QueryContext,
    ScoreBreakdown,
    SemanticCandidate,
)

# ---------------------------------------------------------------------------
# ScoreBreakdown
# ---------------------------------------------------------------------------


class TestScoreBreakdown:
    """ScoreBreakdown round-trips through to_dict / from_dict."""

    def test_round_trip(self) -> None:
        sb = ScoreBreakdown(
            source="fts",
            rank=1,
            relevance=85.0,
            similarity=0.0,
            rrf_score=0.0,
            final_score=85.0,
            confidence="high",
        )
        d = sb.to_dict()
        sb2 = ScoreBreakdown.from_dict(d)
        assert sb2 == sb

    def test_round_trip_with_extra(self) -> None:
        sb = ScoreBreakdown(
            source="fts,semantic",
            rank=3,
            relevance=72.0,
            similarity=65.0,
            rrf_score=0.045,
            final_score=70.5,
            confidence="medium",
            extra={"custom_weight": 1.2},
        )
        d = sb.to_dict()
        assert d["custom_weight"] == 1.2
        sb2 = ScoreBreakdown.from_dict(d)
        assert sb2.extra["custom_weight"] == 1.2
        assert sb2.source == "fts,semantic"

    def test_defaults(self) -> None:
        sb = ScoreBreakdown(source="none", rank=0, relevance=0.0, similarity=0.0)
        assert sb.rrf_score == 0.0
        assert sb.final_score == 0.0
        assert sb.confidence == "low"
        assert sb.extra == {}


# ---------------------------------------------------------------------------
# DocumentRef
# ---------------------------------------------------------------------------


class TestDocumentRef:
    """DocumentRef normalizes path and round-trips."""

    def test_normalizes_backslash_path(self) -> None:
        dr = DocumentRef(
            doc_id="Journals/2026/03/life-index_2026-03-07_001.md",
            title="Test Entry",
            date="2026-03-07",
            path="Journals\\2026\\03\\life-index_2026-03-07_001.md",
        )
        assert dr.doc_id == "Journals/2026/03/life-index_2026-03-07_001.md"
        assert dr.path == "Journals/2026/03/life-index_2026-03-07_001.md"

    def test_round_trip(self) -> None:
        dr = DocumentRef(
            doc_id="Journals/2026/03/life-index_2026-03-07_001.md",
            title="Morning Thoughts",
            date="2026-03-07",
            path="Journals/2026/03/life-index_2026-03-07_001.md",
            topic=["daily"],
            location="Beijing",
            metadata={"weather": "sunny", "mood": ["calm"]},
        )
        d = dr.to_dict()
        dr2 = DocumentRef.from_dict(d)
        assert dr2 == dr

    def test_extra_fields_survive(self) -> None:
        dr = DocumentRef(
            doc_id="Journals/2026/01/life-index_2026-01-01_001.md",
            title="New Year",
            date="2026-01-01",
            extra={"custom_field": "value"},
        )
        d = dr.to_dict()
        assert d["custom_field"] == "value"
        dr2 = DocumentRef.from_dict(d)
        assert dr2.extra["custom_field"] == "value"

    def test_from_dict_uses_path_as_doc_id_when_missing(self) -> None:
        d = {
            "title": "Test",
            "date": "2026-05-09",
            "path": "Journals/2026/05/life-index_2026-05-09_001.md",
        }
        dr = DocumentRef.from_dict(d)
        assert dr.doc_id == "Journals/2026/05/life-index_2026-05-09_001.md"

    def test_from_dict_prefers_explicit_doc_id(self) -> None:
        d = {
            "doc_id": "Journals/2026/05/life-index_2026-05-09_001.md",
            "title": "Test",
            "date": "2026-05-09",
            "path": "Journals/2026/05/life-index_2026-05-09_001.md",
        }
        dr = DocumentRef.from_dict(d)
        assert dr.doc_id == "Journals/2026/05/life-index_2026-05-09_001.md"


# ---------------------------------------------------------------------------
# EvidenceItem
# ---------------------------------------------------------------------------


class TestEvidenceItem:
    """EvidenceItem round-trips with nested document + scores."""

    def _make_item(self) -> EvidenceItem:
        return EvidenceItem(
            document=DocumentRef(
                doc_id="Journals/2026/03/life-index_2026-03-07_001.md",
                title="Test",
                date="2026-03-07",
                path="Journals/2026/03/life-index_2026-03-07_001.md",
            ),
            scores=ScoreBreakdown(
                source="fts",
                rank=1,
                relevance=90.0,
                similarity=0.0,
                final_score=90.0,
                confidence="high",
            ),
            snippet="...matched text...",
            abstract="A brief summary",
            explain={"keyword_pipeline": {"matched_terms": ["test"]}},
            provenance="keyword",
        )

    def test_round_trip(self) -> None:
        item = self._make_item()
        d = item.to_dict()
        item2 = EvidenceItem.from_dict(d)
        assert item2 == item
        assert item2.document.title == "Test"
        assert item2.scores.rank == 1
        assert item2.provenance == "keyword"

    def test_nested_extra(self) -> None:
        item = EvidenceItem(
            document=DocumentRef(
                doc_id="Journals/2026/01/life-index_2026-01-01_001.md",
                title="Entry",
                date="2026-01-01",
                extra={"doc_extra": True},
            ),
            scores=ScoreBreakdown(
                source="none",
                rank=5,
                relevance=0.0,
                similarity=0.0,
                extra={"score_extra": True},
            ),
            snippet="",
            extra={"item_extra": True},
        )
        d = item.to_dict()
        item2 = EvidenceItem.from_dict(d)
        assert item2.document.extra["doc_extra"] is True
        assert item2.scores.extra["score_extra"] is True
        assert item2.extra["item_extra"] is True

    def test_minimal_fields(self) -> None:
        item = EvidenceItem(
            document=DocumentRef(
                doc_id="Journals/2026/01/life-index_2026-01-01_001.md",
                title="Minimal",
                date="2026-01-01",
            ),
            scores=ScoreBreakdown(source="none", rank=1, relevance=0.0, similarity=0.0),
            snippet="",
        )
        d = item.to_dict()
        assert "abstract" not in d or d["abstract"] is None
        assert "explain" not in d or d["explain"] is None


# ---------------------------------------------------------------------------
# SemanticCandidate
# ---------------------------------------------------------------------------


class TestSemanticCandidate:
    """SemanticCandidate round-trips."""

    def test_round_trip(self) -> None:
        sc = SemanticCandidate(
            document=DocumentRef(
                doc_id="Journals/2026/03/life-index_2026-03-08_001.md",
                title="Semantic Match",
                date="2026-03-08",
            ),
            similarity=0.72,
            snippet="...semantic snippet...",
            rank=1,
            provenance="semantic",
        )
        d = sc.to_dict()
        sc2 = SemanticCandidate.from_dict(d)
        assert sc2 == sc
        assert sc2.provenance == "semantic"

    def test_extra_fields(self) -> None:
        sc = SemanticCandidate(
            document=DocumentRef(
                doc_id="Journals/2026/03/life-index_2026-03-08_001.md",
                title="Semantic",
                date="2026-03-08",
            ),
            similarity=0.55,
            snippet="",
            rank=3,
            extra={"model": "bge-m3"},
        )
        d = sc.to_dict()
        assert d["model"] == "bge-m3"
        sc2 = SemanticCandidate.from_dict(d)
        assert sc2.extra["model"] == "bge-m3"


# ---------------------------------------------------------------------------
# QueryContext
# ---------------------------------------------------------------------------


class TestQueryContext:
    """QueryContext round-trips."""

    def test_round_trip(self) -> None:
        qc = QueryContext(
            query="what did I write about family",
            expanded_query="what did I write about family 团团",
            semantic_policy="hybrid",
            warnings=["index_stale"],
            performance={"total_time_ms": 120.5},
        )
        d = qc.to_dict()
        qc2 = QueryContext.from_dict(d)
        assert qc2 == qc
        assert qc2.expanded_query == "what did I write about family 团团"

    def test_extra_survives(self) -> None:
        qc = QueryContext(
            query="test",
            extra={"custom_meta": 42},
        )
        d = qc.to_dict()
        assert d["custom_meta"] == 42
        qc2 = QueryContext.from_dict(d)
        assert qc2.extra["custom_meta"] == 42


# ---------------------------------------------------------------------------
# EvidencePack
# ---------------------------------------------------------------------------


class TestEvidencePack:
    """EvidencePack round-trips with items + semantic candidates."""

    def _make_pack(self) -> EvidencePack:
        items = [
            EvidenceItem(
                document=DocumentRef(
                    doc_id="Journals/2026/03/life-index_2026-03-07_001.md",
                    title="Family Day",
                    date="2026-03-07",
                    topic=["family"],
                ),
                scores=ScoreBreakdown(
                    source="fts",
                    rank=1,
                    relevance=95.0,
                    similarity=0.0,
                    final_score=95.0,
                    confidence="high",
                ),
                snippet="...family day...",
                provenance="keyword",
            ),
            EvidenceItem(
                document=DocumentRef(
                    doc_id="Journals/2026/03/life-index_2026-03-08_001.md",
                    title="Work Thoughts",
                    date="2026-03-08",
                    topic=["work"],
                ),
                scores=ScoreBreakdown(
                    source="fts,semantic",
                    rank=2,
                    relevance=70.0,
                    similarity=65.0,
                    rrf_score=0.038,
                    final_score=68.0,
                    confidence="medium",
                ),
                snippet="...work...",
                provenance="hybrid",
            ),
        ]
        semantic_candidates = [
            SemanticCandidate(
                document=DocumentRef(
                    doc_id="Journals/2026/02/life-index_2026-02-14_001.md",
                    title="Valentine",
                    date="2026-02-14",
                ),
                similarity=0.52,
                snippet="...love...",
                rank=1,
                provenance="semantic",
            ),
        ]
        return EvidencePack(
            query_context=QueryContext(
                query="family memories",
                semantic_policy="hybrid",
                performance={"total_time_ms": 85.0},
            ),
            items=items,
            semantic_candidates=semantic_candidates,
            total_available=2,
            has_more=False,
            no_confident_match=False,
        )

    def test_round_trip(self) -> None:
        pack = self._make_pack()
        d = pack.to_dict()
        pack2 = EvidencePack.from_dict(d)
        assert pack2 == pack
        assert len(pack2.items) == 2
        assert len(pack2.semantic_candidates) == 1
        assert pack2.query_context.query == "family memories"

    def test_extra_at_pack_level(self) -> None:
        pack = EvidencePack(
            query_context=QueryContext(query="test"),
            items=[],
            semantic_candidates=[],
            total_available=0,
            has_more=False,
            no_confident_match=False,
            extra={"schema_version": "0.1.0"},
        )
        d = pack.to_dict()
        assert d["schema_version"] == "0.1.0"
        pack2 = EvidencePack.from_dict(d)
        assert pack2.extra["schema_version"] == "0.1.0"


# ---------------------------------------------------------------------------
# build_evidence_pack()
# ---------------------------------------------------------------------------


def _synthetic_search_result() -> dict:
    """Build a synthetic hierarchical_search() output dict."""
    return {
        "success": True,
        "query_params": {
            "query": "family day out",
            "expanded_query": "family day out 团团",
            "level": 3,
        },
        "merged_results": [
            {
                "path": "Journals/2026/03/life-index_2026-03-07_001.md",
                "title": "Family Day",
                "date": "2026-03-07",
                "snippet": "We went to the park with 团团",
                "source": "fts",
                "relevance": 90,
                "fts_score": 90.0,
                "semantic_score": 0.0,
                "rrf_score": 0.0,
                "final_score": 90.0,
                "search_rank": 1,
                "confidence": "high",
                "metadata": {
                    "topic": "family",
                    "tags": ["weekend"],
                    "mood": ["happy"],
                    "people": ["团团"],
                    "location": "Beijing",
                    "weather": "sunny",
                    "abstract": "A beautiful family day at the park.",
                },
            },
            {
                "path": "Journals/2026/03/life-index_2026-03-08_001.md",
                "title": "Work Reflection",
                "date": "2026-03-08",
                "snippet": "Thinking about work-life balance",
                "source": "fts,semantic",
                "relevance": 70,
                "fts_score": 70.0,
                "semantic_score": 65.0,
                "rrf_score": 0.035,
                "final_score": 68.0,
                "search_rank": 2,
                "confidence": "medium",
                "metadata": {
                    "topic": "work",
                    "abstract": "Work-life balance thoughts.",
                },
            },
        ],
        "semantic_results": [
            {
                "path": "Journals/2026/02/life-index_2026-02-14_001.md",
                "title": "Valentine's Day",
                "date": "2026-02-14",
                "snippet": "A romantic evening",
                "similarity": 0.62,
                "source": "semantic",
                "metadata": {"topic": "love"},
            },
            # This one is ALSO in merged_results, should be excluded from candidates
            {
                "path": "Journals/2026/03/life-index_2026-03-08_001.md",
                "title": "Work Reflection",
                "date": "2026-03-08",
                "snippet": "Thinking about work-life balance",
                "similarity": 0.65,
                "source": "semantic",
                "metadata": {"topic": "work"},
            },
        ],
        "total_available": 2,
        "has_more": False,
        "no_confident_match": False,
        "semantic_effective_policy": "hybrid",
        "entity_hints": [
            {"matched_term": "团团", "entity_id": "tuan_tuan", "entity_type": "person"},
        ],
        "search_plan": {"intent_type": "recall", "query_mode": "natural_language"},
        "warnings": [],
        "performance": {"total_time_ms": 110.5},
    }


class TestBuildEvidencePack:
    """build_evidence_pack() from synthetic search result."""

    def test_builds_items_from_merged_results(self) -> None:
        result = _synthetic_search_result()
        pack = build_evidence_pack(result)

        assert len(pack.items) == 2
        assert pack.items[0].document.title == "Family Day"
        assert pack.items[0].scores.rank == 1
        assert pack.items[0].scores.source == "fts"
        assert pack.items[0].document.topic == ["family"]
        assert pack.items[0].document.metadata["weather"] == "sunny"
        assert pack.items[0].snippet == "We went to the park with 团团"

    def test_separates_semantic_candidates(self) -> None:
        result = _synthetic_search_result()
        pack = build_evidence_pack(result)

        # Only the semantic result NOT in merged_results should appear
        assert len(pack.semantic_candidates) == 1
        assert pack.semantic_candidates[0].document.title == "Valentine's Day"
        assert pack.semantic_candidates[0].similarity == pytest.approx(0.62)
        assert pack.semantic_candidates[0].provenance == "semantic"

    def test_excludes_semantic_docs_already_in_merged(self) -> None:
        result = _synthetic_search_result()
        pack = build_evidence_pack(result)

        # Work Reflection appears in both merged and semantic — should NOT be
        # a semantic candidate
        semantic_ids = {sc.document.doc_id for sc in pack.semantic_candidates}
        item_ids = {item.document.doc_id for item in pack.items}
        assert semantic_ids.isdisjoint(item_ids)

    def test_query_context_populated(self) -> None:
        result = _synthetic_search_result()
        pack = build_evidence_pack(result)

        assert pack.query_context.query == "family day out"
        assert pack.query_context.expanded_query == "family day out 团团"
        assert pack.query_context.semantic_policy == "hybrid"
        assert pack.query_context.entity_hints == [
            {"matched_term": "团团", "entity_id": "tuan_tuan", "entity_type": "person"},
        ]
        assert pack.query_context.performance == {"total_time_ms": 110.5}

    def test_pack_metadata(self) -> None:
        result = _synthetic_search_result()
        pack = build_evidence_pack(result)

        assert pack.total_available == 2
        assert pack.has_more is False
        assert pack.no_confident_match is False

    def test_does_not_modify_input(self) -> None:
        result = _synthetic_search_result()
        import copy

        original = copy.deepcopy(result)
        build_evidence_pack(result)
        assert result == original

    def test_handles_missing_semantic_results(self) -> None:
        result = _synthetic_search_result()
        del result["semantic_results"]
        pack = build_evidence_pack(result)

        assert len(pack.items) == 2
        assert len(pack.semantic_candidates) == 0

    def test_handles_empty_results(self) -> None:
        result = {
            "success": True,
            "query_params": {"query": "nonexistent"},
            "merged_results": [],
            "total_available": 0,
            "has_more": False,
            "no_confident_match": True,
        }
        pack = build_evidence_pack(result)

        assert len(pack.items) == 0
        assert len(pack.semantic_candidates) == 0
        assert pack.total_available == 0
        assert pack.no_confident_match is True
        assert pack.query_context.query == "nonexistent"

    def test_item_provenance_keyword(self) -> None:
        result = _synthetic_search_result()
        pack = build_evidence_pack(result)

        assert pack.items[0].provenance == "keyword"
        assert pack.items[1].provenance == "hybrid"

    def test_hybrid_source_with_plus_is_hybrid(self) -> None:
        result = _synthetic_search_result()
        result["merged_results"][0]["source"] = "l3+semantic"
        result["merged_results"][0]["semantic_score"] = 0.42

        pack = build_evidence_pack(result)

        assert pack.items[0].provenance == "hybrid"
        assert pack.items[0].scores.similarity == pytest.approx(0.42)

    def test_merged_semantic_similarity_fallback(self) -> None:
        result = _synthetic_search_result()
        item = result["merged_results"][0]
        item["source"] = "semantic"
        item.pop("semantic_score", None)
        item["similarity"] = 0.61

        pack = build_evidence_pack(result)

        assert pack.items[0].provenance == "semantic"
        assert pack.items[0].scores.similarity == pytest.approx(0.61)

    def test_top_level_topic_used_when_metadata_topic_missing(self) -> None:
        result = _synthetic_search_result()
        result["merged_results"][0]["topic"] = "project"
        result["merged_results"][0]["metadata"].pop("topic")

        pack = build_evidence_pack(result)

        assert pack.items[0].document.topic == ["project"]

    def test_summary_used_as_abstract_fallback(self) -> None:
        result = _synthetic_search_result()
        result["merged_results"][0]["metadata"].pop("abstract")
        result["merged_results"][0]["metadata"]["summary"] = "Summary fallback"

        pack = build_evidence_pack(result)

        assert pack.items[0].abstract == "Summary fallback"

    def test_round_trip_after_build(self) -> None:
        result = _synthetic_search_result()
        pack = build_evidence_pack(result)
        d = pack.to_dict()
        pack2 = EvidencePack.from_dict(d)
        assert pack2 == pack


class TestExtraFieldSurvival:
    """Unknown extra fields survive at various levels."""

    def test_pack_level_extra(self) -> None:
        pack = EvidencePack(
            query_context=QueryContext(query="test"),
            items=[],
            semantic_candidates=[],
            total_available=0,
            has_more=False,
            no_confident_match=False,
            extra={"future_field": "value"},
        )
        d = pack.to_dict()
        pack2 = EvidencePack.from_dict(d)
        assert pack2.extra["future_field"] == "value"

    def test_item_level_extra(self) -> None:
        item = EvidenceItem(
            document=DocumentRef(doc_id="a.md", title="A", date="2026-01-01"),
            scores=ScoreBreakdown(source="none", rank=1, relevance=0.0, similarity=0.0),
            snippet="",
            extra={"item_future": True},
        )
        d = item.to_dict()
        item2 = EvidenceItem.from_dict(d)
        assert item2.extra["item_future"] is True

    def test_document_level_extra(self) -> None:
        doc = DocumentRef(
            doc_id="a.md",
            title="A",
            date="2026-01-01",
            extra={"doc_future": "yes"},
        )
        d = doc.to_dict()
        doc2 = DocumentRef.from_dict(d)
        assert doc2.extra["doc_future"] == "yes"


# ---------------------------------------------------------------------------
# Path Privacy - absolute paths must never leak
# ---------------------------------------------------------------------------

ABS_MERGED_PATH = (
    "C:/Users/dexter/Documents/Life-Index/Journals/2026/03/" "life-index_2026-03-07_001.md"
)
ABS_SEMANTIC_PATH = (
    "C:/Users/dexter/Documents/Life-Index/Journals/2026/02/" "life-index_2026-02-14_001.md"
)
POSIX_ABS_MERGED_PATH = (
    "/home/user/Documents/Life-Index/Journals/2026/03/" "life-index_2026-03-07_001.md"
)
REL_MERGED_PATH = "Journals/2026/03/life-index_2026-03-07_001.md"


def _absolute_path_search_result() -> dict:
    """Synthetic search result with absolute paths in merged + semantic items."""
    return {
        "success": True,
        "query_params": {"query": "test query"},
        "merged_results": [
            {
                "path": ABS_MERGED_PATH,
                "title": "Absolute Path Entry",
                "date": "2026-03-07",
                "snippet": "content here",
                "source": "fts",
                "relevance": 90,
                "fts_score": 90.0,
                "semantic_score": 0.0,
                "rrf_score": 0.0,
                "final_score": 90.0,
                "search_rank": 1,
                "confidence": "high",
                "metadata": {"topic": "daily"},
            },
        ],
        "semantic_results": [
            {
                "path": ABS_SEMANTIC_PATH,
                "title": "Semantic Absolute",
                "date": "2026-02-14",
                "snippet": "semantic match",
                "similarity": 0.55,
                "source": "semantic",
                "metadata": {"topic": "love"},
            },
        ],
        "total_available": 1,
        "has_more": False,
        "no_confident_match": False,
        "semantic_effective_policy": "hybrid",
        "entity_hints": [],
        "warnings": [],
        "performance": {"total_time_ms": 50.0},
    }


class TestPathPrivacy:
    """Absolute paths must never appear in evidence pack output."""

    def test_merged_item_path_is_relative(self) -> None:
        result = _absolute_path_search_result()
        pack = build_evidence_pack(result)

        path = pack.items[0].document.path
        assert path is not None
        assert not path.startswith("C:")
        assert not path.startswith("/")
        assert "Journals/" in path

    def test_merged_item_doc_id_is_relative(self) -> None:
        result = _absolute_path_search_result()
        pack = build_evidence_pack(result)

        doc_id = pack.items[0].document.doc_id
        assert not doc_id.startswith("C:")
        assert not doc_id.startswith("/")
        assert "Journals/" in doc_id

    def test_semantic_candidate_path_is_relative(self) -> None:
        result = _absolute_path_search_result()
        pack = build_evidence_pack(result)

        assert len(pack.semantic_candidates) == 1
        path = pack.semantic_candidates[0].document.path
        assert path is not None
        assert not path.startswith("C:")
        assert not path.startswith("/")
        assert "Journals/" in path

    def test_semantic_candidate_doc_id_is_relative(self) -> None:
        result = _absolute_path_search_result()
        pack = build_evidence_pack(result)

        doc_id = pack.semantic_candidates[0].document.doc_id
        assert not doc_id.startswith("C:")
        assert not doc_id.startswith("/")
        assert "Journals/" in doc_id

    def test_relative_paths_unchanged(self) -> None:
        """Existing relative paths must not be altered."""
        result = _synthetic_search_result()
        pack = build_evidence_pack(result)

        assert pack.items[0].document.path == REL_MERGED_PATH
        assert pack.items[0].document.doc_id == REL_MERGED_PATH

    def test_rel_path_preferred_over_absolute(self) -> None:
        """When rel_path is present, it should be used instead of absolute path."""
        result = _absolute_path_search_result()
        result["merged_results"][0]["rel_path"] = REL_MERGED_PATH

        pack = build_evidence_pack(result)
        assert pack.items[0].document.path == REL_MERGED_PATH
        assert pack.items[0].document.doc_id == REL_MERGED_PATH

    def test_absolute_path_without_journals_suffix_uses_metadata_doc_id(self) -> None:
        """Non-Journal absolute path omits path but keeps a safe metadata doc_id."""
        result = {
            "query_params": {"query": "test"},
            "merged_results": [
                {
                    "path": "C:/SomeOther/Directory/file.txt",
                    "title": "Non-Journal",
                    "date": "2026-01-01",
                    "source": "none",
                },
            ],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
        }
        pack = build_evidence_pack(result)

        assert pack.items[0].document.path is None
        assert pack.items[0].document.doc_id == "2026-01-01 Non-Journal"

    def test_absolute_rel_path_is_sanitized(self) -> None:
        """Absolute rel_path values must be sanitized before output."""
        result = _absolute_path_search_result()
        result["merged_results"][0]["rel_path"] = (
            "C:/Users/dexter/Documents/Life-Index/Journals/2026/03/" "life-index_2026-03-07_001.md"
        )
        result["merged_results"][0]["path"] = "C:/Other/without-journals.md"

        pack = build_evidence_pack(result)

        assert pack.items[0].document.path == REL_MERGED_PATH
        assert pack.items[0].document.doc_id == REL_MERGED_PATH

    def test_backslash_windows_absolute_path_is_sanitized(self) -> None:
        """Windows backslash absolute paths are normalized and sanitized."""
        result = _absolute_path_search_result()
        result["merged_results"][0]["path"] = (
            "C:\\Users\\dexter\\Documents\\Life-Index\\Journals\\2026\\03\\"
            "life-index_2026-03-07_001.md"
        )

        pack = build_evidence_pack(result)

        assert pack.items[0].document.path == REL_MERGED_PATH
        assert pack.items[0].document.doc_id == REL_MERGED_PATH

    def test_input_not_modified_with_absolute_paths(self) -> None:
        """Input dict must not be modified even with absolute paths."""
        import copy

        result = _absolute_path_search_result()
        original = copy.deepcopy(result)
        build_evidence_pack(result)
        assert result == original

    def test_posix_absolute_path_filtered(self) -> None:
        """POSIX-style absolute paths are also filtered."""
        result = {
            "query_params": {"query": "test"},
            "merged_results": [
                {
                    "path": POSIX_ABS_MERGED_PATH,
                    "title": "POSIX Absolute",
                    "date": "2026-03-07",
                    "source": "none",
                },
            ],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
        }
        pack = build_evidence_pack(result)

        assert pack.items[0].document.path is not None
        assert not pack.items[0].document.path.startswith("/")
        assert "Journals/" in pack.items[0].document.path

    def test_deduplication_uses_safe_paths(self) -> None:
        """Semantic deduplication must use safe paths, not raw absolute paths."""
        result = _absolute_path_search_result()
        # Add semantic result with same absolute path as merged item
        result["semantic_results"].append(
            {
                "path": ABS_MERGED_PATH,
                "title": "Absolute Path Entry",
                "date": "2026-03-07",
                "similarity": 0.40,
                "source": "semantic",
            }
        )

        pack = build_evidence_pack(result)

        # The duplicate should be excluded from semantic_candidates
        assert len(pack.semantic_candidates) == 1
        semantic_ids = {sc.document.doc_id for sc in pack.semantic_candidates}
        item_ids = {item.document.doc_id for item in pack.items}
        assert semantic_ids.isdisjoint(item_ids)

    def test_none_path_uses_metadata_doc_id(self) -> None:
        """path=None falls back to metadata-based doc_id, not literal 'None'."""
        result = {
            "query_params": {"query": "test"},
            "merged_results": [
                {
                    "path": None,
                    "title": "Missing Path",
                    "date": "2026-05-09",
                    "source": "none",
                },
            ],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
        }
        pack = build_evidence_pack(result)

        assert pack.items[0].document.path is None
        assert pack.items[0].document.doc_id == "2026-05-09 Missing Path"

    def test_deduplication_matches_doc_id_not_safe_path(self) -> None:
        """When safe path is empty, deduplication must use metadata doc_id."""
        result = {
            "query_params": {"query": "test"},
            "merged_results": [
                {
                    "path": "C:/NoJournals/file.txt",
                    "title": "Same Title",
                    "date": "2026-05-09",
                    "source": "none",
                },
            ],
            "semantic_results": [
                {
                    "path": "C:/Other/file.txt",
                    "title": "Same Title",
                    "date": "2026-05-09",
                    "similarity": 0.40,
                    "source": "semantic",
                },
            ],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
        }
        pack = build_evidence_pack(result)

        # Both have empty safe path but same metadata doc_id
        assert pack.items[0].document.doc_id == "2026-05-09 Same Title"
        # Semantic duplicate should be excluded
        assert len(pack.semantic_candidates) == 0


# ---------------------------------------------------------------------------
# PipelineComposition
# ---------------------------------------------------------------------------


class TestPipelineComposition:
    """PipelineComposition round-trip and values."""

    def test_none(self) -> None:
        pc = PipelineComposition(primary_pipeline="none")
        d = pc.to_dict()
        assert d["primary_pipeline"] == "none"
        pc2 = PipelineComposition.from_dict(d)
        assert pc2 == pc

    def test_fts(self) -> None:
        pc = PipelineComposition(primary_pipeline="fts")
        d = pc.to_dict()
        assert d["primary_pipeline"] == "fts"
        pc2 = PipelineComposition.from_dict(d)
        assert pc2 == pc

    def test_semantic(self) -> None:
        pc = PipelineComposition(primary_pipeline="semantic")
        d = pc.to_dict()
        assert d["primary_pipeline"] == "semantic"
        pc2 = PipelineComposition.from_dict(d)
        assert pc2 == pc

    def test_hybrid(self) -> None:
        pc = PipelineComposition(primary_pipeline="hybrid")
        d = pc.to_dict()
        assert d["primary_pipeline"] == "hybrid"
        pc2 = PipelineComposition.from_dict(d)
        assert pc2 == pc

    def test_extra_survives(self) -> None:
        pc = PipelineComposition(
            primary_pipeline="hybrid", extra={"detailed_sources": ["fts", "semantic"]}
        )
        d = pc.to_dict()
        assert d["detailed_sources"] == ["fts", "semantic"]
        pc2 = PipelineComposition.from_dict(d)
        assert pc2.extra["detailed_sources"] == ["fts", "semantic"]


# ---------------------------------------------------------------------------
# EvidenceDiagnostics
# ---------------------------------------------------------------------------


class TestEvidenceDiagnostics:
    """EvidenceDiagnostics round-trip and unknown extra preservation."""

    def test_round_trip(self) -> None:
        diag = EvidenceDiagnostics(
            retrieval_outcome="ok",
            outcome_reason="confident_results_present",
            notes=[],
            suggestions=[],
        )
        d = diag.to_dict()
        diag2 = EvidenceDiagnostics.from_dict(d)
        assert diag2 == diag
        assert diag2.retrieval_outcome == "ok"

    def test_round_trip_with_extra(self) -> None:
        diag = EvidenceDiagnostics(
            retrieval_outcome="weak_results",
            outcome_reason="low_scores",
            notes=["sparse results"],
            suggestions=["try broader query"],
            extra={"custom_metric": 0.42},
        )
        d = diag.to_dict()
        assert d["custom_metric"] == pytest.approx(0.42)
        diag2 = EvidenceDiagnostics.from_dict(d)
        assert diag2.extra["custom_metric"] == pytest.approx(0.42)
        assert diag2.notes == ["sparse results"]
        assert diag2.suggestions == ["try broader query"]

    def test_minimal_output(self) -> None:
        diag = EvidenceDiagnostics(retrieval_outcome="zero_results")
        d = diag.to_dict()
        assert d == {"retrieval_outcome": "zero_results"}
        assert "outcome_reason" not in d
        assert "notes" not in d
        assert "suggestions" not in d

    def test_from_dict_without_optional_fields(self) -> None:
        d = {"retrieval_outcome": "ok"}
        diag = EvidenceDiagnostics.from_dict(d)
        assert diag.retrieval_outcome == "ok"
        assert diag.outcome_reason == ""
        assert diag.notes == []
        assert diag.suggestions == []

    def test_unknown_fields_preserved_as_extra(self) -> None:
        d = {
            "retrieval_outcome": "ok",
            "outcome_reason": "test",
            "future_field": "future_value",
        }
        diag = EvidenceDiagnostics.from_dict(d)
        assert diag.extra["future_field"] == "future_value"

    def test_round_trip_with_pipeline_composition(self) -> None:
        diag = EvidenceDiagnostics(
            retrieval_outcome="ok",
            outcome_reason="confident_results_present",
            pipeline_composition=PipelineComposition(primary_pipeline="hybrid"),
        )
        d = diag.to_dict()
        assert d["pipeline_composition"]["primary_pipeline"] == "hybrid"
        diag2 = EvidenceDiagnostics.from_dict(d)
        assert diag2.pipeline_composition is not None
        assert diag2.pipeline_composition.primary_pipeline == "hybrid"

    def test_pipeline_composition_none_omitted_in_dict(self) -> None:
        diag = EvidenceDiagnostics(
            retrieval_outcome="zero_results",
            outcome_reason="no_matches_found",
            pipeline_composition=None,
        )
        d = diag.to_dict()
        assert "pipeline_composition" not in d


# ---------------------------------------------------------------------------
# compute_diagnostics()
# ---------------------------------------------------------------------------


def _search_result_with_items(
    count: int = 2,
    total_available: int | None = None,
    no_confident_match: bool = False,
    confidences: list[str] | None = None,
    has_more: bool = False,
) -> dict:
    """Build a synthetic search result for diagnostics testing."""
    items = []
    for i in range(1, count + 1):
        item: dict = {
            "path": f"Journals/2026/03/life-index_2026-03-0{i}_001.md",
            "title": f"Entry {i}",
            "date": f"2026-03-0{i}",
            "snippet": f"snippet {i}",
            "source": "fts",
            "relevance": 80 - i * 10,
            "confidence": (
                confidences[i - 1] if confidences and i <= len(confidences) else "medium"
            ),
            "metadata": {},
        }
        items.append(item)
    return {
        "success": True,
        "query_params": {"query": "test"},
        "merged_results": items,
        "semantic_results": [],
        "total_available": total_available if total_available is not None else count,
        "has_more": has_more,
        "no_confident_match": no_confident_match,
    }


class TestComputeDiagnostics:
    """compute_diagnostics() classification from search result fields."""

    def test_zero_results(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(count=0, total_available=0, no_confident_match=True)
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "zero_results"
        assert diag.outcome_reason == "no_matches_found"
        assert len(diag.notes) > 0
        assert len(diag.suggestions) > 0

    def test_zero_results_truncated(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(count=0, total_available=5, no_confident_match=False)
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "zero_results"
        assert diag.outcome_reason == "results_truncated_before_delivery"

    def test_no_confident_match_all_low(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=3,
            no_confident_match=True,
            confidences=["low", "low", "low"],
        )
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "no_confident_match"
        assert diag.outcome_reason == "all_items_low_confidence"

    def test_no_confident_flag_mixed_confidence(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=3,
            no_confident_match=True,
            confidences=["high", "medium", "low"],
        )
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "no_confident_match"
        assert diag.outcome_reason == "search_core_flagged_no_confident"

    def test_weak_results_full_recall(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=3,
            total_available=3,
            no_confident_match=False,
            confidences=["low", "low", "low"],
        )
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "weak_results"
        assert diag.outcome_reason == "all_items_low_confidence_full_recall"

    def test_ok_high_confidence(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=2,
            total_available=2,
            no_confident_match=False,
            confidences=["high", "medium"],
        )
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "ok"
        assert diag.outcome_reason == "confident_results_present"
        assert diag.notes == []
        assert diag.suggestions == []

    def test_ok_medium_confidence(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=2,
            total_available=2,
            no_confident_match=False,
            confidences=["medium", "medium"],
        )
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "ok"

    def test_weak_results_with_under_recall_hint(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=2,
            total_available=10,
            no_confident_match=False,
            confidences=["low", "low"],
            has_more=True,
        )
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "weak_results"
        assert "under_recall" in diag.outcome_reason or "total_available" in str(diag.notes)

    def test_diagnostics_in_build_evidence_pack(self) -> None:
        """build_evidence_pack() populates diagnostics."""
        result = _synthetic_search_result()
        pack = build_evidence_pack(result)
        assert pack.diagnostics is not None
        assert pack.diagnostics.retrieval_outcome == "ok"

    def test_diagnostics_in_empty_build(self) -> None:
        """Empty search result produces zero_results diagnostics."""
        result = {
            "query_params": {"query": "nonexistent"},
            "merged_results": [],
            "total_available": 0,
            "has_more": False,
            "no_confident_match": True,
        }
        pack = build_evidence_pack(result)
        assert pack.diagnostics is not None
        assert pack.diagnostics.retrieval_outcome == "zero_results"

    def test_diagnostics_round_trip_through_pack(self) -> None:
        """Diagnostics survive pack to_dict / from_dict round-trip."""
        result = _synthetic_search_result()
        pack = build_evidence_pack(result)
        d = pack.to_dict()
        assert "diagnostics" in d
        pack2 = EvidencePack.from_dict(d)
        assert pack2.diagnostics is not None
        assert pack2.diagnostics.retrieval_outcome == "ok"

    def test_old_payload_without_diagnostics(self) -> None:
        """Old EvidencePack payloads without diagnostics field still deserialize."""
        old_data = {
            "query_context": {"query": "test"},
            "items": [],
            "semantic_candidates": [],
            "total_available": 0,
            "has_more": False,
            "no_confident_match": True,
        }
        pack = EvidencePack.from_dict(old_data)
        assert pack.diagnostics is None
        assert pack.total_available == 0

    # --- S1-A: semantic-only moderate-confidence no_confident_match → weak_results ---

    def test_s1a_semantic_only_medium_confidence_becomes_weak_results(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=2,
            no_confident_match=True,
            confidences=["medium", "medium"],
        )
        # Override source to semantic-only
        for item in result["merged_results"]:
            item["source"] = "semantic"
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "weak_results"
        assert diag.outcome_reason == "semantic_only_moderate_confidence_no_fts_support"
        assert diag.pipeline_composition is not None
        assert diag.pipeline_composition.primary_pipeline == "semantic"

    def test_s1a_semantic_only_high_confidence_becomes_weak_results(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=1,
            no_confident_match=True,
            confidences=["high"],
        )
        result["merged_results"][0]["source"] = "semantic"
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "weak_results"
        assert diag.outcome_reason == "semantic_only_moderate_confidence_no_fts_support"

    def test_s1a_all_low_remains_no_confident_match(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=2,
            no_confident_match=True,
            confidences=["low", "low"],
        )
        for item in result["merged_results"]:
            item["source"] = "semantic"
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "no_confident_match"
        assert diag.outcome_reason == "all_items_low_confidence"

    def test_s1a_hybrid_with_medium_stays_no_confident_match(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=2,
            no_confident_match=True,
            confidences=["medium", "low"],
        )
        result["merged_results"][0]["source"] = "fts,semantic"
        result["merged_results"][1]["source"] = "semantic"
        diag = compute_diagnostics(result)
        assert diag.retrieval_outcome == "no_confident_match"
        assert diag.outcome_reason == "search_core_flagged_no_confident"

    # --- S1-B: pipeline_composition ---

    def test_pipeline_composition_none(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(count=0, total_available=0, no_confident_match=True)
        diag = compute_diagnostics(result)
        assert diag.pipeline_composition is not None
        assert diag.pipeline_composition.primary_pipeline == "none"

    def test_pipeline_composition_fts(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=2,
            no_confident_match=False,
            confidences=["high", "medium"],
        )
        for item in result["merged_results"]:
            item["source"] = "fts"
        diag = compute_diagnostics(result)
        assert diag.pipeline_composition is not None
        assert diag.pipeline_composition.primary_pipeline == "fts"

    def test_pipeline_composition_semantic(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=2,
            no_confident_match=False,
            confidences=["medium", "medium"],
        )
        for item in result["merged_results"]:
            item["source"] = "semantic"
        diag = compute_diagnostics(result)
        assert diag.pipeline_composition is not None
        assert diag.pipeline_composition.primary_pipeline == "semantic"

    def test_pipeline_composition_hybrid(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=2,
            no_confident_match=False,
            confidences=["high", "medium"],
        )
        result["merged_results"][0]["source"] = "fts"
        result["merged_results"][1]["source"] = "semantic"
        diag = compute_diagnostics(result)
        assert diag.pipeline_composition is not None
        assert diag.pipeline_composition.primary_pipeline == "hybrid"

    def test_pipeline_composition_hybrid_from_fts_semantic_source(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(
            count=1,
            no_confident_match=False,
            confidences=["high"],
        )
        result["merged_results"][0]["source"] = "fts,semantic"
        diag = compute_diagnostics(result)
        assert diag.pipeline_composition is not None
        assert diag.pipeline_composition.primary_pipeline == "hybrid"

    def test_pipeline_composition_round_trip_through_pack(self) -> None:
        result = _synthetic_search_result()
        pack = build_evidence_pack(result)
        d = pack.to_dict()
        assert "pipeline_composition" in d["diagnostics"]
        pack2 = EvidencePack.from_dict(d)
        assert pack2.diagnostics is not None
        assert pack2.diagnostics.pipeline_composition is not None
        assert pack2.diagnostics.pipeline_composition.primary_pipeline == "hybrid"


class TestDiagnosticsPathPrivacy:
    """Diagnostics must not contain absolute paths."""

    def test_diagnostics_no_absolute_paths(self) -> None:
        from tools.evidence.builder import compute_diagnostics

        result = _search_result_with_items(count=2, confidences=["high", "medium"])
        diag = compute_diagnostics(result)
        d = diag.to_dict()
        diag_str = str(d)
        assert "C:/" not in diag_str
        assert "/home/" not in diag_str
        assert not any("\\" in n for n in diag.notes)
        assert not any("\\" in s for s in diag.suggestions)
