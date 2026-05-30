#!/usr/bin/env python3
"""Tests for the private EverOS-derived memory research spike."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "everos_derived_memory_spike.v0"


def _seed_journal(
    data_dir: Path,
    *,
    date: str,
    seq: str = "001",
    title: str,
    body: str,
    extra_frontmatter: str = "",
) -> Path:
    year, month, _day = date.split("-")
    journal_dir = data_dir / "Journals" / year / month
    journal_dir.mkdir(parents=True, exist_ok=True)
    path = journal_dir / f"life-index_{date}_{seq}.md"
    frontmatter_lines = [
        "---",
        f'title: "{title}"',
        f"date: {date}",
    ]
    if extra_frontmatter:
        frontmatter_lines.extend(extra_frontmatter.rstrip().splitlines())
    frontmatter_lines.extend(["---", "", body])
    path.write_text("\n".join(frontmatter_lines), encoding="utf-8")
    return path


def _run_spike(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.dev.everos_derived_memory_spike",
            "--json",
            *args,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return json.loads(result.stdout)


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        found: list[str] = []
        for item in value:
            found.extend(_all_strings(item))
        return found
    if isinstance(value, dict):
        found = []
        for item in value.values():
            found.extend(_all_strings(item))
        return found
    return []


def test_spike_emits_private_derived_memory_artifact_from_journal_contracts(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "Life-Index"
    first = _seed_journal(
        data_dir,
        date="2026-05-30",
        seq="001",
        title="Planning EverOS Lessons",
        body=(
            "# Planning EverOS Lessons\n\n"
            "Next week I will compare derived memory views with the journal archive."
        ),
        extra_frontmatter=(
            'abstract: "Compared memory OS ideas with Life Index boundaries."\n'
            'topic: ["work", "research"]\n'
            'people: ["Alice"]\n'
            'project: "Life Index"\n'
            'tags: ["memory", "everos"]\n'
            'mood: ["focused"]\n'
            'location: "Lagos"'
        ),
    )
    _seed_journal(
        data_dir,
        date="2026-05-29",
        seq="001",
        title="Older Reflection",
        body="# Older Reflection\n\nNo future marker here.",
        extra_frontmatter='topic: ["personal"]',
    )

    result = _run_spike(data_dir, "--limit", "1")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["success"] is True
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["command"] == "dev.everos_derived_memory_spike"
    assert payload["source_contracts"] == ["journal.list_recent", "journal.get"]
    assert payload["range"] == {"limit": 1, "offset": 0}
    assert payload["error"] is None

    rel_path = first.relative_to(data_dir).as_posix()
    assert payload["episode_views"] == [
        {
            "journal_id": rel_path,
            "date": "2026-05-30",
            "title": "Planning EverOS Lessons",
            "summary_candidate": "Compared memory OS ideas with Life Index boundaries.",
            "topic": ["work", "research"],
            "people": ["Alice"],
            "project": "Life Index",
            "tags": ["memory", "everos"],
            "evidence_paths": [rel_path],
        }
    ]
    assert {
        "candidate_type": "frontmatter_fact",
        "subject": rel_path,
        "predicate": "mentions_person",
        "object": "Alice",
        "source_field": "people",
        "evidence_paths": [rel_path],
    } in payload["atomic_fact_candidates"]
    assert {
        "candidate_type": "frontmatter_fact",
        "subject": rel_path,
        "predicate": "has_topic",
        "object": "work",
        "source_field": "topic",
        "evidence_paths": [rel_path],
    } in payload["atomic_fact_candidates"]
    assert payload["foresight_candidates"] == [
        {
            "candidate_type": "future_intent_marker",
            "marker": "next week",
            "source_snippet": (
                "Next week I will compare derived memory views with the journal archive."
            ),
            "evidence_paths": [rel_path],
        }
    ]
    assert "Deterministic candidates are not confirmed facts." in payload["limitations"]


def test_spike_is_read_only_and_omits_absolute_paths(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_journal(
        data_dir,
        date="2026-05-30",
        title="Read Only",
        body="# Read Only\n\nTomorrow I will keep this read only.",
        extra_frontmatter='topic: ["work"]',
    )
    before = {
        path.relative_to(data_dir).as_posix(): path.read_bytes()
        for path in sorted(data_dir.rglob("*"))
        if path.is_file()
    }

    result = _run_spike(data_dir, "--limit", "5")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    after = {
        path.relative_to(data_dir).as_posix(): path.read_bytes()
        for path in sorted(data_dir.rglob("*"))
        if path.is_file()
    }
    assert after == before

    payload = _payload(result)
    all_strings = _all_strings(payload)
    assert str(data_dir) not in all_strings
    assert not any(Path(value).is_absolute() for value in all_strings)


def test_spike_module_avoids_llm_network_vector_and_service_dependencies() -> None:
    source = Path("tools/dev/everos_derived_memory_spike.py").read_text(encoding="utf-8")

    forbidden_tokens = [
        "openai",
        "anthropic",
        "sentence_transformers",
        "embedding",
        "Milvus",
        "Elasticsearch",
        "MongoDB",
        "Redis",
        "requests",
        "httpx",
        "urllib",
    ]
    for token in forbidden_tokens:
        assert token not in source
