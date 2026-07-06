"""Materialize deterministic entity profile documents."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.entity.profile import build_entity_profile
from tools.lib.entity_graph import load_entity_graph
from tools.lib.entity_schema import EntityGraphValidationError
from tools.lib.frontmatter import parse_frontmatter
from tools.lib.paths import get_user_data_dir

ENTITIES_DIR_NAME = "Entities"
ENTITY_PROFILE_GENERATOR = "life-index abstract --entities"
ROOT_ENTITIES_START = "<!-- LIFE_INDEX_ENTITIES_START -->"
ROOT_ENTITIES_END = "<!-- LIFE_INDEX_ENTITIES_END -->"


def _safe_rel(path: Path, data_dir: Path) -> str:
    return path.relative_to(data_dir).as_posix()


def _graph_source_hash(graph_path: Path) -> str:
    data = graph_path.read_bytes() if graph_path.exists() else b""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_existing_generated_at(path: Path, source_hash: str) -> str | None:
    if not path.exists():
        return None
    try:
        metadata, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    if metadata.get("source_hash") != source_hash:
        return None
    generated_at = metadata.get("generated_at")
    return generated_at if isinstance(generated_at, str) and generated_at else None


def _generated_at(path: Path, source_hash: str) -> str:
    return _read_existing_generated_at(path, source_hash) or _now_iso()


def _format_yaml_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, list):
        return "[" + ", ".join(_format_yaml_value(item) for item in value) + "]"
    if isinstance(value, str):
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-. :/+")
        if value and all(ch in safe_chars for ch in value):
            return value
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False)


def _frontmatter(fields: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {_format_yaml_value(value)}")
    lines.append("---")
    return "\n".join(lines)


def _escape_cell(value: Any) -> str:
    text = str(value or "")
    return text.replace("|", "\\|").replace("\n", " ")


def _relationship_summary(relationships: list[dict[str, Any]]) -> str:
    if not relationships:
        return "no confirmed relationships"
    first = relationships[0]
    suffix = "" if len(relationships) == 1 else f" (+{len(relationships) - 1})"
    return f"{first.get('relation')} -> {first.get('target')}{suffix}"


def _render_profile_doc(profile: dict[str, Any], *, source_hash: str, path: Path) -> str:
    identity = profile["identity"]
    stats = profile["stats"]
    generated_at = _generated_at(path, source_hash)
    fields = {
        "entity_id": identity["entity_id"],
        "type": identity["type"],
        "kind": identity.get("kind"),
        "status": identity["status"],
        "primary_name": identity["primary_name"],
        "aliases": identity.get("aliases", []),
        "generated_by": ENTITY_PROFILE_GENERATOR,
        "generated_at": generated_at,
        "source_hash": source_hash,
    }
    lines = [
        _frontmatter(fields),
        "",
        f"# {identity['primary_name']}",
        "",
        "> Generated profile. Edit `entity_graph.yaml` or journals, then rerun "
        "`life-index abstract --entities`.",
        "",
        "## Identity",
        "",
        f"- Entity ID: `{identity['entity_id']}`",
        f"- Type: `{identity['type']}`",
        f"- Kind: `{identity.get('kind') or 'unknown'}`",
        f"- Status: `{identity['status']}`",
        "",
        "## Relationships",
        "",
        "| relation | target_id | source | status | evidence |",
        "|---|---|---|---|---|",
    ]
    relationships = profile.get("relationships", [])
    if relationships:
        for relationship in relationships:
            evidence = ", ".join(f"`{item}`" for item in relationship.get("evidence", [])) or "-"
            lines.append(
                "| "
                f"{_escape_cell(relationship.get('relation'))} | "
                f"`{_escape_cell(relationship.get('target'))}` | "
                f"{_escape_cell(relationship.get('source'))} | "
                f"{_escape_cell(relationship.get('status'))} | "
                f"{evidence} |"
            )
    else:
        lines.append("| - | - | - | - | - |")
    lines.extend(["", "## Recent Mentions", "", "| date | title | path |", "|---|---|---|"])
    mentions = profile.get("mentions", [])
    if mentions:
        for mention in mentions:
            lines.append(
                "| "
                f"{_escape_cell(mention.get('date'))} | "
                f"{_escape_cell(mention.get('title'))} | "
                f"`{_escape_cell(mention.get('rel_path'))}` |"
            )
    else:
        lines.append("| - | - | - |")
    lines.extend(
        [
            "",
            "## Statistics",
            "",
            f"- First mention: `{stats.get('first_mention') or 'none'}`",
            f"- Latest mention: `{stats.get('latest_mention') or 'none'}`",
            f"- Mention count: `{stats.get('mention_count', 0)}`",
            f"- Relationship count: `{stats.get('relationship_count', 0)}`",
            "",
        ]
    )
    return "\n".join(lines)


def _render_entities_index(profiles: list[dict[str, Any]], *, source_hash: str, path: Path) -> str:
    generated_at = _generated_at(path, source_hash)
    fields = {
        "generated_by": ENTITY_PROFILE_GENERATOR,
        "generated_at": generated_at,
        "source_hash": source_hash,
        "entity_count": len(profiles),
    }
    lines = [
        _frontmatter(fields),
        "",
        "# Entity Profiles",
        "",
        "> Generated index. Entity IDs are opaque and stable; filenames use IDs, not names.",
        "",
        "| entity | kind | relationship | profile | mentions |",
        "|---|---|---|---|---:|",
    ]
    if profiles:
        for profile in profiles:
            identity = profile["identity"]
            profile_name = f"{identity['entity_id']}.md"
            lines.append(
                "| "
                f"[{_escape_cell(identity['primary_name'])}]({profile_name}) | "
                f"{_escape_cell(identity.get('kind') or 'unknown')} | "
                f"{_escape_cell(_relationship_summary(profile.get('relationships', [])))} | "
                f"`{_escape_cell(profile_name)}` | "
                f"{int(profile.get('stats', {}).get('mention_count', 0) or 0)} |"
            )
    else:
        lines.append("| - | - | - | - | 0 |")
    lines.append("")
    return "\n".join(lines)


def root_entities_section() -> str:
    return "\n".join(
        [
            ROOT_ENTITIES_START,
            "## Entities",
            "",
            "- [Entity Profiles](Entities/index.md)",
            ROOT_ENTITIES_END,
        ]
    )


def _upsert_root_entities_section(existing: str) -> str:
    section = root_entities_section()
    if ROOT_ENTITIES_START in existing and ROOT_ENTITIES_END in existing:
        before = existing.split(ROOT_ENTITIES_START, 1)[0].rstrip()
        after = existing.split(ROOT_ENTITIES_END, 1)[1].lstrip()
        return f"{before}\n\n{section}\n\n{after}".rstrip() + "\n"
    if not existing.strip():
        return f"# Life Index\n\n{section}\n"
    return f"{existing.rstrip()}\n\n{section}\n"


def _write_text(path: Path, text: str, *, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _generated_profile_metadata(path: Path) -> dict[str, Any] | None:
    try:
        metadata, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    if metadata.get("generated_by") != ENTITY_PROFILE_GENERATOR:
        return None
    return metadata


def _cleanup_stale_generated_docs(
    entities_dir: Path,
    keep: set[Path],
    *,
    confirmed_ids: set[str],
    remove_unselected_confirmed: bool,
    dry_run: bool,
) -> list[str]:
    removed: list[str] = []
    if not entities_dir.exists():
        return removed
    for path in sorted(entities_dir.glob("*.md")):
        if path.name == "index.md" or path in keep:
            continue
        metadata = _generated_profile_metadata(path)
        if metadata is None:
            continue
        doc_entity_id = str(metadata.get("entity_id") or "")
        if doc_entity_id in confirmed_ids and not remove_unselected_confirmed:
            continue
        removed.append(path.name)
        if not dry_run:
            path.unlink()
    return removed


def _schema_error_result(exc: EntityGraphValidationError) -> dict[str, Any]:
    return {
        "success": False,
        "type": "entity-profiles",
        "updated": False,
        "profile_count": 0,
        "error": {"code": exc.code, "message": str(exc)},
        "suggested_command": exc.details.get(
            "replacement_command",
            "life-index entity --check",
        ),
    }


def materialize_entity_profiles(
    *,
    data_dir: Path | None = None,
    entity_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    data_dir = data_dir or get_user_data_dir()
    graph_path = data_dir / "entity_graph.yaml"
    entities_dir = data_dir / ENTITIES_DIR_NAME
    index_path = entities_dir / "index.md"
    root_index_path = data_dir / "INDEX.md"
    source_hash = _graph_source_hash(graph_path)

    try:
        entities = load_entity_graph(graph_path)
    except EntityGraphValidationError as exc:
        return _schema_error_result(exc)

    confirmed = [entity for entity in entities if entity.get("status", "confirmed") == "confirmed"]
    confirmed_ids = {entity["id"] for entity in confirmed}
    skipped_candidate_count = len(entities) - len(confirmed)
    if entity_id:
        selected = [entity for entity in confirmed if entity["id"] == entity_id]
        if not selected:
            profile = build_entity_profile(graph_path=graph_path, entity_id=entity_id)
            return {
                "success": False,
                "type": "entity-profiles",
                "updated": False,
                "profile_count": 0,
                "skipped_candidate_count": skipped_candidate_count,
                "error": profile.get("error")
                or {"code": "ENTITY_PROFILE_NOT_FOUND", "message": "entity not found"},
                "data": profile.get("data"),
            }
    else:
        selected = sorted(confirmed, key=lambda item: (item["primary_name"].lower(), item["id"]))

    profiles: list[dict[str, Any]] = []
    profile_paths: list[Path] = []
    for entity in selected:
        profile_result = build_entity_profile(graph_path=graph_path, entity_id=entity["id"])
        if not profile_result.get("success"):
            return {
                "success": False,
                "type": "entity-profiles",
                "updated": False,
                "profile_count": len(profiles),
                "error": profile_result.get("error"),
                "data": profile_result.get("data"),
            }
        profile = profile_result["data"]
        profiles.append(profile)
        profile_path = entities_dir / f"{entity['id']}.md"
        profile_paths.append(profile_path)
        _write_text(
            profile_path,
            _render_profile_doc(profile, source_hash=source_hash, path=profile_path),
            dry_run=dry_run,
        )

    _write_text(
        index_path,
        _render_entities_index(profiles, source_hash=source_hash, path=index_path),
        dry_run=dry_run,
    )

    root_text = root_index_path.read_text(encoding="utf-8") if root_index_path.exists() else ""
    _write_text(root_index_path, _upsert_root_entities_section(root_text), dry_run=dry_run)

    removed = _cleanup_stale_generated_docs(
        entities_dir,
        set(profile_paths),
        confirmed_ids=confirmed_ids,
        remove_unselected_confirmed=entity_id is None,
        dry_run=dry_run,
    )
    rel_profile_paths = [_safe_rel(path, data_dir) for path in profile_paths]
    return {
        "success": True,
        "type": "entity-profiles",
        "updated": not dry_run,
        "dry_run": dry_run,
        "entity_id": entity_id,
        "profile_count": len(profiles),
        "skipped_candidate_count": skipped_candidate_count,
        "source_hash": source_hash,
        "index_path": str(index_path),
        "root_index_path": str(root_index_path),
        "profile_paths": rel_profile_paths,
        "removed_stale_profiles": removed,
        "message": (
            f"{'Would generate' if dry_run else 'Generated'} {len(profiles)} entity profile(s)"
        ),
    }
