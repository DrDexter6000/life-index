#!/usr/bin/env python3
"""
Life Index - On This Day Core Logic

Deterministic same-month/day recall aid. Consumes the existing `timeline` CLI
via subprocess to find prior-year journal entries that share the same month
and day as the target date.
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "m24.on_this_day.v0"


def _error_result(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    recovery_strategy: str = "ask_user",
) -> Dict[str, Any]:
    """Build a structured error result."""
    err: Dict[str, Any] = {
        "code": code,
        "message": message,
        "details": details if details is not None else {},
        "recovery_strategy": recovery_strategy,
    }
    return {
        "success": False,
        "command": "on-this-day",
        "schema_version": SCHEMA_VERSION,
        "error": err,
    }


def _call_timeline(
    range_start: str,
    range_end: str,
) -> Dict[str, Any]:
    """Invoke timeline CLI via subprocess and return parsed JSON."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools",
            "timeline",
            "--range",
            range_start,
            range_end,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    try:
        payload = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        return {
            "success": False,
            "error": f"timeline output not valid JSON: {exc}",
        }
    if not isinstance(payload, dict):
        return {
            "success": False,
            "error": "timeline output JSON was not an object",
        }
    return payload


def run_on_this_day(
    date_str: Optional[str] = None,
    years_back: int = 10,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Find prior-year journal entries sharing the same month-day.

    Args:
        date_str: Target date in YYYY-MM-DD format. Defaults to today.
        years_back: How many years back to scan (target_year - years_back
            through target_year - 1).
        limit: Maximum number of matches to return.

    Returns:
        Structured JSON result with matches, query metadata, and
        performance counters.
    """
    t0 = time.monotonic()
    timeline_calls = 0

    # --- Parse target date ---
    if date_str is None:
        target_date = datetime.now()
    else:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return _error_result(
                "E2401",
                f"Invalid --date value: '{date_str}'. Expected YYYY-MM-DD.",
            )

    # --- Validate numeric bounds ---
    if years_back < 1:
        return _error_result(
            "E2402",
            f"Invalid --years-back value: {years_back}. Must be >= 1.",
        )
    if limit < 1:
        return _error_result(
            "E2402",
            f"Invalid --limit value: {limit}. Must be >= 1.",
        )

    target_year = target_date.year
    month_day = target_date.strftime("%m-%d")
    since_year = target_year - years_back
    until_year = target_year - 1

    # --- Call timeline per year ---
    all_entries: List[Dict[str, Any]] = []

    for year in range(since_year, until_year + 1):
        month_start = f"{year:04d}-{target_date.strftime('%m')}"
        month_end = month_start

        tl_result = _call_timeline(month_start, month_end)
        timeline_calls += 1

        if not tl_result.get("success", False):
            err_msg = tl_result.get("error", "unknown timeline error")
            return _error_result(
                "E2403",
                f"timeline subprocess failed for {month_start}: {err_msg}",
                {"range": [month_start, month_end]},
            )

        for entry in tl_result.get("entries", []):
            entry_date_str = str(entry.get("date", ""))[:10]
            if not entry_date_str.endswith(f"-{month_day}"):
                continue

            entry_year = int(entry_date_str[:4])
            # Normalise path separators to forward slashes
            raw_path = entry.get("path", "")
            norm_path = raw_path.replace("\\", "/")

            all_entries.append(
                {
                    "date": entry_date_str,
                    "year": entry_year,
                    "years_ago": target_year - entry_year,
                    "title": entry.get("title", ""),
                    "abstract": entry.get("abstract", ""),
                    "mood": entry.get("mood", []),
                    "path": norm_path,
                    "source_command": "timeline",
                }
            )

    # --- Sort newest-first ---
    all_entries.sort(key=lambda e: e["date"], reverse=True)

    # --- Apply limit ---
    matched = all_entries[:limit]

    # --- Evidence paths ---
    evidence_paths = [e["path"] for e in matched]

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    return {
        "success": True,
        "command": "on-this-day",
        "schema_version": SCHEMA_VERSION,
        "query": {
            "date": target_date.strftime("%Y-%m-%d"),
            "month_day": month_day,
            "years_back": years_back,
            "since_year": since_year,
            "until_year": until_year,
        },
        "matches": matched,
        "total": len(matched),
        "evidence_paths": evidence_paths,
        "source_contracts": [
            {
                "command": "timeline",
                "contract": "M16 Public JSON Contract",
            }
        ],
        "limitations": [
            "Deterministic same-month/day recall aid; not narrative synthesis.",
            "Relies on timeline CLI subprocess for journal discovery.",
        ],
        "performance": {
            "timeline_calls": timeline_calls,
            "total_time_ms": elapsed_ms,
        },
        "error": None,
    }
