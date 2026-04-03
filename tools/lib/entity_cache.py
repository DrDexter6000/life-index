#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph


def build_entity_cache(yaml_path: Path, db_path: Path) -> None:
    entities = load_entity_graph(yaml_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS entities (lookup TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        conn.execute("DELETE FROM entities")
        for entity in entities:
            payload = json.dumps(entity, ensure_ascii=False)
            for lookup in {
                entity["id"],
                entity["primary_name"],
                *entity.get("aliases", []),
            }:
                conn.execute(
                    "INSERT OR REPLACE INTO entities (lookup, payload) VALUES (?, ?)",
                    (lookup, payload),
                )
        conn.commit()
    finally:
        conn.close()


def query_entity_cache(db_path: Path, name_or_alias: str) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT payload FROM entities WHERE lookup = ?", (name_or_alias,)
        ).fetchall()
        return [json.loads(row[0]) for row in rows]
    finally:
        conn.close()
