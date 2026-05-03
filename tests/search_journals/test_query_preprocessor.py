"""
Unit tests for query_preprocessor time-range edge cases.
"""

from datetime import date

from tools.search_journals.query_preprocessor import parse_time_range


def test_leap_year_feb_29() -> None:
    """闰年 2月29日 应正确解析，平年应返回 None."""
    # Leap year 2024
    dr = parse_time_range("2月29日", reference_date=date(2024, 3, 1))
    assert dr is not None
    assert dr.since == "2024-02-29"
    assert dr.until == "2024-02-29"

    # Non-leap year 2025
    dr = parse_time_range("2月29日", reference_date=date(2025, 3, 1))
    assert dr is None


def test_last_year_winter_spans_year_boundary() -> None:
    """去年的冬天 应跨越前一年的 12 月到当年 2 月."""
    dr = parse_time_range("去年的冬天", reference_date=date(2026, 5, 2))
    assert dr is not None
    assert dr.since == "2024-12-01"
    assert dr.until == "2025-02-28"


def test_mid_month_boundary() -> None:
    """三月中旬 固定返回 11-20 日."""
    dr = parse_time_range("三月中旬", reference_date=date(2026, 5, 2))
    assert dr is not None
    assert dr.since == "2026-03-11"
    assert dr.until == "2026-03-20"


def test_invalid_month_returns_none() -> None:
    """13月 等无效月份应返回 None 而非抛异常."""
    assert parse_time_range("13月") is None
    assert parse_time_range("0月") is None
    assert parse_time_range("13月15日") is None


if __name__ == "__main__":
    test_leap_year_feb_29()
    test_last_year_winter_spans_year_boundary()
    test_mid_month_boundary()
    test_invalid_month_returns_none()
    print("All query_preprocessor edge-case tests passed.")
