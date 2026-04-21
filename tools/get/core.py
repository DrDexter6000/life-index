#!/usr/bin/env python3
"""
Life Index - Get Command Core Logic
Retrieves a single journal entry by ID (filename stem).
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from ..lib.paths import get_journals_dir
from ..lib.frontmatter import parse_journal_file


def get_journal(journal_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a journal entry by its ID (filename stem without .md).

    Args:
        journal_id: Journal filename stem, e.g. "life-index_2026-04-19_001"

    Returns:
        Dict matching the GUI contract, or None if not found.
    """
    journals_dir = get_journals_dir()
    if not journals_dir.exists():
        return None

    # Search for file matching the stem
    match = _find_journal_file(journals_dir, journal_id)
    if match is None:
        return None

    return _parse_to_contract(match, journal_id)


def _find_journal_file(journals_dir: Path, journal_id: str) -> Optional[Path]:
    """Find journal file by stem across year/month directories."""
    # Try extracting date from the ID for direct lookup
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", journal_id)
    if date_match:
        year = date_match.group(1)
        month = date_match.group(2)
        direct = journals_dir / year / month / f"{journal_id}.md"
        if direct.exists():
            return direct

    # Fallback: full scan
    for year_dir in journals_dir.iterdir():
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue
            candidate = month_dir / f"{journal_id}.md"
            if candidate.exists():
                return candidate

    return None


def _parse_to_contract(file_path: Path, journal_id: str) -> Dict[str, Any]:
    """Parse journal file into the GUI contract format."""
    parsed = parse_journal_file(file_path)
    if "_error" in parsed:
        return None  # type: ignore[return-value]

    body = parsed.get("_body", "")
    title_match = re.search(r"^# (.+)$", body, re.MULTILINE)
    title = title_match.group(1) if title_match else parsed.get("title", journal_id)

    # Strip the title line from content to get pure body
    content = body
    if title_match:
        content = body[title_match.end() :].strip()

    word_count = len(body.split())

    return {
        "id": journal_id,
        "title": str(parsed.get("title", title)),
        "content": content,
        "date": str(parsed.get("date", ""))[:10],
        "location": parsed.get("location", ""),
        "mood": parsed.get("mood", []),
        "weather": parsed.get("weather", ""),
        "tags": parsed.get("tags", []),
        "entities": parsed.get("entities", []),
        "sentiment_score": parsed.get("sentiment_score"),
        "themes": parsed.get("themes", []),
        "links": parsed.get("links", []),
        "attachments": parsed.get("attachments", []),
        "word_count": word_count,
    }
