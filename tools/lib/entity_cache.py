#!/usr/bin/env python3
"""
Entity Cache — SQLite-backed lookup cache for entity graph.

Round 7 Phase 1 Task 2: Activated as part of the read path.
- is_cache_fresh(): checks yaml mtime vs db mtime
- resolve_entity_cached(): cache-first resolution with YAML fallback
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph, resolve_entity

try:
    from tools.lib.logger import get_logger

    logger = get_logger("entity_cache")
except ImportError:
    logger = logging.getLogger("entity_cache")


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


def is_cache_fresh(yaml_path: Path, db_path: Path) -> bool:
    """Check if the cache is fresh relative to the YAML source.

    A cache is considered fresh when:
    - Both files exist
    - db mtime >= yaml mtime

    Returns:
        True if cache is up-to-date, False otherwise.
    """
    if not db_path.exists() or not yaml_path.exists():
        return False

    yaml_mtime = yaml_path.stat().st_mtime
    db_mtime = db_path.stat().st_mtime
    return db_mtime >= yaml_mtime


def resolve_entity_cached(
    query: str,
    yaml_path: Path,
    db_path: Path,
) -> dict[str, Any] | None:
    """Resolve an entity using cache-first strategy with YAML fallback.

    1. If cache is fresh → query cache
    2. If cache is stale or missing → load from YAML, rebuild cache, return result
    3. If YAML also fails → return None

    Args:
        query: Entity id, primary_name, or alias to look up.
        yaml_path: Path to entity_graph.yaml.
        db_path: Path to entity cache SQLite database.

    Returns:
        Entity dict if found, None otherwise.
    """
    if is_cache_fresh(yaml_path, db_path):
        rows = query_entity_cache(db_path, query)
        if rows:
            return rows[0]

    # Fallback: load from YAML directly
    try:
        graph = load_entity_graph(yaml_path)
        result = resolve_entity(query, graph)

        # Opportunistic cache rebuild on stale/miss
        try:
            build_entity_cache(yaml_path, db_path)
        except Exception as exc:
            logger.warning("Cache rebuild failed (E1000): %s", exc)

        return result
    except Exception as exc:
        logger.warning(
            "Entity resolution degraded, YAML fallback failed (E1001): %s", exc
        )
        return None
