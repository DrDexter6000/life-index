#!/usr/bin/env python3
"""Contract tests for the public journal read CLI surface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "m16.journal.v1"


def _run_journal(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        [sys.executable, "-m", "tools", "journal", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        encoding="utf-8",
    )


def _run_journal_with_env(
    data_dir: Path, extra_env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "tools", "journal", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        encoding="utf-8",
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
    # v1: the file stores no id, so `id` is null — never the path.
    assert data["id"] is None
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


def test_get_by_path_shaped_id_resolves_as_path(tmp_path: Path) -> None:
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
    assert payload["data"]["rel_path"] == rel_path
    assert payload["data"]["id"] is None


def test_batch_get_returns_multiple_journals_with_one_validation_log_record(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "Life-Index"
    log_path = tmp_path / "tool-calls.jsonl"
    first = _seed_journal(
        data_dir,
        date="2026-05-28",
        title="First Batch Entry",
        body="# First Batch Entry\n\nFirst body.",
    )
    second = _seed_journal(
        data_dir,
        date="2026-05-29",
        title="Second Batch Entry",
        body="# Second Batch Entry\n\nSecond body.",
    )
    first_rel = _rel(first, data_dir)
    second_rel = _rel(second, data_dir)

    result = _run_journal_with_env(
        data_dir,
        {
            "LIFE_INDEX_VALIDATION_MODE": "1",
            "LIFE_INDEX_TOOL_CALL_LOG": str(log_path),
        },
        "batch-get",
        "--path",
        first_rel,
        "--path",
        second_rel,
        "--json",
    )

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["success"] is True
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["error"] is None
    assert payload["data"]["total_requested"] == 2
    assert payload["data"]["total_found"] == 2
    assert [item["rel_path"] for item in payload["data"]["items"]] == [
        first_rel,
        second_rel,
    ]
    assert payload["data"]["items"][0]["content"] == "# First Batch Entry\n\nFirst body."

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["tool"] == "journal batch-get"
    assert records[0]["params"] == {"paths": [first_rel, second_rel], "ids": []}
    assert records[0]["result"] == {
        "total_requested": 2,
        "total_found": 2,
        "rel_paths": [first_rel, second_rel],
    }
    assert str(data_dir) not in json.dumps(records, ensure_ascii=False)


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


def test_get_cjk_continuous_text_counts_by_character_not_whitespace_split(
    tmp_path: Path,
) -> None:
    """Characterization: continuous CJK text must be counted per ideograph."""
    data_dir = tmp_path / "Life-Index"
    body = "今天天气很好我们去公园散步。"
    journal = _seed_journal(
        data_dir,
        date="2026-05-29",
        title="Chinese Entry",
        body=body,
    )
    rel_path = _rel(journal, data_dir)

    result = _run_journal(data_dir, "get", "--path", rel_path)

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    data = payload["data"]
    # Legacy whitespace split would return 1; CJK-aware should return 13.
    assert data["word_count"] == 13


def test_get_mixed_cjk_ascii_counts_cjk_by_char_and_ascii_by_word(
    tmp_path: Path,
) -> None:
    """Characterization: mixed CJK + ASCII must count each script correctly."""
    data_dir = tmp_path / "Life-Index"
    body = "Hello world 今天天气很好。"
    journal = _seed_journal(
        data_dir,
        date="2026-05-30",
        title="Mixed Entry",
        body=body,
    )
    rel_path = _rel(journal, data_dir)

    result = _run_journal(data_dir, "get", "--path", rel_path)

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    data = payload["data"]
    # Hello(1) world(2) 今(3) 天(4) 天(5) 气(6) 很(7) 好(8)
    assert data["word_count"] == 8


def test_list_recent_cjk_word_count_is_character_based(tmp_path: Path) -> None:
    """List summary must use CJK-aware word counts for mixed entries."""
    data_dir = tmp_path / "Life-Index"
    _seed_journal(
        data_dir,
        date="2026-05-29",
        title="Chinese Entry",
        body="今天天气很好我们去公园散步。",
    )

    result = _run_journal(data_dir, "list", "--recent", "--limit", "1")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    data = payload["data"]
    assert data["total_matches"] == 1
    assert data["items"][0]["word_count"] == 13


# ---------------------------------------------------------------------------
# v1 durable-id payload and selectors
# ---------------------------------------------------------------------------

_HEX_A = "a" * 32
_HEX_B = "b" * 32


def test_get_by_path_id_field_is_stored_null_or_value(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    with_id = _seed_journal(
        data_dir,
        date="2026-05-27",
        title="With Id",
        body="body one",
        extra_frontmatter=f"id: {_HEX_A}",
    )
    without_id = _seed_journal(
        data_dir,
        date="2026-05-28",
        title="Without Id",
        body="body two",
    )
    malformed = _seed_journal(
        data_dir,
        date="2026-05-29",
        title="Malformed Id",
        body="body three",
        extra_frontmatter="id: NOT-A-VALID-ID",
    )

    for path, expected_id in ((with_id, _HEX_A), (without_id, None), (malformed, None)):
        result = _run_journal(data_dir, "get", "--path", _rel(path, data_dir))
        assert result.returncode == 0, result.stdout
        payload = _payload(result)
        assert payload["schema_version"] == SCHEMA_VERSION
        assert payload["data"]["id"] == expected_id
        assert payload["data"]["rel_path"] == _rel(path, data_dir)


def test_get_by_durable_id_found_and_after_move(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    journal = _seed_journal(
        data_dir,
        date="2026-05-28",
        title="Movable",
        body="# Movable\n\nThe entry body.",
        extra_frontmatter=f"id: {_HEX_A}",
    )

    result = _run_journal(data_dir, "get", "--id", _HEX_A)
    assert result.returncode == 0, result.stdout
    payload = _payload(result)
    assert payload["data"]["id"] == _HEX_A
    assert payload["data"]["rel_path"] == _rel(journal, data_dir)
    assert payload["data"]["content"] == "# Movable\n\nThe entry body."
    assert "lookup" not in payload["data"]

    # A move plus a rename to a free canonical name must not break id lookup.
    new_dir = data_dir / "Journals" / "2026" / "06"
    new_dir.mkdir(parents=True)
    journal.rename(new_dir / "life-index_2026-06-01_007.md")

    moved = _run_journal(data_dir, "get", "--id", _HEX_A)
    assert moved.returncode == 0, moved.stdout
    moved_payload = _payload(moved)
    assert moved_payload["data"]["rel_path"] == "Journals/2026/06/life-index_2026-06-01_007.md"
    assert moved_payload["data"]["id"] == _HEX_A


def test_get_by_durable_id_not_found_ambiguous_and_invalid(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_journal(
        data_dir,
        date="2026-05-28",
        title="First Carrier",
        body="one",
        extra_frontmatter=f"id: {_HEX_A}",
    )
    _seed_journal(
        data_dir,
        date="2026-05-29",
        title="Second Carrier",
        body="two",
        extra_frontmatter=f"id: {_HEX_A}",
    )

    missing = _run_journal(data_dir, "get", "--id", _HEX_B)
    assert missing.returncode != 0
    missing_payload = _payload(missing)
    assert missing_payload["error"]["code"] == "JOURNAL_NOT_FOUND"

    ambiguous = _run_journal(data_dir, "get", "--id", _HEX_A)
    assert ambiguous.returncode != 0
    ambiguous_payload = _payload(ambiguous)
    assert ambiguous_payload["error"]["code"] == "JOURNAL_ID_AMBIGUOUS"
    assert sorted(ambiguous_payload["error"]["details"]["rel_paths"]) == [
        "Journals/2026/05/life-index_2026-05-28_001.md",
        "Journals/2026/05/life-index_2026-05-29_001.md",
    ]

    invalid = _run_journal(data_dir, "get", "--id", "not-an-id")
    assert invalid.returncode != 0
    assert _payload(invalid)["error"]["code"] == "JOURNAL_ARGUMENT_INVALID"


def test_get_by_id_with_unreadable_stray_file(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_journal(
        data_dir,
        date="2026-05-28",
        title="Readable",
        body="readable body",
        extra_frontmatter=f"id: {_HEX_A}",
    )
    stray = data_dir / "Journals" / "2026" / "05" / "life-index_2026-05-30_001.md"
    stray.write_bytes(b"\xff\xfe\xfd invalid utf8")

    found = _run_journal(data_dir, "get", "--id", _HEX_A)
    assert found.returncode == 0, found.stdout
    found_payload = _payload(found)
    assert found_payload["data"]["id"] == _HEX_A
    assert found_payload["data"]["lookup"] == {"unread_paths": 1}

    absent = _run_journal(data_dir, "get", "--id", _HEX_B)
    assert absent.returncode != 0
    absent_payload = _payload(absent)
    assert absent_payload["error"]["code"] == "JOURNAL_LOOKUP_INCOMPLETE"
    assert absent_payload["error"]["details"] == {"unread_paths": 1}


def test_batch_get_mixes_path_and_id_selectors_and_dedups_one_file(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    first = _seed_journal(
        data_dir,
        date="2026-05-28",
        title="First",
        body="first body",
        extra_frontmatter=f"id: {_HEX_A}",
    )
    second = _seed_journal(
        data_dir,
        date="2026-05-29",
        title="Second",
        body="second body",
        extra_frontmatter=f"id: {_HEX_B}",
    )

    result = _run_journal_with_env(
        data_dir,
        {},
        "batch-get",
        "--id",
        _HEX_B,
        "--path",
        _rel(first, data_dir),
        "--id",
        _HEX_A,  # same file as the --path selector: one item, first position kept
    )

    assert result.returncode == 0, result.stdout
    payload = _payload(result)
    assert payload["data"]["total_requested"] == 3
    assert payload["data"]["total_found"] == 2
    assert [item["rel_path"] for item in payload["data"]["items"]] == [
        _rel(first, data_dir),
        _rel(second, data_dir),
    ]
    assert [item["id"] for item in payload["data"]["items"]] == [_HEX_A, _HEX_B]


def test_batch_get_ambiguous_id_fails_the_whole_batch(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_journal(
        data_dir,
        date="2026-05-28",
        title="First Carrier",
        body="one",
        extra_frontmatter=f"id: {_HEX_A}",
    )
    _seed_journal(
        data_dir,
        date="2026-05-29",
        title="Second Carrier",
        body="two",
        extra_frontmatter=f"id: {_HEX_A}",
    )

    result = _run_journal_with_env(
        data_dir,
        {},
        "batch-get",
        "--path",
        "Journals/2026/05/life-index_2026-05-28_001.md",
        "--id",
        _HEX_A,
    )

    assert result.returncode != 0
    payload = _payload(result)
    assert payload["success"] is False
    assert payload["error"]["code"] == "JOURNAL_ID_AMBIGUOUS"


def test_list_items_carry_the_stored_id(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    _seed_journal(
        data_dir,
        date="2026-05-28",
        title="With Id",
        body="one",
        extra_frontmatter=f"id: {_HEX_A}",
    )
    _seed_journal(
        data_dir,
        date="2026-05-27",
        title="Without Id",
        body="two",
    )

    result = _run_journal(data_dir, "list", "--recent")

    assert result.returncode == 0, result.stdout
    data = _payload(result)["data"]
    assert data["total_matches"] == 2
    by_rel = {item["rel_path"]: item["id"] for item in data["items"]}
    assert by_rel["Journals/2026/05/life-index_2026-05-28_001.md"] == _HEX_A
    assert by_rel["Journals/2026/05/life-index_2026-05-27_001.md"] is None


def test_id_reads_and_list_leave_the_data_tree_identical(tmp_path: Path) -> None:
    from hashlib import sha256

    def snapshot(root: Path) -> dict[str, str]:
        snap: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            snap[f"{relative}/" if path.is_dir() else relative] = (
                "directory" if path.is_dir() else sha256(path.read_bytes()).hexdigest()
            )
        return snap

    data_dir = tmp_path / "Life-Index"
    _seed_journal(
        data_dir,
        date="2026-05-28",
        title="One",
        body="one",
        extra_frontmatter=f"id: {_HEX_A}",
    )
    _seed_journal(
        data_dir,
        date="2026-05-29",
        title="Two",
        body="two",
        extra_frontmatter=f"id: {_HEX_B}",
    )
    before = snapshot(data_dir)

    for args in (
        ("get", "--id", _HEX_A),
        ("batch-get", "--id", _HEX_A, "--id", _HEX_B),
        ("batch-get", "--id", _HEX_A, "--path", "Journals/2026/05/life-index_2026-05-29_001.md"),
        ("list", "--recent"),
    ):
        result = _run_journal_with_env(data_dir, {}, *args)
        assert result.returncode == 0, f"{args}: {result.stdout}\n{result.stderr}"

    assert snapshot(data_dir) == before


def test_batch_get_path_values_keep_path_handling(tmp_path: Path) -> None:
    """`--path` selectors resolve as paths exactly as before this package."""
    data_dir = tmp_path / "Life-Index"
    journal = _seed_journal(
        data_dir,
        date="2026-05-28",
        title="Path Handling",
        body="body",
        extra_frontmatter=f"id: {_HEX_A}",
    )
    rel_path = _rel(journal, data_dir)

    backslashed = rel_path.replace("/", "\\")
    result = _run_journal(data_dir, "batch-get", "--path", backslashed)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    payload = _payload(result)
    assert payload["success"] is True
    assert payload["data"]["items"][0]["rel_path"] == rel_path

    invalid = _run_journal(data_dir, "batch-get", "--path", "../secret.md")
    assert invalid.returncode != 0
    assert _payload(invalid)["error"]["code"] == "JOURNAL_PATH_INVALID"


def test_id_whitespace_rule_is_the_same_in_get_and_batch_get(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    journal = _seed_journal(
        data_dir,
        date="2026-05-28",
        title="Padded Id",
        body="body",
        extra_frontmatter=f"id: {_HEX_A}",
    )
    rel_path = _rel(journal, data_dir)

    got = _run_journal(data_dir, "get", "--id", f"  {_HEX_A}  ")
    assert got.returncode == 0, f"stdout: {got.stdout}\nstderr: {got.stderr}"
    payload = _payload(got)
    assert payload["data"]["id"] == _HEX_A
    assert payload["data"]["rel_path"] == rel_path

    batched = _run_journal(data_dir, "batch-get", "--id", f"  {_HEX_A}  ")
    assert batched.returncode == 0, f"stdout: {batched.stdout}\nstderr: {batched.stderr}"
    batch_payload = _payload(batched)
    assert batch_payload["data"]["items"][0]["id"] == _HEX_A
