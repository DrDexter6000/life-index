"""Round 11 — Query Understanding type definitions.

Defines the structured types for search_plan, ambiguity, and hints
as specified in Round 11 PRD §5.1–5.3.

These types are the contract between CLI query preprocessor and
all callers (Agent, Web, test harness).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


# ── Enums ───────────────────────────────────────────────────────────────


class IntentType(Enum):
    """Query intent classification (PRD §5.1 intent_type)."""

    RECALL = "recall"
    COUNT = "count"
    COMPARE = "compare"
    SUMMARIZE = "summarize"
    UNKNOWN = "unknown"


class QueryMode(Enum):
    """Query mode classification (PRD §5.1 query_mode)."""

    KEYWORD = "keyword"
    NATURAL_LANGUAGE = "natural_language"
    MIXED = "mixed"


class AmbiguityType(Enum):
    """Ambiguity signal types (PRD §7, §5.6 Phase 0 可微调)."""

    AGGREGATION_REQUIRES_AGENT_JUDGEMENT = "aggregation_requires_agent_judgement"
    TIME_RANGE_INTERPRETATION = "time_range_interpretation"
    ENTITY_RESOLUTION_MULTIPLE_CANDIDATES = "entity_resolution_multiple_candidates"
    QUERY_TOO_BROAD = "query_too_broad"


# Type aliases
Severity = Literal["low", "medium", "high"]


# ── DateRange ──────────────────────────────────────────────────────────


@dataclass
class DateRange:
    """Parsed date range from a query (PRD §5.1 date_range)."""

    since: str | None = None
    until: str | None = None
    source: str | None = None

    def to_dict(self) -> dict:
        return {
            "since": self.since,
            "until": self.until,
            "source": self.source,
        }


# ── SearchPlan ─────────────────────────────────────────────────────────


@dataclass
class SearchPlan:
    """Structured query understanding output (PRD §5.1).

    This is the L2 Deterministic Preprocessing output — a caller-facing
    field that describes how the query was structured before retrieval.
    """

    raw_query: str = ""
    normalized_query: str = ""
    intent_type: IntentType = IntentType.UNKNOWN
    query_mode: QueryMode = QueryMode.KEYWORD
    keywords: list[str] = field(default_factory=list)
    date_range: DateRange | None = None
    topic_hints: list[str] = field(default_factory=list)
    entity_hints_used: list[dict] = field(default_factory=list)
    expanded_query: str = ""
    pipelines: dict = field(default_factory=lambda: {"keyword": True, "semantic": True})

    def to_dict(self) -> dict:
        return {
            "raw_query": self.raw_query,
            "normalized_query": self.normalized_query,
            "intent_type": self.intent_type.value,
            "query_mode": self.query_mode.value,
            "keywords": self.keywords,
            "date_range": self.date_range.to_dict() if self.date_range else None,
            "topic_hints": self.topic_hints,
            "entity_hints_used": self.entity_hints_used,
            "expanded_query": self.expanded_query,
            "pipelines": self.pipelines,
        }


# ── Ambiguity ──────────────────────────────────────────────────────────


@dataclass
class AmbiguityItem:
    """Single ambiguity signal (PRD §5.2 items[])."""

    type: AmbiguityType
    severity: Severity
    reason: str
    candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "severity": self.severity,
            "reason": self.reason,
            "candidates": self.candidates,
        }


@dataclass
class AmbiguityReport:
    """Ambiguity report for a search query (PRD §5.2)."""

    has_ambiguity: bool = False
    items: list[AmbiguityItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "has_ambiguity": self.has_ambiguity,
            "items": [item.to_dict() for item in self.items],
        }


# ── Hints ──────────────────────────────────────────────────────────────


@dataclass
class HintItem:
    """Single invocation-time hint (PRD §5.3)."""

    type: str
    severity: Severity
    message: str

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
        }


__all__ = [
    "IntentType",
    "QueryMode",
    "AmbiguityType",
    "Severity",
    "DateRange",
    "SearchPlan",
    "AmbiguityItem",
    "AmbiguityReport",
    "HintItem",
]
