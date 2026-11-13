#!/usr/bin/env python3
"""Contract tests for the journal frontmatter written by ``import run``.

The legacy ``import run --plan … --confirm …`` route owns durable journal
writes.  Its journal text must come from the shared ``format_frontmatter``
serializer so that every plan value (title, topic, tags, content) survives a
parse round-trip, and so an imported journal carries the same canonical
frontmatter fields as a journal written by the write tool.

The compatibility test plants a journal plus ledger/manifest in the *old*
hand-built byte format and proves the new code still recognises it, reports
it, makes it searchable, and rolls it back.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tools.lib.frontmatter import format_frontmatter, parse_frontmatter

ROOT = Path(__file__).resolve().parents[2]
LEDGER_REL_PATH = ".life-index/import-jobs/ledger.json"
LEDGER_SCHEMA_VERSION = "import_job_ledger.v1"
ROLLBACK_MANIFEST_SCHEMA_VERSION = "import_rollback_manifest.v1"


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def _run_tool(data_dir: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m tools ...`` with an isolated data directory."""
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "tools", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=timeout,
    )


def _run_import(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run_tool(data_dir, "import", *args)


def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise AssertionError(
            f"Expected JSON on stdout but got non-JSON output.\n"
            f"stdout[:1000]: {result.stdout[:1000]}\n"
            f"stderr[:1000]: {result.stderr[:1000]}"
        ) from None


def _ok_payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert result.returncode == 0, (
        f"command failed with {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    payload = _payload(result)
    assert payload["success"] is True, payload
    return payload


# ---------------------------------------------------------------------------
# Plan helpers
# ---------------------------------------------------------------------------


def _record(
    index: int,
    title: str,
    topic: str,
    tags: list[str],
    content: str,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one fixture-adapter record with a unique date (and target path)."""
    source_record_id = f"src_frontmatter_{index:03d}"
    record: dict[str, Any] = {
        "source_record_id": source_record_id,
        "source_record_fingerprint": "sha256:"
        + hashlib.sha256(source_record_id.encode("utf-8")).hexdigest(),
        "journal": {
            "title": title,
            "date": f"2026-07-{index:02d}",
            "topic": topic,
            "tags": tags,
            "content": content,
        },
    }
    if attachments:
        record["attachments"] = attachments
    return record


def _write_plan(
    data_dir: Path,
    tmp_path: Path,
    records: list[dict[str, Any]],
    *,
    source_name: str = "source.json",
) -> tuple[dict[str, Any], Path]:
    """Run ``import plan`` and persist the returned plan for ``import run``."""
    source = {
        "adapter_id": "fixture.import_records",
        "adapter_version": "v1",
        "input_label": "frontmatter-contract",
        "records": records,
    }
    source_path = tmp_path / source_name
    source_path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")

    plan_result = _run_import(
        data_dir,
        "plan",
        "--source",
        "fixture.import_records",
        "--input",
        str(source_path),
        "--json",
    )
    plan_payload = _ok_payload(plan_result)
    assert plan_payload["data"]["dry_run"] is True
    plan = plan_payload["data"]

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return plan, plan_path


def _run_plan(data_dir: Path, plan: dict[str, Any], plan_path: Path) -> dict[str, Any]:
    run_result = _run_import(
        data_dir,
        "run",
        "--plan",
        str(plan_path),
        "--confirm",
        plan["import_id"],
        "--json",
    )
    return _ok_payload(run_result)["data"]


def _publish(
    data_dir: Path, tmp_path: Path, records: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan, plan_path = _write_plan(data_dir, tmp_path, records)
    return plan, _run_plan(data_dir, plan, plan_path)


def _journal_path(data_dir: Path, plan: dict[str, Any], index: int = 0) -> Path:
    return data_dir / plan["proposals"][index]["journal"]["target_rel_path"]


# ---------------------------------------------------------------------------
# Values YAML treats specially, across title / topic / tags / content
# ---------------------------------------------------------------------------

SPECIAL_VALUE_CASES = [
    ("double_quote", 'He said "hi"', 'topic "quoted"', ['tag "quoted"'], 'Body says "hi".'),
    ("single_quote", "It's fine", "it's", ["it's"], "It's a body."),
    ("backslash", r"path C:\temp\new", r"topic\path", [r"tag\slash"], r"body\slash"),
    ("colon_space", "Title: subtitle", "topic: value", ["tag: value"], "body: value"),
    ("comma", "Comma, title", "a, b", ["a, b"], "Comma, body."),
    ("leading_hash", "# heading", "#topic", ["#tag"], "# body heading"),
    ("leading_dash", "- item", "-topic", ["-tag"], "- body item"),
    ("padded", "  padded title  ", "  padded topic  ", ["  padded tag  "], "padded body"),
    (
        "title_newline",
        "line one\nline two",
        "line\nbreak",
        ["tag\nbreak"],
        "line one\nline two",
    ),
    ("content_delimiter", "Delimiter body", "work", ["delimiter"], "before\n---\nafter"),
    ("content_quotes", "Quoted body", "work", ["quotes"], 'a "quote", a \\slash, a: colon'),
    ("cjk", "今天心情不错", "生活", ["生活"], "今天心情不错。"),
    ("emoji", "Mood 😀🎉", "mood😀", ["emoji🎉"], "Emoji 😀"),
    ("empty_title", "", "imported", ["imported"], "Body without a title."),
    ("number_title", "12345", "123", ["123"], "Number title."),
    ("date_title", "2026-03-07", "2026-03-07", ["2026-03-07"], "Date title."),
    ("boolean_title", "true", "false", ["true", "false"], "Boolean title."),
]


@pytest.mark.parametrize(
    "case_id,title,topic,tags,content",
    SPECIAL_VALUE_CASES,
    ids=[case_id for case_id, *_values in SPECIAL_VALUE_CASES],
)
def test_import_publish_roundtrips_plan_values(
    tmp_path: Path,
    case_id: str,
    title: str,
    topic: str,
    tags: list[str],
    content: str,
) -> None:
    """Every plan value survives ``parse_frontmatter`` after publish."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)

    plan, run = _publish(data_dir, tmp_path, [_record(1, title, topic, tags, content)])
    assert run["state"] == "committed"
    assert run["created_journal_count"] == 1

    plan_journal = plan["proposals"][0]["journal"]
    journal_path = _journal_path(data_dir, plan)
    parsed, body = parse_frontmatter(journal_path.read_text(encoding="utf-8"))

    # Same canonical frontmatter fields the write tool emits.
    assert parsed["schema_version"] == 3
    assert isinstance(parsed["title"], str)
    assert parsed["title"] == title, f"{case_id}: title did not round-trip"
    assert isinstance(parsed["date"], str)
    assert parsed["date"] == plan_journal["date"]
    assert isinstance(parsed["tags"], list)
    assert parsed["tags"] == tags, f"{case_id}: tags did not round-trip"
    # ``topic`` is a canonical string array in journals; the plan carries the
    # scalar, so the serializer's normalisation is the expected published form.
    assert isinstance(parsed["topic"], list)
    assert parsed["topic"] == [topic], f"{case_id}: topic did not round-trip"
    assert body == content, f"{case_id}: body changed"
    assert set(parsed) == {"schema_version", "title", "date", "tags", "topic"}


def test_import_publish_plain_bytes_use_shared_serializer(tmp_path: Path) -> None:
    """A plain import writes exactly the shared serializer's canonical bytes."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)

    plan, run = _publish(
        data_dir,
        tmp_path,
        [_record(1, "Plain title", "imported", ["imported"], "Plain body.")],
    )
    assert run["state"] == "committed"

    expected = (
        "---\n"
        "schema_version: 3\n"
        'title: "Plain title"\n'
        "date: 2026-07-01\n"
        'tags: ["imported"]\n'
        'topic: ["imported"]\n'
        "---\n\n"
        "Plain body.\n"
    )
    assert _journal_path(data_dir, plan).read_text(encoding="utf-8") == expected


def test_import_publish_escapes_double_quote_bytes(tmp_path: Path) -> None:
    """A double quote is backslash-escaped, keeping the YAML parsable."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)

    plan, run = _publish(
        data_dir,
        tmp_path,
        [_record(1, 'He said "hi"', "imported", ["imported"], "Quote body.")],
    )
    assert run["state"] == "committed"

    expected = (
        "---\n"
        "schema_version: 3\n"
        'title: "He said \\"hi\\""\n'
        "date: 2026-07-01\n"
        'tags: ["imported"]\n'
        'topic: ["imported"]\n'
        "---\n\n"
        "Quote body.\n"
    )
    journal_path = _journal_path(data_dir, plan)
    assert journal_path.read_text(encoding="utf-8") == expected

    parsed, body = parse_frontmatter(journal_path.read_text(encoding="utf-8"))
    assert parsed["title"] == 'He said "hi"'
    assert body == "Quote body."


def test_import_plan_journal_preview_matches_published_frontmatter(tmp_path: Path) -> None:
    """The plan's journal projection serialises to the published frontmatter."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)

    record = _record(1, 'Preview "quote"', "topic: value", ["tag: value"], "before\n---\nafter")
    plan, plan_path = _write_plan(data_dir, tmp_path, [record])

    projected = plan["proposals"][0]["journal"]
    preview_text = (
        format_frontmatter(
            {
                "title": projected["title"],
                "date": projected["date"],
                "topic": projected["topic"],
                "tags": projected["tags"],
            }
        )
        + "\n\n"
        + projected["content"]
        + "\n"
    )
    preview_meta, preview_body = parse_frontmatter(preview_text)

    run = _run_plan(data_dir, plan, plan_path)
    assert run["state"] == "committed"

    published_meta, published_body = parse_frontmatter(
        _journal_path(data_dir, plan).read_text(encoding="utf-8")
    )
    assert published_meta == preview_meta
    assert published_body == preview_body


def test_import_published_special_values_are_searchable(tmp_path: Path) -> None:
    """A journal whose title contains YAML-special characters is searchable."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)

    unique_token = "frontmattersearchtoken"
    record = _record(
        1,
        f'He said "hi" {unique_token}',
        "imported",
        ["imported"],
        "Body with CJK 今天 and emoji 😀.",
    )
    _plan, run = _publish(data_dir, tmp_path, [record])
    assert run["state"] == "committed"

    index_result = _run_tool(data_dir, "index", "--json")
    assert _ok_payload(index_result)["success"] is True

    search_result = _run_tool(data_dir, "search", "--query", unique_token, "--limit", "0")
    search_payload = _ok_payload(search_result)
    assert search_payload["total_matches"] >= 1, (
        "published journal was not indexed/searchable: " f"{search_payload}"
    )


def test_import_rollback_removes_special_value_journal(tmp_path: Path) -> None:
    """Rollback removes exactly the special-value journal + attachment it made."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)

    attachment = {
        "attachment_id": "att_frontmatter_001",
        "source_ref": "source://fixture/frontmatter.bin",
        "source_sha256": "sha256:" + "c" * 64,
        "target_rel_path": "attachments/2026/07/frontmatter.bin",
        "media_type": "application/octet-stream",
        "size_bytes": 4,
        "copy_mode": "copy",
    }
    record = _record(
        1,
        'He said "hi"',
        "topic: value",
        ["tag: value"],
        "before\n---\nafter",
        attachments=[attachment],
    )
    plan, run = _publish(data_dir, tmp_path, [record])
    assert run["state"] == "committed"
    assert {entry["kind"] for entry in run["created_files"]} == {"journal", "attachment"}

    journal_path = _journal_path(data_dir, plan)
    parsed, body = parse_frontmatter(journal_path.read_text(encoding="utf-8"))
    assert parsed["title"] == 'He said "hi"'
    assert body == "before\n---\nafter"

    attachment_path = data_dir / attachment["target_rel_path"]
    assert attachment_path.exists()

    # The rollback manifest records the bytes that were actually written.
    manifest = json.loads(
        (data_dir / run["rollback_manifest_rel_path"]).read_text(encoding="utf-8")
    )
    for entry in manifest["created_files"]:
        raw = (data_dir / entry["rel_path"]).read_bytes()
        assert entry["sha256_after"] == "sha256:" + hashlib.sha256(raw).hexdigest()
        assert entry["size_bytes"] == len(raw)

    sentinel = data_dir / "Journals" / "2026" / "07" / "sentinel.md"
    sentinel.write_text("keep me", encoding="utf-8")

    rollback_result = _run_import(data_dir, "rollback", "--import-id", plan["import_id"], "--json")
    rollback_data = _ok_payload(rollback_result)["data"]
    assert rollback_data["state"] == "rolled_back"
    assert rollback_data["deleted_count"] == 2
    assert not journal_path.exists()
    assert not attachment_path.exists()
    assert sentinel.read_text(encoding="utf-8") == "keep me"


# ---------------------------------------------------------------------------
# Backward compatibility: an import published by the old hand-built code
# ---------------------------------------------------------------------------


def _old_journal_text(title: str, date: str, topic: str, tags: list[str], content: str) -> str:
    """Reproduce the pre-fix ``execute_run`` bytes exactly (historical format)."""
    tags_yaml = json.dumps(tags)
    return (
        "---\n"
        f'title: "{title}"\n'
        f"date: {date}\n"
        f"topic: {topic}\n"
        f"tags: {tags_yaml}\n"
        "---\n\n"
        f"{content}\n"
    )


def _write_legacy_ledger_and_manifest(
    data_dir: Path,
    plan: dict[str, Any],
    journal_rel: str,
    attachment_rel: str,
) -> None:
    created_files = []
    for kind, rel_path in (("journal", journal_rel), ("attachment", attachment_rel)):
        raw = (data_dir / rel_path).read_bytes()
        created_files.append(
            {
                "kind": kind,
                "rel_path": rel_path,
                "sha256_after": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
                "created_by_import": True,
            }
        )

    manifest_rel = f".life-index/import-jobs/{plan['import_id']}/rollback-manifest.json"
    manifest_path = data_dir / manifest_rel
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": ROLLBACK_MANIFEST_SCHEMA_VERSION,
        "import_id": plan["import_id"],
        "idempotency_key": plan["idempotency_key"],
        "plan_fingerprint": plan["plan_fingerprint"],
        "created_at": "2026-01-01T00:00:00+00:00",
        "state": "committed",
        "created_files": created_files,
        "preexisting_files": [],
        "errors": [],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    ledger_path = data_dir / LEDGER_REL_PATH
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "jobs": {
            plan["import_id"]: {
                "state": "committed",
                "idempotency_key": plan["idempotency_key"],
                "plan_fingerprint": plan["plan_fingerprint"],
                "rollback_manifest_rel_path": manifest_rel,
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        },
        "idempotency_index": {plan["idempotency_key"]: plan["import_id"]},
    }
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def test_old_format_import_still_recognised_reviewed_and_rolled_back(
    tmp_path: Path,
) -> None:
    """Compatibility: old hand-built bytes remain visible to every import step."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)

    unique_token = "legacyoldformattoken"
    attachment = {
        "attachment_id": "att_legacy_001",
        "source_ref": "source://fixture/legacy.bin",
        "source_sha256": "sha256:" + "d" * 64,
        "target_rel_path": "attachments/2026/07/legacy.bin",
        "media_type": "application/octet-stream",
        "size_bytes": 8,
        "copy_mode": "copy",
    }
    record = _record(
        1,
        "Legacy imported title",
        "imported",
        ["imported"],
        f"Legacy body with {unique_token}.",
        attachments=[attachment],
    )
    plan, plan_path = _write_plan(data_dir, tmp_path, [record])
    proposal = plan["proposals"][0]
    journal_rel = proposal["journal"]["target_rel_path"]
    attachment_rel = attachment["target_rel_path"]

    journal_path = data_dir / journal_rel
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(
        _old_journal_text(
            proposal["journal"]["title"],
            proposal["journal"]["date"],
            proposal["journal"]["topic"],
            proposal["journal"]["tags"],
            proposal["journal"]["content"],
        ),
        encoding="utf-8",
    )
    attachment_path = data_dir / attachment_rel
    attachment_path.parent.mkdir(parents=True, exist_ok=True)
    attachment_path.write_bytes(b"legacy!!")

    _write_legacy_ledger_and_manifest(data_dir, plan, journal_rel, attachment_rel)

    # The planted bytes are the old format (no schema_version), yet still parse.
    old_parsed, old_body = parse_frontmatter(journal_path.read_text(encoding="utf-8"))
    assert "schema_version" not in old_parsed
    assert old_parsed["title"] == "Legacy imported title"
    assert old_body == f"Legacy body with {unique_token}."

    # 1. Recognised by status/review projection.
    status_result = _run_import(data_dir, "status", "--import-id", plan["import_id"], "--json")
    status = _ok_payload(status_result)["data"]
    assert status["state"] == "committed"
    assert status["counts"]["created_journals"] == 1
    assert status["counts"]["created_attachments"] == 1
    assert status["rollback_available"] is True

    # 2. Recognised by idempotent re-run detection (no rewrite).
    rerun_result = _run_import(
        data_dir,
        "run",
        "--plan",
        str(plan_path),
        "--confirm",
        plan["import_id"],
        "--json",
    )
    rerun = _ok_payload(rerun_result)["data"]
    assert rerun["state"] == "already_committed"
    assert rerun["created_journal_count"] == 1
    assert rerun["created_attachment_count"] == 1
    assert journal_path.read_text(encoding="utf-8") == _old_journal_text(
        proposal["journal"]["title"],
        proposal["journal"]["date"],
        proposal["journal"]["topic"],
        proposal["journal"]["tags"],
        proposal["journal"]["content"],
    )

    # 3. Still visible to the real index + search path.
    index_result = _run_tool(data_dir, "index", "--json")
    assert _ok_payload(index_result)["success"] is True
    search_result = _run_tool(data_dir, "search", "--query", unique_token, "--limit", "0")
    assert _ok_payload(search_result)["total_matches"] >= 1

    # 4. Rolled back exactly, leaving unrelated files alone.
    sentinel = data_dir / "Journals" / "2026" / "07" / "sentinel.md"
    sentinel.write_text("keep me", encoding="utf-8")
    rollback_result = _run_import(data_dir, "rollback", "--import-id", plan["import_id"], "--json")
    rollback = _ok_payload(rollback_result)["data"]
    assert rollback["state"] == "rolled_back"
    assert rollback["deleted_count"] == 2
    assert not journal_path.exists()
    assert not attachment_path.exists()
    assert sentinel.read_text(encoding="utf-8") == "keep me"
