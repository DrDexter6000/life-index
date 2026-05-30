#!/usr/bin/env python3
"""Tests for the private reflection lens consumer spike."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "reflection_lens_spike.v0"


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


def _run_lens(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.dev.reflection_lens_spike",
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


def test_reflection_lens_groups_topic_episodes_facts_and_evidence(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "Life-Index"
    work = _seed_journal(
        data_dir,
        date="2026-05-30",
        title="Work Reflection",
        body="# Work Reflection\n\nTomorrow I will refine the import contract.",
        extra_frontmatter=(
            'abstract: "Reviewed work progress and next contract step."\n'
            'topic: ["work"]\n'
            'people: ["Alice"]\n'
            'project: "Life Index"\n'
            'tags: ["import", "contract"]\n'
            'mood: ["focused"]\n'
            'location: "Lagos"'
        ),
    )
    _seed_journal(
        data_dir,
        date="2026-05-29",
        title="Life Reflection",
        body="# Life Reflection\n\nA personal note.",
        extra_frontmatter='topic: ["life"]\npeople: ["Bob"]',
    )

    result = _run_lens(data_dir, "--topic", "work")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    rel_path = work.relative_to(data_dir).as_posix()

    assert payload["success"] is True
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["command"] == "dev.reflection_lens_spike"
    assert payload["lens"] == {"type": "topic", "value": "work"}
    assert payload["source_artifact_schema_version"] == "everos_derived_memory_spike.v0"
    assert payload["episode_count"] == 1
    assert payload["fact_count"] == 7
    assert payload["evidence_paths"] == [rel_path]
    assert payload["episodes"] == [
        {
            "journal_id": rel_path,
            "date": "2026-05-30",
            "title": "Work Reflection",
            "summary_candidate": "Reviewed work progress and next contract step.",
            "evidence_paths": [rel_path],
        }
    ]
    assert payload["fact_summary"]["by_predicate"] == {
        "at_location": 1,
        "has_mood": 1,
        "has_tag": 2,
        "has_topic": 1,
        "mentions_person": 1,
        "related_project": 1,
    }
    assert payload["fact_summary"]["top_objects"][:4] == [
        {"object": "Alice", "count": 1},
        {"object": "Life Index", "count": 1},
        {"object": "Lagos", "count": 1},
        {"object": "contract", "count": 1},
    ]
    assert payload["foresight_candidates"] == [
        {
            "candidate_type": "future_intent_marker",
            "marker": "tomorrow",
            "source_snippet": "Tomorrow I will refine the import contract.",
            "evidence_paths": [rel_path],
        }
    ]
    assert payload["limitations"]
    assert payload["error"] is None


def test_reflection_lens_empty_topic_is_success_with_limitations(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_journal(
        data_dir,
        date="2026-05-30",
        title="Life Reflection",
        body="# Life Reflection\n\nA personal note.",
        extra_frontmatter='topic: ["life"]',
    )

    result = _run_lens(data_dir, "--topic", "work")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["success"] is True
    assert payload["episode_count"] == 0
    assert payload["fact_count"] == 0
    assert payload["episodes"] == []
    assert payload["fact_summary"] == {"by_predicate": {}, "top_objects": []}
    assert payload["evidence_paths"] == []
    assert "No matching episodes for this lens." in payload["limitations"]
