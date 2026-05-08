#!/usr/bin/env python3
"""Typed dataclasses for Evidence Pack (R2-C MVP).

Frozen dataclasses with to_dict() / from_dict() round-trip support.
Unknown fields preserved in extra dicts for forward-compatibility.

Pattern follows tools/eval/eval_types.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _normalize_path(path: str) -> str:
    """Normalize backslashes to forward slashes."""
    return path.replace("\\", "/")


# ---------------------------------------------------------------------------
# ScoreBreakdown
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoreBreakdown:
    """Per-pipeline score components for a single evidence item."""

    source: str  # "fts", "semantic", "fts,semantic", "none"
    rank: int
    relevance: float = 0.0
    similarity: float = 0.0
    rrf_score: float = 0.0
    final_score: float = 0.0
    confidence: str = "low"  # "high", "medium", "low"
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset(
        {
            "source",
            "rank",
            "relevance",
            "similarity",
            "rrf_score",
            "final_score",
            "confidence",
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoreBreakdown:
        return cls(
            source=str(data.get("source", "none")),
            rank=int(data.get("rank", 0)),
            relevance=float(data.get("relevance", 0.0)),
            similarity=float(data.get("similarity", 0.0)),
            rrf_score=float(data.get("rrf_score", 0.0)),
            final_score=float(data.get("final_score", 0.0)),
            confidence=str(data.get("confidence", "low")),
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "source": self.source,
            "rank": self.rank,
            "relevance": self.relevance,
            "similarity": self.similarity,
            "rrf_score": self.rrf_score,
            "final_score": self.final_score,
            "confidence": self.confidence,
        }
        d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# DocumentRef
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentRef:
    """Lightweight reference to a journal document."""

    doc_id: str
    title: str
    date: str
    path: str | None = None
    topic: list[str] = field(default_factory=list)
    location: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict, repr=False)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset(
        {
            "doc_id",
            "title",
            "date",
            "path",
            "topic",
            "location",
            "metadata",
        }
    )

    def __post_init__(self) -> None:
        if self.path is not None:
            object.__setattr__(self, "path", _normalize_path(self.path))
        object.__setattr__(self, "doc_id", _normalize_path(self.doc_id))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentRef:
        raw_path = data.get("path", "")
        normalized_path = _normalize_path(str(raw_path)) if raw_path else None
        doc_id = data.get("doc_id", normalized_path or "")
        if doc_id:
            doc_id = _normalize_path(str(doc_id))

        topic = data.get("topic", [])
        if isinstance(topic, str):
            topic = [topic]

        return cls(
            doc_id=doc_id,
            title=str(data.get("title", "")),
            date=str(data.get("date", "")),
            path=normalized_path,
            topic=list(topic),
            location=data.get("location"),
            metadata=dict(data["metadata"]) if "metadata" in data else {},
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "doc_id": self.doc_id,
            "title": self.title,
            "date": self.date,
        }
        if self.path is not None:
            d["path"] = self.path
        if self.topic:
            d["topic"] = self.topic
        if self.location is not None:
            d["location"] = self.location
        if self.metadata:
            d["metadata"] = self.metadata
        d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# EvidenceItem
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceItem:
    """One retrieved evidence item with provenance."""

    document: DocumentRef
    scores: ScoreBreakdown
    snippet: str
    abstract: str | None = None
    explain: dict[str, Any] | None = None
    provenance: str = "keyword"
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset(
        {
            "document",
            "scores",
            "snippet",
            "abstract",
            "explain",
            "provenance",
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceItem:
        return cls(
            document=DocumentRef.from_dict(data.get("document", {})),
            scores=ScoreBreakdown.from_dict(data.get("scores", {})),
            snippet=str(data.get("snippet", "")),
            abstract=data.get("abstract"),
            explain=data.get("explain"),
            provenance=str(data.get("provenance", "keyword")),
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "document": self.document.to_dict(),
            "scores": self.scores.to_dict(),
            "snippet": self.snippet,
            "provenance": self.provenance,
        }
        if self.abstract is not None:
            d["abstract"] = self.abstract
        if self.explain is not None:
            d["explain"] = self.explain
        d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# SemanticCandidate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SemanticCandidate:
    """A semantic-only candidate not in main items."""

    document: DocumentRef
    similarity: float
    snippet: str
    rank: int = 0
    provenance: str = "semantic"
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset(
        {
            "document",
            "similarity",
            "snippet",
            "rank",
            "provenance",
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticCandidate:
        return cls(
            document=DocumentRef.from_dict(data.get("document", {})),
            similarity=float(data.get("similarity", 0.0)),
            snippet=str(data.get("snippet", "")),
            rank=int(data.get("rank", 0)),
            provenance=str(data.get("provenance", "semantic")),
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "document": self.document.to_dict(),
            "similarity": self.similarity,
            "snippet": self.snippet,
            "rank": self.rank,
            "provenance": self.provenance,
        }
        d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# QueryContext
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QueryContext:
    """Query-level metadata for the evidence pack."""

    query: str
    expanded_query: str | None = None
    search_plan: dict[str, Any] | None = None
    entity_hints: list[dict[str, Any]] = field(default_factory=list)
    semantic_policy: str = "off"
    warnings: list[str] = field(default_factory=list)
    performance: dict[str, float] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset(
        {
            "query",
            "expanded_query",
            "search_plan",
            "entity_hints",
            "semantic_policy",
            "warnings",
            "performance",
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryContext:
        return cls(
            query=str(data.get("query", "")),
            expanded_query=data.get("expanded_query"),
            search_plan=data.get("search_plan"),
            entity_hints=list(data.get("entity_hints", [])),
            semantic_policy=str(data.get("semantic_policy", "off")),
            warnings=list(data.get("warnings", [])),
            performance={k: float(v) for k, v in data.get("performance", {}).items()},
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"query": self.query}
        if self.expanded_query is not None:
            d["expanded_query"] = self.expanded_query
        if self.search_plan is not None:
            d["search_plan"] = self.search_plan
        if self.entity_hints:
            d["entity_hints"] = self.entity_hints
        if self.semantic_policy != "off":
            d["semantic_policy"] = self.semantic_policy
        if self.warnings:
            d["warnings"] = self.warnings
        if self.performance:
            d["performance"] = self.performance
        d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# EvidencePack
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidencePack:
    """Typed container for one search query's complete evidence."""

    query_context: QueryContext
    items: list[EvidenceItem]
    semantic_candidates: list[SemanticCandidate]
    total_available: int
    has_more: bool
    no_confident_match: bool
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset(
        {
            "query_context",
            "items",
            "semantic_candidates",
            "total_available",
            "has_more",
            "no_confident_match",
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidencePack:
        return cls(
            query_context=QueryContext.from_dict(data.get("query_context", {})),
            items=[EvidenceItem.from_dict(i) for i in data.get("items", [])],
            semantic_candidates=[
                SemanticCandidate.from_dict(sc) for sc in data.get("semantic_candidates", [])
            ],
            total_available=int(data.get("total_available", 0)),
            has_more=bool(data.get("has_more", False)),
            no_confident_match=bool(data.get("no_confident_match", False)),
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "query_context": self.query_context.to_dict(),
            "items": [item.to_dict() for item in self.items],
            "semantic_candidates": [sc.to_dict() for sc in self.semantic_candidates],
            "total_available": self.total_available,
            "has_more": self.has_more,
            "no_confident_match": self.no_confident_match,
        }
        d.update(self.extra)
        return d
