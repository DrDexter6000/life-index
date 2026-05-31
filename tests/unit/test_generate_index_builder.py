#!/usr/bin/env python3
"""Tests for the shared deterministic Index Tree builder model."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _write_journal(
    data_dir: Path,
    *,
    date: str,
    title: str,
    seq: str = "001",
    extra_frontmatter: str = "",
    body: str = "Fixture body",
) -> Path:
    year, month, _day = date.split("-")
    journal_dir = data_dir / "Journals" / year / month
    journal_dir.mkdir(parents=True, exist_ok=True)
    path = journal_dir / f"life-index_{date}_{seq}.md"
    lines = ["---", f'title: "{title}"', f"date: {date}"]
    if extra_frontmatter:
        lines.extend(extra_frontmatter.rstrip().splitlines())
    lines.extend(["---", "", f"# {title}", "", body])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_index(path: Path, frontmatter_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n# Index\n",
        encoding="utf-8",
    )


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


def test_builder_emits_stable_month_model_from_journals(tmp_path: Path, monkeypatch) -> None:
    from tools.generate_index.builder import build_index_tree_model

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    first = _write_journal(
        data_dir,
        date="2026-03-14",
        title="Builder Walk",
        extra_frontmatter=(
            'topic: ["work", "research"]\n' 'people: ["Alice"]\n' 'project: "Life Index"'
        ),
    )
    second = _write_journal(
        data_dir,
        date="2026-03-15",
        title="Second Walk",
        seq="002",
        extra_frontmatter=('topic: ["work"]\npeople: ["Bob"]\nproject: "Life Index"'),
    )
    _write_index(
        data_dir / "Journals" / "2026" / "03" / "index_2026-03.md",
        [
            "entries: 2",
            "topics: {work: 2, research: 1}",
            'date_range: "2026-03"',
        ],
    )

    model = build_index_tree_model(level="month")

    assert model["source"] == {"truth_source": "journals", "builder": "deterministic"}
    assert len(model["nodes"]) == 1
    node = model["nodes"][0]
    assert node["node_id"] == "month:2026-03"
    assert node["relative_path"] == "Journals/2026/03/index_2026-03.md"
    assert node["entry_count"] == 2
    assert node["freshness"] == "fresh"
    assert [entry["relative_path"] for entry in node["entry_refs"]] == [
        first.relative_to(data_dir).as_posix(),
        second.relative_to(data_dir).as_posix(),
    ]
    assert node["frontmatter_signals"]["topic_counts"] == {"work": 2, "research": 1}
    assert node["frontmatter_signals"]["people_counts"] == {"Alice": 1, "Bob": 1}
    assert node["frontmatter_signals"]["project_counts"] == {"Life Index": 2}
    assert node["signal_coverage"]["topic"] == {
        "entries_in_scope": 2,
        "present": 2,
        "parseable": 2,
    }


def test_builder_omits_absolute_paths(tmp_path: Path, monkeypatch) -> None:
    from tools.generate_index.builder import build_index_tree_model

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_journal(
        data_dir,
        date="2026-04-01",
        title="Private",
        extra_frontmatter='topic: ["privacy"]',
    )

    model = build_index_tree_model(level="all")

    strings = _all_strings(model)
    assert str(data_dir) not in strings
    assert not any(Path(value).is_absolute() for value in strings)


def test_builder_degrades_malformed_frontmatter(tmp_path: Path, monkeypatch) -> None:
    from tools.generate_index.builder import build_index_tree_model

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    journal_dir = data_dir / "Journals" / "2026" / "05"
    journal_dir.mkdir(parents=True)
    (journal_dir / "life-index_2026-05-01_001.md").write_text(
        "---\ntitle: Broken\ntopic: [unterminated\n---\n\n# Broken\n",
        encoding="utf-8",
    )
    _write_index(
        journal_dir / "index_2026-05.md",
        ["entries: 1", 'date_range: "2026-05"'],
    )

    model = build_index_tree_model(level="month")

    node = model["nodes"][0]
    assert node["entry_refs"][0]["relative_path"] == (
        "Journals/2026/05/life-index_2026-05-01_001.md"
    )
    assert node["frontmatter_signals"] == {
        "topic_counts": {},
        "people_counts": {},
        "project_counts": {},
    }
    assert node["signal_coverage"]["topic"] == {
        "entries_in_scope": 1,
        "present": 0,
        "parseable": 0,
    }
