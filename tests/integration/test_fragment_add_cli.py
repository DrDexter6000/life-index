#!/usr/bin/env python3
"""Integration tests for the `life-index fragment add` CLI surface.

Drives the real CLI through subprocesses against a temporary
LIFE_INDEX_DATA_DIR: the three input forms (`--data`, `--data-file`,
`--data -`), exit codes, immediate searchability, `journal get` read-back,
`verify` / `health --data-audit` cleanliness, and the two-real-process
concurrency guarantee for the dedupe key (one file on disk).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPRESSED = "2026-11-12T15:02:10+01:00"


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    data = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data))
    return data


def _run_cli(data_dir: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(
        [sys.executable, "-m", "tools", *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        input=stdin,
        env=env,
    )


def _fragment_add(data_dir: Path, payload: dict, *extra: str) -> subprocess.CompletedProcess:
    return _run_cli(
        data_dir, "fragment", "add", "--data", json.dumps(payload, ensure_ascii=False), *extra
    )


def _fragment_files(data_dir: Path) -> list[Path]:
    journals = data_dir / "Journals"
    if not journals.exists():
        return []
    return sorted(p for p in journals.rglob("life-index_*.md") if p.is_file())


class TestInputForms:
    def test_data_flag(self, data_dir):
        result = _fragment_add(data_dir, {"text": "命令行表格式的原话", "expressed_at": EXPRESSED})
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["deduplicated"] is False
        assert len(_fragment_files(data_dir)) == 1

    def test_data_file_flag(self, data_dir, tmp_path):
        payload_file = tmp_path / "fragment.json"
        payload_file.write_text(
            json.dumps({"text": "文件形式的原话", "expressed_at": EXPRESSED}, ensure_ascii=False),
            encoding="utf-8",
        )
        result = _run_cli(data_dir, "fragment", "add", "--data-file", str(payload_file))
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["success"] is True

    def test_data_dash_reads_stdin(self, data_dir):
        result = _run_cli(
            data_dir,
            "fragment",
            "add",
            "--data",
            "-",
            stdin=json.dumps({"text": "标准输入的原话", "expressed_at": EXPRESSED}),
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["success"] is True

    def test_invalid_json_exits_nonzero_with_error_envelope(self, data_dir):
        result = _run_cli(data_dir, "fragment", "add", "--data", "{not json")
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["success"] is False
        assert payload["error"]["code"] == "E0001"

    def test_missing_payload_exits_nonzero(self, data_dir):
        result = _run_cli(data_dir, "fragment", "add")
        assert result.returncode != 0

    def test_error_envelope_exits_one(self, data_dir):
        result = _fragment_add(data_dir, {"text": "x", "title": "会被拒绝"})
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["error"]["code"] == "E0001"
        assert _fragment_files(data_dir) == []


class TestImmediateRetrieval:
    def test_search_and_journal_get_right_after_add(self, data_dir):
        added = _fragment_add(data_dir, {"text": "江边看鹭的傍晚", "expressed_at": EXPRESSED})
        assert added.returncode == 0
        rel_path = json.loads(added.stdout)["rel_path"]

        search = _run_cli(data_dir, "search", "--query", "看鹭", "--level", "3")
        assert search.returncode == 0, search.stderr
        results = json.loads(search.stdout)
        assert any(
            item.get("rel_path") == rel_path
            and item.get("kind") == "fragment"
            and item.get("display_label")
            for item in results.get("merged_results", [])
        )

        got = _run_cli(data_dir, "journal", "get", "--path", rel_path)
        assert got.returncode == 0, got.stderr
        entry = json.loads(got.stdout)
        assert entry["data"]["content"] == "江边看鹭的傍晚"
        assert entry["data"]["metadata"]["kind"] == "fragment"

    def test_verify_and_health_data_audit_stay_clean(self, data_dir, tmp_path):
        attachment = tmp_path / "note.txt"
        attachment.write_bytes("attachment-bytes".encode("utf-8"))
        added = _fragment_add(
            data_dir,
            {
                "text": "带附件的碎片",
                "expressed_at": EXPRESSED,
                "attachments": [{"source_path": str(attachment)}],
            },
        )
        assert added.returncode == 0, added.stderr

        verified = _run_cli(data_dir, "verify", "--json")
        assert verified.returncode == 0, verified.stdout + verified.stderr
        assert json.loads(verified.stdout)["success"] is True

        health = _run_cli(data_dir, "health", "--data-audit")
        assert health.returncode == 0, health.stdout + health.stderr
        audit = json.loads(health.stdout)
        assert audit["success"] is True
        # Allowed pre-existing audit facts, identical for `write`:
        # - generated indexes are missing (a fragment write deliberately does
        #   not regenerate them — the auditor counts only Markdown image
        #   links, not frontmatter `attachments`, for every command);
        # - a fresh data dir has no backup manifest.
        # Nothing may implicate the fragment itself.
        rel_path = json.loads(added.stdout)["rel_path"]
        allowed = (
            "layout.missing_generated_index",
            "backup.",
            "attachments.orphan_attachment_candidate",
        )
        for issue in audit["data"]["issues_preview"]:
            issue_text = json.dumps(issue, ensure_ascii=False)
            assert rel_path not in issue_text, issue_text
            assert issue["issue_id"].startswith(allowed), issue_text


class TestConcurrentSameKeyProcesses:
    def test_two_real_processes_same_key_yield_one_file(self, data_dir):
        """Two concurrent `fragment add` processes with the same dedupe key.

        Both hold the same journals lock in turn; the second one's file-authority
        dedupe scan sees the first one's fragment. Exactly one file lands on
        disk and both invocations succeed (one stored, one deduplicated).
        """
        payload = json.dumps(
            {
                "text": "并发写入的同一句话",
                "expressed_at": EXPRESSED,
                "source": {"channel": "race", "message_id": "race-mid-1"},
            },
            ensure_ascii=False,
        )
        env = dict(os.environ)
        env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
        env.setdefault("PYTHONIOENCODING", "utf-8")

        processes = [
            subprocess.Popen(
                [sys.executable, "-m", "tools", "fragment", "add", "--data", payload],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=env,
            )
            for _ in range(2)
        ]
        outputs = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=180)
            outputs.append((process.returncode, stdout, stderr))

        for returncode, stdout, stderr in outputs:
            assert returncode == 0, f"exit={returncode}\nstdout={stdout}\nstderr={stderr}"

        results = [json.loads(stdout) for _code, stdout, _stderr in outputs]
        assert sorted(r["deduplicated"] for r in results) == [False, True]
        assert len({r["id"] for r in results}) == 1
        files = _fragment_files(data_dir)
        assert len(files) == 1, f"expected exactly one fragment, found: {files}"
