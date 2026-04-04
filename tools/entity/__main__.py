#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph, resolve_entity, save_entity_graph
from tools.lib.paths import USER_DATA_DIR


def _graph_path() -> Path:
    return USER_DATA_DIR / "entity_graph.yaml"


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="life-index entity")
    parser.add_argument("--list", action="store_true", dest="list_entities")
    parser.add_argument("--type", dest="entity_type")
    parser.add_argument("--add")
    parser.add_argument("--resolve")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--id", dest="entity_id")
    parser.add_argument("--add-alias", dest="add_alias")
    args = parser.parse_args(argv)

    graph_path = _graph_path()
    entities = load_entity_graph(graph_path)

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

    parser.print_help()
    raise SystemExit(1)
