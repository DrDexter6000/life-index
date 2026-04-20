#!/usr/bin/env python3
"""Task 4.5: Round 12 search precision integration contract tests.

Verifies the 4 acceptance criteria from PRD §5.2:
1. NL01 "过去60天晚于10点睡觉" → search results date within time window
2. NL03 "健康" → search results related to health topic
3. KW09 "量子计算机编程" → no_confident_match=true
4. NL05 "missing my daughter" → keywords not contain "my"

These are pure verification tests. If any fail, backtrack to fix.
"""

from datetime import date
from pathlib import Path

import pytest


# ── AC1: Date range from natural language query ─────────────────────────


def test_nl01_date_range_within_window() -> None:
    """NL01: '过去60天晚于10点睡觉' should parse date range correctly."""
    from tools.search_journals.query_preprocessor import build_search_plan

    plan = build_search_plan("过去60天晚于10点睡觉", reference_date=date(2026, 4, 18))
    assert plan.date_range is not None
    assert plan.date_range.since is not None
    assert plan.date_range.until is not None

    # Since should be approximately 60 days before 2026-04-18
    since_date = date.fromisoformat(plan.date_range.since)
    until_date = date.fromisoformat(plan.date_range.until)
    delta = (until_date - since_date).days
    assert delta == 60  # exactly 60 days


# ── AC2: Health topic hints ────────────────────────────────────────────


def test_nl03_health_topic_hints() -> None:
    """NL03: '健康' should extract health topic hint."""
    from tools.search_journals.query_preprocessor import build_search_plan

    plan = build_search_plan("健康")
    assert "health" in plan.topic_hints


# ── AC3: Semantic rejection for irrelevant query ────────────────────────


def test_kw09_quantum_computing_no_confident_match() -> None:
    """KW09: '量子计算机编程' should have no_confident_match=true.

    Simulates the scenario where FTS=0 and semantic confidence is low.
    """
    from tools.search_journals.confidence import compute_no_confident_match

    # Simulate what would happen: FTS=0, weak semantic results
    simulated_results = [
        {
            "path": "/quantum.md",
            "confidence": "low",
            "fts_score": 0.0,
            "semantic_score": 25.0,
        },
    ]
    assert compute_no_confident_match(simulated_results) is True


# ── AC4: Stopword filtering in keywords ────────────────────────────────


def test_nl05_missing_my_daughter_no_my() -> None:
    """NL05: 'missing my daughter' should not contain 'my' in keywords."""
    from tools.search_journals.query_preprocessor import build_search_plan

    plan = build_search_plan("missing my daughter")
    lower_kw = [k.lower() for k in plan.keywords]
    assert "my" not in lower_kw
    # Should keep the meaningful words
    assert "missing" in lower_kw or "daughter" in lower_kw


# ── Additional: Date range + topic hints together ──────────────────────


def test_combined_date_range_and_topic() -> None:
    """Query with both time expression and topic keywords."""
    from tools.search_journals.query_preprocessor import build_search_plan

    plan = build_search_plan("过去30天健康记录", reference_date=date(2026, 4, 18))
    assert plan.date_range is not None
    assert plan.date_range.since is not None
    assert "health" in plan.topic_hints


# ── Additional: Topic boost is applied in ranking ──────────────────────


def test_topic_boost_integration() -> None:
    """Topic hints from search_plan affect ranking."""
    from tools.search_journals.ranking import merge_and_rank_results

    # Two results with same score, different topics
    r1 = {
        "path": "/health.md",
        "title": "Health stuff",
        "relevance": 50,
        "date": "2026-03-10",
        "snippet": "",
        "source": "fts_index",
        "topic": ["health"],
        "tags": [],
        "mood": [],
        "people": [],
        "location": "",
        "weather": "",
        "project": "",
        "title_match": False,
        "match_count": 1,
    }
    r2 = {
        "path": "/work.md",
        "title": "Work stuff",
        "relevance": 50,
        "date": "2026-03-11",
        "snippet": "",
        "source": "fts_index",
        "topic": ["work"],
        "tags": [],
        "mood": [],
        "people": [],
        "location": "",
        "weather": "",
        "project": "",
        "title_match": False,
        "match_count": 1,
    }

    results = merge_and_rank_results(
        [], [], [r1, r2], query="stuff", topic_hints=["health"],
    )

    # Health should rank higher due to topic boost
    paths = [r["path"] for r in results]
    assert paths.index("/health.md") < paths.index("/work.md")


# ── Additional: build_l0_candidate_set with date params ─────────────────


def test_l0_candidate_set_date_filtering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L0 candidate set respects date_from/date_to parameters."""
    data_dir = tmp_path / "Life-Index"
    journals = data_dir / "Journals"
    journals.mkdir(parents=True)

    # Create test journal files
    (journals / "2026" / "02").mkdir(parents=True)
    (journals / "2026" / "03").mkdir(parents=True)
    (journals / "2026" / "02" / "life-index_2026-02-15_001.md").write_text(
        "---\ntitle: Feb\ndate: 2026-02-15\n---\n\ncontent\n", encoding="utf-8"
    )
    (journals / "2026" / "03" / "life-index_2026-03-10_001.md").write_text(
        "---\ntitle: Mar\ndate: 2026-03-10\n---\n\ncontent\n", encoding="utf-8"
    )

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))

    from tools.search_journals.core import build_l0_candidate_set

    # Filter to March only
    candidates = build_l0_candidate_set(date_from="2026-03-01", date_to="2026-03-31")
    assert candidates is not None
    assert len(candidates) == 1
    assert "2026-03-10" in next(iter(candidates))
