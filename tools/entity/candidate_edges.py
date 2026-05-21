#!/usr/bin/env python3
"""Phase C: Candidate edges report — read-only candidate relationship surface.

Extractors:
- people_cooccurrence: frontmatter `people` field pairs → suggestion candidates
- related_entry: frontmatter `related_entries` → cross-journal link candidates
- wikilink: body text `[[X]]` → linked-topic relationship candidates
- body_cooccurrence: body text repeated term co-occurrence → implicit link candidates

Zero production graph writes. Output is JSON with deduplicated candidate objects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.lib.frontmatter import parse_journal_file
from tools.lib.paths import get_journals_dir

SCHEMA_VERSION = "m16.entity_candidate_edges.v0"

# ── wikilink regex ────────────────────────────────────────────────
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def _rel_path(abs_path: Path, journals_dir: Path) -> str:
    """Convert absolute path to relative path with forward slashes."""
    try:
        rel = abs_path.relative_to(journals_dir)
    except ValueError:
        rel = abs_path
    return rel.as_posix()


def _suggested_action(evidence_count: int) -> str:
    """Contract: evidence_count → suggested_action."""
    if evidence_count >= 3:
        return "auto-confirm-recommended"
    if evidence_count >= 2:
        return "review-recommended"
    return "review-required-low-confidence"


def _confidence(evidence_count: int, max_expected: int = 5) -> float:
    """Linear confidence 0.0–1.0 capped at max_expected."""
    return min(1.0, evidence_count / max_expected)


# ── Extractors ────────────────────────────────────────────────────


def extract_candidates_from_people(
    journals: list[dict[str, Any]],
    journals_dir: Path,
) -> list[dict[str, Any]]:
    """Scan frontmatter `people` for co-occurrence pairs.

    For each journal with >=2 people, emit a candidate for each unordered pair
    that co-occurs at least once.
    """
    candidates: list[dict[str, Any]] = []
    for entry in journals:
        people = entry.get("people", [])
        if not isinstance(people, list) or len(people) < 2:
            continue
        path = Path(entry["_file"])
        rel = _rel_path(path, journals_dir)
        for i in range(len(people)):
            for j in range(i + 1, len(people)):
                a, b = sorted([people[i], people[j]])
                candidates.append(
                    {
                        "type": "people_cooccurrence",
                        "source": a,
                        "target": b,
                        "evidence_paths": [rel],
                    }
                )
    return candidates


def extract_candidates_from_related_entries(
    journals: list[dict[str, Any]],
    journals_dir: Path,
) -> list[dict[str, Any]]:
    """Scan frontmatter `related_entries` for cross-journal link candidates."""
    candidates: list[dict[str, Any]] = []
    for entry in journals:
        related = entry.get("related_entries", [])
        if not isinstance(related, list) or not related:
            continue
        path = Path(entry["_file"])
        rel = _rel_path(path, journals_dir)
        source_title = entry.get("title", entry.get("_title", path.stem))
        for target_rel in related:
            candidates.append(
                {
                    "type": "related_entry",
                    "source": source_title,
                    "target": target_rel,
                    "evidence_paths": [rel],
                }
            )
    return candidates


def extract_candidates_from_wikilinks(
    journals: list[dict[str, Any]],
    journals_dir: Path,
) -> list[dict[str, Any]]:
    """Scan body text for `[[X]]` wikilink patterns."""
    candidates: list[dict[str, Any]] = []
    for entry in journals:
        body = entry.get("_body", "")
        if not body:
            continue
        path = Path(entry["_file"])
        rel = _rel_path(path, journals_dir)
        source_title = entry.get("title", entry.get("_title", path.stem))
        for match in _WIKILINK_RE.finditer(body):
            target = match.group(1).strip()
            if not target:
                continue
            candidates.append(
                {
                    "type": "wikilink",
                    "source": source_title,
                    "target": target,
                    "evidence_paths": [rel],
                }
            )
    return candidates


def extract_candidates_from_cooccurrence(
    journals: list[dict[str, Any]],
    journals_dir: Path,
) -> list[dict[str, Any]]:
    """Detect body-text co-occurrence of capitalized/proper-noun terms.

    Strategy: extract capitalized words (2+ chars) from body text as
    potential named entities, then emit pairs that co-occur in the same
    journal body. This is a simple heuristic — no LLM, no NER model.
    """
    # Pre-compiled: matches standalone capitalized words (2+ chars)
    _proper_re = re.compile(r"\b([A-Z][a-z]{1,})\b")

    candidates: list[dict[str, Any]] = []
    for entry in journals:
        body = entry.get("_body", "")
        if not body:
            continue
        path = Path(entry["_file"])
        rel = _rel_path(path, journals_dir)

        terms = _proper_re.findall(body)
        unique_terms = sorted(set(terms))
        if len(unique_terms) < 2:
            continue

        for i in range(len(unique_terms)):
            for j in range(i + 1, len(unique_terms)):
                a, b = sorted([unique_terms[i], unique_terms[j]])
                candidates.append(
                    {
                        "type": "body_cooccurrence",
                        "source": a,
                        "target": b,
                        "evidence_paths": [rel],
                    }
                )
    return candidates


# ── Aggregation ───────────────────────────────────────────────────


def _aggregate(
    raw_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate by (type, source, target) and merge evidence_paths.

    Confidence and suggested_action are computed from merged evidence_count.
    """
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}

    for cand in raw_candidates:
        key = (cand["type"], cand["source"], cand["target"])
        if key in merged:
            existing = merged[key]
            existing["evidence_paths"].extend(cand["evidence_paths"])
        else:
            merged[key] = {
                "type": cand["type"],
                "source": cand["source"],
                "target": cand["target"],
                "evidence_paths": list(cand["evidence_paths"]),
            }

    result: list[dict[str, Any]] = []
    for entry in merged.values():
        evidence_paths = sorted(set(entry["evidence_paths"]))
        evidence_count = len(evidence_paths)
        entry["evidence_paths"] = evidence_paths
        entry["confidence"] = _confidence(evidence_count)
        entry["suggested_action"] = _suggested_action(evidence_count)
        result.append(entry)

    return result


def run(journals_dir: Path | None = None) -> dict[str, Any]:
    """Entry point: scan journals, run all extractors, aggregate, return JSON.

    This is read-only — no writes to entity_graph.yaml or any user data.
    """
    jdir = journals_dir or get_journals_dir()

    # Scan all .md files under Journals/ (skip non-journal markdown)
    journal_files: list[Path] = []
    if jdir.exists():
        for md_file in jdir.rglob("*.md"):
            # Skip index files and by-topic files
            if md_file.name.startswith("index_") or md_file.name.startswith("主题_"):
                continue
            if md_file.name.startswith("项目_") or md_file.name.startswith("标签_"):
                continue
            # Only include files matching journal pattern: *_{YYYY-MM-DD}_*.md
            if re.search(r"_\d{4}-\d{2}-\d{2}_\d+\.md$", md_file.name) or re.search(
                r"_\d{4}-\d{2}-\d{2}\.md$", md_file.name
            ):
                journal_files.append(md_file)
            elif "by-topic" not in str(md_file) and "index" not in str(md_file).lower():
                # Include any .md that's not an index — it might be a journal
                journal_files.append(md_file)

    journals: list[dict[str, Any]] = []
    for fpath in journal_files:
        parsed = parse_journal_file(fpath)
        if "_error" not in parsed:
            journals.append(parsed)

    raw: list[dict[str, Any]] = []
    raw.extend(extract_candidates_from_people(journals, jdir))
    raw.extend(extract_candidates_from_related_entries(journals, jdir))
    raw.extend(extract_candidates_from_wikilinks(journals, jdir))
    raw.extend(extract_candidates_from_cooccurrence(journals, jdir))

    aggregated = _aggregate(raw)

    return {
        "success": True,
        "schema_version": SCHEMA_VERSION,
        "candidates": aggregated,
        "total": len(aggregated),
        "error": None,
    }
