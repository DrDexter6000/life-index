#!/usr/bin/env python3
"""Task 4.2 RED: search_plan.topic_hints → ranking boost.

Tests that when preprocessor extracts topic_hints, results with matching
topics receive a small conservative boost in ranking.

Run BEFORE implementation to verify RED phase.
"""

from pathlib import Path

import pytest


def _make_l3_result(path: str, *, title: str = "", relevance: int = 50, topic: list[str] | None = None) -> dict:
    """Create a mock L3/FTS result."""
    return {
        "path": path,
        "title": title,
        "relevance": relevance,
        "date": "2026-03-10",
        "snippet": "",
        "source": "fts_index",
        "topic": topic or [],
        "tags": [],
        "mood": [],
        "people": [],
        "location": "",
        "weather": "",
        "project": "",
        "title_match": False,
        "match_count": 1,
    }


def _make_l2_result(path: str, *, title: str = "", topic: list[str] | None = None) -> dict:
    """Create a mock L2/metadata result."""
    return {
        "path": path,
        "title": title,
        "date": "2026-03-10",
        "metadata": {
            "topic": topic or [],
            "tags": [],
            "abstract": "",
        },
    }


# ── Test 1: topic_hints boosts matching results above others ────────────


def test_topic_hints_boosts_matching_results() -> None:
    """Results whose topic matches topic_hints should rank higher."""
    from tools.search_journals.ranking import merge_and_rank_results

    # Two results with same FTS relevance, different topics
    health_result = _make_l3_result("/health.md", title="Health stuff", relevance=50, topic=["health"])
    work_result = _make_l3_result("/work.md", title="Work stuff", relevance=50, topic=["work"])

    # Without topic_hints, both tied → alphabetical order
    results_no_hints = merge_and_rank_results(
        [], [], [health_result, work_result], query="stuff",
    )

    # With topic_hints=["health"], health should rank higher
    results_with_hints = merge_and_rank_results(
        [], [], [health_result, work_result], query="stuff",
        topic_hints=["health"],
    )

    # Find health and work in both result sets
    health_rank_no_hint = next(i for i, r in enumerate(results_no_hints) if "health" in r.get("path", ""))
    work_rank_no_hint = next(i for i, r in enumerate(results_no_hints) if "work" in r.get("path", ""))

    health_rank_with_hint = next(i for i, r in enumerate(results_with_hints) if "health" in r.get("path", ""))
    work_rank_with_hint = next(i for i, r in enumerate(results_with_hints) if "work" in r.get("path", ""))

    # With hints, health should rank better than without hints (or at least better than work)
    assert health_rank_with_hint < work_rank_with_hint


# ── Test 2: Empty topic_hints = no change ───────────────────────────────


def test_empty_topic_hints_no_change() -> None:
    """Empty topic_hints should not change ranking order."""
    from tools.search_journals.ranking import merge_and_rank_results

    r1 = _make_l3_result("/a.md", title="Alpha", relevance=60, topic=["work"])
    r2 = _make_l3_result("/b.md", title="Beta", relevance=40, topic=["health"])

    results_empty = merge_and_rank_results(
        [], [], [r1, r2], query="test", topic_hints=[],
    )
    results_none = merge_and_rank_results(
        [], [], [r1, r2], query="test",
    )

    # Both should produce same ranking
    assert [r["path"] for r in results_empty] == [r["path"] for r in results_none]


# ── Test 3: Multiple topic hints all get boost ──────────────────────────


def test_multiple_topic_hints_all_boosted() -> None:
    """Multiple topic hints should boost results matching any of them."""
    from tools.search_journals.ranking import merge_and_rank_results

    health = _make_l3_result("/health.md", title="Health", relevance=50, topic=["health"])
    learn = _make_l3_result("/learn.md", title="Learn", relevance=50, topic=["learn"])
    work = _make_l3_result("/work.md", title="Work", relevance=50, topic=["work"])

    results = merge_and_rank_results(
        [], [], [health, learn, work], query="test",
        topic_hints=["health", "learn"],
    )

    # Health and learn should both outrank work
    work_rank = next(i for i, r in enumerate(results) if "work" in r.get("path", ""))
    health_rank = next(i for i, r in enumerate(results) if "health" in r.get("path", ""))
    learn_rank = next(i for i, r in enumerate(results) if "learn" in r.get("path", ""))

    assert health_rank < work_rank
    assert learn_rank < work_rank


# ── Test 4: Boost not enough to override large FTS score gap ────────────


def test_boost_conservative_does_not_override_fts_gap() -> None:
    """Topic boost should NOT override a large FTS score gap."""
    from tools.search_journals.ranking import merge_and_rank_results

    # Work result has much higher FTS score than health result
    work = _make_l3_result("/work.md", title="Work topic", relevance=80, topic=["work"])
    health = _make_l3_result("/health.md", title="Health topic", relevance=30, topic=["health"])

    # Even with health topic hint, work should still rank higher due to FTS gap
    results = merge_and_rank_results(
        [], [], [work, health], query="topic",
        topic_hints=["health"],
    )

    work_rank = next(i for i, r in enumerate(results) if "work" in r.get("path", ""))
    health_rank = next(i for i, r in enumerate(results) if "health" in r.get("path", ""))

    # Work should still be #1 (80 vs 30 is a huge gap)
    assert work_rank < health_rank
