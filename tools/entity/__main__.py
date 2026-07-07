#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph, resolve_entity, save_entity_graph
from tools.lib.observability import build_provenance_envelope
from tools.lib.paths import get_user_data_dir

SCHEMA_VERSION = "m16.entity.v0"


def _graph_path() -> Path:
    return get_user_data_dir() / "entity_graph.yaml"


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _alias_name(alias: Any) -> str | None:
    if isinstance(alias, str):
        return alias
    if isinstance(alias, dict):
        name = alias.get("name")
        if isinstance(name, str):
            return name
    return None


def _stamp_entity_write(entity: dict[str, Any], *, source: str) -> None:
    created_at = _now_iso()
    entity.setdefault("source", source)
    entity.setdefault("status", "confirmed")
    entity.setdefault("created_at", created_at)
    entity.setdefault("evidence", [])
    alias_metadata = entity.setdefault("alias_metadata", {})
    for alias in entity.get("aliases", []) or []:
        if isinstance(alias, dict):
            alias.setdefault("source", source)
            alias.setdefault("created_at", created_at)
            alias.setdefault("confidence", 1.0)
        name = _alias_name(alias)
        if name:
            alias_metadata.setdefault(
                name,
                {
                    "source": alias.get("source", source) if isinstance(alias, dict) else source,
                    "confidence": (
                        alias.get("confidence", 1.0) if isinstance(alias, dict) else 1.0
                    ),
                    "created_at": (
                        alias.get("created_at", created_at)
                        if isinstance(alias, dict)
                        else created_at
                    ),
                },
            )

    for relationship in entity.get("relationships", []) or []:
        relationship.setdefault("source", source)
        relationship.setdefault("created_at", created_at)
        relationship.setdefault("status", "confirmed")
        relationship.setdefault("evidence", [])


def _attach_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    provenance_envelope = build_provenance_envelope(
        source_data=payload.get("data", {}),
        generator="entity",
        params={},
    )
    payload["schema_version"] = provenance_envelope["schema_version"]
    payload["provenance"] = provenance_envelope["provenance"]
    return payload


def _print(payload: dict[str, Any]) -> None:
    payload = _attach_provenance(payload)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        fallback_text = json.dumps(payload, ensure_ascii=True, indent=2)
        print(fallback_text, flush=True)


_RETIRED_TOP_LEVEL_PRIMITIVES = {
    "--seed": "life-index entity build --from-journals --preview --json",
    "--update": "life-index entity --add-alias ALIAS --id ENTITY_ID",
    "--merge": "life-index entity --review --action preview",
    "--delete": "life-index entity maintain --delete --id ENTITY_ID --preview --json",
}

_WORKFLOW_HINTS = {
    "--check": {
        "workflow": "audit",
        "preferred_command": "life-index entity audit --json",
        "reason": (
            "Use the audit workflow facade for graph health; "
            "--check is a low-level structural component."
        ),
    },
    "--audit": {
        "workflow": "audit",
        "preferred_command": "life-index entity audit --json",
        "reason": (
            "Use the audit workflow facade for graph health; "
            "--audit is a low-level quality component."
        ),
    },
    "--stats": {
        "workflow": "audit",
        "preferred_command": "life-index entity audit --json",
        "reason": (
            "Use the audit workflow facade for graph health; "
            "--stats is a low-level statistics component."
        ),
    },
    "--review": {
        "workflow": "maintain",
        "preferred_command": "life-index entity audit --json",
        "reason": (
            "Start from the audit workflow facade, then follow its review "
            "next_step when human judgment is needed."
        ),
    },
}


def _with_workflow_hint(payload: dict[str, Any], primitive: str) -> dict[str, Any]:
    payload["workflow_hint"] = dict(_WORKFLOW_HINTS[primitive])
    return payload


def _entity_ref(entity: dict[str, Any]) -> dict[str, str]:
    return {
        "entity_id": str(entity["id"]),
        "primary_name": str(entity.get("primary_name", "")),
    }


def _set_self_anchor(
    entities: list[dict[str, Any]],
    *,
    entity_id: str,
    graph_path: Path,
) -> dict[str, Any]:
    target = next((entity for entity in entities if entity["id"] == entity_id), None)
    if target is None:
        return {
            "success": False,
            "data": {"entity_id": entity_id},
            "error": {"code": "ENTITY_NOT_FOUND", "message": "entity not found"},
        }
    if target.get("status", "confirmed") != "confirmed":
        return {
            "success": False,
            "data": {"entity_id": entity_id, "status": target.get("status", "candidate")},
            "error": {
                "code": "ENTITY_SELF_REQUIRES_CONFIRMED",
                "message": "self anchor can only be set on a confirmed entity",
            },
        }

    created_at = _now_iso()
    previous = next(
        (
            _entity_ref(entity)
            for entity in entities
            if (entity.get("attributes") or {}).get("self") is True
        ),
        None,
    )
    for entity in entities:
        attributes = entity.setdefault("attributes", {})
        attributes.pop("self", None)
        attributes.pop("self_source", None)
        attributes.pop("self_created_at", None)
    target_attributes = target.setdefault("attributes", {})
    target_attributes["self"] = True
    target_attributes["self_source"] = "user"
    target_attributes["self_created_at"] = created_at
    save_entity_graph(entities, graph_path)
    return {
        "success": True,
        "data": {
            "self_entity": _entity_ref(target),
            "previous_self_entity": previous,
            "source": "user",
            "created_at": created_at,
        },
        "error": None,
    }


def _unset_self_anchor(entities: list[dict[str, Any]], *, graph_path: Path) -> dict[str, Any]:
    previous_entity: dict[str, Any] | None = None
    changed = False
    for entity in entities:
        attributes = entity.setdefault("attributes", {})
        if attributes.get("self") is True and previous_entity is None:
            previous_entity = entity
        for key in ("self", "self_source", "self_created_at"):
            if key in attributes:
                attributes.pop(key, None)
                changed = True
    if changed:
        save_entity_graph(entities, graph_path)
    return {
        "success": True,
        "data": {
            "previous_self_entity": (
                _entity_ref(previous_entity) if previous_entity is not None else None
            )
        },
        "error": None,
    }


def _handle_retired_top_level_primitives(argv: list[str]) -> None:
    if argv and argv[0] in {"build", "audit", "maintain"}:
        return
    retired_flag = next((flag for flag in _RETIRED_TOP_LEVEL_PRIMITIVES if flag in argv), None)
    if retired_flag is None:
        return
    replacement = _RETIRED_TOP_LEVEL_PRIMITIVES[retired_flag]
    _print(
        {
            "success": False,
            "data": {
                "retired_flag": retired_flag,
                "replacement_command": replacement,
            },
            "error": {
                "code": "ENTITY_PRIMITIVE_REMOVED",
                "message": f"{retired_flag} was removed. Use: {replacement}",
            },
        }
    )
    raise SystemExit(2)


def _run_audit_workflow(argv: list[str]) -> None:
    audit_parser = argparse.ArgumentParser(prog="life-index entity audit")
    audit_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    audit_parser.parse_args(argv)
    from tools.entity.audit_facade import build_audit_facade
    from tools.lib.paths import get_journals_dir

    graph_path = _graph_path()
    journals_dir = get_journals_dir()
    result = build_audit_facade(
        graph_path=graph_path,
        journals_dir=journals_dir if journals_dir.exists() else None,
    )
    _print(result)


def _run_maintain_workflow(argv: list[str]) -> None:
    maintain_parser = argparse.ArgumentParser(prog="life-index entity maintain")
    maintain_parser.add_argument("--normalize", action="store_true")
    maintain_parser.add_argument("--delete", action="store_true")
    maintain_parser.add_argument("--add-relationship", action="store_true")
    maintain_parser.add_argument("--id", dest="entity_id")
    maintain_parser.add_argument("--target-id", dest="target_id")
    maintain_parser.add_argument("--relation", dest="relation")
    maintain_parser.add_argument("--preview", action="store_true")
    maintain_parser.add_argument("--apply", action="store_true")
    maintain_parser.add_argument("--backup", action="store_true")
    maintain_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    maintain_args = maintain_parser.parse_args(argv)
    operations = [
        maintain_args.normalize,
        maintain_args.delete,
        maintain_args.add_relationship,
    ]
    if sum(1 for enabled in operations if enabled) > 1:
        raise SystemExit("entity maintain accepts only one operation at a time")
    if not any(operations):
        raise SystemExit(
            "entity maintain currently requires --normalize, --delete, or --add-relationship"
        )
    if maintain_args.delete:
        from tools.entity.delete import run_delete

        result = run_delete(
            graph_path=_graph_path(),
            entity_id=maintain_args.entity_id,
            preview=maintain_args.preview,
            apply=maintain_args.apply,
            backup=maintain_args.backup,
        )
        _print(result)
        return
    if maintain_args.add_relationship:
        from tools.entity.relationship import run_add_relationship

        result = run_add_relationship(
            graph_path=_graph_path(),
            source_id=maintain_args.entity_id,
            target_id=maintain_args.target_id,
            relation=maintain_args.relation,
            preview=maintain_args.preview,
            apply=maintain_args.apply,
        )
        _print(result)
        return
    from tools.entity.normalize import run_normalize

    result = run_normalize(
        graph_path=_graph_path(),
        preview=maintain_args.preview,
        apply=maintain_args.apply,
        backup=maintain_args.backup,
    )
    _print(result)


def _run_build_workflow(argv: list[str]) -> None:
    build_parser = argparse.ArgumentParser(prog="life-index entity build")
    build_parser.add_argument("--from-batch", dest="from_batch")
    build_parser.add_argument("--from-journals", action="store_true")
    build_parser.add_argument("--preview", action="store_true")
    build_parser.add_argument("--apply", action="store_true")
    build_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    build_args = build_parser.parse_args(argv)
    if build_args.from_batch and build_args.from_journals:
        raise SystemExit("entity build accepts only one source")
    if build_args.from_journals:
        if not build_args.preview or build_args.apply:
            raise SystemExit("entity build --from-journals currently supports --preview only")
        from tools.entity.seed import preview_seed_entity_graph
        from tools.lib.paths import get_journals_dir

        result = preview_seed_entity_graph(_graph_path(), get_journals_dir())
        _print(result)
        return
    if not build_args.from_batch:
        raise SystemExit("entity build currently requires --from-batch FILE or --from-journals")
    if build_args.preview == build_args.apply:
        raise SystemExit("entity build --from-batch requires exactly one of --preview/--apply")
    from tools.entity.batch import apply_batch_file

    result = apply_batch_file(
        batch_path=Path(build_args.from_batch),
        graph_path=_graph_path(),
        preview=build_args.preview,
    )
    _print(result)


def _run_profile_workflow(argv: list[str]) -> None:
    profile_parser = argparse.ArgumentParser(prog="life-index entity profile")
    profile_parser.add_argument("--id", dest="entity_id")
    profile_parser.add_argument("--name", dest="name")
    profile_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    profile_args = profile_parser.parse_args(argv)
    from tools.entity.profile import build_entity_profile

    result = build_entity_profile(
        graph_path=_graph_path(),
        entity_id=profile_args.entity_id,
        name=profile_args.name,
    )
    _print(result)


def _run_workflow_command(argv: list[str]) -> bool:
    if not argv:
        return False
    if argv[0] == "build":
        _run_build_workflow(argv[1:])
        return True
    if argv[0] == "audit":
        _run_audit_workflow(argv[1:])
        return True
    if argv[0] == "maintain":
        _run_maintain_workflow(argv[1:])
        return True
    if argv[0] == "profile":
        _run_profile_workflow(argv[1:])
        return True
    return False


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    _handle_retired_top_level_primitives(argv)
    if _run_workflow_command(argv):
        return

    parser = argparse.ArgumentParser(
        prog="life-index entity",
        description="Life Index Entity Graph tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Workflow gates:
  life-index entity build --from-journals --preview --json
  life-index entity build --from-batch FILE --preview --json
  life-index entity build --from-batch FILE --apply --json
  life-index entity profile --id ENTITY_ID --json
  life-index entity audit --json
  life-index entity maintain --normalize --preview --json
  life-index entity maintain --delete --id ENTITY_ID --preview --json
  life-index entity maintain --add-relationship --id SOURCE_ID \
--target-id TARGET_ID --relation RELATION --preview --json

JSON contract:
  --json emits the stable machine-readable contract. Advanced read-only
  primitives accept --json for host-agent compatibility and include workflow_hint.

Advanced primitives appendix:
  life-index entity --review --json        Human-in-the-loop review queue
  life-index entity --check --json         Structural graph check component
  life-index entity --audit --json         Low-level quality audit component
  life-index entity --stats --json         Graph statistics component
  life-index entity --set-self --id ENTITY_ID --json
                                        Set the unique self anchor
  life-index entity --unset-self --json  Clear the self anchor
""",
    )
    parser.add_argument("--list", action="store_true", dest="list_entities")
    parser.add_argument("--type", dest="entity_type")
    parser.add_argument("--add")
    parser.add_argument("--resolve")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--check", action="store_true", dest="run_check")
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--unmerge", action="store_true")
    parser.add_argument("--propose")
    parser.add_argument("--apply-batch", dest="apply_batch")
    parser.add_argument("--set-self", action="store_true")
    parser.add_argument("--unset-self", action="store_true")
    parser.add_argument(
        "--preview", action="store_true", help="Preview only, do not mutate the graph"
    )
    parser.add_argument("--id", dest="entity_id")
    parser.add_argument("--target-id", dest="target_id")
    parser.add_argument("--relation", dest="relation")
    parser.add_argument("--add-alias", dest="add_alias")
    parser.add_argument(
        "--action",
        dest="review_action",
        choices=[
            "merge_as_alias",
            "add_relationship",
            "confirm_candidate",
            "reject_candidate",
            "keep_separate",
            "undo_keep_separate",
            "skip",
            "preview",
        ],
    )
    parser.add_argument("--export", dest="export_format", choices=["csv", "xlsx"])
    parser.add_argument("--import", dest="import_file")
    parser.add_argument("--output", dest="output_file")
    parser.add_argument(
        "--candidate-edges",
        action="store_true",
        help="Generate candidate relationship edges report (read-only, zero graph writes)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    if args.review_action and not args.review:
        if args.review_action == "add_relationship":
            replacement = (
                "life-index entity maintain --add-relationship --id SOURCE_ID "
                "--target-id TARGET_ID --relation RELATION --preview --json"
            )
            _print(
                {
                    "success": False,
                    "data": {
                        "action": args.review_action,
                        "replacement_command": replacement,
                    },
                    "error": {
                        "code": "ENTITY_RELATIONSHIP_ACTION_REQUIRES_REVIEW",
                        "message": (
                            "--action add_relationship is only valid with --review. "
                            "For a user-confirmed relationship fact, use the maintain "
                            "preview/apply relationship primitive."
                        ),
                        "suggested_command": replacement,
                    },
                }
            )
            raise SystemExit(2)
        raise SystemExit("--action requires --review")

    graph_path = _graph_path()
    if args.run_check:
        from tools.entity.check import run_check

        result = run_check(graph_path=graph_path)
        _print(_with_workflow_hint(result, "--check"))
        return

    entities = load_entity_graph(graph_path)

    if args.set_self and args.unset_self:
        raise SystemExit("choose only one of --set-self or --unset-self")

    if args.set_self:
        if not args.entity_id:
            raise SystemExit("--set-self requires --id ENTITY_ID")
        _print(_set_self_anchor(entities, entity_id=args.entity_id, graph_path=graph_path))
        return

    if args.unset_self:
        _print(_unset_self_anchor(entities, graph_path=graph_path))
        return

    if args.apply_batch:
        from tools.entity.batch import apply_batch_file

        result = apply_batch_file(
            batch_path=Path(args.apply_batch),
            graph_path=graph_path,
            preview=args.preview,
        )
        _print(result)
        return

    if args.propose:
        from tools.entity.propose import apply_proposal

        payload = json.loads(args.propose)
        if not isinstance(payload, dict):
            raise SystemExit("--propose requires JSON object")
        result = apply_proposal(payload=payload, graph_path=graph_path)
        _print(result)
        return

    if args.list_entities:
        results = entities
        if args.entity_type:
            results = [entity for entity in entities if entity["type"] == args.entity_type]
        _print({"success": True, "data": results, "error": None})
        return

    if args.resolve:
        resolved = resolve_entity(args.resolve, entities)
        _print(
            {
                "success": resolved is not None,
                "data": resolved,
                "error": None if resolved else "Entity not found",
            }
        )
        return

    if args.add:
        payload = json.loads(args.add)
        if not isinstance(payload, dict):
            raise SystemExit("--add requires JSON object")
        _stamp_entity_write(payload, source="user")
        entities.append(payload)
        save_entity_graph(entities, graph_path)
        _print({"success": True, "data": payload, "error": None})
        return

    if args.add_alias:
        if not args.entity_id or not args.add_alias:
            raise SystemExit("--add-alias requires --id and --add-alias")
        for entity in entities:
            if entity["id"] == args.entity_id:
                aliases = entity.setdefault("aliases", [])
                if args.add_alias not in aliases:
                    aliases.append(args.add_alias)
                entity.setdefault("alias_metadata", {})[args.add_alias] = {
                    "source": "user",
                    "confidence": 1.0,
                    "created_at": _now_iso(),
                }
                save_entity_graph(entities, graph_path)
                _print({"success": True, "data": entity, "error": None})
                return
        _print({"success": False, "data": None, "error": "Entity not found"})
        return

    if args.audit:
        from tools.entity.audit import audit_entity_graph
        from tools.lib.paths import get_journals_dir

        _journals_dir = get_journals_dir()
        report = audit_entity_graph(
            graph_path,
            journals_dir=_journals_dir if _journals_dir.exists() else None,
        )
        _print(_with_workflow_hint({"success": True, "data": report, "error": None}, "--audit"))
        return

    if args.stats:
        from tools.entity.stats import compute_stats

        result = compute_stats(graph_path=graph_path)
        _print(_with_workflow_hint(result, "--stats"))
        return

    if args.review:
        from tools.entity.review import (
            build_review_queue,
            generate_preview,
            apply_action,
        )

        # --review --export csv/xlsx [--output file]
        if args.export_format:
            output_path = (
                Path(args.output_file)
                if args.output_file
                else get_user_data_dir() / f"review_queue.{args.export_format}"
            )

            if args.export_format == "csv":
                from tools.entity.review_io import export_review_csv

                result = export_review_csv(output_path=output_path, graph_path=graph_path)
            else:
                from tools.entity.review_io import export_review_xlsx

                result = export_review_xlsx(output_path=output_path, graph_path=graph_path)
            _print(result)
            return

        # --review --import <file>
        if args.import_file:
            from tools.entity.review_io import import_review_csv

            result = import_review_csv(
                input_path=Path(args.import_file),
                graph_path=graph_path,
            )
            _print(result)
            return

        # --review alone: show queue
        if not args.review_action:
            queue = build_review_queue(graph_path=graph_path)
            _print(
                _with_workflow_hint(
                    {
                        "success": True,
                        "data": {"queue": queue, "total": len(queue)},
                        "error": None,
                    },
                    "--review",
                )
            )
            return

        # --review --action preview --id ... --target-id ...
        if args.review_action == "preview":
            if not args.entity_id:
                raise SystemExit("--action preview requires --id (item_id)")
            preview_action = "add_relationship" if args.relation else "merge_as_alias"
            preview = generate_preview(
                item_id=args.entity_id,
                action=preview_action,
                source_id=args.entity_id,
                target_id=args.target_id,
                relation=args.relation,
                graph_path=graph_path,
            )
            _print({"success": True, "data": preview, "error": None})
            return

        # --review --action merge_as_alias|keep_separate|undo_keep_separate|skip
        # with --id ... --target-id ...
        result = apply_action(
            action=args.review_action,
            source_id=args.entity_id,
            target_id=args.target_id,
            relation=args.relation,
            source="review",
            graph_path=graph_path,
        )
        _print(result)
        return

    if args.unmerge:
        if not args.entity_id or not args.target_id:
            raise SystemExit("--unmerge requires --id (merged entity) and --target-id (target)")
        from tools.entity.review import unmerge_entity

        result = unmerge_entity(
            merged_id=args.entity_id,
            target_id=args.target_id,
            graph_path=graph_path,
        )
        _print(result)
        return

    if args.candidate_edges:
        from tools.entity.candidate_edges import run as run_candidate_edges

        result = run_candidate_edges()
        _print(result)
        return

    parser.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()
