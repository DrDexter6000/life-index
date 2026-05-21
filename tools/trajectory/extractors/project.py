"""Project extractor: frontmatter project + tags + body project names."""

from __future__ import annotations

import re
from typing import Any, Dict, List

# Body patterns like "Project X 项目" or project names from frontmatter
_PROJECT_BODY_RE = re.compile(
    r"([A-Z][a-zA-Z0-9_-]+)[ \t]*(?:项目|project|roadmap|路线图)",
)


def extract_project(metadata: Dict[str, Any], body: str) -> List[str]:
    """Return list of project strings found in metadata, tags, or body."""
    values: List[str] = []

    raw = metadata.get("project")
    if isinstance(raw, str) and raw.strip():
        values.append(raw.strip())

    # Tags that look like project names
    tags = metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    for tag in tags:
        if isinstance(tag, str) and tag.strip():
            tag_clean = tag.strip()
            # Skip generic tags that are unlikely to be project names
            if tag_clean.lower() not in {
                "dev",
                "work",
                "hobby",
                "milestone",
                "holiday",
                "family",
                "bugfix",
                "planning",
                "wrap-up",
                "release",
                "travel",
            }:
                if tag_clean not in values:
                    values.append(tag_clean)

    _DENY_LIST = {"Side", "The", "A", "An", "My", "Our", "This", "That"}
    for match in _PROJECT_BODY_RE.finditer(body):
        proj = match.group(1).strip()
        if proj and len(proj) >= 3 and proj not in _DENY_LIST and proj not in values:
            values.append(proj)

    return values
