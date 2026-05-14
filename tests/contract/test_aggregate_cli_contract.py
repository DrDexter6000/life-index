#!/usr/bin/env python3
"""Contract test: life-index aggregate CLI subprocess interface.

Verifies:
- `python -m tools aggregate --range ... --unit ... --predicate ... --json` exits 0
- Emits valid JSON
- Uses relative evidence paths
- Does not write production data
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def sandbox(tmp_path: Path):
    """Create sandbox data dir with journals, return (data_dir, env)."""
    data_dir = tmp_path / "Life-Index"
    journals_dir = data_dir / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True)

    for day in (14, 15, 16):
        path = journals_dir / f"life-index_2026-03-{day:02d}_001.md"
        content = f"---\ndate: 2026-03-{day:02d}\n---\n\n# Test {day}\n\nEntry for day {day}.\n"
        path.write_text(content, encoding="utf-8")

    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    return data_dir, env


class TestAggregateCliContract:
    def test_aggregate_journal_count_exits_0_valid_json(self, sandbox):
        data_dir, env = sandbox
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools",
                "aggregate",
                "--range",
                "2026-03-14..2026-03-16",
                "--unit",
                "day",
                "--predicate",
                "journal_count",
                "--json",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["command"] == "aggregate"
        assert payload["result"]["count"] == 3

    def test_aggregate_uses_relative_paths(self, sandbox):
        data_dir, env = sandbox
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools",
                "aggregate",
                "--range",
                "2026-03-14..2026-03-16",
                "--unit",
                "day",
                "--predicate",
                "journal_count",
                "--json",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        payload = json.loads(result.stdout)
        for p in payload.get("evidence_paths", []):
            assert not os.path.isabs(p), f"Absolute path in output: {p}"
            assert "\\" not in p, f"Backslash in path: {p}"

    def test_aggregate_does_not_write_production_data(self, sandbox):
        data_dir, env = sandbox
        journals_dir = data_dir / "Journals"

        files_before = set(journals_dir.rglob("*"))

        subprocess.run(
            [
                sys.executable,
                "-m",
                "tools",
                "aggregate",
                "--range",
                "2026-03-14..2026-03-16",
                "--unit",
                "day",
                "--predicate",
                "journal_count",
                "--json",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        files_after = set(journals_dir.rglob("*"))
        assert files_before == files_after, "aggregate wrote files to data dir"

    def test_aggregate_invalid_predicate_exits_nonzero(self, sandbox):
        data_dir, env = sandbox
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools",
                "aggregate",
                "--range",
                "2026-03-14..2026-03-16",
                "--unit",
                "day",
                "--predicate",
                "bogus_predicate",
                "--json",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        assert result.returncode != 0
        payload = json.loads(result.stdout)
        assert payload["success"] is False

    def test_aggregate_includes_claim_envelope_and_evidence_pack(self, sandbox):
        data_dir, env = sandbox
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools",
                "aggregate",
                "--range",
                "2026-03-14..2026-03-16",
                "--unit",
                "day",
                "--predicate",
                "journal_count",
                "--json",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        payload = json.loads(result.stdout)
        assert "claim_envelope" in payload
        assert "evidence_pack" in payload
        ce = payload["claim_envelope"]
        assert ce["schema_version"] == "m02a.claim_envelope.v0"
        assert ce["claim_type"] == "measurable_exact"
        assert ce["evidence_pack_ref"] == "aggregate.evidence_pack"
        ep = payload["evidence_pack"]
        assert ep["schema_version"] == "m02a.aggregate_evidence_pack.v0"
        assert "items" in ep
        for item in ep["items"]:
            assert "\\" not in item["path"], f"Backslash in path: {item['path']}"
            assert not os.path.isabs(item["path"]), f"Absolute path: {item['path']}"

    def test_analyze_alias_matches_aggregate_contract(self, sandbox):
        data_dir, env = sandbox
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools",
                "analyze",
                "--range",
                "2026-03-14..2026-03-16",
                "--unit",
                "day",
                "--predicate",
                "journal_count",
                "--json",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["command"] == "aggregate"
        assert payload["result"]["count"] == 3
        assert "claim_envelope" in payload
        assert "evidence_pack" in payload
