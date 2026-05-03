"""Tests for F1: deterministic eval anchor injection."""

from __future__ import annotations

import os
from datetime import date

from tools.lib.time_parser import parse_time_expression
from tools.search_journals.core import _eval_anchor
from tools.search_journals.query_preprocessor import build_search_plan


class TestEvalAnchorEnvVar:
    """_eval_anchor reads LIFE_INDEX_TIME_ANCHOR from the environment."""

    def test_reads_iso_date(self) -> None:
        os.environ["LIFE_INDEX_TIME_ANCHOR"] = "2026-03-15"
        assert _eval_anchor() == date(2026, 3, 15)

    def test_returns_none_when_unset(self) -> None:
        os.environ.pop("LIFE_INDEX_TIME_ANCHOR", None)
        assert _eval_anchor() is None


class TestParseTimeExpressionAnchor:
    """parse_time_expression respects the anchor date."""

    def test_relative_month_with_anchor(self) -> None:
        result = parse_time_expression("上个月的工作日志", now=date(2026, 3, 15))
        assert result is not None
        assert result.date_range.start == date(2026, 2, 1)
        assert result.date_range.end == date(2026, 2, 28)

    def test_relative_month_with_different_anchor(self) -> None:
        result = parse_time_expression("上个月的工作日志", now=date(2026, 1, 10))
        assert result is not None
        assert result.date_range.start == date(2025, 12, 1)
        assert result.date_range.end == date(2025, 12, 31)

    def test_defaults_to_today_when_now_is_none(self) -> None:
        os.environ.pop("LIFE_INDEX_TIME_ANCHOR", None)
        result = parse_time_expression("上个月的工作日志")
        assert result is not None
        today = date.today()
        if today.month > 1:
            expected_start = date(today.year, today.month - 1, 1)
        else:
            expected_start = date(today.year - 1, 12, 1)
        assert result.date_range.start == expected_start

    def test_rejected_expressions_return_none(self) -> None:
        assert parse_time_expression("最近的工作日志", now=date(2026, 3, 15)) is None


class TestBuildSearchPlanAnchor:
    """build_search_plan passes reference_date through to time parsing."""

    def test_reference_date_affects_month_expression(self) -> None:
        plan_jan = build_search_plan("上个月的工作日志", reference_date=date(2026, 3, 15))
        plan_mar = build_search_plan("上个月的工作日志", reference_date=date(2026, 5, 10))

        assert plan_jan.date_range is not None
        assert plan_mar.date_range is not None
        # Different anchors → different date ranges
        assert plan_jan.date_range.since != plan_mar.date_range.since

    def test_reference_date_defaults_to_today(self) -> None:
        plan = build_search_plan("上个月的工作日志")
        assert plan.date_range is not None
        today = date.today()
        if today.month > 1:
            expected_start = date(today.year, today.month - 1, 1)
        else:
            expected_start = date(today.year - 1, 12, 1)
        assert plan.date_range.since == expected_start.isoformat()

    def test_no_time_expression_no_date_range(self) -> None:
        plan = build_search_plan("乐乐", reference_date=date(2026, 3, 15))
        assert plan.date_range is None
