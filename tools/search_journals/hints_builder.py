"""Round 11 — Hints Builder.

Builds invocation-time hints based on the search plan and ambiguity report.
Hints are short, contextual tips for the caller — not a second SKILL.md.
"""

from __future__ import annotations

from .query_types import (
    AmbiguityReport,
    AmbiguityType,
    HintItem,
    IntentType,
    SearchPlan,
)

# Maximum hints per call
_MAX_HINTS = 5

# Maximum message length
_MAX_MESSAGE_LEN = 120


def build_hints(
    search_plan: SearchPlan,
    ambiguity: AmbiguityReport,
) -> list[HintItem]:
    """Build invocation-time hints for a search query.

    Args:
        search_plan: The structured query understanding.
        ambiguity: The ambiguity report for this query.

    Returns:
        List of HintItem, at most _MAX_HINTS items.
    """
    hints: list[HintItem] = []

    # Hint 1: Retrieval boundary for aggregation intents
    if search_plan.intent_type in {IntentType.COUNT, IntentType.COMPARE, IntentType.SUMMARIZE}:
        hints.append(
            HintItem(
                type="retrieval_boundary",
                severity="high",
                message="Search returns an evidence set, not the final answer, for count/compare queries.",
            )
        )
        hints.append(
            HintItem(
                type="refinement_suggestion",
                severity="medium",
                message="If the user wants an exact count, inspect matched entries one by one.",
            )
        )

    # Hint 2: Time range was parsed
    if search_plan.date_range is not None and search_plan.date_range.source == "relative_time_parse":
        since = search_plan.date_range.since or "?"
        until = search_plan.date_range.until or "?"
        msg = f"Query time range was parsed as {since} to {until}."
        if len(msg) > _MAX_MESSAGE_LEN:
            msg = msg[:_MAX_MESSAGE_LEN - 3] + "..."
        hints.append(
            HintItem(
                type="time_range_parsed",
                severity="low",
                message=msg,
            )
        )

    # Hint 3: Entity hints suggest expanded search
    if search_plan.entity_hints_used:
        count = len(search_plan.entity_hints_used)
        hints.append(
            HintItem(
                type="entity_expansion_applied",
                severity="low",
                message=f"Query was expanded with {count} entity hint(s) from the entity graph.",
            )
        )

    # Hint 4: Topic hints detected
    if search_plan.topic_hints:
        topics = ", ".join(search_plan.topic_hints)
        msg = f"Detected topic hints: {topics}. Results may be filtered accordingly."
        if len(msg) > _MAX_MESSAGE_LEN:
            msg = msg[:_MAX_MESSAGE_LEN - 3] + "..."
        hints.append(
            HintItem(
                type="topic_detected",
                severity="low",
                message=msg,
            )
        )

    # Trim to max hints, keeping highest severity first
    if len(hints) > _MAX_HINTS:
        severity_order = {"high": 0, "medium": 1, "low": 2}
        hints.sort(key=lambda h: severity_order.get(h.severity, 3))
        hints = hints[:_MAX_HINTS]

    return hints
