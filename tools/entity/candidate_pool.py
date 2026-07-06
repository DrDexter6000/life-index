"""Persistent entity candidate pool helpers."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph, save_entity_graph
from tools.lib.frontmatter import parse_frontmatter
from tools.lib.paths import get_journals_dir, get_user_data_dir, resolve_user_data_dir

DEFAULT_WRITE_TIME_THRESHOLD = 2
WRITE_TIME_THRESHOLD_ENV = "LIFE_INDEX_ENTITY_CANDIDATE_THRESHOLD"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_time_threshold() -> int:
    raw = os.environ.get(WRITE_TIME_THRESHOLD_ENV, "")
    try:
        threshold = int(raw)
    except ValueError:
        threshold = DEFAULT_WRITE_TIME_THRESHOLD
    return max(1, threshold)


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


def entity_names(entity: dict[str, Any]) -> set[str]:
    names = {str(entity.get("primary_name", ""))}
    names.update(str(alias) for alias in entity.get("aliases", []) or [])
    names.discard("")
    return {normalize_name(name) for name in names}


def find_entity_by_name(
    graph: list[dict[str, Any]],
    name: str,
    *,
    status: str | None = None,
) -> dict[str, Any] | None:
    needle = normalize_name(name)
    for entity in graph:
        if status is not None and entity.get("status", "confirmed") != status:
            continue
        if needle in entity_names(entity):
            return entity
    return None


def has_confirmed_name(graph: list[dict[str, Any]], name: str) -> bool:
    return find_entity_by_name(graph, name, status="confirmed") is not None


def name_conflicts_confirmed(
    graph: list[dict[str, Any]],
    *,
    primary_name: str,
    aliases: list[str] | None = None,
    entity_id: str | None = None,
) -> bool:
    names = {normalize_name(primary_name)}
    names.update(normalize_name(alias) for alias in aliases or [])
    for entity in graph:
        if entity.get("status", "confirmed") != "confirmed":
            continue
        if entity_id and entity.get("id") == entity_id:
            continue
        if names & entity_names(entity):
            return True
    return False


def relationship_exists(
    graph: list[dict[str, Any]],
    *,
    source_id: str,
    target_id: str,
    relation: str,
    status: str | None = None,
) -> bool:
    source = next((entity for entity in graph if entity["id"] == source_id), None)
    if source is None:
        return False
    for relationship in source.get("relationships", []) or []:
        if status is not None and relationship.get("status", "confirmed") != status:
            continue
        if relationship.get("target") == target_id and relationship.get("relation") == relation:
            return True
    return False


def stable_candidate_id(
    *,
    entity_type: str,
    primary_name: str,
    reason: str,
    prefix: str = "candidate",
) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_name(primary_name)).strip("-")
    if not slug:
        slug = hashlib.sha1(primary_name.encode("utf-8")).hexdigest()[:8]
    digest = hashlib.sha1(f"{entity_type}|{primary_name}|{reason}".encode("utf-8")).hexdigest()
    return f"{prefix}-{entity_type}-{slug}-{digest[:8]}"


def cutover_entity_shape(kind: str | None) -> tuple[str, dict[str, Any]]:
    """Map legacy frontmatter candidate kinds to schema-cutover entity shape."""
    if kind in {"person", "actor"}:
        return "actor", {"kind": "human"}
    if kind == "place":
        return "place", {}
    if kind == "project":
        return "project", {}
    return "concept", {}


def upsert_candidate_entity(
    graph: list[dict[str, Any]],
    *,
    primary_name: str,
    entity_type: str,
    source: str,
    reason: str,
    evidence: list[str] | None = None,
    requested_id: str | None = None,
    aliases: list[str] | None = None,
    attributes: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> tuple[dict[str, Any], bool, bool]:
    """Insert or update a candidate entity.

    Returns (entity, created, changed).
    """
    evidence = _dedupe_strings(evidence or [])
    aliases = _dedupe_strings(aliases or [])
    attributes = dict(attributes or {})
    created_at = created_at or now_iso()

    entity_id = requested_id or stable_candidate_id(
        entity_type=entity_type,
        primary_name=primary_name,
        reason=reason,
    )
    existing = next((entity for entity in graph if entity["id"] == entity_id), None)
    if existing is None:
        existing = find_entity_by_name(graph, primary_name, status="candidate")
    if existing is not None and existing.get("status", "confirmed") == "confirmed":
        return existing, False, False

    if existing is None:
        entity = {
            "id": entity_id,
            "type": entity_type,
            "primary_name": primary_name,
            "aliases": aliases,
            "attributes": attributes,
            "relationships": [],
            "source": source,
            "status": "candidate",
            "created_at": created_at,
            "evidence": evidence,
            "reason": reason,
        }
        graph.append(entity)
        return entity, True, True

    changed = False
    for field, value in (
        ("source", source),
        ("status", "candidate"),
        ("reason", reason),
    ):
        if existing.get(field) != value:
            existing[field] = value
            changed = True
    if "created_at" not in existing:
        existing["created_at"] = created_at
        changed = True
    merged_evidence = _dedupe_strings([*existing.get("evidence", []), *evidence])
    if merged_evidence != existing.get("evidence", []):
        existing["evidence"] = merged_evidence
        changed = True
    if aliases:
        merged_aliases = _dedupe_strings([*existing.get("aliases", []), *aliases])
        if merged_aliases != existing.get("aliases", []):
            existing["aliases"] = merged_aliases
            changed = True
    if attributes:
        existing_attributes = existing.setdefault("attributes", {})
        if not isinstance(existing_attributes, dict):
            existing_attributes = {}
            existing["attributes"] = existing_attributes
            changed = True
        for key, value in attributes.items():
            if existing_attributes.get(key) != value:
                existing_attributes[key] = value
                changed = True
    return existing, False, changed


def upsert_candidate_relationship(
    graph: list[dict[str, Any]],
    *,
    source_id: str,
    target_id: str,
    relation: str,
    source: str,
    reason: str,
    evidence: list[str] | None = None,
    created_at: str | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    owner = next((entity for entity in graph if entity["id"] == source_id), None)
    if owner is None or not any(entity["id"] == target_id for entity in graph):
        return None, False

    created_at = created_at or now_iso()
    evidence = _dedupe_strings(evidence or [])
    relationships = owner.setdefault("relationships", [])
    existing = next(
        (
            relationship
            for relationship in relationships
            if relationship.get("target") == target_id and relationship.get("relation") == relation
        ),
        None,
    )
    if existing is None:
        relationship = {
            "target": target_id,
            "relation": relation,
            "source": source,
            "status": "candidate",
            "created_at": created_at,
            "evidence": evidence,
            "reason": reason,
        }
        relationships.append(relationship)
        return relationship, True

    changed = False
    for field, value in (
        ("source", source),
        ("status", "candidate"),
        ("reason", reason),
    ):
        if existing.get(field) != value:
            existing[field] = value
            changed = True
    if "created_at" not in existing:
        existing["created_at"] = created_at
        changed = True
    merged_evidence = _dedupe_strings([*existing.get("evidence", []), *evidence])
    if merged_evidence != existing.get("evidence", []):
        existing["evidence"] = merged_evidence
        changed = True
    return existing, changed


def capture_write_time_candidates(
    *,
    metadata: dict[str, Any],
    candidates: list[dict[str, Any]],
    journal_path: Path,
    graph_path: Path | None = None,
) -> dict[str, Any]:
    """Promote repeated deterministic unknown names into persistent candidates."""
    del metadata  # future extension hook; candidates already contain normalized fields
    graph_path = graph_path or resolve_user_data_dir() / "entity_graph.yaml"
    threshold = write_time_threshold()
    unknowns = [
        candidate
        for candidate in candidates
        if candidate.get("matched_entity_id") is None
        and str(candidate.get("text", "")).strip()
        and candidate.get("source") in {"frontmatter", "frontmatter_fallback"}
        and candidate.get("kind") in {"person", "actor", "place", "project"}
    ]
    if not unknowns:
        return {"threshold": threshold, "created": [], "updated": []}

    graph = load_entity_graph(graph_path)
    created: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    journals_dir = get_journals_dir()
    counts = _frontmatter_occurrences(journals_dir)

    for candidate in unknowns:
        text = str(candidate["text"]).strip()
        evidence = counts.get(normalize_name(text), [])
        if len(evidence) < threshold:
            continue
        if has_confirmed_name(graph, text):
            continue
        entity_type, attributes = cutover_entity_shape(str(candidate.get("kind") or "concept"))
        entity, was_created, changed = upsert_candidate_entity(
            graph,
            primary_name=text,
            entity_type=entity_type,
            source="seed",
            reason=(
                f"Repeated unknown {candidate.get('kind') or 'entity'} mention "
                f"reached threshold {threshold}."
            ),
            evidence=evidence,
            attributes=attributes,
        )
        item = {"id": entity["id"], "primary_name": entity["primary_name"], "evidence": evidence}
        if was_created:
            created.append(item)
        elif changed:
            updated.append(item)

    if created or updated:
        save_entity_graph(graph, graph_path)

    return {
        "threshold": threshold,
        "journal_path": _rel_path(journal_path),
        "created": created,
        "updated": updated,
    }


def _frontmatter_occurrences(journals_dir: Path) -> dict[str, list[str]]:
    occurrences: dict[str, list[str]] = {}
    if not journals_dir.exists():
        return occurrences
    data_dir = get_user_data_dir()
    journal_pattern = re.compile(r"^life-index_\d{4}-\d{2}-\d{2}_\d+\.md$")
    for md_file in sorted(journals_dir.rglob("*.md")):
        if not journal_pattern.match(md_file.name):
            continue
        try:
            metadata, _body = parse_frontmatter(md_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        for field in ("people", "location", "project"):
            for value in _iter_field_values(metadata.get(field)):
                occurrences.setdefault(normalize_name(value), []).append(
                    _rel_path(md_file, data_dir)
                )
    return occurrences


def _iter_field_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _rel_path(path: Path, base: Path | None = None) -> str:
    base = base or get_user_data_dir()
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def _dedupe_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
