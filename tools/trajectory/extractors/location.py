"""Location extractor: frontmatter location + body patterns."""

from __future__ import annotations

import re
from typing import Any, Dict, List

# Chinese pattern: 在 <location> 的 / 里 / 看 / 工作
_LOCATION_CN_RE = re.compile(
    r"在[ \t]*([A-Za-z][A-Za-z']*|[\u4e00-\u9fff]{2,}?)[ \t]*"
    r"(?:的|里|看|工作|讨论|散步|第二|最后|一晚|咖啡馆|办公室|园林)",
)

# English pattern: in/at <location>
_LOCATION_EN_RE = re.compile(
    r"(?:in|at)[ \t]+([A-Z][a-zA-Z']*(?:[ ]+[A-Z][a-zA-Z']*)*)",
)


def extract_location(metadata: Dict[str, Any], body: str) -> List[str]:
    """Return list of location strings found in metadata or body."""
    values: List[str] = []

    raw = metadata.get("location")
    if isinstance(raw, str) and raw.strip():
        values.append(raw.strip())

    for match in _LOCATION_CN_RE.finditer(body):
        loc = match.group(1).strip()
        if loc and loc not in values:
            values.append(loc)

    for match in _LOCATION_EN_RE.finditer(body):
        loc = match.group(1).strip()
        if loc and loc not in values:
            values.append(loc)

    return values
