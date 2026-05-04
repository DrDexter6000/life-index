#!/usr/bin/env python3
"""
Time expression parser for Chinese natural-language search queries.

Semantic contracts (frozen for Phase 1-C)
==========================================
The following table is the authoritative definition of each supported expression.
Any deviation must be treated as a schema change (see CHARTER.md §1.8).

Expression          | Output date range (inclusive)
--------------------|----------------------------------
"X月份" / "X月"     | [year-X-01, year-X-last_day]   (year defaults to now.year)
"YYYY年X月"         | [YYYY-X-01, YYYY-X-last_day]
"X月初"             | [year-X-01, year-X-10]           (aligned with query_preprocessor)
"X月中"             | [year-X-11, year-X-20]
"X月底"/"X月末"     | [year-X-25, year-X-last_day]     (aligned with query_preprocessor)
"上个月"            | [prev_month-01, prev_month-last_day]  (relative to now)

REJECTED (return None)
----------------------
"最近" / "N天前" / "上周" / "昨天" / "今天" — any expression whose
interpretation depends on a moving anchor and cannot be frozen for eval.

Eval reproducibility
--------------------
Set LIFE_INDEX_TIME_ANCHOR=YYYY-MM-DD in the environment to pin ``now``.
Production code calls ``parse_time_expression(query)`` without ``now``,
which defaults to ``date.today()``.

Phase 1-D known limitation
--------------------------
Yearless expressions ("三月份", "四月初") default to ``now.year``.
When the corpus spans > 1 year this heuristic will become ambiguous.
The fix is tracked as a post-Phase-1-C decision (ADR-024 known-limitations).
"""

from __future__ import annotations

import calendar
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DateRange:
    """Inclusive date range."""

    start: date
    end: date


@dataclass(frozen=True)
class TimeFilter:
    """Result of parsing a time expression."""

    date_range: DateRange
    # The exact substring of the original query that matched.
    matched_span: str


# ---------------------------------------------------------------------------
# Reproducibility hook
# ---------------------------------------------------------------------------

_EVAL_ANCHOR_ENV: str = "LIFE_INDEX_TIME_ANCHOR"


def _eval_anchor() -> date | None:
    env = os.environ.get(_EVAL_ANCHOR_ENV)
    if env:
        return date.fromisoformat(env)
    return None


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

_MONTH_NAMES: dict[str, int] = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "11": 11,
    "12": 12,
    "01": 1,
    "02": 2,
    "03": 3,
    "04": 4,
    "05": 5,
    "06": 6,
    "07": 7,
    "08": 8,
    "09": 9,
}

# Map Chinese month part qualifiers to (start_day, end_day_fn)
# "底" is treated as an alias for "末" (common colloquial usage).
_MONTH_PARTS: dict[str, tuple[int, Any]] = {
    "初": (1, lambda _: 10),  # 1-10 to align with query_preprocessor (fixes GQ57 regression)
    "中": (11, lambda _: 20),
    "末": (25, calendar.monthrange),  # aligned with query_preprocessor
    "底": (25, calendar.monthrange),  # aligned with query_preprocessor
}


# ---------------------------------------------------------------------------
# Low-level parsers (operate on the matched text only)
# ---------------------------------------------------------------------------


def _parse_explicit_year_month(text: str) -> TimeFilter | None:
    """Parse '2026年3月' or '2026年03月' or '2026年三月份'."""
    m = re.match(r"(\d{4})年([一二三四五六七八九十\d]{1,2})月(?:份)?", text)
    if not m:
        return None
    year = int(m.group(1))
    month = _MONTH_NAMES.get(m.group(2))
    if month is None:
        return None
    _, last_day = calendar.monthrange(year, month)
    return TimeFilter(
        date_range=DateRange(
            start=date(year, month, 1),
            end=date(year, month, last_day),
        ),
        matched_span=m.group(0),
    )


def _parse_month_only(text: str, now: date) -> TimeFilter | None:
    """Parse '三月份' or '3月' (year defaults to now.year)."""
    m = re.match(r"([一二三四五六七八九十\d]{1,2})月(?:份)?", text)
    if not m:
        return None
    month = _MONTH_NAMES.get(m.group(1))
    if month is None:
        return None
    year = now.year
    _, last_day = calendar.monthrange(year, month)
    return TimeFilter(
        date_range=DateRange(
            start=date(year, month, 1),
            end=date(year, month, last_day),
        ),
        matched_span=m.group(0),
    )


def _parse_month_part(text: str, now: date) -> TimeFilter | None:
    """Parse '四月初', '三月中', '二月底'."""
    m = re.match(r"([一二三四五六七八九十\d]{1,2})月(初|中|末|底)", text)
    if not m:
        return None
    month = _MONTH_NAMES.get(m.group(1))
    if month is None:
        return None
    part = m.group(2)
    year = now.year
    start_day, end_fn = _MONTH_PARTS[part]
    if end_fn is calendar.monthrange:
        _, end_day = end_fn(year, month)
    else:
        end_day = end_fn(year)
    return TimeFilter(
        date_range=DateRange(
            start=date(year, month, start_day),
            end=date(year, month, end_day),
        ),
        matched_span=m.group(0),
    )


def _parse_relative(text: str, now: date) -> TimeFilter | None:
    """Parse '上个月'. REJECTS all other relative expressions."""
    if text.strip() == "上个月":
        if now.month == 1:
            year = now.year - 1
            month = 12
        else:
            year = now.year
            month = now.month - 1
        _, last_day = calendar.monthrange(year, month)
        return TimeFilter(
            date_range=DateRange(
                start=date(year, month, 1),
                end=date(year, month, last_day),
            ),
            matched_span="上个月",
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Ordered from most-specific to least-specific. The first match wins.
_PATTERN_HANDLERS: list[tuple[re.Pattern, Any]] = [
    (re.compile(r"\d{4}年[一二三四五六七八九十\d]{1,2}月(?:份)?"), _parse_explicit_year_month),
    # Month-part MUST come before month-only to prevent "四月初" matching "四月"
    (re.compile(r"[一二三四五六七八九十\d]{1,2}月[初中末底]"), _parse_month_part),
    (re.compile(r"[一二三四五六七八九十\d]{1,2}月(?:份)?"), _parse_month_only),
    (re.compile(r"上个月"), _parse_relative),
]


# Expressions we explicitly do NOT support (range connectors, anchor drift)
_RANGE_CONNECTORS = re.compile(r"[到至~\-—]")


def parse_time_expression(query: str, now: date | None = None) -> TimeFilter | None:
    """Extract the first supported time expression from *query*.

    Args:
        query: Free-form Chinese search query (e.g. "三月份的工作日志").
        now:   Anchor date for relative expressions and year-defaulting.
               If ``None``, uses ``LIFE_INDEX_TIME_ANCHOR`` env var when set,
               otherwise ``date.today()``.

    Returns:
        ``TimeFilter`` if a supported expression is found, ``None`` otherwise.
        "最近" and other anchor-drift expressions always return ``None``.
        Range expressions ("三月到四月") also return ``None`` — they require
        a range parser that is out of scope for Phase 1-C.
    """
    if now is None:
        now = _eval_anchor() or date.today()

    # Phase 1-C limitation: we only handle single time expressions.
    # Range expressions like "三月下旬到四月" would match "三月" and
    # produce a wrong filter that excludes the second month's data (e.g. GQ58).
    if _RANGE_CONNECTORS.search(query):
        return None

    for pattern, handler in _PATTERN_HANDLERS:
        m = pattern.search(query)
        if m:
            span = m.group(0)
            result = handler(span, now) if handler.__code__.co_argcount > 1 else handler(span)
            if result is not None:
                return result  # type: ignore[no-any-return]

    return None
