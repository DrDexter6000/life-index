"""Deterministic validation for L3 maintenance proposals."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

PROPOSAL_SCHEMA_VERSION = "m33.maintenance_proposal.v0"

_TOKEN_RE = re.compile(r"(ghp_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,})")
_ALLOWED_FRONTMATTER_FIELDS = {
    "title",
    "date",
    "topic",
    "tags",
    "people",
    "location",
    "weather",
    "schema_version",
}


def _payload(
    *,
    valid: bool,
    proposal_id: str | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    error_items = errors or []
    return {
        "success": valid,
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "command": "maintenance proposal validate",
        "valid": valid,
        "proposal_id": proposal_id,
        "accepted_change_count": 0 if not valid else None,
        "errors": error_items,
        "error": error_items[0] if error_items else None,
    }


def _error(code: str, message: str, proposal_id: str | None) -> tuple[dict[str, Any], int]:
    return (
        _payload(
            valid=False,
            proposal_id=proposal_id,
            errors=[{"code": code, "message": message}],
        ),
        2,
    )


def _contains_secret(value: Any) -> bool:
    if isinstance(value, str):
        return _TOKEN_RE.search(value) is not None
    if isinstance(value, dict):
        return any(_contains_secret(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    return False


def _resolve_relative(root: Path, rel_path: str) -> Path | None:
    candidate = Path(rel_path)
    if candidate.is_absolute():
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_entities(root: Path) -> list[dict[str, Any]]:
    graph_path = root / "entity_graph.yaml"
    if not graph_path.exists():
        return []
    payload = yaml.safe_load(graph_path.read_text(encoding="utf-8")) or {"entities": []}
    entities = payload.get("entities", []) if isinstance(payload, dict) else []
    return [entity for entity in entities if isinstance(entity, dict)]


def _entity_ids(entities: list[dict[str, Any]]) -> set[str]:
    return {str(entity.get("id")) for entity in entities if entity.get("id")}


def _labels_by_entity(entities: list[dict[str, Any]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for entity in entities:
        entity_id = str(entity.get("id", ""))
        primary = entity.get("primary_name")
        if isinstance(primary, str) and primary:
            labels[primary.casefold()] = entity_id
        aliases = entity.get("aliases", []) or []
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str) and alias:
                    labels[alias.casefold()] = entity_id
    return labels


def validate_proposal(
    *,
    data_dir: str | Path,
    proposal_file: str | Path,
) -> tuple[dict[str, Any], int]:
    root = Path(data_dir)
    try:
        proposal = json.loads(Path(proposal_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _error("MAINTENANCE_PROPOSAL_INVALID_JSON", str(exc), None)

    if not isinstance(proposal, dict):
        return _error("MAINTENANCE_PROPOSAL_INVALID_SCHEMA", "Proposal must be an object.", None)

    proposal_id = proposal.get("proposal_id")
    proposal_id_str = str(proposal_id) if proposal_id is not None else None

    if proposal.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
        return _error(
            "MAINTENANCE_PROPOSAL_INVALID_SCHEMA",
            "Unsupported maintenance proposal schema version.",
            proposal_id_str,
        )
    if proposal.get("requires_user_ack") is not True:
        return _error(
            "MAINTENANCE_PROPOSAL_MISSING_USER_ACK",
            "Proposal must carry requires_user_ack=true.",
            proposal_id_str,
        )
    evidence = proposal.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return _error(
            "MAINTENANCE_PROPOSAL_MISSING_EVIDENCE",
            "Proposal must include at least one evidence item.",
            proposal_id_str,
        )
    changes = proposal.get("changes")
    if not isinstance(changes, list) or not changes:
        return _error(
            "MAINTENANCE_PROPOSAL_INVALID_SCHEMA",
            "Proposal must include at least one change item.",
            proposal_id_str,
        )
    source = proposal.get("source")
    if not isinstance(source, dict):
        return _error(
            "MAINTENANCE_PROPOSAL_INVALID_SCHEMA",
            "Proposal source must be an object.",
            proposal_id_str,
        )
    source_path = source.get("path")
    if not isinstance(source_path, str):
        return _error(
            "MAINTENANCE_PROPOSAL_INVALID_SCHEMA",
            "Proposal source.path must be a relative path string.",
            proposal_id_str,
        )
    resolved_source = _resolve_relative(root, source_path)
    if resolved_source is None:
        return _error(
            "MAINTENANCE_PROPOSAL_PATH_ESCAPE",
            "Proposal source path must stay inside LIFE_INDEX_DATA_DIR.",
            proposal_id_str,
        )

    for item in evidence:
        if not isinstance(item, dict):
            return _error(
                "MAINTENANCE_PROPOSAL_MISSING_EVIDENCE",
                "Evidence items must be objects.",
                proposal_id_str,
            )
        evidence_path = item.get("path")
        if isinstance(evidence_path, str) and _resolve_relative(root, evidence_path) is None:
            return _error(
                "MAINTENANCE_PROPOSAL_PATH_ESCAPE",
                "Evidence paths must stay inside LIFE_INDEX_DATA_DIR.",
                proposal_id_str,
            )

    for change in changes:
        if not isinstance(change, dict):
            return _error(
                "MAINTENANCE_PROPOSAL_INVALID_SCHEMA",
                "Change items must be objects.",
                proposal_id_str,
            )
        change_path = change.get("path")
        if isinstance(change_path, str) and _resolve_relative(root, change_path) is None:
            return _error(
                "MAINTENANCE_PROPOSAL_PATH_ESCAPE",
                "Change paths must stay inside LIFE_INDEX_DATA_DIR.",
                proposal_id_str,
            )

    if _contains_secret(proposal):
        return _error(
            "MAINTENANCE_PROPOSAL_SECRET_EXPOSURE",
            "Proposal contains a secret-like token pattern.",
            proposal_id_str,
        )

    entities = _load_entities(root)
    entity_ids = _entity_ids(entities)
    labels = _labels_by_entity(entities)

    for change in changes:
        change_type = change.get("type")
        if change_type == "frontmatter_update":
            field = change.get("field")
            if field not in _ALLOWED_FRONTMATTER_FIELDS:
                return _error(
                    "MAINTENANCE_PROPOSAL_UNSUPPORTED_FIELD",
                    "Frontmatter proposal field is not supported.",
                    proposal_id_str,
                )
        elif change_type == "entity_alias_add":
            entity_id = str(change.get("entity_id", ""))
            alias = change.get("alias")
            if entity_id not in entity_ids or not isinstance(alias, str) or not alias:
                return _error(
                    "MAINTENANCE_PROPOSAL_INVALID_SCHEMA",
                    "Entity alias proposal must reference an existing entity and alias.",
                    proposal_id_str,
                )
            existing_owner = labels.get(alias.casefold())
            if existing_owner is not None and existing_owner != entity_id:
                return _error(
                    "MAINTENANCE_PROPOSAL_ENTITY_ALIAS_COLLISION",
                    "Entity alias collides with an existing entity label.",
                    proposal_id_str,
                )
        elif change_type == "entity_relation_add":
            source_id = str(change.get("source_id", ""))
            target_id = str(change.get("target_id", ""))
            relation = change.get("relation")
            if source_id not in entity_ids or target_id not in entity_ids or not relation:
                return _error(
                    "MAINTENANCE_PROPOSAL_INVALID_SCHEMA",
                    "Entity relation proposal must reference existing source and target entities.",
                    proposal_id_str,
                )
        else:
            return _error(
                "MAINTENANCE_PROPOSAL_UNSUPPORTED_FIELD",
                "Proposal change type is not supported.",
                proposal_id_str,
            )

    expected_hash = source.get("sha256")
    if not isinstance(expected_hash, str) or not resolved_source.exists():
        return _error(
            "MAINTENANCE_PROPOSAL_STALE_SOURCE_HASH",
            "Proposal source hash cannot be verified.",
            proposal_id_str,
        )
    if _sha256(resolved_source) != expected_hash:
        return _error(
            "MAINTENANCE_PROPOSAL_STALE_SOURCE_HASH",
            "Proposal source hash is stale.",
            proposal_id_str,
        )

    payload = _payload(valid=True, proposal_id=proposal_id_str)
    payload["accepted_change_count"] = len(changes)
    return payload, 0


__all__ = ["PROPOSAL_SCHEMA_VERSION", "validate_proposal"]
