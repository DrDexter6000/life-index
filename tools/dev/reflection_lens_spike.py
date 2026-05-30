#!/usr/bin/env python3
"""Private reflection lens consumer over EverOS-derived memory candidates."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from typing import Any, cast

from tools.dev.everos_derived_memory_spike import (
    SCHEMA_VERSION as SOURCE_SCHEMA_VERSION,
    build_artifact,
)

SCHEMA_VERSION = "reflection_lens_spike.v0"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m tools.dev.reflection_lens_spike",
        description="Private read-only reflection lens research spike.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument("--topic", required=True, help="Topic lens value.")
    parser.add_argument("--limit", type=int, default=20, help="Recent journals to inspect.")
    parser.add_argument("--offset", type=int, default=0, help="Recent journal offset.")
    return parser.parse_args(argv)


def _limitations() -> list[str]:
    return [
        "Reflection lenses are derived research views, not confirmed memories.",
        "No LLM interpretation or semantic merge was performed.",
        "Output is private dev tooling and not a public CLI contract.",
    ]


def _error_payload(
    code: str,
    message: str,
    *,
    topic: str,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    return {
        "success": False,
        "schema_version": SCHEMA_VERSION,
        "command": "dev.reflection_lens_spike",
        "lens": {"type": "topic", "value": topic},
        "source_artifact_schema_version": SOURCE_SCHEMA_VERSION,
        "range": {"limit": limit, "offset": offset},
        "episode_count": 0,
        "fact_count": 0,
        "evidence_paths": [],
        "episodes": [],
        "fact_summary": {"by_predicate": {}, "top_objects": []},
        "foresight_candidates": [],
        "limitations": _limitations(),
        "error": {"code": code, "message": message, "details": {}},
    }


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def _ordered_unique(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def _episode_matches_topic(episode: dict[str, Any], topic: str) -> bool:
    values = episode.get("topic")
    if not isinstance(values, list):
        return False
    return any(str(value).casefold() == topic.casefold() for value in values)


def _evidence_key(item: dict[str, Any]) -> str:
    paths = item.get("evidence_paths")
    if not isinstance(paths, list) or not paths:
        return ""
    return str(paths[0])


def _fact_summary(facts: list[dict[str, Any]]) -> dict[str, Any]:
    predicates = Counter(str(fact.get("predicate") or "") for fact in facts)
    objects = Counter(str(fact.get("object") or "") for fact in facts)
    predicate_priority = {
        "mentions_person": 0,
        "related_project": 1,
        "at_location": 2,
        "has_tag": 3,
        "has_topic": 4,
        "has_mood": 5,
    }
    object_priority: dict[str, int] = {}
    for fact in facts:
        obj = str(fact.get("object") or "")
        predicate = str(fact.get("predicate") or "")
        if not obj:
            continue
        priority = predicate_priority.get(predicate, 99)
        object_priority[obj] = min(priority, object_priority.get(obj, priority))
    return {
        "by_predicate": {
            predicate: count for predicate, count in sorted(predicates.items()) if predicate
        },
        "top_objects": [
            {"object": obj, "count": count}
            for obj, count in sorted(
                ((obj, count) for obj, count in objects.items() if obj),
                key=lambda item: (
                    -item[1],
                    object_priority.get(item[0], 99),
                    item[0].casefold(),
                    item[0],
                ),
            )
        ],
    }


def _lens_episode(episode: dict[str, Any]) -> dict[str, Any]:
    return {
        "journal_id": str(episode.get("journal_id") or ""),
        "date": str(episode.get("date") or ""),
        "title": str(episode.get("title") or ""),
        "summary_candidate": str(episode.get("summary_candidate") or ""),
        "evidence_paths": [
            str(path)
            for path in episode.get("evidence_paths", [])
            if isinstance(path, str) and path
        ],
    }


def build_reflection_lens(
    topic: str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    topic = topic.strip()
    if not topic:
        return _error_payload(
            "SPIKE_ARGUMENT_INVALID",
            "topic must be non-empty.",
            topic=topic,
            limit=limit,
            offset=offset,
        )

    source = build_artifact(limit=limit, offset=offset)
    if not source.get("success"):
        error = _as_dict(source.get("error"))
        return _error_payload(
            str(error.get("code") or "SPIKE_SOURCE_FAILED"),
            str(error.get("message") or "source artifact failed"),
            topic=topic,
            limit=limit,
            offset=offset,
        )

    source_episodes = source.get("episode_views", [])
    if not isinstance(source_episodes, list):
        source_episodes = []

    episodes = [
        _lens_episode(episode)
        for episode in source_episodes
        if isinstance(episode, dict) and _episode_matches_topic(episode, topic)
    ]
    evidence_paths = _ordered_unique(
        [
            path
            for episode in episodes
            for path in episode.get("evidence_paths", [])
            if isinstance(path, str) and path
        ]
    )
    evidence_set = set(evidence_paths)

    source_facts = source.get("atomic_fact_candidates", [])
    if not isinstance(source_facts, list):
        source_facts = []
    facts = [
        fact
        for fact in source_facts
        if isinstance(fact, dict) and _evidence_key(fact) in evidence_set
    ]

    source_foresights = source.get("foresight_candidates", [])
    if not isinstance(source_foresights, list):
        source_foresights = []
    foresights = [
        foresight
        for foresight in source_foresights
        if isinstance(foresight, dict) and _evidence_key(foresight) in evidence_set
    ]

    limitations = _limitations()
    if not episodes:
        limitations.append("No matching episodes for this lens.")

    return {
        "success": True,
        "schema_version": SCHEMA_VERSION,
        "command": "dev.reflection_lens_spike",
        "lens": {"type": "topic", "value": topic},
        "source_artifact_schema_version": SOURCE_SCHEMA_VERSION,
        "range": {"limit": limit, "offset": offset},
        "episode_count": len(episodes),
        "fact_count": len(facts),
        "evidence_paths": evidence_paths,
        "episodes": episodes,
        "fact_summary": _fact_summary(facts),
        "foresight_candidates": foresights,
        "limitations": limitations,
        "error": None,
    }


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    payload = build_reflection_lens(
        args.topic,
        limit=args.limit,
        offset=args.offset,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
