"""L2 subprocess adapter for trajectory data access.

trajectory must not read journal files directly; it consumes the L2 search CLI
via subprocess and extracts typed observation sources from the returned JSON.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from calendar import monthrange
from datetime import datetime
from typing import Any, Dict, List


def _last_day_of_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def _build_date_range(start_month: str, end_month: str) -> tuple[str, str]:
    end_dt = datetime.strptime(end_month, "%Y-%m")
    start_date = f"{start_month}-01"
    end_date = f"{end_month}-{_last_day_of_month(end_dt.year, end_dt.month):02d}"
    return start_date, end_date


def fetch_journals_via_l2(
    start_month: str,
    end_month: str,
    timeout: int = 120,
) -> List[Dict[str, Any]]:
    """Fetch journal metadata and body via L2 search CLI subprocess.

    Returns a list of dicts with keys:
        - metadata: frontmatter dict
        - body: journal body text
        - rel_path: relative path under data dir
        - date: YYYY-MM-DD date string
    """
    date_from, date_to = _build_date_range(start_month, end_month)

    cmd = [
        sys.executable,
        "-m",
        "tools",
        "search",
        "--query",
        "",
        "--date-from",
        date_from,
        "--date-to",
        date_to,
        "--no-semantic",
        "--no-index",
        "--limit",
        "1000",
        "--read-top",
        "1000",
    ]

    env = os.environ.copy()
    env["LIFE_INDEX_L2_CACHE"] = "0"

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )

    if proc.returncode != 0:
        return []

    try:
        payload = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(payload, dict):
        return []

    results: List[Dict[str, Any]] = []
    for item in payload.get("merged_results", []):
        rel_path = item.get("rel_path", "")
        # Skip monthly abstraction files
        if rel_path and "monthly_" in rel_path.split("/")[-1]:
            continue

        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            continue

        body = item.get("full_content", "") or ""
        date_str = str(metadata.get("date", ""))[:10]

        results.append(
            {
                "metadata": metadata,
                "body": body,
                "rel_path": rel_path,
                "date": date_str,
            }
        )

    # Sort by path for stable ordering
    results.sort(key=lambda r: r["rel_path"])
    return results
