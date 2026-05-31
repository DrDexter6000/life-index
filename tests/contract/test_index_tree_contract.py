#!/usr/bin/env python3
"""Contract tests for the public index-tree CLI surface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _write_journal(
    data_dir: Path,
    *,
    date: str,
    title: str,
    extra_frontmatter: str = "",
) -> Path:
    year, month, _day = date.split("-")
    journal_dir = data_dir / "Journals" / year / month
    journal_dir.mkdir(parents=True, exist_ok=True)
    path = journal_dir / f"life-index_{date}_001.md"
    lines = ["---", f'title: "{title}"', f"date: {date}"]
    if extra_frontmatter:
        lines.extend(extra_frontmatter.rstrip().splitlines())
    lines.extend(["---", "", f"# {title}", "", "alpha body marker"])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_index(path: Path, frontmatter_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n# Index\n",
        encoding="utf-8",
    )


def _seed_data(data_dir: Path) -> Path:
    journal = _write_journal(
        data_dir,
        date="2026-03-14",
        title="Alpha Work",
        extra_frontmatter='topic: ["work"]\npeople: ["Alice"]\nproject: "Life Index"',
    )
    _write_index(
        data_dir / "Journals" / "2026" / "03" / "index_2026-03.md",
        ["entries: 1", "topics: {work: 1}", 'date_range: "2026-03"'],
    )
    return journal


def _invoke(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        [sys.executable, "-m", "tools", "index-tree", *args],
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


def test_nodes_json_contract(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_data(data_dir)

    result = _invoke(data_dir, "nodes", "--level", "month", "--json")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["success"] is True
    assert payload["schema_version"] == "m31.index_tree.v1"
    assert payload["command"] == "index-tree.nodes"
    node = payload["data"]["nodes"][0]
    assert node["node_id"] == "month:2026-03"
    assert node["relative_path"] == "Journals/2026/03/index_2026-03.md"
    assert str(data_dir) not in _all_strings(payload)


def test_lens_json_contract(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    journal = _seed_data(data_dir)

    result = _invoke(data_dir, "lens", "--signal", "topic", "--json")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["command"] == "index-tree.lens"
    assert payload["data"]["signal"] == "topic"
    assert payload["data"]["items"][0]["value"] == "work"
    assert payload["data"]["items"][0]["evidence_paths"] == [
        journal.relative_to(data_dir).as_posix()
    ]


def test_shadow_json_contract(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_data(data_dir)

    result = _invoke(data_dir, "shadow", "--query", "Alpha", "--json")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["command"] == "index-tree.shadow"
    assert payload["data"]["diagnostic_only"] is True
    assert payload["data"]["recall_preserved"] is True


def test_lens_invalid_signal_returns_structured_error(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_data(data_dir)

    result = _invoke(data_dir, "lens", "--signal", "mood", "--json")

    assert result.returncode != 0
    payload = _payload(result)
    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "INDEX_TREE_INVALID_SIGNAL"


def test_main_help_includes_index_tree() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "index-tree" in result.stdout
