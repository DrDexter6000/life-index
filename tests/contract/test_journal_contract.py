#!/usr/bin/env python3
"""Contract tests for the public journal read CLI surface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "m16.journal.v0"


def _run_journal(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        [sys.executable, "-m", "tools", "journal", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


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


def _rel(path: Path, data_dir: Path) -> str:
    return path.relative_to(data_dir).as_posix()


def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return json.loads(result.stdout)


def test_get_by_path_returns_content_metadata_attachments_and_word_count(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "Life-Index"
    body = "# First Entry\n\nThis is a small test entry."
    journal = _seed_journal(
        data_dir,
        date="2026-05-27",
        title="First Entry",
        body=body,
        extra_frontmatter=(
            'topic: ["work"]\n'
            'attachments: [{"rel_path": "../../../attachments/2026/05/photo.png", '
            '"description": "photo", "content_type": "image/png", "size": 123}]'
        ),
    )
    rel_path = _rel(journal, data_dir)

    result = _run_journal(data_dir, "get", "--path", rel_path)

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["success"] is True
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["error"] is None

    data = payload["data"]
    assert data["rel_path"] == rel_path
    assert data["id"] == rel_path
    assert data["metadata"]["title"] == "First Entry"
    assert data["metadata"]["date"] == "2026-05-27"
    assert data["content"] == body
    assert data["word_count"] == len(body.split())
    assert data["attachments"] == [
        {
            "raw_path": "../../../attachments/2026/05/photo.png",
            "path": "../../../attachments/2026/05/photo.png",
            "name": "photo.png",
            "description": "photo",
            "source_url": None,
            "content_type": "image/png",
            "size": 123,
        }
    ]


def test_get_by_id_uses_current_rel_path_identity(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    journal = _seed_journal(
        data_dir,
        date="2026-05-28",
        title="ID Entry",
        body="# ID Entry\n\nIdentity test.",
    )
    rel_path = _rel(journal, data_dir)

    result = _run_journal(data_dir, "get", "--id", rel_path)

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["success"] is True
    assert payload["data"]["id"] == rel_path
    assert payload["data"]["rel_path"] == rel_path


def test_get_rejects_path_traversal_as_json_error(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)

    result = _run_journal(data_dir, "get", "--path", "../secret.md")

    assert result.returncode != 0
    payload = _payload(result)
    assert payload["success"] is False
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["data"] is None
    assert payload["error"]["code"] == "JOURNAL_PATH_INVALID"


def test_get_reports_missing_journal_as_json_error(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"

    result = _run_journal(
        data_dir,
        "get",
        "--path",
        "Journals/2026/05/life-index_2026-05-28_001.md",
    )

    assert result.returncode != 0
    payload = _payload(result)
    assert payload["success"] is False
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["data"] is None
    assert payload["error"]["code"] == "JOURNAL_NOT_FOUND"


def test_list_recent_filters_generated_docs_and_sorts_descending(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    older = _seed_journal(
        data_dir,
        date="2026-05-26",
        title="Older Entry",
        body="# Older Entry\n\nOlder body.",
    )
    newer_001 = _seed_journal(
        data_dir,
        date="2026-05-28",
        seq="001",
        title="Newer Entry 1",
        body="# Newer Entry 1\n\nNewer body 1.",
    )
    newer_002 = _seed_journal(
        data_dir,
        date="2026-05-28",
        seq="002",
        title="Newer Entry 2",
        body="# Newer Entry 2\n\nNewer body 2.",
    )
    generated = data_dir / "Journals" / "2026" / "05" / "INDEX.md"
    generated.write_text("# Generated index\n", encoding="utf-8")
    by_topic = data_dir / "by-topic" / "topic_work.md"
    by_topic.parent.mkdir(parents=True, exist_ok=True)
    by_topic.write_text("# Topic index\n", encoding="utf-8")
    non_journal = data_dir / "Journals" / "2026" / "05" / "notes.md"
    non_journal.write_text("# Notes\n", encoding="utf-8")

    result = _run_journal(data_dir, "list", "--recent", "--limit", "2")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["success"] is True
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["error"] is None

    data = payload["data"]
    assert data["total_matches"] == 3
    assert data["total_found"] == 2
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert data["has_more"] is True
    assert [item["rel_path"] for item in data["items"]] == [
        _rel(newer_002, data_dir),
        _rel(newer_001, data_dir),
    ]
    assert _rel(older, data_dir) not in [item["rel_path"] for item in data["items"]]


def test_list_recent_supports_offset_pagination(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    first = _seed_journal(
        data_dir,
        date="2026-05-28",
        seq="002",
        title="First",
        body="# First\n\nFirst body.",
    )
    second = _seed_journal(
        data_dir,
        date="2026-05-28",
        seq="001",
        title="Second",
        body="# Second\n\nSecond body.",
    )

    result = _run_journal(
        data_dir,
        "list",
        "--recent",
        "--limit",
        "1",
        "--offset",
        "1",
    )

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    data = payload["data"]
    assert data["total_matches"] == 2
    assert data["total_found"] == 1
    assert data["has_more"] is False
    assert [item["rel_path"] for item in data["items"]] == [_rel(second, data_dir)]
    assert _rel(first, data_dir) not in [item["rel_path"] for item in data["items"]]


def test_list_recent_empty_archive_is_success(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"

    result = _run_journal(data_dir, "list", "--recent")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["success"] is True
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["data"]["items"] == []
    assert payload["data"]["total_matches"] == 0
    assert payload["data"]["total_found"] == 0
    assert payload["data"]["has_more"] is False
    assert payload["error"] is None
