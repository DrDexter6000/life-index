#!/usr/bin/env python3
"""Private read-only derived memory spike over journal read contracts."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import PurePosixPath
from typing import Any, cast

SCHEMA_VERSION = "everos_derived_memory_spike.v0"
SOURCE_CONTRACTS = ["journal.list_recent", "journal.get"]

FACT_FIELDS = [
    ("people", "mentions_person"),
    ("topic", "has_topic"),
    ("project", "related_project"),
    ("tags", "has_tag"),
    ("mood", "has_mood"),
    ("location", "at_location"),
]

FORESIGHT_MARKERS = [
    "next week",
    "tomorrow",
    "later",
    "pending",
    "todo",
    "to-do",
    "will",
    "计划",
    "明天",
    "下周",
    "待办",
]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m tools.dev.everos_derived_memory_spike",
        description="Private read-only EverOS-derived memory research spike.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument("--limit", type=int, default=20, help="Recent journals to inspect.")
    parser.add_argument("--offset", type=int, default=0, help="Recent journal offset.")
    return parser.parse_args(argv)


def _error_payload(
    code: str,
    message: str,
    *,
    limit: int,
    offset: int,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "schema_version": SCHEMA_VERSION,
        "command": "dev.everos_derived_memory_spike",
        "source_contracts": SOURCE_CONTRACTS,
        "range": {"limit": limit, "offset": offset},
        "episode_views": [],
        "atomic_fact_candidates": [],
        "foresight_candidates": [],
        "limitations": _limitations(),
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def _limitations() -> list[str]:
    return [
        "Deterministic candidates are not confirmed facts.",
        "No LLM interpretation or relationship judgment was performed.",
        "Derived views are private research artifacts, not a public CLI contract.",
    ]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def _run_journal_command(args: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, "-m", "tools", "journal", *args, "--json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"journal command returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("journal command returned non-object JSON")
    payload = cast(dict[str, Any], parsed)
    if proc.returncode != 0 or not payload.get("success"):
        err = _as_dict(payload.get("error"))
        message = str(err.get("message") or "")
        raise RuntimeError(message or "journal command failed")
    return payload


def _safe_rel_path(raw: Any) -> str:
    rel = str(raw or "").replace("\\", "/").strip()
    if not rel:
        return ""
    if rel.startswith("/") or rel.startswith("//") or re.match(r"^[A-Za-z]:/", rel):
        parts = PurePosixPath(rel).parts
        if "Journals" in parts:
            idx = parts.index("Journals")
            return "/".join(parts[idx:])
        return ""
    if any(part == ".." for part in PurePosixPath(rel).parts):
        return ""
    return rel


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _clean_body_text(body: str) -> str:
    kept: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        kept.append(stripped)
    return " ".join(kept)


def _first_sentence(text: str) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return ""
    match = re.search(r"^(.+?[.!?。！？])(?:\s|$)", normalized)
    if match:
        return match.group(1).strip()
    return normalized[:240]


def _summary_candidate(metadata: dict[str, Any], body: str) -> str:
    for field in ("abstract", "summary"):
        value = metadata.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _first_sentence(_clean_body_text(body))


def _episode_view(detail: dict[str, Any]) -> dict[str, Any]:
    rel_path = _safe_rel_path(detail.get("rel_path") or detail.get("id"))
    metadata = _as_dict(detail.get("metadata"))
    body = str(detail.get("content") or "")
    return {
        "journal_id": rel_path,
        "date": str(metadata.get("date") or detail.get("date") or ""),
        "title": str(metadata.get("title") or detail.get("title") or rel_path),
        "summary_candidate": _summary_candidate(metadata, body),
        "topic": _as_list(metadata.get("topic")),
        "people": _as_list(metadata.get("people")),
        "project": str(metadata.get("project") or ""),
        "tags": _as_list(metadata.get("tags")),
        "evidence_paths": [rel_path] if rel_path else [],
    }


def _atomic_fact_candidates(detail: dict[str, Any]) -> list[dict[str, Any]]:
    rel_path = _safe_rel_path(detail.get("rel_path") or detail.get("id"))
    metadata = _as_dict(detail.get("metadata"))
    facts: list[dict[str, Any]] = []
    for field, predicate in FACT_FIELDS:
        for obj in _as_list(metadata.get(field)):
            facts.append(
                {
                    "candidate_type": "frontmatter_fact",
                    "subject": rel_path,
                    "predicate": predicate,
                    "object": obj,
                    "source_field": field,
                    "evidence_paths": [rel_path] if rel_path else [],
                }
            )
    return facts


def _sentences(text: str) -> list[str]:
    cleaned = _clean_body_text(text)
    if not cleaned:
        return []
    parts = re.findall(r"[^.!?。！？]+[.!?。！？]?", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _foresight_candidates(detail: dict[str, Any]) -> list[dict[str, Any]]:
    rel_path = _safe_rel_path(detail.get("rel_path") or detail.get("id"))
    body = str(detail.get("content") or "")
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for sentence in _sentences(body):
        lowered = sentence.casefold()
        for marker in FORESIGHT_MARKERS:
            if marker.casefold() not in lowered:
                continue
            key = (marker, sentence)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "candidate_type": "future_intent_marker",
                    "marker": marker,
                    "source_snippet": sentence,
                    "evidence_paths": [rel_path] if rel_path else [],
                }
            )
            break
    return candidates


def build_artifact(limit: int = 20, offset: int = 0) -> dict[str, Any]:
    if limit < 0 or offset < 0:
        return _error_payload(
            "SPIKE_ARGUMENT_INVALID",
            "limit and offset must be non-negative.",
            limit=limit,
            offset=offset,
        )

    try:
        list_payload = _run_journal_command(
            ["list", "--recent", "--limit", str(limit), "--offset", str(offset)]
        )
        items = list_payload.get("data", {}).get("items", [])
        if not isinstance(items, list):
            raise RuntimeError("journal list payload did not contain data.items")

        details: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            rel_path = _safe_rel_path(item.get("rel_path") or item.get("id"))
            if not rel_path:
                continue
            get_payload = _run_journal_command(["get", "--path", rel_path])
            detail = get_payload.get("data")
            if isinstance(detail, dict):
                details.append(detail)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return _error_payload(
            "SPIKE_JOURNAL_CONTRACT_FAILED",
            str(exc),
            limit=limit,
            offset=offset,
        )

    episode_views = [_episode_view(detail) for detail in details]
    atomic_facts: list[dict[str, Any]] = []
    foresights: list[dict[str, Any]] = []
    for detail in details:
        atomic_facts.extend(_atomic_fact_candidates(detail))
        foresights.extend(_foresight_candidates(detail))

    return {
        "success": True,
        "schema_version": SCHEMA_VERSION,
        "command": "dev.everos_derived_memory_spike",
        "source_contracts": SOURCE_CONTRACTS,
        "range": {"limit": limit, "offset": offset},
        "episode_views": episode_views,
        "atomic_fact_candidates": atomic_facts,
        "foresight_candidates": foresights,
        "limitations": _limitations(),
        "error": None,
    }


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    payload = build_artifact(limit=args.limit, offset=args.offset)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
