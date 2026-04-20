"""Round 11 — Ambiguity Signal Detector.

Detects structural ambiguity signals in queries and returns an
AmbiguityReport. CLI detects signals; Agent decides what to do.

This follows the existing pattern of no_confident_match, warnings,
entity_hints — deterministic signal reporting, not decision-making.
"""

from __future__ import annotations

from .query_types import (
    AmbiguityItem,
    AmbiguityReport,
    AmbiguityType,
    IntentType,
    SearchPlan,
)

# Maximum ambiguity items to report (prevent noise)
_MAX_ITEMS = 4


def detect_ambiguity(
    search_plan: SearchPlan,
    query: str,
    entity_hints: list[dict] | None = None,
) -> AmbiguityReport:
    """Detect ambiguity signals from a search plan.

    Args:
        search_plan: The structured query understanding output.
        query: Raw query string.
        entity_hints: Resolved entity hints from entity graph.

    Returns:
        AmbiguityReport with has_ambiguity flag and detected signals.
    """
    items: list[AmbiguityItem] = []

    # Rule 1: Aggregation intent requires agent judgment
    if search_plan.intent_type in {IntentType.COUNT, IntentType.COMPARE, IntentType.SUMMARIZE}:
        items.append(
            AmbiguityItem(
                type=AmbiguityType.AGGREGATION_REQUIRES_AGENT_JUDGEMENT,
                severity="high",
                reason=(
                    f"intent_type={search_plan.intent_type.value}: "
                    "search can retrieve evidence but cannot derive "
                    "the final answer deterministically"
                ),
                candidates=[],
            )
        )

    # Rule 2: Relative time range may have multiple interpretations
    if (
        search_plan.date_range is not None
        and search_plan.date_range.source == "relative_time_parse"
    ):
        candidates = []
        # Provide alternative interpretations
        if "过去" in (query or "") and "天" in (query or ""):
            candidates = ["rolling_window", "calendar_period"]
        elif "上个月" in (query or ""):
            candidates = ["last_calendar_month", "previous_30_days"]
        elif "最近" in (query or ""):
            candidates = ["last_30_days", "last_7_days"]
        else:
            candidates = ["parsed_range", "alternative_interpretation"]

        items.append(
            AmbiguityItem(
                type=AmbiguityType.TIME_RANGE_INTERPRETATION,
                severity="medium",
                reason=(
                    f"time range was parsed from relative expression: "
                    f"{search_plan.date_range.since} to {search_plan.date_range.until}"
                ),
                candidates=candidates,
            )
        )

    # Rule 3: Entity resolution returned multiple candidates for same token
    if entity_hints:
        seen_terms: dict[str, int] = {}
        for hint in entity_hints:
            term = hint.get("matched_term", "")
            count = seen_terms.get(term, 0) + 1
            seen_terms[term] = count
        for term, count in seen_terms.items():
            if count > 1:
                items.append(
                    AmbiguityItem(
                        type=AmbiguityType.ENTITY_RESOLUTION_MULTIPLE_CANDIDATES,
                        severity="medium",
                        reason=f'"{term}" resolved to {count} entity candidates',
                        candidates=[term],
                    )
                )

    # Rule 4: Query too broad (no meaningful keywords after extraction)
    if not search_plan.keywords or all(len(k) <= 1 for k in search_plan.keywords):
        items.append(
            AmbiguityItem(
                type=AmbiguityType.QUERY_TOO_BROAD,
                severity="low",
                reason="query yielded no meaningful keywords after normalization",
                candidates=[],
            )
        )

    # Trim to max items, keeping highest severity first
    if len(items) > _MAX_ITEMS:
        severity_order = {"high": 0, "medium": 1, "low": 2}
        items.sort(key=lambda x: severity_order.get(x.severity, 3))
        items = items[:_MAX_ITEMS]

    return AmbiguityReport(has_ambiguity=len(items) > 0, items=items)
