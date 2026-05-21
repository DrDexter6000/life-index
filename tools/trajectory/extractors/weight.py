"""Weight extractor: frontmatter weight_kg + body patterns."""

from __future__ import annotations

import re
from typing import Any, Dict, List

_WEIGHT_BODY_RE = re.compile(
    r"体重[:：]\s*(\d+(?:\.\d+)?)\s*kg",
    re.IGNORECASE,
)
_WEIGHT_EN_RE = re.compile(
    r"(?:weight|weighed)\s+(?:at\s+)?(\d+(?:\.\d+)?)\s*kg",
    re.IGNORECASE,
)


def extract_weight(metadata: Dict[str, Any], body: str) -> List[float]:
    """Return list of weight values (kg) found in metadata or body."""
    values: List[float] = []

    raw = metadata.get("weight_kg")
    if raw is not None:
        try:
            values.append(float(raw))
        except (ValueError, TypeError):
            pass

    for match in _WEIGHT_BODY_RE.finditer(body):
        try:
            values.append(float(match.group(1)))
        except (ValueError, TypeError):
            pass

    for match in _WEIGHT_EN_RE.finditer(body):
        try:
            values.append(float(match.group(1)))
        except (ValueError, TypeError):
            pass

    return values
