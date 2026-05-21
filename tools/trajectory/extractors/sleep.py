"""Sleep extractor: frontmatter sleep_hours + body patterns."""

from __future__ import annotations

import re
from typing import Any, Dict, List

_SLEEP_CN_RE = re.compile(r"睡了\s*(\d+(?:\.\d+)?)\s*(?:小时|hours?)")
_SLEEP_EN_RE = re.compile(
    r"(?:slept|sleep)\s+(?:for\s+)?(?:about\s+)?(?:only\s+)?(\d+(?:\.\d+)?)\s*hours?",
    re.IGNORECASE,
)


def extract_sleep(metadata: Dict[str, Any], body: str) -> List[float]:
    """Return list of sleep duration values (hours) found in metadata or body."""
    values: List[float] = []

    raw = metadata.get("sleep_hours")
    if raw is not None:
        try:
            values.append(float(raw))
        except (ValueError, TypeError):
            pass

    for match in _SLEEP_CN_RE.finditer(body):
        try:
            values.append(float(match.group(1)))
        except (ValueError, TypeError):
            pass

    for match in _SLEEP_EN_RE.finditer(body):
        try:
            values.append(float(match.group(1)))
        except (ValueError, TypeError):
            pass

    return values
