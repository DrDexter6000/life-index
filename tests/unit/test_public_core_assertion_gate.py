from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / ".github" / "scripts" / "run_public_core_assertions.py"


def _run_gate(tmp_path: Path, source: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    test_file = tmp_path / "test_synthetic_core.py"
    test_file.write_text(source, encoding="utf-8")
    sentinel = tmp_path / "sentinel.json"
    result = subprocess.run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--root",
            str(tmp_path),
            "--target",
            str(test_file),
            "--sentinel",
            str(sentinel),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    payload = json.loads(sentinel.read_text(encoding="utf-8")) if sentinel.exists() else {}
    return result, payload


def test_public_core_gate_records_real_assertion_execution(tmp_path: Path) -> None:
    result, payload = _run_gate(
        tmp_path,
        "def test_core_recall_assertion():\n    assert 'token' in 'synthetic token fixture'\n",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["core_assertions_collected"] == 1
    assert payload["core_assertions_executed"] == 1
    assert payload["core_assertions_passed"] == 1
    assert payload["status"] == "PASS"


def test_public_core_gate_rejects_all_skipped_assertions(tmp_path: Path) -> None:
    result, payload = _run_gate(
        tmp_path,
        "import pytest\n\n@pytest.mark.skip(reason='synthetic skip')\n"
        "def test_core_recall_assertion():\n    assert True\n",
    )

    assert result.returncode != 0
    assert payload["core_assertions_collected"] == 1
    assert payload["core_assertions_executed"] == 0
    assert payload["core_assertions_skipped"] == 1
    assert payload["status"] == "FAIL"


def test_public_core_gate_rejects_missing_or_deselected_target(tmp_path: Path) -> None:
    sentinel = tmp_path / "sentinel.json"
    result = subprocess.run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--root",
            str(tmp_path),
            "--target",
            str(tmp_path / "missing_test.py"),
            "--sentinel",
            str(sentinel),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert result.returncode != 0
    payload = json.loads(sentinel.read_text(encoding="utf-8"))
    assert payload["core_assertions_executed"] == 0
    assert payload["status"] == "FAIL"
