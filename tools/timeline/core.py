#!/usr/bin/env python3
"""
Life Index - Timeline Command Core Logic
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..lib.paths import get_journals_dir
from ..lib.frontmatter import (
    empty_indexable_metadata,
    indexable_date,
    normalize_indexable_metadata,
    parse_journal_file,
)


def run_timeline(
    range_start: str,
    range_end: str,
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate chronological summary stream.

    Args:
        range_start: Start month (YYYY-MM)
        range_end: End month (YYYY-MM)
        topic: Optional topic filter

    Returns:
        {
            "success": bool,
            "range": [start, end],
            "entries": [...],
            "total": int
        }
    """
    result: Dict[str, Any] = {
        "success": True,
        "range": [range_start, range_end],
        "entries": [],
        "total": 0,
    }

    # Parse range
    try:
        start_date = datetime.strptime(range_start, "%Y-%m")
        end_date = datetime.strptime(range_end, "%Y-%m")
    except ValueError:
        result["success"] = False
        result["error"] = "Invalid date format. Use YYYY-MM"
        return result

    # Scan journals
    _journals_dir = get_journals_dir()
    if not _journals_dir.exists():
        return result

    entries: List[Dict] = []

    for year_dir in _journals_dir.iterdir():
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue

        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue

            # Check if month is in range
            try:
                month_str = f"{year_dir.name}-{month_dir.name}"
                month_date = datetime.strptime(month_str, "%Y-%m")

                if start_date <= month_date <= end_date:
                    # Scan journals in this month
                    for journal_file in month_dir.glob("life-index_*.md"):
                        if journal_file.name.startswith("monthly_"):
                            continue

                        metadata = parse_journal_file(journal_file)
                        if not metadata:
                            continue

                        # D7: read every field through the shared rule, so
                        # ``topic: null``, a mapping in a field or an unparsable
                        # frontmatter can never raise here.
                        indexable = (
                            normalize_indexable_metadata(metadata) or empty_indexable_metadata()
                        )

                        # Topic filter
                        if topic and topic not in indexable["topic"]:
                            continue

                        # Extract fields
                        entry = {
                            "date": indexable_date(indexable, journal_file),
                            "title": indexable["title"],
                            "mood": indexable["mood"],
                            "abstract": indexable["abstract"],
                            "path": str(journal_file.relative_to(_journals_dir.parent)),
                        }
                        entries.append(entry)
            except ValueError:
                continue

    # Sort by date
    entries.sort(key=lambda x: x["date"])

    result["entries"] = entries
    result["total"] = len(entries)

    return result
