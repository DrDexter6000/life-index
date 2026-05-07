"""Tests for date-only generic noun suppression (R1 D4.11).

Covers the Phase 2-C extension: when a query has date_range but no
topic_hints, and the only content keywords are generic nouns
(日志/记录/笔记), those nouns should be stripped from keywords.
"""

from __future__ import annotations

from datetime import date

from tools.search_journals.query_preprocessor import build_search_plan


class TestDateOnlyGenericNounSuppression:
    """Phase 2-C: date-only broad recall generic noun suppression."""

    REF_DATE = date(2026, 4, 18)

    def test_date_only_日志_suppressed(self) -> None:
        """'2026年03月的日志' should suppress '日志' from keywords and expanded_query."""
        plan = build_search_plan("2026年03月的日志", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        assert "日志" not in plan.keywords
        assert "日志" not in plan.expanded_query
        assert "2026" in plan.expanded_query

    def test_date_only_记录_suppressed(self) -> None:
        """'2026年03月的记录' should suppress '记录' from keywords and expanded_query."""
        plan = build_search_plan("2026年03月的记录", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        assert "记录" not in plan.keywords
        assert "记录" not in plan.expanded_query

    def test_date_only_笔记_suppressed(self) -> None:
        """'2026年03月的笔记' should suppress '笔记' from keywords and expanded_query."""
        plan = build_search_plan("2026年03月的笔记", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        assert "笔记" not in plan.keywords
        assert "笔记" not in plan.expanded_query

    def test_bare_日志_not_suppressed(self) -> None:
        """'日志' without date range must NOT be suppressed."""
        plan = build_search_plan("日志", reference_date=self.REF_DATE)
        assert plan.date_range is None
        assert "日志" in plan.keywords
        assert "日志" in plan.expanded_query

    def test_date_plus_meaningful_keyword_preserves_keyword(self) -> None:
        """'2026年03月的工作日志' should keep '工作' keyword, not become empty."""
        plan = build_search_plan("2026年03月的工作日志", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        # "工作" maps to topic_hints=["work"], so Phase 2-B logic applies (not 2-C).
        # Either way, "工作" must survive.
        assert "工作" in plan.keywords
        assert len(plan.keywords) >= 1
        assert "工作" in plan.expanded_query

    def test_date_only_empty_keywords_valid_plan(self) -> None:
        """After suppression, keywords may be empty — plan must still be valid."""
        plan = build_search_plan("2026年03月的日志", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        # keywords is a list (possibly empty) — no exception raised
        assert isinstance(plan.keywords, list)
        assert plan.expanded_query is not None

    def test_date_plus_topic_preserves_old_logic(self) -> None:
        """'work相关的日志' should still use Phase 2-B (topic_hints present)."""
        plan = build_search_plan("work相关的日志", reference_date=self.REF_DATE)
        assert "work" in plan.topic_hints
        assert "日志" not in plan.keywords


class TestDateOnlyGenericNounNoRegression:
    """Ensure existing query patterns are not broken by Phase 2-C."""

    REF_DATE = date(2026, 4, 18)

    def test_normal_keyword_query_unchanged(self) -> None:
        """'乐乐' should still have '乐乐' in keywords."""
        plan = build_search_plan("乐乐", reference_date=self.REF_DATE)
        assert "乐乐" in plan.keywords

    def test_date_query_with_real_keyword_unchanged(self) -> None:
        """'过去30天睡觉' should keep '睡觉' keyword."""
        plan = build_search_plan("过去30天睡觉", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        assert "睡觉" in plan.keywords

    def test_english_query_unchanged(self) -> None:
        """'Claude Opus' should remain unchanged."""
        plan = build_search_plan("Claude Opus", reference_date=self.REF_DATE)
        assert "Claude" in plan.keywords
        assert "Opus" in plan.keywords

    def test_topic_hint_query_unchanged(self) -> None:
        """'上个月在工作中取得了什么进展' should still have 'work' topic hint."""
        plan = build_search_plan("上个月在工作中取得了什么进展", reference_date=self.REF_DATE)
        assert "work" in plan.topic_hints


class TestSeasonAndRelativeTimeGuard:
    """Phase 2-C must NOT trigger for season/relative time queries (D4.13)."""

    REF_DATE = date(2026, 4, 18)

    def test_season_记录_not_suppressed(self) -> None:
        """'春天的记录' must NOT suppress '记录' — season is not absolute date."""
        plan = build_search_plan("春天的记录", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        assert plan.date_range.source != "absolute_date_parse"
        assert "记录" in plan.keywords
        assert "记录" in plan.expanded_query

    def test_relative_time_记录_not_suppressed(self) -> None:
        """'最近一周的记录' must NOT suppress '记录' — relative time."""
        plan = build_search_plan("最近一周的记录", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        assert plan.date_range.source != "absolute_date_parse"
        assert "记录" in plan.keywords
        assert "记录" in plan.expanded_query
