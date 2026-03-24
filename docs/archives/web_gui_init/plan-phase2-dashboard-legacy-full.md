# Phase 2: Dashboard — TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dashboard renders all 8 components (heatmap, stats cards, on-this-day, streak milestones, mood frequency, topic distribution, tag cloud, people graph) with real data from `metadata_cache`.

**Architecture:** `web/services/stats.py` aggregates all dashboard data from `metadata_cache.get_all_cached_metadata()` in a single pass, returning a typed `DashboardStats` dataclass. `web/routes/dashboard.py` exposes `GET /` calling the stats service, rendering `dashboard.html`. The template inherits `base.html` and uses ECharts (CDN) for all 5 chart types. Each component implements its degradation strategy per design-spec §5.1.

**Tech Stack:** Python 3.11+ (dataclasses, collections, datetime), ECharts (CDN), Jinja2, Alpine.js (milestone animations)

**Spec Reference:** `docs/web-gui/design-spec.md` v1.4 — §5.1, §6.1

---

## Phase Scope

| Task | Component | Difficulty | Time Est. |
|:--|:--|:--|:--|
| Task 7 | `web/services/stats.py` — Stats data aggregation service | Hard | 45 min |
| Task 8 | `web/routes/dashboard.py` + `web/templates/dashboard.html` — Dashboard route and template | Hard | 60 min |

**Dependencies:** Task 7 depends on Phase 1 Task 3 (web/ package exists). Task 8 depends on Phase 1 Task 6 (base.html) + Task 7 (stats service).

## Split Navigation

- Task 7 focused doc: [plan-phase2a-stats-service.md](plan-phase2a-stats-service.md)
- Task 8 focused doc: [plan-phase2b-dashboard-route-template.md](plan-phase2b-dashboard-route-template.md)

> 本文件暂时保留完整 legacy TDD 细节；新的执行入口应优先查看上述 split subplans。

---

## Prerequisites

Before starting, verify Phase 1 is complete:

```bash
python -m pytest tests/unit/test_web_scaffold.py -v  # All Phase 1 tests pass
life-index serve &                                     # Server starts
curl -s http://127.0.0.1:8765/api/health               # {"status":"ok",...}
kill %1
```

Read these files (required context):
- `docs/web-gui/design-spec.md` §5.1 — Dashboard components, degradation strategies, milestone thresholds
- `tools/lib/metadata_cache.py` line 251–298 — `get_all_cached_metadata()` return structure
- `web/app.py` — `create_app()` factory, `app.state.templates` pattern
- `web/templates/base.html` — Block names (`{% block title %}`, `{% block content %}`)
- `web/config.py` — Path constants

### Key Data Contract

`get_all_cached_metadata()` returns `List[Dict]` where each dict has:

```python
{
    "file_path": "C:/Users/.../Documents/Life-Index/Journals/2026/03/life-index_2026-03-07_001.md",  # str
    "date": "2026-03-07",           # YYYY-MM-DD str
    "title": "日志标题",             # str
    "location": "Lagos, Nigeria",   # str | None
    "weather": "晴天 28°C",         # str | None
    "topic": ["work", "create"],    # List[str] (JSON-parsed)
    "project": "LifeIndex",         # str | None
    "tags": ["重构", "优化"],        # List[str] (JSON-parsed)
    "mood": ["专注", "充实"],        # List[str] (JSON-parsed)
    "people": ["团团"],              # List[str] (JSON-parsed)
    "abstract": "100字内摘要",       # str | None
}
```

**Important limitation:** The metadata cache does NOT contain `content` or `word_count`. The "总字数" stat (per §5.1 "基础统计") requires reading actual journal files. The stats service will use `frontmatter.parse_journal_file()` to read the `_body` field for word count calculation. This is acceptable for typical scale (100–500 journals per §6.1) but may need caching for 2000+ journals.

---

## Task 7: Stats Service (`web/services/stats.py`)

**Files:**
- Create: `web/services/stats.py`
- Test: `tests/unit/test_web_dashboard.py` (create)

**Difficulty:** Hard (~45 min)

**Acceptance Criteria:**
1. `compute_dashboard_stats()` returns a `DashboardStats` dataclass with all 8 component data sets
2. Stats are computed from `metadata_cache.get_all_cached_metadata()` — no direct filesystem access except for word count
3. Word count uses `frontmatter.parse_journal_file()` to read `_body` from each journal
4. Streak calculation correctly handles non-consecutive dates and returns the longest consecutive run
5. Current streak (from today backwards) is also computed
6. "On this day" (`on_this_day`) returns journals matching current month-day, sorted by year descending
7. Milestone detection returns the highest reached milestone from `[7, 30, 100, 365]`
8. Mood frequency returns per-period (weekly/monthly) stacked bar chart data with Top 5–8 moods + "其他"
9. Topic distribution returns pie chart data `[{name, value}]`
10. Tag cloud returns frequency data `[{name, value}]`
11. People graph returns nodes `[{name, count}]` + edges `[{source, target, weight}]` from co-occurrence
12. Heatmap returns `{date_str: count}` mapping for all dates
13. Empty metadata list produces valid zero/empty results for all components (no crashes)
14. Journals with missing optional fields (mood=[], tags=[], people=[]) are handled gracefully

**Subagent Governance:**
- MUST DO: Use `dataclasses.dataclass` for `DashboardStats` and sub-structures — NOT plain dicts
- MUST DO: Import `get_all_cached_metadata` from `tools.lib.metadata_cache`
- MUST DO: Import `parse_journal_file` from `tools.lib.frontmatter` for word count
- MUST DO: Import path constants from `tools.lib.config` (JOURNALS_DIR)
- MUST DO: Process all metadata in a single pass where possible (iterate `entries` once for multiple aggregations)
- MUST DO: Use `datetime.date.today()` for "on this day" and streak calculations (injectable for testing)
- MUST DO: Handle all list fields defensively — `mood`, `tags`, `people`, `topic` may be empty lists
- MUST DO: Use `collections.Counter` for frequency calculations
- MUST DO: All function signatures must have complete type annotations
- MUST DO: Follow snake_case naming for all functions and variables
- MUST NOT DO: Import or call any `web/routes/` code — this is a pure service module
- MUST NOT DO: Access the filesystem directly for metadata — use `get_all_cached_metadata()` only
- MUST NOT DO: Raise exceptions on empty data — return zero/empty defaults
- MUST NOT DO: Hardcode dates in logic — use `datetime.date.today()` (parameterized for testing)
- MUST NOT DO: Use `pandas` or `numpy` — standard library only for aggregation
- MUST NOT DO: Modify any `tools/` module code

**Error Handling:**
- If `get_all_cached_metadata()` raises (e.g., DB corruption), catch the exception, log a warning, and return empty `DashboardStats`
- If `parse_journal_file()` fails for a specific journal (file deleted, corrupt), skip that journal's word count and continue
- If no metadata exists (fresh install), all stats return zero/empty — no error raised

**TDD Steps:**

- [ ] **Step 1: Write the failing tests — dataclass structure**

Create `tests/unit/test_web_dashboard.py`:

```python
"""Tests for Web GUI Dashboard — Phase 2 (Tasks 7–8)."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import patch, MagicMock

import pytest


# ── Fixtures ──────────────────────────────────────────────────

def _make_entry(
    *,
    date: str = "2026-03-07",
    title: str = "Test Journal",
    topic: list[str] | None = None,
    mood: list[str] | None = None,
    tags: list[str] | None = None,
    people: list[str] | None = None,
    abstract: str = "Test abstract",
    location: str | None = "Lagos, Nigeria",
    weather: str | None = "Sunny 28°C",
    project: str | None = None,
    file_path: str | None = None,
) -> dict[str, Any]:
    """Factory for metadata cache entries."""
    if file_path is None:
        file_path = f"Journals/2026/03/life-index_{date}_001.md"
    return {
        "file_path": file_path,
        "date": date,
        "title": title,
        "topic": topic or ["work"],
        "mood": mood or [],
        "tags": tags or [],
        "people": people or [],
        "abstract": abstract,
        "location": location,
        "weather": weather,
        "project": project,
    }


SAMPLE_ENTRIES: list[dict[str, Any]] = [
    _make_entry(
        date="2026-03-01",
        title="Day 1",
        topic=["work"],
        mood=["专注"],
        tags=["python"],
        people=["团团"],
    ),
    _make_entry(
        date="2026-03-02",
        title="Day 2",
        topic=["think"],
        mood=["平静", "专注"],
        tags=["python", "反思"],
        people=["团团", "妻子"],
    ),
    _make_entry(
        date="2026-03-03",
        title="Day 3",
        topic=["work", "create"],
        mood=["兴奋"],
        tags=["项目"],
        people=["妻子"],
    ),
]


# ── Task 7: Stats Service ─────────────────────────────────────


class TestDashboardStatsDataclass:
    """DashboardStats dataclass has all required fields."""

    def test_dataclass_importable(self) -> None:
        """DashboardStats can be imported from web.services.stats."""
        from web.services.stats import DashboardStats
        import dataclasses
        assert dataclasses.is_dataclass(DashboardStats)

    def test_dataclass_has_all_fields(self) -> None:
        """DashboardStats contains fields for all 8 dashboard components."""
        from web.services.stats import DashboardStats
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(DashboardStats)}
        required = {
            "total_journals",
            "total_words",
            "longest_streak",
            "current_streak",
            "month_journals",
            "most_frequent_mood",
            "most_active_topic",
            "on_this_day",
            "milestone",
            "mood_frequency",
            "topic_distribution",
            "tag_cloud",
            "people_graph",
            "heatmap",
        }
        assert required.issubset(field_names), (
            f"Missing fields: {required - field_names}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_web_dashboard.py::TestDashboardStatsDataclass -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'web.services.stats'`.

- [ ] **Step 3: Write the failing tests — compute_dashboard_stats()**

Append to `tests/unit/test_web_dashboard.py`:

```python
class TestComputeDashboardStats:
    """Test compute_dashboard_stats() with mock metadata."""

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_returns_dashboard_stats(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Returns a DashboardStats instance."""
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 1500
        from web.services.stats import compute_dashboard_stats, DashboardStats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        assert isinstance(result, DashboardStats)

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_total_journals(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """total_journals equals the number of entries."""
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        assert result.total_journals == 3

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_month_journals(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """month_journals counts journals in the current month."""
        entries = SAMPLE_ENTRIES + [
            _make_entry(date="2026-02-15", title="Feb entry")
        ]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        assert result.month_journals == 3  # Only March entries

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_empty_entries(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Empty metadata produces zero/empty results."""
        mock_meta.return_value = []
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        assert result.total_journals == 0
        assert result.total_words == 0
        assert result.longest_streak == 0
        assert result.current_streak == 0
        assert result.month_journals == 0
        assert result.most_frequent_mood is None
        assert result.most_active_topic is None
        assert result.on_this_day == []
        assert result.milestone is None
        assert result.mood_frequency == {}
        assert result.topic_distribution == []
        assert result.tag_cloud == []
        assert result.people_graph == {"nodes": [], "edges": []}
        assert result.heatmap == {}


class TestStreakCalculation:
    """Test consecutive-day streak logic."""

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_consecutive_streak(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Three consecutive days → streak = 3."""
        mock_meta.return_value = SAMPLE_ENTRIES  # Mar 1, 2, 3
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        assert result.longest_streak == 3
        assert result.current_streak == 3

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_broken_streak(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Gap in dates → streak breaks."""
        entries = [
            _make_entry(date="2026-03-01"),
            _make_entry(date="2026-03-02"),
            # Mar 03 missing
            _make_entry(date="2026-03-04"),
            _make_entry(date="2026-03-05"),
            _make_entry(date="2026-03-06"),
        ]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 6))
        assert result.longest_streak == 3  # Mar 4, 5, 6
        assert result.current_streak == 3

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_multiple_entries_same_day(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Multiple journals on the same day count as one day for streak."""
        entries = [
            _make_entry(date="2026-03-01", file_path="a.md"),
            _make_entry(date="2026-03-01", file_path="b.md"),
            _make_entry(date="2026-03-02", file_path="c.md"),
        ]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 2))
        assert result.longest_streak == 2

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_current_streak_not_today(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Current streak is 0 if the latest entry is not today or yesterday."""
        entries = [
            _make_entry(date="2026-03-01"),
            _make_entry(date="2026-03-02"),
        ]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        # Today is March 10 — gap of 8 days
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 10))
        assert result.current_streak == 0
        assert result.longest_streak == 2


class TestOnThisDay:
    """Test 那年今日 component."""

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_matches_month_day(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Returns journals from same month-day in previous years."""
        entries = [
            _make_entry(date="2024-03-07", title="Two years ago"),
            _make_entry(date="2025-03-07", title="Last year"),
            _make_entry(date="2025-03-08", title="Wrong day"),
            _make_entry(date="2026-03-07", title="Today"),
        ]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 7))
        # Should include all March 7th entries EXCEPT current year
        titles = [e["title"] for e in result.on_this_day]
        assert "Two years ago" in titles
        assert "Last year" in titles
        assert "Wrong day" not in titles
        assert "Today" not in titles  # Current year excluded

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_sorted_by_year_desc(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """On-this-day entries are sorted by year descending."""
        entries = [
            _make_entry(date="2023-03-07", title="Three years ago"),
            _make_entry(date="2025-03-07", title="Last year"),
            _make_entry(date="2024-03-07", title="Two years ago"),
        ]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 7))
        years = [e["date"][:4] for e in result.on_this_day]
        assert years == ["2025", "2024", "2023"]

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_no_matches(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Returns empty list when no historical match exists."""
        entries = [_make_entry(date="2026-03-07")]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 7))
        assert result.on_this_day == []


class TestMilestone:
    """Test streak milestone detection."""

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_milestone_7(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """7-day streak triggers milestone 7."""
        entries = [
            _make_entry(date=f"2026-03-{d:02d}") for d in range(1, 8)
        ]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 7))
        assert result.milestone == 7

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_milestone_30(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """30-day streak triggers milestone 30."""
        entries = [
            _make_entry(
                date=(datetime.date(2026, 2, 1) + datetime.timedelta(days=i)).isoformat(),
                file_path=f"j_{i}.md",
            )
            for i in range(30)
        ]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(
            today=datetime.date(2026, 2, 1) + datetime.timedelta(days=29)
        )
        assert result.milestone == 30

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_no_milestone(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Streak < 7 triggers no milestone."""
        entries = [
            _make_entry(date=f"2026-03-{d:02d}") for d in range(1, 6)
        ]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 5))
        assert result.milestone is None


class TestMoodFrequency:
    """Test mood stacked bar chart data."""

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_mood_grouped_by_month(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Mood data is grouped by period with mood counts."""
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        # mood_frequency is a dict: {period_key: {mood: count}}
        assert isinstance(result.mood_frequency, dict)
        # SAMPLE_ENTRIES all in 2026-03
        assert len(result.mood_frequency) > 0

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_empty_mood(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Entries with no mood field are skipped."""
        entries = [_make_entry(mood=[])]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 7))
        # All periods should have empty mood dicts (or no entries)
        for period_data in result.mood_frequency.values():
            assert sum(period_data.values()) == 0 or period_data == {}


class TestTopicDistribution:
    """Test topic pie chart data."""

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_topic_counts(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Topic distribution returns {name, value} pairs."""
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        assert isinstance(result.topic_distribution, list)
        # Each item should have name and value
        for item in result.topic_distribution:
            assert "name" in item
            assert "value" in item
        # "work" appears in 2 entries
        work_items = [i for i in result.topic_distribution if i["name"] == "work"]
        assert len(work_items) == 1
        assert work_items[0]["value"] == 2


class TestTagCloud:
    """Test tag cloud frequency data."""

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_tag_frequencies(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Tag cloud returns {name, value} pairs with correct counts."""
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        assert isinstance(result.tag_cloud, list)
        # "python" appears in 2 entries
        python_items = [i for i in result.tag_cloud if i["name"] == "python"]
        assert len(python_items) == 1
        assert python_items[0]["value"] == 2


class TestPeopleGraph:
    """Test people co-occurrence relationship graph data."""

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_people_nodes(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """People graph has correct nodes."""
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        nodes = result.people_graph["nodes"]
        names = {n["name"] for n in nodes}
        assert "团团" in names
        assert "妻子" in names

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_people_co_occurrence_edges(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Co-occurring people in same journal create edges."""
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        edges = result.people_graph["edges"]
        # Day 2 has 团团 + 妻子 → edge between them
        assert len(edges) > 0
        edge_pairs = {(e["source"], e["target"]) for e in edges}
        assert ("团团", "妻子") in edge_pairs or ("妻子", "团团") in edge_pairs

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_people_node_counts(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Each node has an appearance count."""
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        nodes = {n["name"]: n["count"] for n in result.people_graph["nodes"]}
        assert nodes["团团"] == 2   # Day 1 + Day 2
        assert nodes["妻子"] == 2   # Day 2 + Day 3


class TestHeatmap:
    """Test writing heatmap data."""

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_heatmap_date_counts(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """Heatmap maps dates to journal counts."""
        entries = SAMPLE_ENTRIES + [
            _make_entry(date="2026-03-01", file_path="extra.md"),
        ]
        mock_meta.return_value = entries
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        assert result.heatmap["2026-03-01"] == 2
        assert result.heatmap["2026-03-02"] == 1
        assert result.heatmap["2026-03-03"] == 1


class TestMostFrequent:
    """Test most-frequent mood and most-active topic."""

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_most_frequent_mood(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """most_frequent_mood returns the mood with highest count."""
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        # "专注" appears in Day 1 and Day 2 → count 2
        assert result.most_frequent_mood == "专注"

    @patch("web.services.stats.get_all_cached_metadata")
    @patch("web.services.stats._compute_total_words")
    def test_most_active_topic(
        self, mock_words: MagicMock, mock_meta: MagicMock
    ) -> None:
        """most_active_topic returns the topic with highest count."""
        mock_meta.return_value = SAMPLE_ENTRIES
        mock_words.return_value = 0
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        # "work" appears in Day 1 and Day 3 → count 2
        assert result.most_active_topic == "work"


class TestStatsServiceErrorHandling:
    """Test graceful degradation on errors."""

    @patch("web.services.stats.get_all_cached_metadata")
    def test_metadata_exception_returns_empty(
        self, mock_meta: MagicMock
    ) -> None:
        """Database error produces empty DashboardStats, no exception."""
        mock_meta.side_effect = Exception("DB corrupted")
        from web.services.stats import compute_dashboard_stats
        result = compute_dashboard_stats(today=datetime.date(2026, 3, 3))
        assert result.total_journals == 0
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_dashboard.py -v
```

Expected: ALL FAIL — `ModuleNotFoundError: No module named 'web.services.stats'`.

- [ ] **Step 5: Implement `web/services/stats.py`**

```python
"""Dashboard statistics aggregation service.

Reads all journal metadata from metadata_cache and computes stats
for the 8 Dashboard components (per design-spec §5.1).

This service NEVER accesses the filesystem directly for metadata.
Word count requires reading journal files via frontmatter.parse_journal_file().
"""

from __future__ import annotations

import datetime
import logging
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Optional

from tools.lib.config import JOURNALS_DIR
from tools.lib.metadata_cache import get_all_cached_metadata

logger = logging.getLogger(__name__)

# Milestone thresholds per design-spec §5.1
MILESTONE_THRESHOLDS: list[int] = [7, 30, 100, 365]


@dataclass
class DashboardStats:
    """Aggregated statistics for all 8 Dashboard components."""

    # Basic stats cards
    total_journals: int = 0
    total_words: int = 0
    longest_streak: int = 0
    current_streak: int = 0
    month_journals: int = 0
    most_frequent_mood: Optional[str] = None
    most_active_topic: Optional[str] = None

    # On This Day (那年今日) — list of entry dicts, sorted by year desc
    on_this_day: list[dict[str, Any]] = field(default_factory=list)

    # Milestone — highest reached threshold, or None
    milestone: Optional[int] = None

    # Mood frequency — {period_key: {mood: count}}
    mood_frequency: dict[str, dict[str, int]] = field(default_factory=dict)

    # Topic distribution — [{name, value}]
    topic_distribution: list[dict[str, Any]] = field(default_factory=list)

    # Tag cloud — [{name, value}]
    tag_cloud: list[dict[str, Any]] = field(default_factory=list)

    # People graph — {nodes: [{name, count}], edges: [{source, target, weight}]}
    people_graph: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {"nodes": [], "edges": []}
    )

    # Heatmap — {date_str: count}
    heatmap: dict[str, int] = field(default_factory=dict)


def _compute_total_words(entries: list[dict[str, Any]]) -> int:
    """Compute total word count by reading journal file bodies.

    Uses frontmatter.parse_journal_file() to read content.
    Skips files that cannot be read (deleted, corrupt, etc.).

    Args:
        entries: Metadata entries with absolute `file_path` keys.

    Returns:
        Total character count across all readable journal bodies.
    """
    from tools.lib.frontmatter import parse_journal_file

    total = 0
    for entry in entries:
        try:
            file_path = Path(entry["file_path"])
            parsed = parse_journal_file(file_path)
            body = parsed.get("_body", "")
            if body:
                total += len(body)
        except Exception:
            # File missing, corrupt, or unreadable — skip
            continue
    return total


def _compute_streaks(
    dates: list[datetime.date], today: datetime.date
) -> tuple[int, int]:
    """Compute longest streak and current streak from sorted unique dates.

    Args:
        dates: Sorted list of unique dates (ascending).
        today: Reference date for current streak calculation.

    Returns:
        Tuple of (longest_streak, current_streak).
    """
    if not dates:
        return 0, 0

    # Compute all streaks
    streaks: list[int] = []
    current_run = 1

    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            current_run += 1
        else:
            streaks.append(current_run)
            current_run = 1
    streaks.append(current_run)

    longest = max(streaks) if streaks else 0

    # Current streak: count backwards from today (or yesterday)
    if dates[-1] == today or dates[-1] == today - datetime.timedelta(days=1):
        current = 1
        for i in range(len(dates) - 2, -1, -1):
            if (dates[i + 1] - dates[i]).days == 1:
                current += 1
            else:
                break
    else:
        current = 0

    return longest, current


def _detect_milestone(current_streak: int) -> Optional[int]:
    """Return the highest milestone reached by the current streak.

    Milestones: 7, 30, 100, 365 (per §5.1).

    Args:
        current_streak: Current consecutive days count.

    Returns:
        Highest milestone reached, or None if streak < 7.
    """
    reached = [m for m in MILESTONE_THRESHOLDS if current_streak >= m]
    return reached[-1] if reached else None


def _compute_mood_frequency(
    entries: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Compute mood frequency grouped by month.

    Groups by YYYY-MM period. For each period, counts mood appearances.

    Args:
        entries: Metadata entries.

    Returns:
        Dict mapping period keys to {mood: count} dicts.
    """
    periods: dict[str, Counter[str]] = {}
    for entry in entries:
        moods = entry.get("mood", [])
        if not moods:
            continue
        date_str = entry.get("date", "")
        if len(date_str) < 7:
            continue
        period = date_str[:7]  # YYYY-MM
        if period not in periods:
            periods[period] = Counter()
        for m in moods:
            periods[period][m] += 1

    return {k: dict(v) for k, v in sorted(periods.items())}


def _compute_people_graph(
    entries: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Compute people co-occurrence graph.

    Nodes: each person with appearance count.
    Edges: pairs of people appearing in the same journal, with co-occurrence weight.

    Args:
        entries: Metadata entries.

    Returns:
        Dict with "nodes" and "edges" lists.
    """
    person_count: Counter[str] = Counter()
    co_occurrence: Counter[tuple[str, str]] = Counter()

    for entry in entries:
        people = entry.get("people", [])
        if not people:
            continue
        for person in people:
            person_count[person] += 1
        # Co-occurrence: all pairs in same journal
        for a, b in combinations(sorted(people), 2):
            co_occurrence[(a, b)] += 1

    nodes = [{"name": name, "count": count} for name, count in person_count.most_common()]
    edges = [
        {"source": pair[0], "target": pair[1], "weight": weight}
        for pair, weight in co_occurrence.most_common()
    ]

    return {"nodes": nodes, "edges": edges}


def compute_dashboard_stats(
    today: Optional[datetime.date] = None,
) -> DashboardStats:
    """Compute all dashboard statistics from metadata cache.

    Reads metadata via get_all_cached_metadata() and aggregates into
    DashboardStats. Handles empty data and errors gracefully.

    Args:
        today: Override date for testing (defaults to datetime.date.today()).

    Returns:
        Populated DashboardStats dataclass.
    """
    if today is None:
        today = datetime.date.today()

    # Fetch metadata — graceful degradation on error
    try:
        entries = get_all_cached_metadata()
    except Exception:
        logger.warning("Failed to read metadata cache; returning empty stats")
        return DashboardStats()

    if not entries:
        return DashboardStats()

    # ── Single-pass aggregations ──────────────────────────────

    all_moods: Counter[str] = Counter()
    all_topics: Counter[str] = Counter()
    all_tags: Counter[str] = Counter()
    heatmap: Counter[str] = Counter()
    month_key = f"{today.year}-{today.month:02d}"
    month_count = 0
    on_this_day: list[dict[str, Any]] = []
    today_md = f"{today.month:02d}-{today.day:02d}"
    date_set: set[datetime.date] = set()

    for entry in entries:
        date_str = entry.get("date", "")

        # Heatmap
        heatmap[date_str] += 1

        # Parse date
        try:
            entry_date = datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            continue

        date_set.add(entry_date)

        # Month count
        if date_str.startswith(month_key):
            month_count += 1

        # On This Day (same month-day, different year)
        entry_md = f"{entry_date.month:02d}-{entry_date.day:02d}"
        if entry_md == today_md and entry_date.year != today.year:
            on_this_day.append(entry)

        # Mood aggregation
        for m in entry.get("mood", []):
            all_moods[m] += 1

        # Topic aggregation
        for t in entry.get("topic", []):
            all_topics[t] += 1

        # Tag aggregation
        for tag in entry.get("tags", []):
            all_tags[tag] += 1

    # ── Derived computations ──────────────────────────────────

    sorted_dates = sorted(date_set)
    longest_streak, current_streak = _compute_streaks(sorted_dates, today)

    # On This Day — sorted by year descending
    on_this_day.sort(key=lambda e: e.get("date", ""), reverse=True)

    # Milestone — based on current streak
    milestone = _detect_milestone(current_streak)

    # Total words — requires reading files (separate call)
    total_words = _compute_total_words(entries)

    # Most frequent mood / topic
    most_frequent_mood = all_moods.most_common(1)[0][0] if all_moods else None
    most_active_topic = all_topics.most_common(1)[0][0] if all_topics else None

    # Topic distribution (pie chart data)
    topic_distribution = [
        {"name": name, "value": count}
        for name, count in all_topics.most_common()
    ]

    # Tag cloud data
    tag_cloud = [
        {"name": name, "value": count}
        for name, count in all_tags.most_common()
    ]

    # Mood frequency (stacked bar chart data)
    mood_frequency = _compute_mood_frequency(entries)

    # People graph
    people_graph = _compute_people_graph(entries)

    return DashboardStats(
        total_journals=len(entries),
        total_words=total_words,
        longest_streak=longest_streak,
        current_streak=current_streak,
        month_journals=month_count,
        most_frequent_mood=most_frequent_mood,
        most_active_topic=most_active_topic,
        on_this_day=on_this_day,
        milestone=milestone,
        mood_frequency=mood_frequency,
        topic_distribution=topic_distribution,
        tag_cloud=tag_cloud,
        people_graph=people_graph,
        heatmap=dict(heatmap),
    )
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_web_dashboard.py -v
```

Expected: All tests pass (dataclass, compute_dashboard_stats, streaks, on_this_day, milestones, mood, topics, tags, people, heatmap, error handling).

- [ ] **Step 7: Verify existing tests still pass**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures.

- [ ] **Step 8: Commit**

```bash
git add web/services/stats.py tests/unit/test_web_dashboard.py
git commit -m "feat(web): add stats aggregation service for dashboard components"
```

---

## Task 8: Dashboard Route + Template (`web/routes/dashboard.py` + `web/templates/dashboard.html`)

**Files:**
- Create: `web/routes/dashboard.py`
- Create: `web/templates/dashboard.html`
- Create: `web/static/js/charts.js`
- Modify: `web/app.py` (register dashboard router)
- Test: `tests/unit/test_web_dashboard.py` (append)

**Difficulty:** Hard (~60 min)

**Acceptance Criteria:**
1. `GET /` returns HTTP 200 with rendered `dashboard.html`
2. Dashboard template extends `base.html`
3. Template renders all 8 components: heatmap, stats cards, on-this-day, milestones, mood chart, topic chart, tag cloud, people graph
4. ECharts is loaded via CDN (only on dashboard page, not in `base.html`)
5. Heatmap renders as GitHub-style calendar heatmap using ECharts
6. Stats cards show: total journals, total words, longest streak, month journals, most frequent mood, most active topic
7. Milestone badge displays when `milestone is not None` (per §5.1 thresholds)
8. On-this-day section shows carousel of historical entries or encouragement text when empty
9. Each component implements its degradation strategy per §5.1 table
10. Page title is "仪表盘 — Life Index"
11. All chart data is passed via Jinja2 `tojson` filter (no additional API calls)
12. Dashboard route is registered in `create_app()` via `app.include_router()`

**Subagent Governance:**
- MUST DO: Create `web/routes/dashboard.py` as a FastAPI `APIRouter` with `GET /` route
- MUST DO: Call `compute_dashboard_stats()` in the route handler and pass result to template
- MUST DO: Register the dashboard router in `web/app.py` via `app.include_router(dashboard_router)`
- MUST DO: Use `app.state.templates.TemplateResponse()` for rendering
- MUST DO: Use `request` parameter in template context (required by Starlette/Jinja2)
- MUST DO: Load ECharts via CDN in a `{% block head_extra %}` or `{% block scripts %}` block (add this block to `base.html` if not present)
- MUST DO: Pass chart data to JavaScript via `{{ data | tojson }}` in `<script>` tags
- MUST DO: Implement ALL 8 component degradation strategies from §5.1 table
- MUST DO: Use semantic HTML and Tailwind CSS classes consistent with `base.html`
- MUST DO: Use Chinese text for all user-facing strings
- MUST DO: Create `web/static/js/charts.js` for reusable ECharts initialization helpers
- MUST NOT DO: Make AJAX/fetch calls for dashboard data — all data is server-rendered
- MUST NOT DO: Import ECharts in `base.html` — it's dashboard-specific
- MUST NOT DO: Add any write/mutation endpoints — this is read-only
- MUST NOT DO: Skip degradation handling — every component MUST handle its empty/insufficient-data case

**Error Handling:**
- If `compute_dashboard_stats()` fails unexpectedly (should not happen due to internal error handling), the route catches the exception and renders dashboard with empty stats
- Template guards against `None` values using Jinja2 `{% if %}` checks

**TDD Steps:**

- [ ] **Step 1: Write the failing tests — route and rendering**

Append to `tests/unit/test_web_dashboard.py`:

```python
# ── Task 8: Dashboard Route + Template ────────────────────────


class TestDashboardRoute:
    """Test GET / dashboard route."""

    @patch("web.routes.dashboard.compute_dashboard_stats")
    def test_dashboard_returns_200(self, mock_stats: MagicMock) -> None:
        """GET / returns HTTP 200."""
        from web.services.stats import DashboardStats
        mock_stats.return_value = DashboardStats()

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200

    @patch("web.routes.dashboard.compute_dashboard_stats")
    def test_dashboard_html_content(self, mock_stats: MagicMock) -> None:
        """Dashboard page contains expected HTML elements."""
        from web.services.stats import DashboardStats
        mock_stats.return_value = DashboardStats(
            total_journals=42,
            total_words=12345,
            longest_streak=7,
            current_streak=3,
            month_journals=10,
            most_frequent_mood="专注",
            most_active_topic="work",
        )

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/")
        html = response.text

        # Page title
        assert "仪表盘" in html
        # Stats values
        assert "42" in html           # total journals
        assert "12345" in html        # total words (character count)
        assert "7" in html            # longest streak
        assert "10" in html           # month journals
        assert "专注" in html         # most frequent mood
        assert "work" in html         # most active topic

    @patch("web.routes.dashboard.compute_dashboard_stats")
    def test_dashboard_echarts_loaded(self, mock_stats: MagicMock) -> None:
        """Dashboard page loads ECharts from CDN."""
        from web.services.stats import DashboardStats
        mock_stats.return_value = DashboardStats()

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/")
        assert "echarts" in response.text.lower()

    @patch("web.routes.dashboard.compute_dashboard_stats")
    def test_dashboard_degradation_no_data(
        self, mock_stats: MagicMock
    ) -> None:
        """Dashboard shows degradation messages when data is empty."""
        from web.services.stats import DashboardStats
        mock_stats.return_value = DashboardStats()

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/")
        html = response.text

        # On-this-day encouragement text (per §5.1)
        assert "写日志" in html or "写一篇" in html
        # Stats should show zeros
        assert "0" in html

    @patch("web.routes.dashboard.compute_dashboard_stats")
    def test_dashboard_milestone_badge(self, mock_stats: MagicMock) -> None:
        """Milestone badge renders when milestone is set."""
        from web.services.stats import DashboardStats
        mock_stats.return_value = DashboardStats(
            current_streak=7,
            longest_streak=7,
            milestone=7,
        )

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/")
        html = response.text
        assert "连续 7 天" in html or "7 天" in html

    @patch("web.routes.dashboard.compute_dashboard_stats")
    def test_dashboard_on_this_day_entries(
        self, mock_stats: MagicMock
    ) -> None:
        """On-this-day section renders historical entries."""
        from web.services.stats import DashboardStats
        mock_stats.return_value = DashboardStats(
            on_this_day=[
                {
                    "date": "2025-03-07",
                    "title": "去年的记忆",
                    "mood": ["温暖"],
                    "abstract": "这是一段美好的回忆",
                    "file_path": "Journals/2025/03/life-index_2025-03-07_001.md",
                },
            ],
        )

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/")
        html = response.text
        assert "去年的记忆" in html
        assert "2025" in html


class TestDashboardRouterRegistration:
    """Verify dashboard router is registered in app."""

    def test_root_route_exists(self) -> None:
        """App has a route registered at /."""
        from web.app import create_app
        app = create_app()
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/" in routes
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_dashboard.py::TestDashboardRoute -v
python -m pytest tests/unit/test_web_dashboard.py::TestDashboardRouterRegistration -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'web.routes.dashboard'`.

- [ ] **Step 3a: Add `{% block scripts %}` to `base.html`**

If not already present, add before `</body>` in `web/templates/base.html`:

```html
    <!-- Page-specific scripts -->
    {% block scripts %}{% endblock %}

</body>
```

This allows `dashboard.html` to load ECharts without adding it to every page.

- [ ] **Step 3b: Create `web/routes/dashboard.py`**

```python
"""Dashboard route — GET / renders the main dashboard.

Calls stats service and passes all data to the template.
Per design-spec §5.1, all chart data is server-rendered (no AJAX).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web.services.stats import DashboardStats, compute_dashboard_stats

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the dashboard page with all 8 components.

    Computes stats from metadata cache and passes to Jinja2 template.
    Handles errors gracefully — renders empty dashboard on failure.
    """
    try:
        stats = compute_dashboard_stats()
    except Exception:
        logger.exception("Unexpected error computing dashboard stats")
        stats = DashboardStats()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            # Pre-serialize chart data for JavaScript consumption
            "heatmap_json": json.dumps(stats.heatmap, ensure_ascii=False),
            "mood_frequency_json": json.dumps(
                stats.mood_frequency, ensure_ascii=False
            ),
            "topic_distribution_json": json.dumps(
                stats.topic_distribution, ensure_ascii=False
            ),
            "tag_cloud_json": json.dumps(
                stats.tag_cloud, ensure_ascii=False
            ),
            "people_graph_json": json.dumps(
                stats.people_graph, ensure_ascii=False
            ),
        },
    )
```

- [ ] **Step 3c: Create `web/static/js/charts.js`**

```javascript
/**
 * Life Index Dashboard — ECharts initialization helpers.
 *
 * Each function takes a DOM element ID and data, initializing
 * the appropriate chart type. Handles dark mode via CSS media query.
 */

/**
 * Detect if dark mode is active.
 * @returns {string} 'dark' or 'light'
 */
function getTheme() {
    return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

/**
 * Initialize a GitHub-style calendar heatmap.
 * @param {string} elementId - DOM element ID
 * @param {Object} data - {date_str: count} mapping
 */
function initHeatmap(elementId, data) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const chart = echarts.init(el, getTheme());

    // Convert {date: count} to [[date, count]] for ECharts
    const chartData = Object.entries(data).map(([date, count]) => [date, count]);

    // Determine date range (last 365 days)
    const end = new Date();
    const start = new Date();
    start.setFullYear(start.getFullYear() - 1);

    const option = {
        tooltip: {
            formatter: function(params) {
                return params.value[0] + ': ' + (params.value[1] || 0) + ' 篇日志';
            }
        },
        visualMap: {
            min: 0,
            max: Math.max(...Object.values(data), 1),
            show: false,
            inRange: {
                color: ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39']
            }
        },
        calendar: {
            range: [start.toISOString().slice(0, 10), end.toISOString().slice(0, 10)],
            cellSize: [13, 13],
            itemStyle: {
                borderWidth: 2,
                borderColor: getTheme() === 'dark' ? '#1f2937' : '#ffffff'
            },
            splitLine: { show: false },
            dayLabel: { nameMap: 'ZH' },
            monthLabel: { nameMap: 'ZH' }
        },
        series: [{
            type: 'heatmap',
            coordinateSystem: 'calendar',
            data: chartData
        }]
    };

    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
}

/**
 * Initialize a stacked bar chart for mood frequency.
 * @param {string} elementId - DOM element ID
 * @param {Object} data - {period: {mood: count}} mapping
 */
function initMoodChart(elementId, data) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const chart = echarts.init(el, getTheme());

    const periods = Object.keys(data).sort();
    // Collect all unique moods
    const allMoods = new Set();
    periods.forEach(p => Object.keys(data[p]).forEach(m => allMoods.add(m)));

    // Take top 8 moods by total count, rest → "其他"
    const moodTotals = {};
    allMoods.forEach(m => {
        moodTotals[m] = periods.reduce((sum, p) => sum + (data[p][m] || 0), 0);
    });
    const sorted = Object.entries(moodTotals).sort((a, b) => b[1] - a[1]);
    const topMoods = sorted.slice(0, 8).map(e => e[0]);
    const hasOther = sorted.length > 8;

    const series = topMoods.map(mood => ({
        name: mood,
        type: 'bar',
        stack: 'mood',
        data: periods.map(p => data[p][mood] || 0)
    }));

    if (hasOther) {
        const otherMoods = sorted.slice(8).map(e => e[0]);
        series.push({
            name: '其他',
            type: 'bar',
            stack: 'mood',
            data: periods.map(p =>
                otherMoods.reduce((sum, m) => sum + (data[p][m] || 0), 0)
            )
        });
    }

    const option = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { data: [...topMoods, ...(hasOther ? ['其他'] : [])] },
        xAxis: { type: 'category', data: periods },
        yAxis: { type: 'value', name: '篇数' },
        series: series
    };

    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
}

/**
 * Initialize a pie/donut chart for topic distribution.
 * @param {string} elementId - DOM element ID
 * @param {Array} data - [{name, value}] array
 */
function initTopicChart(elementId, data) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const chart = echarts.init(el, getTheme());

    const option = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: true,
            itemStyle: { borderRadius: 6 },
            label: { show: true, formatter: '{b}' },
            data: data
        }]
    };

    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
}

/**
 * Initialize a word cloud chart.
 * @param {string} elementId - DOM element ID
 * @param {Array} data - [{name, value}] array
 */
function initTagCloud(elementId, data) {
    const el = document.getElementById(elementId);
    if (!el) return;

    // ECharts wordCloud requires echarts-wordcloud extension
    // Fallback: render as simple weighted list if extension not loaded
    if (typeof echarts !== 'undefined' && echarts.binds && echarts.binds.wordCloud) {
        // Use echarts-wordcloud if available
        const chart = echarts.init(el, getTheme());
        chart.setOption({
            series: [{
                type: 'wordCloud',
                shape: 'circle',
                sizeRange: [14, 48],
                rotationRange: [0, 0],
                data: data.map(d => ({ name: d.name, value: d.value }))
            }]
        });
        window.addEventListener('resize', () => chart.resize());
    } else {
        // Fallback: CSS-based tag cloud
        el.innerHTML = data.map(d => {
            const size = Math.max(14, Math.min(48, 14 + d.value * 4));
            return `<a href="/search?q=${encodeURIComponent(d.name)}"
                       class="inline-block m-1 px-2 py-1 rounded
                              text-indigo-600 dark:text-indigo-400
                              hover:bg-indigo-50 dark:hover:bg-indigo-900/30
                              transition-colors cursor-pointer"
                       style="font-size:${size}px">${d.name}</a>`;
        }).join('');
    }
}

/**
 * Initialize a force-directed graph for people relationships.
 * @param {string} elementId - DOM element ID
 * @param {Object} graphData - {nodes: [{name, count}], edges: [{source, target, weight}]}
 */
function initPeopleGraph(elementId, graphData) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const chart = echarts.init(el, getTheme());

    const maxCount = Math.max(...graphData.nodes.map(n => n.count), 1);

    const option = {
        tooltip: {
            formatter: function(params) {
                if (params.dataType === 'node') {
                    return params.data.name + ': ' + params.data.count + ' 篇日志';
                }
                return params.data.source + ' ↔ ' + params.data.target + ': ' + params.data.weight + ' 次共现';
            }
        },
        series: [{
            type: 'graph',
            layout: 'force',
            roam: true,
            label: { show: true, position: 'right' },
            force: {
                repulsion: 200,
                edgeLength: [50, 200]
            },
            data: graphData.nodes.map(n => ({
                name: n.name,
                count: n.count,
                symbolSize: 20 + (n.count / maxCount) * 40,
            })),
            edges: graphData.edges.map(e => ({
                source: e.source,
                target: e.target,
                weight: e.weight,
                lineStyle: { width: Math.min(e.weight * 2, 10) }
            }))
        }]
    };

    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
}
```

- [ ] **Step 3d: Create `web/templates/dashboard.html`**

```html
{% extends "base.html" %}

{% block title %}仪表盘 — Life Index{% endblock %}

{% block content %}
<div class="space-y-8">

    <!-- ── Writing Heatmap ──────────────────────────────────── -->
    <section>
        <h2 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
            写作热力图
        </h2>
        {% if stats.total_journals > 0 %}
        <div id="heatmap-chart" class="w-full h-40 bg-white dark:bg-gray-800 rounded-lg shadow p-4"></div>
        {% else %}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center text-gray-500 dark:text-gray-400">
            暂无日志
        </div>
        {% endif %}
    </section>

    <!-- ── Stats Cards ──────────────────────────────────────── -->
    <section>
        <h2 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
            基础统计
        </h2>
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <!-- Total Journals -->
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 text-center">
                <div class="text-3xl font-bold text-indigo-600 dark:text-indigo-400">
                    {{ stats.total_journals }}
                </div>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">总日志数</div>
            </div>

            <!-- Total Words -->
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 text-center">
                <div class="text-3xl font-bold text-indigo-600 dark:text-indigo-400">
                    {{ stats.total_words }}
                </div>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">总字数</div>
            </div>

            <!-- Longest Streak -->
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 text-center relative">
                <div class="text-3xl font-bold text-indigo-600 dark:text-indigo-400">
                    {{ stats.longest_streak }}
                </div>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">最长连续天数</div>
                {% if stats.milestone %}
                <!-- Milestone Badge (per §5.1) -->
                <div x-data="{ show: !localStorage.getItem('milestone_{{ stats.milestone }}') }"
                     x-init="if(show) { setTimeout(() => { localStorage.setItem('milestone_{{ stats.milestone }}', '1'); }, 3000) }"
                     x-show="show"
                     x-transition
                     class="absolute -top-2 -right-2 bg-yellow-400 text-yellow-900 text-xs font-bold px-2 py-1 rounded-full shadow">
                    {% if stats.milestone == 7 %}
                        连续 7 天 ✨
                    {% elif stats.milestone == 30 %}
                        连续 30 天 🎉
                    {% elif stats.milestone == 100 %}
                        连续 100 天 🏆
                    {% elif stats.milestone == 365 %}
                        连续 365 天 👑
                    {% endif %}
                </div>
                {% endif %}
            </div>

            <!-- Month Journals -->
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 text-center">
                <div class="text-3xl font-bold text-indigo-600 dark:text-indigo-400">
                    {{ stats.month_journals }}
                </div>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">本月日志</div>
            </div>

            <!-- Most Frequent Mood -->
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 text-center">
                <div class="text-2xl font-bold text-indigo-600 dark:text-indigo-400">
                    {{ stats.most_frequent_mood or "—" }}
                </div>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">最常情绪</div>
            </div>

            <!-- Most Active Topic -->
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 text-center">
                <div class="text-2xl font-bold text-indigo-600 dark:text-indigo-400">
                    {{ stats.most_active_topic or "—" }}
                </div>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">最活跃主题</div>
            </div>
        </div>
    </section>

    <!-- ── On This Day (那年今日) ───────────────────────────── -->
    <section>
        <h2 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
            那年今日
        </h2>
        {% if stats.on_this_day %}
        <div x-data="{ current: 0, total: {{ stats.on_this_day | length }} }"
             class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 relative">
            {% for entry in stats.on_this_day %}
            <div x-show="current === {{ loop.index0 }}"
                 x-transition
                 class="space-y-2">
                <div class="text-sm font-medium text-indigo-500 dark:text-indigo-400">
                    {{ entry.date[:4] }}
                </div>
                <h3 class="text-lg font-semibold">
                    <a href="/journal/{{ entry.journal_route_path }}"
                       class="text-gray-800 dark:text-gray-200 hover:text-indigo-600 dark:hover:text-indigo-400">
                        {{ entry.title }}
                    </a>
                </h3>
                {% if entry.abstract %}
                <p class="text-sm text-gray-500 dark:text-gray-400 line-clamp-2">
                    {{ entry.abstract }}
                </p>
                {% endif %}
                {% if entry.mood %}
                <div class="flex gap-1 flex-wrap">
                    {% for m in entry.mood %}
                    <span class="text-xs px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300">
                        {{ m }}
                    </span>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            {% endfor %}
            <!-- Navigation arrows -->
            <div x-show="total > 1" class="flex justify-between mt-4">
                <button @click="current = (current - 1 + total) % total"
                        class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                    ← 上一篇
                </button>
                <span class="text-sm text-gray-400" x-text="(current + 1) + ' / ' + total"></span>
                <button @click="current = (current + 1) % total"
                        class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                    下一篇 →
                </button>
            </div>
        </div>
        {% else %}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center">
            <p class="text-gray-500 dark:text-gray-400">
                今天还没有历史记忆——今天写一篇，明年今日就能看到了 ✨
            </p>
            <a href="/write"
               class="inline-block mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm">
                写日志
            </a>
        </div>
        {% endif %}
    </section>

    <!-- ── Mood Frequency (情绪频率) ────────────────────────── -->
    <section>
        <h2 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
            情绪频率
        </h2>
        {% set mood_count = stats.mood_frequency.values() | list | length %}
        {% set total_mood_entries = 0 %}
        {% for period_data in stats.mood_frequency.values() %}
            {% set total_mood_entries = total_mood_entries + period_data.values() | list | sum %}
        {% endfor %}
        {% if mood_count > 0 and stats.total_journals >= 5 %}
        <div id="mood-chart" class="w-full h-80 bg-white dark:bg-gray-800 rounded-lg shadow p-4"></div>
        {% else %}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center text-gray-500 dark:text-gray-400">
            记录更多情绪以解锁此图表
        </div>
        {% endif %}
    </section>

    <!-- ── Topic Distribution (主题分布) ────────────────────── -->
    <section>
        <h2 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
            主题分布
        </h2>
        {% if stats.topic_distribution %}
        <div id="topic-chart" class="w-full h-80 bg-white dark:bg-gray-800 rounded-lg shadow p-4"></div>
        {% else %}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center text-gray-500 dark:text-gray-400">
            暂无日志
        </div>
        {% endif %}
    </section>

    <!-- ── Tag Cloud (标签词云) ──────────────────────────────── -->
    <section>
        <h2 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
            标签词云
        </h2>
        {% set unique_tags = stats.tag_cloud | length %}
        {% if unique_tags >= 3 %}
        <div id="tag-cloud" class="w-full min-h-40 bg-white dark:bg-gray-800 rounded-lg shadow p-6 flex flex-wrap items-center justify-center"></div>
        {% elif unique_tags > 0 %}
        <!-- Degradation: simple tag list when < 3 unique tags -->
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 flex flex-wrap gap-2">
            {% for tag in stats.tag_cloud %}
            <a href="/search?q={{ tag.name | urlencode }}"
               class="px-3 py-1 rounded-full bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 text-sm hover:bg-indigo-200 dark:hover:bg-indigo-800/40">
                {{ tag.name }} ({{ tag.value }})
            </a>
            {% endfor %}
        </div>
        {% else %}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center text-gray-500 dark:text-gray-400">
            暂无标签
        </div>
        {% endif %}
    </section>

    <!-- ── People Graph (人物关系图) ────────────────────────── -->
    <section>
        <h2 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
            人物关系图
        </h2>
        {% set people_entries = stats.people_graph.nodes | length %}
        {% if people_entries >= 2 %}
        <div id="people-graph" class="w-full h-96 bg-white dark:bg-gray-800 rounded-lg shadow p-4"></div>
        {% else %}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center text-gray-500 dark:text-gray-400">
            在日志中标记人物以解锁关系图
        </div>
        {% endif %}
    </section>

</div>
{% endblock %}

{% block scripts %}
<!-- ECharts (CDN — Dashboard only, per design-spec §2) -->
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<!-- Dashboard chart helpers -->
<script src="/static/js/charts.js"></script>

<script>
    document.addEventListener('DOMContentLoaded', function() {
        // Heatmap
        {% if stats.total_journals > 0 %}
        initHeatmap('heatmap-chart', {{ heatmap_json | safe }});
        {% endif %}

        // Mood frequency
        {% if stats.mood_frequency and stats.total_journals >= 5 %}
        initMoodChart('mood-chart', {{ mood_frequency_json | safe }});
        {% endif %}

        // Topic distribution
        {% if stats.topic_distribution %}
        initTopicChart('topic-chart', {{ topic_distribution_json | safe }});
        {% endif %}

        // Tag cloud
        {% if stats.tag_cloud | length >= 3 %}
        initTagCloud('tag-cloud', {{ tag_cloud_json | safe }});
        {% endif %}

        // People graph
        {% if stats.people_graph.nodes | length >= 2 %}
        initPeopleGraph('people-graph', {{ people_graph_json | safe }});
        {% endif %}
    });
</script>
{% endblock %}
```

- [ ] **Step 3e: Register dashboard router in `web/app.py`**

Add the following import and `include_router` call inside `create_app()`, after the health endpoint and before `return app`:

```python
    # --- Routes ---
    from web.routes.dashboard import router as dashboard_router
    app.include_router(dashboard_router)
```

The import is inside `create_app()` to maintain the lazy-import pattern established in Phase 1.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_web_dashboard.py::TestDashboardRoute -v
python -m pytest tests/unit/test_web_dashboard.py::TestDashboardRouterRegistration -v
```

Expected: All pass.

- [ ] **Step 5: Run all dashboard tests**

```bash
python -m pytest tests/unit/test_web_dashboard.py -v
```

Expected: All tests pass (Task 7 + Task 8 tests).

- [ ] **Step 6: Verify existing tests still pass**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures.

- [ ] **Step 7: Visual smoke test**

```bash
life-index serve &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/
# Expected: 200
kill %1
```

Then open `http://127.0.0.1:8765/` in a browser to visually verify:
- Stats cards render (showing 0 if no data)
- Degradation messages appear for empty components
- Theme toggle still works
- No JavaScript console errors

- [ ] **Step 8: Commit**

```bash
git add web/routes/dashboard.py web/templates/dashboard.html web/static/js/charts.js web/app.py tests/unit/test_web_dashboard.py
git commit -m "feat(web): add dashboard route with 8 components and ECharts visualization"
```

---

## Phase 2 Completion Checklist

Run all checks before declaring Phase 2 complete:

- [ ] **All Phase 2 tests pass:**

```bash
python -m pytest tests/unit/test_web_dashboard.py -v
```

Expected: All tests in `TestDashboardStatsDataclass`, `TestComputeDashboardStats`, `TestStreakCalculation`, `TestOnThisDay`, `TestMilestone`, `TestMoodFrequency`, `TestTopicDistribution`, `TestTagCloud`, `TestPeopleGraph`, `TestHeatmap`, `TestMostFrequent`, `TestStatsServiceErrorHandling`, `TestDashboardRoute`, `TestDashboardRouterRegistration` pass.

- [ ] **All existing tests still pass:**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures (including all Phase 1 tests).

- [ ] **Dashboard renders at GET /:**

```bash
life-index serve &
sleep 2
curl -s http://127.0.0.1:8765/ | head -5
kill %1
```

Expected: HTML output starting with `<!DOCTYPE html>` containing "仪表盘".

- [ ] **Dashboard with empty data shows degradation:**

Fresh install (no journals) should show:
- All stats cards display `0` or `—`
- Heatmap shows "暂无日志"
- On-this-day shows encouragement text with "写日志" button
- Mood chart shows "记录更多情绪以解锁此图表"
- Topic chart shows "暂无日志"  (empty pie)
- Tag cloud shows "暂无标签"
- People graph shows "在日志中标记人物以解锁关系图"

- [ ] **ECharts loads only on dashboard page:**

```bash
life-index serve &
sleep 2
# Dashboard should have echarts
curl -s http://127.0.0.1:8765/ | grep -c "echarts"
# Health endpoint should NOT have echarts
curl -s http://127.0.0.1:8765/api/health | grep -c "echarts"
kill %1
```

Expected: Dashboard grep count > 0; health grep count = 0.

- [ ] **Health endpoint still works:**

```bash
life-index serve &
sleep 2
curl -s http://127.0.0.1:8765/api/health | python -m json.tool
kill %1
```

Expected: `{"status": "ok", "version": "..."}`.

- [ ] **Files created/modified:**

```
web/
├── services/
│   └── stats.py             ✅ (created)
├── routes/
│   └── dashboard.py         ✅ (created)
├── templates/
│   ├── base.html            ✅ (modified — added {% block scripts %})
│   └── dashboard.html       ✅ (created)
├── static/
│   └── js/
│       └── charts.js        ✅ (created)
└── app.py                   ✅ (modified — registered dashboard router)

tests/unit/
└── test_web_dashboard.py    ✅ (created)
```

**Phase 2 is complete when all checkboxes above are checked. Proceed to Phase 3: Journal View + Search.**
