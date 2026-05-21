"""Life Index - Trajectory Core Logic

Read-only typed observation extraction across weight, sleep, mood, location,
and project fields. Consumes L2 search CLI via subprocess (no direct L1 reads).
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from .extractors.weight import extract_weight
from .extractors.sleep import extract_sleep
from .extractors.mood import extract_mood
from .extractors.location import extract_location
from .extractors.project import extract_project
from .data_provider import fetch_journals_via_l2

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
    journal_entries = fetch_journals_via_l2(start_month, end_month)

    extractor = FIELD_EXTRACTORS[field]
    observations: List[Dict[str, Any]] = []

    for entry in journal_entries:
        metadata = entry["metadata"]
        if not metadata:
            continue

        date_str = entry["date"]
        if not date_str:
            continue

        body = entry["body"]
        rel_path = entry["rel_path"]

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
            "files_scanned": len(journal_entries),
            "total_time_ms": elapsed_ms,
        },
        "error": None,
    }
