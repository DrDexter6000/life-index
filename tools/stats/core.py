#!/usr/bin/env python3
"""
Life Index - Stats Command Core Logic
Computes dashboard statistics from journal files.
"""

import yaml
from collections import Counter
from datetime import date, timedelta
from typing import Any, Dict, List

from ..lib.paths import get_journals_dir

# Celestial 7 topic color mapping
TOPIC_COLORS: Dict[str, str] = {
    "work": "#FFE792",
    "learn": "#92C7FF",
    "health": "#92FFB6",
    "relation": "#FF92B6",
    "think": "#C792FF",
    "create": "#FFB692",
    "life": "#CBD5E1",
}
DEFAULT_TOPIC_COLOR = "#CBD5E1"


def compute_stats() -> Dict[str, Any]:
    """
    Compute dashboard statistics.

    Returns dict matching the GUI contract:
        totalJournals, totalWords, activeDays, streakDays, avgWordsPerDay,
        topics, moods, heatmap
    """
    journals_dir = get_journals_dir()
    total_journals = 0
    total_words = 0
    unique_dates: set[str] = set()
    date_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    mood_counts: Counter[str] = Counter()

    if journals_dir.exists():
        for year_dir in sorted(journals_dir.iterdir()):
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue
            for month_dir in sorted(year_dir.iterdir()):
                if not month_dir.is_dir():
                    continue
                for f in sorted(month_dir.glob("*.md")):
                    if f.name.startswith("monthly_"):
                        continue
                    total_journals += 1
                    try:
                        text = f.read_text(encoding="utf-8")
                        total_words += len(text.split())
                        if text.startswith("---"):
                            parts = text.split("---", 2)
                            if len(parts) >= 2:
                                try:
                                    fm = yaml.safe_load(parts[1]) or {}
                                except yaml.YAMLError:
                                    fm = {}
                                d = fm.get("date")
                                if d:
                                    ds = str(d)[:10]
                                    unique_dates.add(ds)
                                    date_counts[ds] += 1
                                _collect_list_field(fm, "topic", topic_counts)
                                _collect_list_field(fm, "mood", mood_counts)
                    except (IOError, OSError, UnicodeDecodeError):
                        continue

    streak = _compute_streak(unique_dates)
    active_days = len(unique_dates)
    avg_words = round(total_words / active_days) if active_days > 0 else 0

    return {
        "totalJournals": total_journals,
        "totalWords": total_words,
        "activeDays": active_days,
        "streakDays": streak,
        "avgWordsPerDay": avg_words,
        "topics": _build_topics(topic_counts),
        "moods": [{"name": name, "count": cnt} for name, cnt in mood_counts.most_common()],
        "heatmap": [{"date": d, "count": c} for d, c in sorted(date_counts.items())],
    }


def _collect_list_field(fm: Dict[str, Any], field: str, counter: Counter) -> None:
    """Collect values from a frontmatter list field into a counter."""
    val = fm.get(field, [])
    if isinstance(val, str):
        val = [val]
    if isinstance(val, list):
        for item in val:
            if isinstance(item, str) and item.strip():
                counter[item.strip()] += 1


def _build_topics(topic_counts: Counter) -> List[Dict[str, Any]]:
    """Build topic list with Celestial 7 color mapping."""
    result = []
    for name, cnt in topic_counts.most_common():
        color = TOPIC_COLORS.get(name.lower(), DEFAULT_TOPIC_COLOR)
        result.append({"name": name, "count": cnt, "color": color})
    return result


def _compute_streak(dates: set[str]) -> int:
    """
    Compute current writing streak: count consecutive days ending at
    today or yesterday. Returns 0 if no recent writing.
    """
    if not dates:
        return 0

    today = date.today()
    yesterday = today - timedelta(days=1)
    today_s = today.isoformat()
    yesterday_s = yesterday.isoformat()

    # Streak must end at today or yesterday
    if today_s not in dates and yesterday_s not in dates:
        return 0

    # Start counting from whichever is present
    current = today if today_s in dates else yesterday
    streak = 0
    while current.isoformat() in dates:
        streak += 1
        current -= timedelta(days=1)

    return streak
