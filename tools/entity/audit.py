"""Entity graph quality audit — CLI detection, Agent decision."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

# Kinship term mapping for semantic duplicate detection
_KINSHIP_MAP: dict[str, set[str]] = {
    "妈妈": {"母亲", "妈", "老妈", "mom", "mother"},
    "母亲": {"妈妈", "妈", "老妈", "mom", "mother"},
    "爸爸": {"父亲", "爸", "老爸", "dad", "father"},
    "父亲": {"爸爸", "爸", "老爸", "dad", "father"},
    "奶奶": {"祖母", "奶奶"},
    "爷爷": {"祖父", "爷爷"},
    "外公": {"外祖父"},
    "外婆": {"外祖母"},
}


def audit_entity_graph(
    graph_path: Path,
    journals_dir: Path | None = None,
) -> dict[str, Any]:
    """Run entity graph quality audit, return structured report.

    Detection types:
    1. possible_duplicate — primary_name/alias overlap or high similarity
    2. orphan_entity — zero references in journals
    3. incomplete_relationship — frequent co-occurrence without relationship record

    Returns:
        {
            "audit_date": str,
            "total_entities": int,
            "issues": [{"type", "severity", ...}],
            "summary": {"high": int, "medium": int, "low": int},
        }
    """
    if not graph_path.exists():
        return _empty_report()

    with graph_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {"entities": []}

    entities: list[dict[str, Any]] = data.get("entities", [])
    issues: list[dict[str, Any]] = []

    # 1. Duplicate detection
    issues.extend(_detect_duplicates(entities))

    # 2. Orphan detection (requires journals_dir)
    if journals_dir is not None:
        issues.extend(_detect_orphans(entities, journals_dir))

    # 3. Incomplete relationships (requires journals_dir)
    if journals_dir is not None:
        issues.extend(_detect_incomplete_relationships(entities, journals_dir))

    # Build summary
    summary = {"high": 0, "medium": 0, "low": 0}
    for issue in issues:
        sev = issue["severity"]
        if sev in summary:
            summary[sev] += 1

    return {
        "audit_date": date.today().isoformat(),
        "total_entities": len(entities),
        "issues": issues,
        "summary": summary,
    }


def _detect_duplicates(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect possible duplicate entities."""
    issues: list[dict[str, Any]] = []

    # Build alias → entity_id map
    name_to_ids: dict[str, list[str]] = {}
    for entity in entities:
        eid = entity["id"]
        primary = entity.get("primary_name", "")
        if primary:
            name_to_ids.setdefault(primary, []).append(eid)
        for alias in entity.get("aliases", []):
            name_to_ids.setdefault(alias, []).append(eid)

    # Check alias/primary_name overlap between different entities
    seen_pairs: set[frozenset[str]] = set()
    for entity_a in entities:
        for entity_b in entities:
            if entity_a["id"] >= entity_b["id"]:
                continue
            pair = frozenset([entity_a["id"], entity_b["id"]])
            if pair in seen_pairs:
                continue

            # Exact alias overlap
            names_a = {entity_a.get("primary_name", "")} | set(
                entity_a.get("aliases", [])
            )
            names_b = {entity_b.get("primary_name", "")} | set(
                entity_b.get("aliases", [])
            )
            overlap = names_a & names_b - {""}
            if overlap:
                seen_pairs.add(pair)
                issues.append(
                    {
                        "type": "possible_duplicate",
                        "severity": "high",
                        "entities": [
                            entity_a.get("primary_name", ""),
                            entity_b.get("primary_name", ""),
                        ],
                        "entity_ids": [entity_a["id"], entity_b["id"]],
                        "confidence": 1.0,
                        "evidence": f"alias overlap: {overlap}",
                        "suggested_action": "merge",
                    }
                )
                continue

            # Kinship similarity
            name_a = entity_a.get("primary_name", "")
            name_b = entity_b.get("primary_name", "")
            if name_a in _KINSHIP_MAP and name_b in _KINSHIP_MAP.get(name_a, set()):
                seen_pairs.add(pair)
                issues.append(
                    {
                        "type": "possible_duplicate",
                        "severity": "high",
                        "entities": [name_a, name_b],
                        "entity_ids": [entity_a["id"], entity_b["id"]],
                        "confidence": 0.9,
                        "evidence": f"kinship synonyms: {name_a} ↔ {name_b}",
                        "suggested_action": "merge",
                    }
                )
                continue

            # Edit distance (Levenshtein ≤ 1, length > 2)
            if (
                len(name_a) > 2
                and len(name_b) > 2
                and _levenshtein(name_a, name_b) <= 1
            ):
                seen_pairs.add(pair)
                issues.append(
                    {
                        "type": "possible_duplicate",
                        "severity": "medium",
                        "entities": [name_a, name_b],
                        "entity_ids": [entity_a["id"], entity_b["id"]],
                        "confidence": 0.7,
                        "evidence": "similar names: edit distance ≤ 1",
                        "suggested_action": "merge",
                    }
                )

    return issues


def _detect_orphans(
    entities: list[dict[str, Any]],
    journals_dir: Path,
) -> list[dict[str, Any]]:
    """Detect entities with zero references in journals."""
    import re

    # Collect all referenced names from journal frontmatter
    referenced_names: set[str] = set()
    pattern = re.compile(r"^life-index_\d{4}-\d{2}-\d{2}_\d+\.md$")

    if journals_dir.exists():
        for md_file in journals_dir.rglob("*.md"):
            if not pattern.match(md_file.name):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                if not content.startswith("---"):
                    continue
                end = content.find("---", 3)
                if end < 0:
                    continue
                fm_text = content[3:end]
                try:
                    fm = yaml.safe_load(fm_text) or {}
                except yaml.YAMLError:
                    continue
                for field_name in ("people", "entities"):
                    vals = fm.get(field_name, [])
                    if isinstance(vals, list):
                        referenced_names.update(str(v) for v in vals if v)
            except Exception:
                continue

    issues: list[dict[str, Any]] = []
    for entity in entities:
        names = {entity.get("primary_name", "")}
        names.update(entity.get("aliases", []))
        names.discard("")

        if not names.intersection(referenced_names):
            issues.append(
                {
                    "type": "orphan_entity",
                    "severity": "medium",
                    "entity_id": entity["id"],
                    "primary_name": entity.get("primary_name", ""),
                    "message": f"实体 '{entity.get('primary_name', '')}' 在日志中零引用",
                    "suggested_action": "archive",
                }
            )

    return issues


def _detect_incomplete_relationships(
    entities: list[dict[str, Any]],
    journals_dir: Path,
) -> list[dict[str, Any]]:
    """Detect entities frequently co-occurring without a relationship record."""
    import re
    from collections import Counter

    # Build existing relationship pairs
    existing_pairs: set[frozenset[str]] = set()
    entity_by_name: dict[str, str] = {}
    for entity in entities:
        entity_by_name[entity.get("primary_name", "")] = entity["id"]
        for rel in entity.get("relationships", []):
            target = rel.get("target", "")
            existing_pairs.add(frozenset([entity["id"], target]))

    # Count co-occurrences in journal frontmatter people/entities fields
    co_occurrence: Counter[frozenset[str]] = Counter()
    pattern = re.compile(r"^life-index_\d{4}-\d{2}-\d{2}_\d+\.md$")

    if journals_dir.exists():
        for md_file in journals_dir.rglob("*.md"):
            if not pattern.match(md_file.name):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                if not content.startswith("---"):
                    continue
                end = content.find("---", 3)
                if end < 0:
                    continue
                fm_text = content[3:end]
                try:
                    fm = yaml.safe_load(fm_text) or {}
                except yaml.YAMLError:
                    continue
                names_in_entry: set[str] = set()
                for field_name in ("people", "entities"):
                    vals = fm.get(field_name, [])
                    if isinstance(vals, list):
                        names_in_entry.update(str(v) for v in vals if v)
                # Count pairwise co-occurrences
                names_list = sorted(names_in_entry)
                for i in range(len(names_list)):
                    for j in range(i + 1, len(names_list)):
                        pair = frozenset([names_list[i], names_list[j]])
                        co_occurrence[pair] += 1
            except Exception:
                continue

    issues: list[dict[str, Any]] = []
    # Threshold: co-occur 3+ times without relationship
    for pair, count in co_occurrence.items():
        if count < 3:
            continue
        names = sorted(pair)
        # Check if there's already a relationship
        ids = [entity_by_name.get(n) for n in names]
        if all(ids):
            pair_ids = frozenset(ids)
            if pair_ids in existing_pairs:
                continue

        issues.append(
            {
                "type": "incomplete_relationship",
                "severity": "low",
                "entities": names,
                "co_occurrence_count": count,
                "message": f"'{names[0]}' 和 '{names[1]}' 在 {count} 篇日志中共现但无关系记录",
                "suggested_action": "add_relationship",
            }
        )

    return issues


def _levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def _empty_report() -> dict[str, Any]:
    return {
        "audit_date": date.today().isoformat(),
        "total_entities": 0,
        "issues": [],
        "summary": {"high": 0, "medium": 0, "low": 0},
    }
