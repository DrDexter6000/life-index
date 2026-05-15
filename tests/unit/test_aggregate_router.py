#!/usr/bin/env python3
"""Tests for aggregate_router deterministic route detection.

Covers the quoted term mention aggregate route: explicit quoted term
mention count queries delegate to aggregate with term_presence=TERM.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.search_journals.aggregate_router import detect_aggregate_intent


def _set_anchor(monkeypatch, date_str: str):
    monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", date_str)


class TestQuotedTermMentionRoute:
    def test_chinese_quoted_term_past_n_days_entry_count(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("过去60天有多少次提到\u201cOpenClaw\u201d")
        assert route is not None
        assert "term_presence=OpenClaw" in route.predicate
        assert route.unit == "entry"
        assert route.range_str == "2026-03-17..2026-05-15"

    def test_chinese_quoted_term_past_n_days_day_count(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("过去60天有多少天提到\u201cOpenClaw\u201d")
        assert route is not None
        assert "term_presence=OpenClaw" in route.predicate
        assert route.unit == "day"
        assert route.range_str == "2026-03-17..2026-05-15"

    def test_english_quoted_term_past_n_days_entry_count(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent('past 60 days how many entries mention "OpenClaw"')
        assert route is not None
        assert "term_presence=OpenClaw" in route.predicate
        assert route.unit == "entry"
        assert route.range_str == "2026-03-17..2026-05-15"

    def test_english_quoted_term_past_n_days_day_count(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent('past 60 days how many days mention "OpenClaw"')
        assert route is not None
        assert "term_presence=OpenClaw" in route.predicate
        assert route.unit == "day"

    def test_japanese_corner_quotes(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("过去30天有多少次提到\u300cOpenClaw\u300d")
        assert route is not None
        assert "term_presence=OpenClaw" in route.predicate
        assert route.unit == "entry"

    def test_chinese_topic_term(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("过去90天有多少次提到\u201c投资\u201d")
        assert route is not None
        assert "term_presence=投资" in route.predicate
        assert route.unit == "entry"

    def test_current_year_quoted_term(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("今年有多少次提到\u201cOpenClaw\u201d")
        assert route is not None
        assert "term_presence=OpenClaw" in route.predicate
        assert route.unit == "entry"
        assert route.range_str == "2026-01-01..2026-05-15"


class TestQuotedTermMentionNegative:
    def test_unquoted_term_not_routed(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("过去60天有多少次提到OpenClaw")
        assert route is None

    def test_no_aggregate_signal_not_routed(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("过去60天提到\u201cOpenClaw\u201d")
        assert route is None

    def test_no_time_range_not_routed(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("有多少次提到\u201cOpenClaw\u201d")
        assert route is None

    def test_quoted_term_without_mention_not_routed(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("过去60天有多少个\u201cOpenClaw\u201d")
        assert route is None

    def test_empty_quoted_term_not_routed(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("过去60天有多少次提到\u201c\u201d")
        assert route is None


class TestExistingRoutesUnchanged:
    def test_late_sleep_still_routes(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-13")
        route = detect_aggregate_intent("过去60天我有多少天晚睡")
        assert route is not None
        assert route.predicate == "entry_time_after=22:00"
        assert route.unit == "day"

    def test_journal_entry_count_still_routes(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("过去90天有多少篇日志")
        assert route is not None
        assert route.predicate == "journal_count"
        assert route.unit == "entry"

    def test_journal_day_count_still_routes(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("过去90天有多少天写日志")
        assert route is not None
        assert route.predicate == "journal_count"
        assert route.unit == "day"

    def test_yearly_journal_trend_still_routes(self, monkeypatch):
        _set_anchor(monkeypatch, "2026-05-15")
        route = detect_aggregate_intent("统计一下我今年写日志的频率趋势")
        assert route is not None
        assert route.predicate == "journal_count"
        assert route.unit == "month"

    def test_no_match_returns_none(self):
        route = detect_aggregate_intent("今天心情怎么样")
        assert route is None
