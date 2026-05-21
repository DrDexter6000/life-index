"""Life Index - Trajectory Core Logic

Read-only typed observation extraction across weight, sleep, mood, location,
and project fields. Scans journal files directly (no index dependency).
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from ..lib.paths import get_journals_dir
from ..lib.frontmatter import parse_journal_file
from .extractors.weight import extract_weight
from .extractors.sleep import extract_sleep
from .extractors.mood import extract_mood
from .extractors.location import extract_location
from .extractors.project import extract_project

SCHEMA_VERSION = "m26.trajectory.v0"

ExtractorFunc = Callable[[Dict[str, Any], str], List[Any]]

FIELD_EXTRACTORS: Dict[str, ExtractorFunc] = {
    "weight": extract_weight,
    "sleep": extract_sleep,
    "mood": extract_mood,
    "location": extract_location,
    "project": extract_project,
}


def _error_result(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    recovery_strategy: str = "ask_user",
) -> Dict[str, Any]:
    err: Dict[str, Any] = {
        "code": code,
        "message": message,
        "details": details if details is not None else {},
        "recovery_strategy": recovery_strategy,
    }
    return {
        "success": False,
        "command": "trajectory",
        "schema_version": SCHEMA_VERSION,
        "error": err,
    }


def _parse_range(range_str: str) -> Optional[tuple[str, str]]:
    """Parse range string like '2025-01..2025-12' into (start, end) month strings."""
    if ".." not in range_str:
        return None
    start, end = range_str.split("..", 1)
    start = start.strip()
    end = end.strip()
    # Validate month format YYYY-MM
    try:
        datetime.strptime(start, "%Y-%m")
        datetime.strptime(end, "%Y-%m")
    except ValueError:
        return None
    return start, end


def _month_in_range(month_str: str, start: str, end: str) -> bool:
    """Check if YYYY-MM string is within inclusive range."""
    return start <= month_str <= end


def _scan_journals(start_month: str, end_month: str) -> List[Path]:
    """Scan journals directory and return files within month range."""
    journals_dir = get_journals_dir()
    if not journals_dir.exists():
        return []

    files: List[Path] = []
    for year_dir in journals_dir.iterdir():
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue
            month_str = f"{year_dir.name}-{month_dir.name}"
            if not _month_in_range(month_str, start_month, end_month):
                continue
            for journal_file in month_dir.glob("life-index_*.md"):
                if journal_file.name.startswith("monthly_"):
                    continue
                files.append(journal_file)

    # Sort by path for stable ordering
    files.sort(key=lambda p: p.as_posix())
    return files


def _make_observation(
    field: str,
    value: Any,
    time_str: str,
    rel_path: str,
) -> Dict[str, Any]:
    return {
        "type": field,
        "value": value,
        "time": time_str,
        "evidence_paths": [rel_path],
    }


def run_trajectory(field: str, range_str: str) -> Dict[str, Any]:
    """Extract typed observations for a given field over a month range.

    Args:
        field: One of weight, sleep, mood, location, project.
        range_str: Month range like '2025-01..2025-12'.

    Returns:
        Structured JSON result with observations list.
    """
    t0 = time.monotonic()

    if field not in FIELD_EXTRACTORS:
        return _error_result(
            "E2601",
            f"Invalid field: '{field}'. Allowed: {', '.join(FIELD_EXTRACTORS.keys())}.",
        )

    parsed = _parse_range(range_str)
    if parsed is None:
        return _error_result(
            "E2602",
            f"Invalid range: '{range_str}'. Expected YYYY-MM..YYYY-MM.",
        )

    start_month, end_month = parsed
    journal_files = _scan_journals(start_month, end_month)

    extractor = FIELD_EXTRACTORS[field]
    observations: List[Dict[str, Any]] = []
    journals_dir = get_journals_dir()
    data_dir = journals_dir.parent

    for journal_file in journal_files:
        metadata = parse_journal_file(journal_file)
        if not metadata or "_error" in metadata:
            continue

        date_str = str(metadata.get("date", ""))[:10]
        if not date_str:
            continue

        body = metadata.get("_body", "")
        rel_path = journal_file.relative_to(data_dir).as_posix()

        values = extractor(metadata, body)
        for value in values:
            observations.append(_make_observation(field, value, date_str, rel_path))

    # Sort by time ascending
    observations.sort(key=lambda o: o["time"])

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    return {
        "success": True,
        "command": "trajectory",
        "schema_version": SCHEMA_VERSION,
        "field": field,
        "range": [start_month, end_month],
        "observations": observations,
        "total": len(observations),
        "performance": {
            "files_scanned": len(journal_files),
            "total_time_ms": elapsed_ms,
        },
        "error": None,
    }
