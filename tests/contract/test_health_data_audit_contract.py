#!/usr/bin/env python3
"""Contract test: life-index health --data-audit CLI subprocess interface.

Verifies:
- `python -m tools health --data-audit` exits 0 on clean sandbox
- Emits valid JSON with success, data.file_count, data.anomalies, data.distribution
- Detects non-standard journal filenames as anomalies
- Detects loose revision files in Journals/ as anomalies
- Does not create or modify files in the sandbox Journals tree
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def sandbox(tmp_path: Path):
    """Create sandbox data dir with standard journals, return (data_dir, env)."""
    data_dir = tmp_path / "Life-Index"
    journals_dir = data_dir / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True)

    for day in (14, 15, 16):
        p = journals_dir / f"life-index_2026-03-{day:02d}_001.md"
        p.write_text(
            f"---\ndate: 2026-03-{day:02d}\n---\n\n# Test {day}\n\nEntry.\n",
            encoding="utf-8",
        )

    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    return data_dir, env


def _run_data_audit(env):
    return subprocess.run(
        [sys.executable, "-m", "tools", "health", "--data-audit"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


class TestHealthDataAuditContract:
    def test_clean_sandbox_exits_0_valid_json(self, sandbox):
        data_dir, env = sandbox
        result = _run_data_audit(env)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert isinstance(payload["data"]["file_count"], int)
        assert isinstance(payload["data"]["anomalies"], list)
        assert isinstance(payload["data"]["distribution"], dict)

    def test_clean_sandbox_no_anomalies(self, sandbox):
        data_dir, env = sandbox
        result = _run_data_audit(env)

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["data"]["anomalies"] == []
        assert payload["data"]["file_count"] == 3

    def test_non_standard_filename_reported_as_anomaly(self, tmp_path):
        data_dir = tmp_path / "Life-Index"
        month_dir = data_dir / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)

        (month_dir / "life-index_2026-03-14_001.md").write_text("---\n---\n")
        (month_dir / "random_notes.md").write_text("# Not standard")

        env = os.environ.copy()
        env["LIFE_INDEX_DATA_DIR"] = str(data_dir)

        result = _run_data_audit(env)
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        naming = [a for a in payload["data"]["anomalies"] if a["type"] == "naming"]
        assert len(naming) >= 1
        assert any("random_notes.md" in a["description"] for a in naming)

    def test_revision_file_in_journals_reported_as_anomaly(self, tmp_path):
        data_dir = tmp_path / "Life-Index"
        month_dir = data_dir / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)

        (month_dir / "life-index_2026-03-14_001.md").write_text("---\n---\n")
        (month_dir / "life-index_2026-03-14_001_20260418_120000_000000.md").write_text("---\n---\n")

        env = os.environ.copy()
        env["LIFE_INDEX_DATA_DIR"] = str(data_dir)

        result = _run_data_audit(env)
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        revision = [a for a in payload["data"]["anomalies"] if a["type"] == "revision_file"]
        assert len(revision) >= 1

    def test_does_not_modify_journals_tree(self, sandbox):
        data_dir, env = sandbox
        journals_dir = data_dir / "Journals"

        files_before = set(journals_dir.rglob("*"))

        _run_data_audit(env)

        files_after = set(journals_dir.rglob("*"))
        assert files_before == files_after, "health --data-audit modified files in Journals/"
