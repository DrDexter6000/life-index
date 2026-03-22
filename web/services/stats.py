"""Dashboard stats aggregation service."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from tools.lib.frontmatter import parse_journal_file
from tools.lib.metadata_cache import get_all_cached_metadata


@dataclass(slots=True)
class DashboardStats:
    total_journals: int = 0
    total_words: int = 0
    longest_streak: int = 0
    current_streak: int = 0
    month_journals: int = 0
    most_frequent_mood: str = ""
    most_active_topic: str = ""
    on_this_day: list[dict[str, Any]] = field(default_factory=list)
    milestone: int = 0
    mood_frequency: list[dict[str, Any]] = field(default_factory=list)
    topic_distribution: list[dict[str, Any]] = field(default_factory=list)
    tag_cloud: list[dict[str, Any]] = field(default_factory=list)
    people_graph: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {"nodes": [], "edges": []}
    )
    heatmap: dict[str, int] = field(default_factory=dict)


def _today() -> date:
    return date.today()


def _today_month_day() -> tuple[int, int]:
    today = _today()
    return today.month, today.day


def _compute_total_words(entries: list[dict[str, Any]]) -> int:
    total = 0
    for entry in entries:
        file_path = entry.get("file_path")
        if not file_path:
            continue
        parsed = parse_journal_file(Path(file_path))
        total += len(str(parsed.get("_body", "")).split())
    return total


def _parse_dates(entries: list[dict[str, Any]]) -> list[date]:
    parsed_dates: list[date] = []
    for entry in entries:
        raw = entry.get("date")
        if not raw:
            continue
        try:
            parsed_dates.append(datetime.strptime(str(raw)[:10], "%Y-%m-%d").date())
        except ValueError:
            continue
    return sorted(set(parsed_dates))


def _compute_streaks(entries: list[dict[str, Any]]) -> tuple[int, int]:
    dates = _parse_dates(entries)
    if not dates:
        return 0, 0

    longest = 1
    current_run = 1
    for idx in range(1, len(dates)):
        if (dates[idx] - dates[idx - 1]).days == 1:
            current_run += 1
            longest = max(longest, current_run)
        else:
            current_run = 1

    today = _today()
    date_set = set(dates)
    probe = today
    current = 0
    while probe in date_set:
        current += 1
        probe = probe.fromordinal(probe.toordinal() - 1)

    return longest, current


def _counter_to_chart(counter: Counter[str]) -> list[dict[str, Any]]:
    return [{"name": name, "value": value} for name, value in counter.most_common()]


def _build_on_this_day(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    month, day = _today_month_day()
    matches: list[dict[str, Any]] = []
    for entry in entries:
        raw = str(entry.get("date", ""))[:10]
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            continue
        if parsed.month == month and parsed.day == day:
            matches.append(
                {
                    "date": raw,
                    "title": entry.get("title", "无标题"),
                    "abstract": entry.get("abstract", ""),
                    "journal_route_path": entry.get("journal_route_path", ""),
                }
            )
    return sorted(matches, key=lambda item: item["date"], reverse=True)


def _build_people_graph(
    entries: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    people_counter: Counter[str] = Counter()
    edge_counter: Counter[tuple[str, str]] = Counter()

    for entry in entries:
        people = [str(name) for name in entry.get("people", []) if name]
        for name in people:
            people_counter[name] += 1
        unique_people = sorted(set(people))
        for idx in range(len(unique_people)):
            for jdx in range(idx + 1, len(unique_people)):
                edge_counter[(unique_people[idx], unique_people[jdx])] += 1

    return {
        "nodes": [
            {"name": name, "count": count}
            for name, count in people_counter.most_common()
        ],
        "edges": [
            {"source": source, "target": target, "weight": weight}
            for (source, target), weight in edge_counter.items()
        ],
    }


def compute_dashboard_stats() -> DashboardStats:
    try:
        entries = get_all_cached_metadata()
    except Exception:
        entries = []

    stats = DashboardStats()
    stats.total_journals = len(entries)
    stats.total_words = _compute_total_words(entries)

    longest_streak, current_streak = _compute_streaks(entries)
    stats.longest_streak = longest_streak
    stats.current_streak = current_streak
    stats.month_journals = sum(
        1
        for entry in entries
        if str(entry.get("date", ""))[:7] == _today().strftime("%Y-%m")
    )
    stats.milestone = max(
        (m for m in (7, 30, 100, 365) if longest_streak >= m), default=0
    )

    mood_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()
    heatmap_counter: Counter[str] = Counter()

    for entry in entries:
        for mood in entry.get("mood", []):
            mood_counter[str(mood)] += 1
        for topic in entry.get("topic", []):
            topic_counter[str(topic)] += 1
        for tag in entry.get("tags", []):
            tag_counter[str(tag)] += 1
        raw_date = str(entry.get("date", ""))[:10]
        if raw_date:
            heatmap_counter[raw_date] += 1

    stats.most_frequent_mood = mood_counter.most_common(1)[0][0] if mood_counter else ""
    stats.most_active_topic = (
        topic_counter.most_common(1)[0][0] if topic_counter else ""
    )
    stats.mood_frequency = _counter_to_chart(mood_counter)
    stats.topic_distribution = _counter_to_chart(topic_counter)
    stats.tag_cloud = _counter_to_chart(tag_counter)
    stats.people_graph = _build_people_graph(entries)
    stats.heatmap = dict(heatmap_counter)
    stats.on_this_day = _build_on_this_day(entries)

    return stats
