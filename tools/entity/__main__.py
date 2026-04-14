#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph, resolve_entity, save_entity_graph
from tools.lib.paths import resolve_user_data_dir


def _graph_path() -> Path:
    return resolve_user_data_dir() / "entity_graph.yaml"


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="life-index entity")
    parser.add_argument("--list", action="store_true", dest="list_entities")
    parser.add_argument("--type", dest="entity_type")
    parser.add_argument("--add")
    parser.add_argument("--resolve")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--check", action="store_true", dest="run_check")
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--merge")
    parser.add_argument("--delete", action="store_true", dest="delete_entity")
    parser.add_argument("--id", dest="entity_id")
    parser.add_argument("--target-id", dest="target_id")
    parser.add_argument("--add-alias", dest="add_alias")
    parser.add_argument(
        "--action",
        dest="review_action",
        choices=[
            "merge_as_alias",
            "keep_separate",
            "skip",
            "preview",
        ],
    )
    parser.add_argument("--export", dest="export_format", choices=["csv", "xlsx"])
    parser.add_argument("--import", dest="import_file")
    parser.add_argument("--output", dest="output_file")
    args = parser.parse_args(argv)

    graph_path = _graph_path()
    entities = load_entity_graph(graph_path)

    if args.list_entities:
        results = entities
        if args.entity_type:
            results = [
                entity for entity in entities if entity["type"] == args.entity_type
            ]
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
        entities.append(payload)
        save_entity_graph(entities, graph_path)
        _print({"success": True, "data": payload, "error": None})
        return

    if args.update:
        if not args.entity_id or not args.add_alias:
            raise SystemExit("--update requires --id and --add-alias")
        for entity in entities:
            if entity["id"] == args.entity_id:
                aliases = entity.setdefault("aliases", [])
                if args.add_alias not in aliases:
                    aliases.append(args.add_alias)
                save_entity_graph(entities, graph_path)
                _print({"success": True, "data": entity, "error": None})
                return
        _print({"success": False, "data": None, "error": "Entity not found"})
        return

    if args.audit:
        from tools.entity.audit import audit_entity_graph
        from tools.lib.paths import JOURNALS_DIR

        report = audit_entity_graph(
            graph_path,
            journals_dir=JOURNALS_DIR if JOURNALS_DIR.exists() else None,
        )
        _print({"success": True, "data": report, "error": None})
        return

    if args.stats:
        from tools.entity.stats import compute_stats

        result = compute_stats(graph_path=graph_path)
        _print(result)
        return

    if args.run_check:
        from tools.entity.check import run_check

        result = run_check(graph_path=graph_path)
        _print(result)
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
                else resolve_user_data_dir() / f"review_queue.{args.export_format}"
            )

            if args.export_format == "csv":
                from tools.entity.review_io import export_review_csv

                result = export_review_csv(
                    output_path=output_path, graph_path=graph_path
                )
            else:
                from tools.entity.review_io import export_review_xlsx

                result = export_review_xlsx(
                    output_path=output_path, graph_path=graph_path
                )
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
                {
                    "success": True,
                    "data": {"queue": queue, "total": len(queue)},
                    "error": None,
                }
            )
            return

        # --review --action preview --id ... --target-id ...
        if args.review_action == "preview":
            if not args.entity_id:
                raise SystemExit("--action preview requires --id (item_id)")
            preview = generate_preview(
                item_id=args.entity_id,
                action="merge_as_alias",
                source_id=args.entity_id,
                target_id=args.target_id,
                graph_path=graph_path,
            )
            _print({"success": True, "data": preview, "error": None})
            return

        # --review --action merge_as_alias|keep_separate|skip --id ... --target-id ...
        result = apply_action(
            action=args.review_action,
            source_id=args.entity_id,
            target_id=args.target_id,
            graph_path=graph_path,
        )
        _print(result)
        return

    if args.merge:
        if not args.entity_id or not args.target_id:
            raise SystemExit("--merge requires --id (source) and --target-id (target)")
        from tools.entity.review import apply_action

        result = apply_action(
            action="merge_as_alias",
            source_id=args.entity_id,
            target_id=args.target_id,
            graph_path=graph_path,
        )
        _print(result)
        return

    if args.delete_entity:
        if not args.entity_id:
            raise SystemExit("--delete requires --id")
        entity_id = args.entity_id

        source = next((e for e in entities if e["id"] == entity_id), None)
        if source is None:
            _print(
                {
                    "success": False,
                    "data": None,
                    "error": f"Entity not found: {entity_id}",
                }
            )
            return

        # Report entities that reference this one
        refs = []
        for entity in entities:
            for rel in entity.get("relationships", []):
                if rel["target"] == entity_id:
                    refs.append(
                        {"entity_id": entity["id"], "relation": rel["relation"]}
                    )

        # Remove entity
        entities = [e for e in entities if e["id"] != entity_id]

        # Clean up dangling relationship references
        for entity in entities:
            entity["relationships"] = [
                r for r in entity.get("relationships", []) if r["target"] != entity_id
            ]

        save_entity_graph(entities, graph_path)
        _print(
            {
                "success": True,
                "data": {
                    "deleted_id": entity_id,
                    "deleted_name": source.get("primary_name", ""),
                    "cleaned_refs": refs,
                },
                "error": None,
            }
        )
        return

    parser.print_help()
    raise SystemExit(1)
