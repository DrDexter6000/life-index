#!/usr/bin/env python3
"""Tests for public Index Tree derived lenses."""

from __future__ import annotations

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
    lines.extend(["---", "", f"# {title}", "", "Fixture body"])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_index(path: Path, frontmatter_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n# Index\n",
        encoding="utf-8",
    )


def test_topic_lens_is_evidence_backed_with_coverage(tmp_path: Path, monkeypatch) -> None:
    from tools.index_tree.core import build_lens_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    first = _write_journal(
        data_dir,
        date="2026-03-14",
        title="Lens Work",
        extra_frontmatter='topic: ["work", "research"]\npeople: ["Alice"]',
    )
    second = _write_journal(
        data_dir,
        date="2026-04-01",
        title="Lens Life",
        extra_frontmatter='topic: ["life"]\npeople: ["Alice"]',
    )
    _write_index(
        data_dir / "Journals" / "2026" / "03" / "index_2026-03.md",
        ["entries: 1", "topics: {work: 1, research: 1}", 'date_range: "2026-03"'],
    )
    _write_index(
        data_dir / "Journals" / "2026" / "04" / "index_2026-04.md",
        ["entries: 1", "topics: {life: 1}", 'date_range: "2026-04"'],
    )

    payload = build_lens_payload("topic")

    assert payload["success"] is True
    assert payload["schema_version"] == "m31.index_tree.v1"
    assert payload["command"] == "index-tree.lens"
    assert payload["errors"] == []
    assert payload["data"]["signal"] == "topic"
    assert payload["data"]["privacy_level"] == "same_as_journals"
    assert payload["data"]["truth_source"] == "journals"
    assert payload["data"]["coverage"] == {
        "entries_in_scope": 2,
        "present": 2,
        "parseable": 2,
    }
    by_value = {item["value"]: item for item in payload["data"]["items"]}
    assert by_value["work"]["count"] == 1
    assert by_value["work"]["evidence_paths"] == [first.relative_to(data_dir).as_posix()]
    assert by_value["work"]["node_refs"] == [
        {
            "type": "month",
            "node_id": "month:2026-03",
            "id": "Journals/2026/03",
            "path": "Journals/2026/03/index_2026-03.md",
        }
    ]
    assert by_value["life"]["evidence_paths"] == [second.relative_to(data_dir).as_posix()]


def test_lens_rejects_non_allowlisted_signal(tmp_path: Path, monkeypatch) -> None:
    from tools.index_tree.core import build_lens_payload

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path / "Life-Index"))

    payload = build_lens_payload("mood")

    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["errors"][0]["code"] == "INDEX_TREE_INVALID_SIGNAL"


def test_lens_degrades_missing_frontmatter_to_partial_coverage(tmp_path: Path, monkeypatch) -> None:
    from tools.index_tree.core import build_lens_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_journal(
        data_dir,
        date="2026-05-01",
        title="Covered",
        extra_frontmatter='project: "Life Index"',
    )
    journal_dir = data_dir / "Journals" / "2026" / "05"
    (journal_dir / "life-index_2026-05-02_001.md").write_text(
        "# No frontmatter\n",
        encoding="utf-8",
    )
    _write_index(
        journal_dir / "index_2026-05.md",
        ["entries: 2", 'date_range: "2026-05"'],
    )

    payload = build_lens_payload("project")

    assert payload["success"] is True
    assert payload["data"]["coverage"] == {
        "entries_in_scope": 2,
        "present": 1,
        "parseable": 1,
    }
    assert payload["data"]["items"][0]["value"] == "Life Index"
