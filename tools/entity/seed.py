"""
Entity graph cold-start: seed from journal frontmatter.

Extracts entity candidates from people/tags/location fields across
all journals. Only entities appearing >= min_frequency times are
included. The seed operation is idempotent: existing graph entries
are never modified.

Round 10, T1.1 (D3).
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..lib.entity_graph import load_entity_graph, save_entity_graph
from ..lib.frontmatter import parse_frontmatter

logger = logging.getLogger(__name__)


# ── Data structures ─────────────────────────────────────────────────────


@dataclass
class EntityCandidate:
    """A candidate entity extracted from journal frontmatter."""

    primary_name: str
    type: str  # person | place | project | event | concept
    frequency: int = 1
    source_field: str = ""  # people | location | tags


# ── Type inference rules ────────────────────────────────────────────────

# Tags matching this pattern are classified as "tool" (software, libraries, frameworks)
_TOOL_PATTERN = re.compile(r"^[A-Z][a-zA-Z0-9 ]+$")


def _infer_type_from_source(source_field: str, value: str) -> str:
    """
    Infer entity type from the frontmatter field it came from.

    Rules:
    - people → person
    - location → place
    - tags + matches TOOL_PATTERN → concept (v1 schema has no "tool" type)
    - tags + doesn't match → concept
    """
    if source_field == "people":
        return "person"
    if source_field == "location":
        return "place"
    if source_field == "tags":
        if _TOOL_PATTERN.match(value):
            return "concept"
        return "concept"
    return "concept"


# ── Candidate collection ────────────────────────────────────────────────


def collect_candidates(
    journals_dir: Path,
    min_frequency: int = 2,
) -> list[EntityCandidate]:
    """
    Scan all journal frontmatter and collect entity candidates.

    Args:
        journals_dir: Path to Journals/ directory
        min_frequency: Minimum number of occurrences to include (default 2)

    Returns:
        List of EntityCandidate sorted by frequency (descending).
    """
    if not journals_dir.exists():
        return []

    # Accumulate counts per (name, source_field)
    counter: Counter[tuple[str, str]] = Counter()

    # Walk all markdown files in year/month subdirectories
    for year_dir in sorted(journals_dir.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            for md_file in sorted(month_dir.glob("*.md")):
                _extract_frontmatter_entities(md_file, counter)

    # Build candidates with frequency >= threshold
    # Group by name (may appear in multiple fields)
    name_data: dict[str, dict[str, Any]] = {}
    for (name, source_field), count in counter.items():
        if name not in name_data or count > name_data[name]["frequency"]:
            name_data[name] = {
                "frequency": count,
                "source_field": source_field,
                "value": name,
            }
        else:
            name_data[name]["frequency"] += count

    candidates = []
    for name, data in name_data.items():
        if data["frequency"] >= min_frequency:
            entity_type = _infer_type_from_source(data["source_field"], data["value"])
            candidates.append(
                EntityCandidate(
                    primary_name=name,
                    type=entity_type,
                    frequency=data["frequency"],
                    source_field=data["source_field"],
                )
            )

    # Sort by frequency descending, then name for determinism
    candidates.sort(key=lambda c: (-c.frequency, c.primary_name))
    return candidates


def _extract_frontmatter_entities(md_file: Path, counter: Counter[tuple[str, str]]) -> None:
    """Parse a single journal file and accumulate entity counts."""
    try:
        content = md_file.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return

        metadata, _ = parse_frontmatter(content)
        if not metadata:
            return

        # Extract from people field
        people = metadata.get("people", [])
        if isinstance(people, list):
            for name in people:
                if isinstance(name, str) and name.strip():
                    counter[(name.strip(), "people")] += 1

        # Extract from location field
        location = metadata.get("location", "")
        if isinstance(location, str) and location.strip():
            counter[(location.strip(), "location")] += 1

        # Extract from tags field
        tags = metadata.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.strip():
                    counter[(tag.strip(), "tags")] += 1

    except (OSError, ValueError) as e:
        logger.debug("Skipping %s: %s", md_file, e)


# ── Seed operation ──────────────────────────────────────────────────────


def seed_entity_graph(
    graph_path: Path,
    journals_dir: Path,
    min_frequency: int = 2,
) -> dict[str, Any]:
    """
    Cold-start entity graph from journal frontmatter.

    Idempotent: existing entities are never modified.
    Only new primary_names not already in the graph are added.

    Args:
        graph_path: Path to entity_graph.yaml
        journals_dir: Path to Journals/ directory
        min_frequency: Minimum occurrences to include

    Returns:
        {
            "success": bool,
            "added": list[dict],
            "skipped_existing": list[dict],
            "skipped_low_frequency": list[dict],
            "error": str | None,
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "added": [],
        "skipped_existing": [],
        "skipped_low_frequency": [],
        "error": None,
    }

    try:
        # Load existing graph (may be empty)
        existing = load_entity_graph(graph_path)
        existing_names = {e["primary_name"] for e in existing}

        # Collect candidates from frontmatter
        candidates = collect_candidates(journals_dir, min_frequency)

        new_entities: list[dict[str, Any]] = []

        for candidate in candidates:
            if candidate.primary_name in existing_names:
                result["skipped_existing"].append(
                    {
                        "primary_name": candidate.primary_name,
                        "type": candidate.type,
                        "frequency": candidate.frequency,
                    }
                )
                continue

            # Generate a stable ID
            entity_id = f"seed_{candidate.type}_{candidate.primary_name.replace(' ', '_').lower()}"

            # Ensure ID uniqueness
            existing_ids = {e["id"] for e in existing} | {e["id"] for e in new_entities}
            if entity_id in existing_ids:
                entity_id = f"{entity_id}_{candidate.frequency}"

            new_entity = {
                "id": entity_id,
                "type": candidate.type,
                "primary_name": candidate.primary_name,
                "aliases": [],
                "attributes": {
                    "seed_source": "frontmatter",
                    "seed_field": candidate.source_field,
                    "occurrence_count": candidate.frequency,
                },
                "relationships": [],
            }
            new_entities.append(new_entity)
            result["added"].append(
                {
                    "id": entity_id,
                    "primary_name": candidate.primary_name,
                    "type": candidate.type,
                    "frequency": candidate.frequency,
                }
            )

        # Collect low-frequency candidates (below threshold)
        all_candidates = collect_candidates(journals_dir, min_frequency=1)
        high_freq_names = {c.primary_name for c in candidates}
        for c in all_candidates:
            if c.primary_name not in high_freq_names:
                result["skipped_low_frequency"].append(
                    {
                        "primary_name": c.primary_name,
                        "type": _infer_type_from_source(c.source_field, c.primary_name),
                        "frequency": c.frequency,
                    }
                )

        # Append new entities to existing graph
        if new_entities:
            merged = existing + new_entities
            save_entity_graph(merged, graph_path)

        result["success"] = True

    except (OSError, ValueError) as e:
        result["error"] = str(e)
        logger.error("seed_entity_graph failed: %s", e)

    return result
