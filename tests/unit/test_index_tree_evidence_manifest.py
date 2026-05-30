#!/usr/bin/env python3
"""Tests for the private Index Tree Evidence Navigation manifest prototype."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tools.generate_index.navigation import IndexNode

SCHEMA_VERSION = "index_tree_evidence_manifest.dev.v0"


def _seed_journal(
    data_dir: Path,
    *,
    date: str,
    seq: str = "001",
    title: str,
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
    frontmatter_lines.extend(["---", "", f"# {title}", "", "Fixture body"])
    path.write_text("\n".join(frontmatter_lines), encoding="utf-8")
    return path


def _seed_index(path: Path, frontmatter_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n# Index\n",
        encoding="utf-8",
    )


def _run_manifest(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.dev.index_tree_evidence_manifest",
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


def test_manifest_emits_private_schema_and_month_evidence(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    first = _seed_journal(
        data_dir,
        date="2026-03-14",
        title="Index Tree Walk",
        extra_frontmatter=(
            'topic: ["work", "research"]\n' 'people: ["Alice"]\n' 'project: "Life Index"'
        ),
    )
    second = _seed_journal(
        data_dir,
        date="2026-03-15",
        seq="002",
        title="Second Walk",
        extra_frontmatter=('topic: ["work"]\n' 'people: ["Bob"]\n' 'project: "Life Index"'),
    )
    _seed_index(
        data_dir / "Journals" / "2026" / "03" / "index_2026-03.md",
        [
            "year: 2026",
            "month: 3",
            "entries: 2",
            "topics: {work: 2, research: 1}",
            'date_range: "2026-03"',
        ],
    )

    result = _run_manifest(data_dir, "--level", "month")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["success"] is True
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["command"] == "dev.index_tree_evidence_manifest"
    assert payload["source"] == {"builder": "prototype", "public_contract": False}
    assert payload["error"] is None

    rel_first = first.relative_to(data_dir).as_posix()
    rel_second = second.relative_to(data_dir).as_posix()
    assert payload["nodes"] == [
        {
            "node_id": "month:2026-03",
            "level": "month",
            "relative_path": "Journals/2026/03/index_2026-03.md",
            "year": 2026,
            "month": 3,
            "entry_count": 2,
            "date_range": "2026-03",
            "has_index": True,
            "freshness": "fresh",
            "entry_refs": [rel_first, rel_second],
            "frontmatter_signals": {
                "topic_counts": {"work": 2, "research": 1},
                "people_counts": {"Alice": 1, "Bob": 1},
                "project_counts": {"Life Index": 2},
            },
            "source_hashes": {
                "index": payload["nodes"][0]["source_hashes"]["index"],
                "entries": {
                    rel_first: payload["nodes"][0]["source_hashes"]["entries"][rel_first],
                    rel_second: payload["nodes"][0]["source_hashes"]["entries"][rel_second],
                },
            },
        }
    ]
    assert len(payload["nodes"][0]["source_hashes"]["index"]) == 64
    assert all(
        len(value) == 64 for value in payload["nodes"][0]["source_hashes"]["entries"].values()
    )
    assert "Private dev artifact; not a public CLI/API contract." in payload["limitations"]


def test_manifest_is_read_only_and_omits_absolute_paths(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_journal(
        data_dir,
        date="2026-04-01",
        title="Read Only",
        extra_frontmatter='topic: ["private"]',
    )
    before = {
        path.relative_to(data_dir).as_posix(): path.read_bytes()
        for path in sorted(data_dir.rglob("*"))
        if path.is_file()
    }

    result = _run_manifest(data_dir, "--level", "all")

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


def test_manifest_is_deterministic_for_same_fixture(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_journal(
        data_dir,
        date="2026-05-01",
        title="Stable",
        extra_frontmatter='topic: ["stable"]',
    )

    first = _run_manifest(data_dir, "--level", "all")
    second = _run_manifest(data_dir, "--level", "all")

    assert first.returncode == 0, f"stdout: {first.stdout}\nstderr: {first.stderr}"
    assert second.returncode == 0, f"stdout: {second.stdout}\nstderr: {second.stderr}"
    assert _payload(first) == _payload(second)


def test_manifest_node_confines_forged_node_paths(tmp_path: Path) -> None:
    from tools.dev import index_tree_evidence_manifest as manifest_mod

    data_dir = tmp_path / "Life-Index"
    outside_file = tmp_path / "outside_escape.md"
    outside_file.write_text("outside", encoding="utf-8")
    forged_paths = [
        str(outside_file),
        "../outside_escape.md",
        "C:/Users/Example/outside_escape.md",
    ]

    for forged_path in forged_paths:
        node = IndexNode(
            node_id="month:2026-06",
            level="month",
            path=outside_file,
            relative_path=forged_path,
            year=2026,
            month=6,
            entry_count=1,
            topics={},
            date_range="2026-06",
            has_index=True,
            freshness="fresh",
        )

        manifest_node = manifest_mod._manifest_node(node, data_dir)
        all_strings = _all_strings(manifest_node)

        assert manifest_node["relative_path"] == ""
        assert str(outside_file) not in all_strings
        assert "../outside_escape.md" not in all_strings
        assert "C:/Users/Example/outside_escape.md" not in all_strings
        assert not any(Path(value).is_absolute() for value in all_strings)
        assert not any(".." in Path(value).parts for value in all_strings)


def test_manifest_marks_stale_when_journal_is_newer_than_index(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_journal(
        data_dir,
        date="2026-07-01",
        title="Fresh Journal",
        extra_frontmatter='topic: ["freshness"]',
    )
    index_path = data_dir / "Journals" / "2026" / "07" / "index_2026-07.md"
    _seed_index(
        index_path,
        [
            "year: 2026",
            "month: 7",
            "entries: 1",
            "topics: {freshness: 1}",
            'date_range: "2026-07"',
        ],
    )
    old_mtime = time.time() - 3600
    os.utime(index_path, (old_mtime, old_mtime))

    result = _run_manifest(data_dir, "--level", "month")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["nodes"][0]["node_id"] == "month:2026-07"
    assert payload["nodes"][0]["freshness"] == "stale"


def test_manifest_degrades_malformed_frontmatter_to_empty_signals(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    journal_dir = data_dir / "Journals" / "2026" / "08"
    journal_dir.mkdir(parents=True, exist_ok=True)
    malformed = journal_dir / "life-index_2026-08-01_001.md"
    malformed.write_text(
        "---\ntitle: Broken\ntopic: [unterminated\n---\n\n# Broken\n",
        encoding="utf-8",
    )
    no_frontmatter = journal_dir / "life-index_2026-08-02_001.md"
    no_frontmatter.write_text("# No frontmatter\n", encoding="utf-8")
    _seed_index(
        journal_dir / "index_2026-08.md",
        [
            "year: 2026",
            "month: 8",
            "entries: 2",
            'date_range: "2026-08"',
        ],
    )

    result = _run_manifest(data_dir, "--level", "month")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["nodes"][0]["entry_refs"] == [
        "Journals/2026/08/life-index_2026-08-01_001.md",
        "Journals/2026/08/life-index_2026-08-02_001.md",
    ]
    assert payload["nodes"][0]["frontmatter_signals"] == {
        "topic_counts": {},
        "people_counts": {},
        "project_counts": {},
    }


def test_manifest_module_avoids_public_surface_and_llm_dependencies() -> None:
    source_path = Path("tools/dev/index_tree_evidence_manifest.py")
    source = source_path.read_text(encoding="utf-8")

    forbidden_tokens = [
        "tools.__main__",
        "docs/API.md",
        "pyproject.toml",
        "bootstrap-manifest.json",
        "tools.search_journals",
        "openai",
        "anthropic",
        "sentence_transformers",
        "embedding",
        "requests",
        "httpx",
        "urllib",
    ]
    for token in forbidden_tokens:
        assert token not in source
