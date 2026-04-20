"""Tests for Chinese time expression normalization module (Round 13 Phase 3 T3.1).

RED phase: Run BEFORE implementation to verify tests fail.
"""

from __future__ import annotations

import pytest

from tools.search_journals.chinese_time_units import (
    chinese_numeral_to_int,
    normalize_chinese_time,
)


# ── chinese_numeral_to_int ────────────────────────────────────────────


class TestChineseNumeralToInt:
    """Convert Chinese numeral characters/strings to integers."""

    def test_chinese_numeral_to_int_single(self) -> None:
        assert chinese_numeral_to_int("一") == 1
        assert chinese_numeral_to_int("两") == 2
        assert chinese_numeral_to_int("三") == 3
        assert chinese_numeral_to_int("十") == 10

    def test_chinese_numeral_to_int_compound(self) -> None:
        assert chinese_numeral_to_int("十二") == 12
        assert chinese_numeral_to_int("二十") == 20
        assert chinese_numeral_to_int("十五") == 15
        assert chinese_numeral_to_int("三十一") == 31

    def test_chinese_numeral_to_int_zero(self) -> None:
        assert chinese_numeral_to_int("零") == 0
        assert chinese_numeral_to_int("〇") == 0

    def test_chinese_numeral_to_int_invalid(self) -> None:
        assert chinese_numeral_to_int("") is None
        assert chinese_numeral_to_int("abc") is None

    def test_chinese_numeral_to_int_four(self) -> None:
        assert chinese_numeral_to_int("四") == 4

    def test_chinese_numeral_to_int_nine(self) -> None:
        assert chinese_numeral_to_int("九") == 9

    def test_chinese_numeral_to_int_thirty(self) -> None:
        assert chinese_numeral_to_int("三十") == 30


# ── normalize_chinese_time ────────────────────────────────────────────


class TestNormalizeChineseTime:
    """Normalize Chinese time expressions to parseable forms."""

    def test_normalize_chinese_time_one_month(self) -> None:
        result = normalize_chinese_time("一个月")
        assert result is not None
        assert "1" in result and "月" in result

    def test_normalize_chinese_time_half_year(self) -> None:
        result = normalize_chinese_time("半年")
        assert result is not None
        assert "6" in result and "月" in result

    def test_normalize_chinese_time_one_week(self) -> None:
        result = normalize_chinese_time("一周")
        assert result is not None
        assert "1" in result and "周" in result

    def test_normalize_chinese_time_two_weeks(self) -> None:
        result = normalize_chinese_time("两周")
        assert result is not None
        assert "2" in result and "周" in result

    def test_normalize_chinese_time_one_year(self) -> None:
        result = normalize_chinese_time("一年")
        assert result is not None
        assert "1" in result and "年" in result

    def test_normalize_chinese_time_half_month(self) -> None:
        result = normalize_chinese_time("半个月")
        assert result is not None
        assert "0.5" in result and "月" in result

    def test_normalize_chinese_time_no_match(self) -> None:
        assert normalize_chinese_time("今天天气不错") is None

    def test_normalize_chinese_time_empty(self) -> None:
        assert normalize_chinese_time("") is None

    def test_normalize_chinese_time_in_context(self) -> None:
        """Should extract time expression from a longer query."""
        result = normalize_chinese_time("过去一个月学到了什么")
        assert result is not None
        assert "月" in result

    def test_normalize_chinese_time_two_months(self) -> None:
        """两个月 must be matched, not absorbed by 一个月."""
        result = normalize_chinese_time("两个月")
        assert result is not None
        assert "2" in result

    def test_normalize_chinese_time_three_months(self) -> None:
        result = normalize_chinese_time("三个月")
        assert result is not None
        assert "3" in result and "月" in result

    def test_normalize_chinese_time_two_years(self) -> None:
        result = normalize_chinese_time("两年")
        assert result is not None
        assert "2" in result and "年" in result

    def test_normalize_chinese_time_one_day(self) -> None:
        result = normalize_chinese_time("一天")
        assert result is not None
        assert "1" in result and "天" in result

    def test_normalize_chinese_time_two_days(self) -> None:
        result = normalize_chinese_time("两天")
        assert result is not None
        assert "2" in result and "天" in result

    def test_normalize_chinese_time_big_half_month(self) -> None:
        result = normalize_chinese_time("大半个月")
        assert result is not None
        assert "0.7" in result
