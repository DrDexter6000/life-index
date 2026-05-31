#!/usr/bin/env python3
"""Tests for Index Tree Search Shadow Mode diagnostics."""

from __future__ import annotations

import os
import time
from pathlib import Path


def _write_journal(
    data_dir: Path,
    *,
    date: str,
    title: str,
    seq: str = "001",
    extra_frontmatter: str = "",
) -> Path:
    year, month, _day = date.split("-")
    journal_dir = data_dir / "Journals" / year / month
    journal_dir.mkdir(parents=True, exist_ok=True)
    path = journal_dir / f"life-index_{date}_{seq}.md"
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


def test_shadow_candidate_set_contains_baseline_hits(tmp_path: Path, monkeypatch) -> None:
    from tools.index_tree.core import build_shadow_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    first = _write_journal(
        data_dir,
        date="2026-03-14",
        title="Alpha Work",
        extra_frontmatter='topic: ["work"]',
    )
    _write_journal(
        data_dir,
        date="2026-04-01",
        title="Beta Life",
        extra_frontmatter='topic: ["life"]',
    )
    _write_index(
        data_dir / "Journals" / "2026" / "03" / "index_2026-03.md",
        ["entries: 1", "topics: {work: 1}", 'date_range: "2026-03"'],
    )
    _write_index(
        data_dir / "Journals" / "2026" / "04" / "index_2026-04.md",
        ["entries: 1", "topics: {life: 1}", 'date_range: "2026-04"'],
    )

    payload = build_shadow_payload("Alpha")

    rel_first = first.relative_to(data_dir).as_posix()
    data = payload["data"]
    assert payload["success"] is True
    assert payload["command"] == "index-tree.shadow"
    assert data["enabled"] is True
    assert data["diagnostic_only"] is True
    assert data["baseline_paths"] == [rel_first]
    assert set(data["baseline_paths"]) <= set(data["shadow_candidate_paths"])
    assert data["recall_preserved"] is True
    assert data["dropped_paths"] == []
    assert data["default_search_mutated"] is False
    assert data["default_smart_search_mutated"] is False


def test_shadow_gate_fails_when_candidate_drops_relevant_hit(tmp_path: Path, monkeypatch) -> None:
    from tools.index_tree.core import build_shadow_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    first = _write_journal(
        data_dir,
        date="2026-05-01",
        title="Alpha Drop",
        extra_frontmatter='topic: ["work"]',
    )
    _write_index(
        data_dir / "Journals" / "2026" / "05" / "index_2026-05.md",
        ["entries: 1", "topics: {work: 1}", 'date_range: "2026-05"'],
    )

    payload = build_shadow_payload("Alpha", candidate_filter=lambda _paths: [])

    rel_first = first.relative_to(data_dir).as_posix()
    assert payload["data"]["recall_preserved"] is False
    assert payload["data"]["dropped_paths"] == [rel_first]


def test_shadow_disables_on_stale_index(tmp_path: Path, monkeypatch) -> None:
    from tools.index_tree.core import build_shadow_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_journal(
        data_dir,
        date="2026-06-01",
        title="Alpha Stale",
        extra_frontmatter='topic: ["work"]',
    )
    index_path = data_dir / "Journals" / "2026" / "06" / "index_2026-06.md"
    _write_index(
        index_path,
        ["entries: 1", "topics: {work: 1}", 'date_range: "2026-06"'],
    )
    old_mtime = time.time() - 3600
    os.utime(index_path, (old_mtime, old_mtime))

    payload = build_shadow_payload("Alpha")

    data = payload["data"]
    assert data["enabled"] is False
    assert data["disabled_reason"] == "index_tree_not_fresh"
    assert data["recall_preserved"] is None
    assert data["shadow_candidate_paths"] == []
    assert data["freshness_issues"][0]["freshness"] == "stale"


def test_shadow_does_not_mutate_default_search_or_smart_search_modules() -> None:
    search_source = Path("tools/search_journals/__main__.py").read_text(encoding="utf-8")
    smart_source = Path("tools/smart_search/__main__.py").read_text(encoding="utf-8")

    assert "index_tree" not in search_source
    assert "index_tree" not in smart_source
