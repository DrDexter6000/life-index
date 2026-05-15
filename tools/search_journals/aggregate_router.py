#!/usr/bin/env python3
"""Deterministic aggregate intent router for smart-search.

Detects aggregate/count/trend intent from natural language queries using
regex pattern matching (no LLM). When matched, returns the parameters
needed to call tools.aggregate.core.run_aggregate.

The orchestrator calls try_route_aggregate() before entering the
normal search pipeline.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class AggregateRoute:
    range_str: str
    unit: str
    predicate: str
    query: str


_QUOTE_CHARS = r'"\u201c\u201d\u300c\u300d\'\u2018\u2019'
_QUOTED_TERM_RE = re.compile(rf"[{_QUOTE_CHARS}]([^{_QUOTE_CHARS}]+)[{_QUOTE_CHARS}]")

_MENTION_DAY_PATTERNS = [
    re.compile(r"多少天.*提到"),
    re.compile(r"几天.*提到"),
    re.compile(r"how\s+many\s+days?\s+mention", re.IGNORECASE),
]

_MENTION_PATTERNS = [
    re.compile(r"提到"),
    re.compile(r"提及"),
    re.compile(r"mention", re.IGNORECASE),
    re.compile(r"提到.*次"),
    re.compile(r"几次.*提到"),
]

_LATE_SLEEP_PATTERNS = [
    re.compile(r"晚睡"),
    re.compile(r"late\s+sleep", re.IGNORECASE),
    re.compile(r"熬夜"),
    re.compile(r"睡得晚"),
    re.compile(r"很晚.*睡"),
]

_AGGREGATE_SIGNAL_PATTERNS = [
    re.compile(r"多少"),
    re.compile(r"几[天个]?"),
    re.compile(r"统计"),
    re.compile(r"count", re.IGNORECASE),
    re.compile(r"how\s+many", re.IGNORECASE),
    re.compile(r"频率"),
    re.compile(r"frequency", re.IGNORECASE),
    re.compile(r"趋势"),
    re.compile(r"trend", re.IGNORECASE),
    re.compile(r"几次"),
    re.compile(r"几次了"),
]

_PAST_N_DAYS_RE = re.compile(r"过去(\d+)天")
_PAST_N_DAYS_EN_RE = re.compile(r"past\s+(\d+)\s+days?", re.IGNORECASE)
_LAST_N_DAYS_RE = re.compile(r"last\s+(\d+)\s+days?", re.IGNORECASE)

_CURRENT_YEAR_PATTERNS = [
    re.compile(r"今年"),
    re.compile(r"this\s+year", re.IGNORECASE),
    re.compile(r"年度"),
    re.compile(r"本年度"),
    re.compile(r"current\s+year", re.IGNORECASE),
]

_WRITE_JOURNAL_PATTERNS = [
    re.compile(r"写日志"),
    re.compile(r"写日记"),
    re.compile(r"日志.*频率"),
    re.compile(r"日志.*趋势"),
    re.compile(r"writing\s+(journal|diary|log)", re.IGNORECASE),
    re.compile(r"journal\s+(writing|entries|count|frequency)", re.IGNORECASE),
    re.compile(r"日志.*统计"),
]

_JOURNAL_ENTRY_COUNT_PATTERNS = [
    re.compile(r"多少[篇条个]?(日志|日记|记录)"),
    re.compile(r"几[篇条个](日志|日记|记录)"),
    re.compile(r"(how\s+many|count).*(journal|diary|log)\s+entr", re.IGNORECASE),
    re.compile(r"(how\s+many|count).*(journals|diaries|logs)", re.IGNORECASE),
]

_JOURNAL_DAY_COUNT_PATTERNS = [
    re.compile(r"多少天.*(写日志|写日记|有日志|有日记|有记录)"),
    re.compile(r"几天.*(写日志|写日记|有日志|有日记|有记录)"),
    re.compile(r"(how\s+many|count).*days?.*(journal|diary|log)", re.IGNORECASE),
    re.compile(r"journal.*days?", re.IGNORECASE),
]


def _get_anchor() -> date:
    anchor_str = os.environ.get("LIFE_INDEX_TIME_ANCHOR", "")
    if anchor_str:
        try:
            return date.fromisoformat(anchor_str)
        except ValueError:
            pass
    return date.today()


def detect_aggregate_intent(query: str) -> AggregateRoute | None:
    anchor = _get_anchor()

    past_match = _PAST_N_DAYS_RE.search(query)
    if not past_match:
        past_match = _PAST_N_DAYS_EN_RE.search(query)
    if not past_match:
        past_match = _LAST_N_DAYS_RE.search(query)

    if past_match:
        n_days = int(past_match.group(1))
        has_late_sleep = any(p.search(query) for p in _LATE_SLEEP_PATTERNS)
        has_aggregate_signal = any(p.search(query) for p in _AGGREGATE_SIGNAL_PATTERNS)

        if has_late_sleep and has_aggregate_signal:
            since = anchor - timedelta(days=n_days - 1)
            return AggregateRoute(
                range_str=f"{since.isoformat()}..{anchor.isoformat()}",
                unit="day",
                predicate="entry_time_after=22:00",
                query=query,
            )

        has_journal_day_count = any(p.search(query) for p in _JOURNAL_DAY_COUNT_PATTERNS)
        has_journal_entry_count = any(p.search(query) for p in _JOURNAL_ENTRY_COUNT_PATTERNS)
        if has_aggregate_signal and (has_journal_day_count or has_journal_entry_count):
            since = anchor - timedelta(days=n_days - 1)
            return AggregateRoute(
                range_str=f"{since.isoformat()}..{anchor.isoformat()}",
                unit="day" if has_journal_day_count else "entry",
                predicate="journal_count",
                query=query,
            )

    has_current_year = any(p.search(query) for p in _CURRENT_YEAR_PATTERNS)
    has_write_journal = any(p.search(query) for p in _WRITE_JOURNAL_PATTERNS)
    has_aggregate_signal = any(p.search(query) for p in _AGGREGATE_SIGNAL_PATTERNS)

    if has_current_year and has_write_journal and has_aggregate_signal:
        year_start = date(anchor.year, 1, 1)
        return AggregateRoute(
            range_str=f"{year_start.isoformat()}..{anchor.isoformat()}",
            unit="month",
            predicate="journal_count",
            query=query,
        )

    quoted_match = _QUOTED_TERM_RE.search(query)
    if quoted_match and has_aggregate_signal:
        term = quoted_match.group(1).strip()
        if term:
            has_mention = any(p.search(query) for p in _MENTION_PATTERNS)
            if has_mention:
                use_day = any(p.search(query) for p in _MENTION_DAY_PATTERNS)
                effective_range_str = None
                if past_match:
                    n = int(past_match.group(1))
                    since = anchor - timedelta(days=n - 1)
                    effective_range_str = f"{since.isoformat()}..{anchor.isoformat()}"
                else:
                    for yp in _CURRENT_YEAR_PATTERNS:
                        if yp.search(query):
                            year_start = date(anchor.year, 1, 1)
                            effective_range_str = f"{year_start.isoformat()}..{anchor.isoformat()}"
                            break
                if effective_range_str:
                    return AggregateRoute(
                        range_str=effective_range_str,
                        unit="day" if use_day else "entry",
                        predicate=f"term_presence={term}",
                        query=query,
                    )

    return None


def try_route_aggregate(query: str) -> AggregateRoute | None:
    return detect_aggregate_intent(query)
