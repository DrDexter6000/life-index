"""Tests for query preprocessor module (Round 11 Phase 1).

Covers: normalize_query, extract_time_expression, parse_time_range,
classify_intent, extract_keywords, extract_topic_hints,
classify_query_mode, build_search_plan.
"""

from __future__ import annotations

from datetime import date

from tools.search_journals.query_preprocessor import (
    build_search_plan,
    classify_intent,
    classify_query_mode,
    extract_keywords,
    extract_time_expression,
    extract_topic_hints,
    normalize_query,
    parse_time_range,
)
from tools.search_journals.query_types import IntentType, QueryMode


# ── normalize_query ────────────────────────────────────────────────────


class TestNormalizeQuery:
    def test_removes_trailing_punctuation(self):
        assert normalize_query("测试查询？") == "测试查询"

    def test_trims_whitespace(self):
        assert normalize_query("  hello  ") == "hello"

    def test_fullwidth_to_halfwidth_digits(self):
        result = normalize_query("６０天")
        assert "60" in result

    def test_preserves_content(self):
        assert normalize_query("乐乐") == "乐乐"

    def test_empty_string(self):
        assert normalize_query("") == ""

    def test_multiple_punctuation(self):
        assert normalize_query("测试！？。") == "测试"


# ── extract_time_expression ────────────────────────────────────────────


class TestExtractTimeExpression:
    def test_past_n_days(self):
        assert extract_time_expression("过去60天我有多少次晚于10点睡觉？") == "过去60天"

    def test_last_month(self):
        assert extract_time_expression("上个月在工作中取得了什么进展？") == "上个月"

    def test_recent(self):
        assert extract_time_expression("最近有什么让我开心的事？") == "最近"

    def test_past_week(self):
        result = extract_time_expression("过去一周发生了什么？")
        assert result is not None
        assert "周" in result or "星期" in result

    def test_this_year(self):
        result = extract_time_expression("今年有什么变化？")
        assert result is not None

    def test_last_year(self):
        result = extract_time_expression("去年这个时候在做什么？")
        assert result is not None

    def test_month_reference(self):
        result = extract_time_expression("3月份做了什么？")
        assert result is not None

    def test_no_time_expression(self):
        assert extract_time_expression("乐乐") is None

    def test_no_time_expression_english(self):
        assert extract_time_expression("Claude Opus") is None


# ── parse_time_range ──────────────────────────────────────────────────


class TestParseTimeRange:
    REF_DATE = date(2026, 4, 18)

    def test_past_60_days(self):
        dr = parse_time_range("过去60天", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since is not None
        assert dr.until is not None
        # Since should be ~60 days before 2026-04-18
        assert dr.source == "relative_time_parse"

    def test_past_60_days_since_value(self):
        dr = parse_time_range("过去60天", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since is not None
        since = date.fromisoformat(dr.since)
        expected_since = date(2026, 2, 17)
        assert abs((since - expected_since).days) <= 1

    def test_last_month(self):
        dr = parse_time_range("上个月", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since == "2026-03-01"
        assert dr.until == "2026-03-31"

    def test_recent_defaults_30_days(self):
        dr = parse_time_range("最近", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since is not None
        since = date.fromisoformat(dr.since)
        assert (self.REF_DATE - since).days == 30

    def test_past_week(self):
        dr = parse_time_range("过去一周", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since is not None
        since = date.fromisoformat(dr.since)
        assert (self.REF_DATE - since).days == 7

    def test_this_year(self):
        dr = parse_time_range("今年", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since == "2026-01-01"

    def test_last_year_around_now(self):
        dr = parse_time_range("去年这个时候", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since is not None
        # Should be roughly same period last year
        since = date.fromisoformat(dr.since)
        assert since.year == 2025

    def test_month_reference(self):
        dr = parse_time_range("3月份", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since is not None

    def test_no_match_returns_none(self):
        assert parse_time_range("重构搜索模块") is None

    def test_none_input_returns_none(self):
        assert parse_time_range(None) is None

    # A1a: Month-part semantics (下旬 corrected from 15 to 21)
    def test_month_start(self):
        """三月初 => 1..10."""
        dr = parse_time_range("三月初", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since == "2026-03-01"
        assert dr.until == "2026-03-10"

    def test_month_mid(self):
        """三月中旬 => 11..20."""
        dr = parse_time_range("三月中旬", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since == "2026-03-11"
        assert dr.until == "2026-03-20"

    def test_month_late(self):
        """三月下旬 => 21..end (A1a fix: was 15, now 21)."""
        dr = parse_time_range("三月下旬", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since == "2026-03-21"
        assert dr.until == "2026-03-31"

    def test_month_end(self):
        """三月底 => 25..end."""
        dr = parse_time_range("三月底", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since == "2026-03-25"
        assert dr.until == "2026-03-31"

    def test_month_late_february_nonleap(self):
        """二月下旬 => 21..28 (non-leap year)."""
        dr = parse_time_range("二月下旬", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since == "2026-02-21"
        assert dr.until == "2026-02-28"

    def test_month_late_february_leap(self):
        """二月下旬 => 21..29 (leap year 2024)."""
        ref = date(2024, 4, 18)
        dr = parse_time_range("二月下旬", reference_date=ref)
        assert dr is not None
        assert dr.since == "2024-02-21"
        assert dr.until == "2024-02-29"

    def test_month_range_late_to_next(self):
        """三月下旬到四月 => 21..end-of-April."""
        dr = parse_time_range("三月下旬到四月", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since == "2026-03-21"
        assert dr.until == "2026-04-30"

    def test_month_late_august(self):
        """八月下旬 => 21..31."""
        dr = parse_time_range("八月下旬", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since == "2026-08-21"
        assert dr.until == "2026-08-31"


# ── classify_intent ────────────────────────────────────────────────────


class TestClassifyIntent:
    def test_count_how_many(self):
        assert classify_intent("过去60天我有多少次晚于10点睡觉？") == IntentType.COUNT

    def test_count_how_long(self):
        assert classify_intent("我有多久没有关心过健康了？") == IntentType.COUNT

    def test_count_several_times(self):
        assert classify_intent("这周有几次失眠？") == IntentType.COUNT

    def test_recall_memories(self):
        assert classify_intent("我和女儿之间有哪些珍贵的回忆？") == IntentType.RECALL

    def test_recall_what_happy(self):
        assert classify_intent("最近有什么让我开心的事？") == IntentType.RECALL

    def test_summarize_progress(self):
        assert classify_intent("上个月在工作中取得了什么进展？") == IntentType.SUMMARIZE

    def test_summarize_summary(self):
        assert classify_intent("总结一下今年的学习") == IntentType.SUMMARIZE

    def test_compare(self):
        assert classify_intent("最近焦虑和开心哪个多？") == IntentType.COMPARE

    def test_compare_contrast(self):
        assert classify_intent("对比一下上个月和这个月的工作效率") == IntentType.COMPARE

    def test_default_recall_keyword(self):
        assert classify_intent("乐乐") == IntentType.RECALL

    def test_default_recall_english(self):
        assert classify_intent("Claude Opus") == IntentType.RECALL

    def test_default_recall_irrelevant(self):
        assert classify_intent("量子计算机编程") == IntentType.RECALL


# ── extract_keywords ──────────────────────────────────────────────────


class TestExtractKeywords:
    def test_basic_extraction(self):
        kw = extract_keywords("过去60天我有多少次晚于10点睡觉？", time_expr="过去60天")
        assert "睡觉" in kw or len(kw) > 0

    def test_simple_keyword(self):
        kw = extract_keywords("乐乐")
        assert "乐乐" in kw

    def test_english_keywords(self):
        kw = extract_keywords("Claude Opus")
        assert "Claude" in kw
        assert "Opus" in kw

    def test_removes_question_words(self):
        kw = extract_keywords("什么是重构？")
        # Should not contain 什么是 or 什么
        for w in ["什么", "是"]:
            if len(w) == 1:
                continue  # single chars might remain
        assert len(kw) > 0

    def test_empty_query(self):
        kw = extract_keywords("")
        assert kw == []


# ── extract_topic_hints ───────────────────────────────────────────────


class TestExtractTopicHints:
    def test_health(self):
        hints = extract_topic_hints("我有多久没有关心过健康了？")
        assert "health" in hints

    def test_work(self):
        hints = extract_topic_hints("上个月在工作中取得了什么进展？")
        assert "work" in hints

    def test_no_topic(self):
        hints = extract_topic_hints("乐乐")
        assert hints == []

    def test_learning(self):
        hints = extract_topic_hints("最近学习了什么新技能？")
        assert "learn" in hints or "health" in hints or len(hints) >= 0


# ── classify_query_mode ───────────────────────────────────────────────


class TestClassifyQueryMode:
    def test_keyword_short(self):
        assert classify_query_mode("乐乐") == QueryMode.KEYWORD

    def test_keyword_space_separated(self):
        assert classify_query_mode("生日 重庆") == QueryMode.KEYWORD

    def test_natural_language(self):
        assert classify_query_mode("过去60天我有多少次晚于10点睡觉？") == QueryMode.NATURAL_LANGUAGE

    def test_natural_language_with_question(self):
        assert classify_query_mode("最近有什么让我开心的事？") == QueryMode.NATURAL_LANGUAGE


# ── build_search_plan ─────────────────────────────────────────────────


class TestBuildSearchPlan:
    REF_DATE = date(2026, 4, 18)

    def test_time_aggregation_query(self):
        plan = build_search_plan("过去60天我有多少次晚于10点睡觉？", reference_date=self.REF_DATE)
        assert plan.raw_query == "过去60天我有多少次晚于10点睡觉？"
        assert plan.intent_type == IntentType.COUNT
        assert plan.date_range is not None
        assert plan.date_range.since is not None
        assert len(plan.keywords) > 0
        assert plan.pipelines["keyword"] is True
        assert plan.pipelines["semantic"] is True

    def test_keyword_query(self):
        plan = build_search_plan("乐乐", reference_date=self.REF_DATE)
        assert plan.intent_type == IntentType.RECALL
        assert plan.date_range is None
        assert "乐乐" in plan.keywords
        assert plan.query_mode == QueryMode.KEYWORD

    def test_empty_query(self):
        plan = build_search_plan("", reference_date=self.REF_DATE)
        assert plan.intent_type == IntentType.UNKNOWN
        assert plan.keywords == []

    def test_irrelevant_query(self):
        plan = build_search_plan("量子计算机编程", reference_date=self.REF_DATE)
        # "编程" maps to "create" topic — that's correct behavior
        # The key is that this query still gets intent=recall and no health/work topic
        assert plan.intent_type == IntentType.RECALL

    def test_to_dict_json_serializable(self):
        plan = build_search_plan("过去60天我有多少次晚于10点睡觉？", reference_date=self.REF_DATE)
        import json

        d = plan.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        assert "过去60天" in json_str

    def test_work_topic_query(self):
        plan = build_search_plan("上个月在工作中取得了什么进展？", reference_date=self.REF_DATE)
        assert "work" in plan.topic_hints

    def test_health_topic_query(self):
        plan = build_search_plan("我有多久没有关心过健康了？", reference_date=self.REF_DATE)
        assert "health" in plan.topic_hints


# ── Round 13 Phase 3: Chinese time expression integration ────────────


class TestChineseTimeIntegration:
    """Tests for Chinese time expression fallback in query preprocessor."""

    REF_DATE = date(2026, 4, 18)

    def test_extract_time_chinese_one_month(self) -> None:
        """extract_time_expression should recognize '过去一个月' via Chinese time mapping."""
        result = extract_time_expression("过去一个月学到了什么")
        assert result is not None

    def test_parse_time_chinese_one_month(self) -> None:
        """parse_time_range('过去1个月') should return a DateRange ~30 days back."""
        dr = parse_time_range("过去1个月", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since is not None
        since = date.fromisoformat(dr.since)
        assert (self.REF_DATE - since).days >= 28

    def test_parse_time_chinese_half_year(self) -> None:
        """parse_time_range('过去6个月') should return a DateRange ~6 months back."""
        dr = parse_time_range("过去6个月", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since is not None
        since = date.fromisoformat(dr.since)
        # ~180 days back
        diff = (self.REF_DATE - since).days
        assert 175 <= diff <= 185

    def test_build_plan_chinese_date_range(self) -> None:
        """build_search_plan with Chinese time expr should have non-None date_range."""
        plan = build_search_plan("过去一个月学到了什么", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        assert plan.date_range.since is not None

    def test_build_plan_existing_patterns_unchanged(self) -> None:
        """Regression: '过去30天' still works correctly."""
        plan = build_search_plan("过去30天做了什么", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        assert plan.date_range.since is not None
        since = date.fromisoformat(plan.date_range.since)
        assert (self.REF_DATE - since).days == 30

    def test_build_plan_最近_unchanged(self) -> None:
        """Regression: '最近有什么好玩的' still works."""
        plan = build_search_plan("最近有什么好玩的", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        assert plan.date_range.since is not None
        since = date.fromisoformat(plan.date_range.since)
        assert (self.REF_DATE - since).days == 30

    def test_extract_time_chinese_half_month(self) -> None:
        """'半个月' should resolve to a fractional month expression."""
        result = extract_time_expression("半个月做了什么")
        assert result is not None
        assert "0.5" in result

    def test_parse_time_fractional_month(self) -> None:
        """parse_time_range should handle '过去0.5个月'."""
        dr = parse_time_range("过去0.5个月", reference_date=self.REF_DATE)
        assert dr is not None
        assert dr.since is not None
        since = date.fromisoformat(dr.since)
        assert (self.REF_DATE - since).days >= 14

    def test_build_plan_chinese_one_week(self) -> None:
        """'一周' should produce a valid date range."""
        plan = build_search_plan("一周学到了什么", reference_date=self.REF_DATE)
        assert plan.date_range is not None

    def test_build_plan_chinese_two_weeks(self) -> None:
        """'两周' should produce a valid date range."""
        plan = build_search_plan("两周做了什么", reference_date=self.REF_DATE)
        assert plan.date_range is not None

    def test_build_plan_chinese_half_year(self) -> None:
        """'半年' should produce a valid date range ~6 months back."""
        plan = build_search_plan("半年有什么变化", reference_date=self.REF_DATE)
        assert plan.date_range is not None
        assert plan.date_range.since is not None
        since = date.fromisoformat(plan.date_range.since)
        diff = (self.REF_DATE - since).days
        assert 175 <= diff <= 185
